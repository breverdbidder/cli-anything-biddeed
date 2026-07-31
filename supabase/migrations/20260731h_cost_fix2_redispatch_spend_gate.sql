-- COST-FIX-2: spend gate + cap max_attempts default on cc_redispatch_guard
--
-- cc_redispatch_tick() (jobid 232, */20 * * * *) re-fires blocked SUMMIT
-- shards up to max_attempts times. Each re-fire is a full CC session, so a
-- shard that keeps failing its dod_sql burns max_attempts full sessions
-- before the guard gives up. Two changes:
--   1. A spend gate at the top of the active-row loop: if
--      v_cc_cost_budget_status.spent_this_month_usd exceeds $150, park every
--      'active' row instead of re-firing and log the trip to agent_ops_log.
--      NOTE: the view is currently seeded with stale July estimates showing
--      ~$1,535 spent — so this gate WILL trip on the first tick after this
--      migration ships, parking the (currently 2) active rows. That is the
--      intended behavior per dispatch e29368d3; Ariel resets the seed data
--      separately once August is confirmed clean.
--   2. max_attempts default lowered from 12 to 1 for future inserts only —
--      existing rows are untouched, so this does not change behavior for any
--      shard already in flight.
--
-- agent_ops_log has no outcome/detail columns (dispatch_id/task/status/
-- evidence/severity instead, dispatch_id NOT NULL) — the gate's log write is
-- adapted to the real schema rather than the outcome/detail shape sketched
-- in the dispatch.

ALTER TABLE public.cc_redispatch_guard
  ALTER COLUMN max_attempts SET DEFAULT 1;

CREATE OR REPLACE FUNCTION public.cc_redispatch_tick()
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'extensions', 'vault'
AS $function$
declare
  g record; v_done boolean; v_fired jsonb; v_actions jsonb := '[]'::jsonb; v_gh int;
  v_reconcile jsonb;
  v_spent numeric;
begin
  v_reconcile := public.cc_redispatch_reconcile();

  -- SPEND GATE: halt all redispatch if monthly budget exceeded
  SELECT COALESCE(spent_this_month_usd, 0) INTO v_spent
    FROM public.v_cc_cost_budget_status LIMIT 1;
  IF v_spent > 150 THEN
    UPDATE public.cc_redispatch_guard SET status='parked', last_error='spend_gate: $'||v_spent::text||' > $150 limit'
      WHERE status='active';
    INSERT INTO public.agent_ops_log (dispatch_id, task, status, evidence)
      VALUES ('cron-cc-redispatch-tick-'||to_char(now(),'YYYYMMDDHH24MI'), 'cc_redispatch_tick', 'BLOCKED',
        'spend_gate_triggered: Monthly spend $'||v_spent::text||' exceeded $150 threshold. All active shards parked.');
    RETURN jsonb_build_object('spend_gate', true, 'spent_usd', v_spent, 'action', 'all_shards_parked');
  END IF;

  for g in select * from cc_redispatch_guard where status='active' order by issue_number loop
    begin
      execute 'select ('||g.dod_sql||')::boolean' into v_done;
    exception when others then
      v_done := false;
      update cc_redispatch_guard set last_error=left(SQLERRM,300) where issue_number=g.issue_number;
    end;

    if v_done then
      update cc_redispatch_guard set status='delivered', delivered_at=now(), last_error=null
        where issue_number=g.issue_number;
      v_actions := v_actions || jsonb_build_array(jsonb_build_object('issue',g.issue_number,'action','DELIVERED'));

    elsif g.attempts >= g.max_attempts then
      update cc_redispatch_guard set status='blocked' where issue_number=g.issue_number;

      if g.task_label NOT LIKE 'TRIAGE:%' then
        -- TIER 2: engineers exhausted → dispatch ONE architect triage session
        insert into ops_alerts (source, severity, ref, message)
        values ('cc_redispatch_guard','medium','issue-'||g.issue_number,
          'Engineer attempts exhausted ('||g.attempts||'/'||g.max_attempts||'). Architect triage auto-dispatched. last_error='||coalesce(g.last_error,'none'));
        insert into summit_chat_dispatch
          (chat_session_id, ai_architect_model, summit_title, summit_body, target_repo, target_workflow,
           priority, state, max_attempts, verification_scope, evidence_schema_version, dod_sql)
        values
          ('auto-triage-issue-'||g.issue_number||'-'||to_char(now(),'YYYYMMDDHH24MI'),
           'tick-auto',
           'TRIAGE: architect diagnosis for blocked issue #'||g.issue_number,
           E'## ARCHITECT TRIAGE MANDATE (auto-dispatched — engineers exhausted 3 attempts)\n\n'
           ||'Blocked issue: #'||g.issue_number||E'\n'
           ||'DoD (still failing): '||g.dod_sql||E'\n'
           ||'last_error: '||coalesce(g.last_error,'none logged')||E'\n\n'
           ||E'You are operating as ARCHITECT, not engineer. Protocol:\n'
           ||E'1. READ the full thread of issue #'||g.issue_number||E' — including all guard protocol comments and any prior architect diagnosis.\n'
           ||E'2. READ public.decision_log for related entries; query the database directly for evidence (tables named in the DoD).\n'
           ||E'3. DIAGNOSE across systems before writing any code. Reproduce the failure with a direct probe where possible.\n'
           ||E'4. FIX anything within autonomous authority (bug fixes, function patches, data corrections in non-critical tables, redeploys). Verify by re-executing the DoD SQL and reading it back true.\n'
           ||E'5. If the fix requires human action (credentials, dashboard permissions, spend, schema on protected tables): post a comment on issue #'||g.issue_number||' in EXACTLY this format: "BLOCKED: [issue]. Tried: [attempts]. Recommend: [one concrete action with clicking path]. Approve?" — then stop.\n'
           ||E'6. Before ending: comment your findings with Honesty V3 markers. A silent end counts as failure.\n'
           ||E'7. Log your diagnosis to public.decision_log (decision_type=triage).\n'
           ||'/loop until DoD true or the human-ask comment is posted.',
           'breverdbidder/cli-anything-biddeed', g.workflow_file,
           'p0', 'queued', 1, 'supabase_only', 'v1.0',
           g.dod_sql);
        v_actions := v_actions || jsonb_build_array(jsonb_build_object('issue',g.issue_number,'action','BLOCKED→TRIAGE_DISPATCHED'));
      else
        -- TIER 3: architect triage itself blocked → escalate to Ariel, loudly
        insert into ops_alerts (source, severity, ref, message)
        values ('cc_redispatch_guard','high','issue-'||g.issue_number,
          'TRIAGE BLOCKED: architect session could not resolve. Tried: engineer x3 + architect x1. Recommend: Ariel review issue #'||g.issue_number||'. last_error='||coalesce(g.last_error,'none'));
        begin
          v_gh := public.gh_issue_comment(g.issue_number,
            E'## \U0001F6A8 FULL ESCALATION — ENGINEERS + ARCHITECT EXHAUSTED\n\n'
            ||'**DoD:** `'||left(g.dod_sql,200)||E'`\n'
            ||'**last_error:** '||coalesce(g.last_error,'none logged')||E'\n\n'
            ||'@breverdbidder — Tier 3: human decision required. See ops_alerts + this thread for the full trail.');
        exception when others then null;
        end;
        v_actions := v_actions || jsonb_build_array(jsonb_build_object('issue',g.issue_number,'action','TRIAGE_BLOCKED→ARIEL_ALERTED'));
      end if;

    elsif g.last_fired_at is null
          or (now()-g.last_fired_at) > make_interval(mins => g.run_window_min) then
      begin
        v_gh := public.gh_issue_comment(g.issue_number,
          E'## \U0001F501 GUARD RE-FIRE — attempt '||(g.attempts+1)||'/'||g.max_attempts||E'\n\n'
          ||E'DoD still unmet. **REDISPATCH PROTOCOL — binding on this session:**\n'
          ||E'1. READ every prior comment in this thread before writing any code.\n'
          ||E'2. Before ending, COMMENT verified progress (Honesty V3) or a blocker + RCA. Silent end = failed session.\n'
          ||E'3. Do not repeat work a prior comment marks complete.');
      exception when others then null;
      end;
      v_fired := public.fire_workflow_dispatch(
        'breverdbidder/cli-anything-biddeed', g.workflow_file, 'main',
        jsonb_build_object('issues', g.issue_number::text));
      update cc_redispatch_guard set attempts=attempts+1, last_fired_at=now()
        where issue_number=g.issue_number;
      v_actions := v_actions || jsonb_build_array(jsonb_build_object('issue',g.issue_number,'action','RE-FIRED','attempt',g.attempts+1,'http',v_fired->'http'));
    else
      v_actions := v_actions || jsonb_build_array(jsonb_build_object('issue',g.issue_number,'action','waiting'));
    end if;
  end loop;
  return jsonb_build_object('ticked_at',now(),'actions',v_actions,'reconcile',v_reconcile);
end
$function$;
