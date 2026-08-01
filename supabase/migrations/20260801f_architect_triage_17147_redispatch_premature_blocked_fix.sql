-- ARCHITECT TRIAGE for issue #17147 (dispatch 228b8cd0, auto-triage cc_redispatch_guard)
--
-- Root cause (VERIFIED live): cc_redispatch_tick()'s "elsif g.attempts >=
-- g.max_attempts" branch judges a shard as engineer-exhausted and dispatches
-- architect triage UNCONDITIONALLY on attempts count -- it never checks
-- whether run_window_min has actually elapsed since last_fired_at. Combined
-- with COST-FIX-3 (20260731h) dropping max_attempts default 3->1, and
-- auto_register_cc_guard() inserting new guard rows already at attempts=1
-- (pre-exhausted), every freshly-dispatched SUMMIT session now gets
-- automatically triaged on the very next cron tick (jobid 232, */20 * * * *)
-- -- as little as ~18 minutes after firing -- while its real engineer
-- session (cc-runner-ghonly.yml, timeout-minutes: 360) is still running.
--
-- Confirmed fleet-wide, not specific to #17147: every Gold Standard shard
-- issue from the current 16:00Z wave (17123-17127, 17145-17150) and the
-- prior 08:00Z wave shows cc_redispatch_guard.status IN ('blocked','parked')
-- within ~20 minutes of dispatch, well inside the declared 6h session
-- budget. #17147's actual engineer session (GHA run 30707197043, job
-- run-cc(17147)) was independently confirmed still IN_PROGRESS at the time
-- this triage fired.
--
-- Fix: (1) cc_redispatch_tick() must not judge a shard blocked/exhausted
-- until run_window_min has actually elapsed since last_fired_at, regardless
-- of attempts count. (2) auto_register_cc_guard()'s hardcoded run_window_min
-- of 90 predates the 6h GHA ceiling; bump to 370 (360 + 10min queue/startup
-- buffer) so the wait window covers a full session before any redispatch or
-- triage judgment.

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
  v_window_elapsed boolean;
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

    v_window_elapsed := g.last_fired_at is null
      or (now()-g.last_fired_at) > make_interval(mins => g.run_window_min);

    if v_done then
      update cc_redispatch_guard set status='delivered', delivered_at=now(), last_error=null
        where issue_number=g.issue_number;
      v_actions := v_actions || jsonb_build_array(jsonb_build_object('issue',g.issue_number,'action','DELIVERED'));

    elsif g.attempts >= g.max_attempts and v_window_elapsed then
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

    elsif g.attempts < g.max_attempts and v_window_elapsed then
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

CREATE OR REPLACE FUNCTION public.auto_register_cc_guard()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF NEW.state = 'dispatched' AND NEW.github_issue_number IS NOT NULL
     AND (OLD.state IS DISTINCT FROM 'dispatched') THEN
    INSERT INTO public.cc_redispatch_guard
      (issue_number, task_label, dod_sql, status, attempts, max_attempts, run_window_min, last_fired_at, workflow_file)
    VALUES
      (NEW.github_issue_number,
       CASE WHEN NEW.summit_title LIKE 'TRIAGE:%' THEN left(NEW.summit_title, 200)
            ELSE left(NEW.summit_title, 200) END,
       CASE WHEN NEW.dod_sql IS NOT NULL AND btrim(NEW.dod_sql) <> '' THEN NEW.dod_sql ELSE 'SELECT false' END,
       CASE WHEN NEW.dod_sql IS NOT NULL AND btrim(NEW.dod_sql) <> '' THEN 'active' ELSE 'needs_dod' END,
       1, COALESCE(NEW.max_attempts, 3), 370, now(),
       COALESCE(NEW.target_workflow, 'cc-runner-ghonly.yml'))
    ON CONFLICT (issue_number) DO UPDATE
      SET task_label = EXCLUDED.task_label,
          dod_sql = EXCLUDED.dod_sql,
          status = 'active',
          attempts = 1,
          max_attempts = EXCLUDED.max_attempts,
          run_window_min = 370,
          last_fired_at = now()
      WHERE cc_redispatch_guard.status = 'blocked'; -- triage reactivates a blocked guard under the TRIAGE label
  END IF;
  RETURN NEW;
END
$function$;

-- Repair the current wave's guard rows: their real cc-runner-ghonly.yml
-- sessions (fired 2026-08-01T16:0[12]Z, 360min GHA ceiling) are confirmed
-- still in flight or well within budget as of this migration. They were
-- flipped to 'blocked' by the buggy unconditional check above, not because
-- their sessions actually failed or exhausted their time. Reactivate with
-- the corrected run_window_min so the tick judges them correctly once their
-- real session window elapses, instead of leaving them stuck (and untracked
-- for auto-delivery/re-fire) in 'blocked' forever.
UPDATE public.cc_redispatch_guard
SET status = 'active',
    run_window_min = 370
WHERE status = 'blocked'
  AND task_label LIKE 'GOLD STANDARD SHARD-%'
  AND last_fired_at >= '2026-08-01T16:00:00Z'::timestamptz;
