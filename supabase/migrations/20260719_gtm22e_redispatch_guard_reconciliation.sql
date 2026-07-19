-- GTM-22E: cc_redispatch_guard reconciliation pass
--
-- Problem (verified against live DB 2026-07-19): cc_redispatch_tick() only
-- re-evaluates dod_sql for status='active' rows. Once a row's attempts hit
-- max_attempts it flips to 'blocked' and is NEVER re-checked again. Of 337
-- blocked rows, 245 are real shard tasks (attempts=max_attempts, mostly no
-- last_error) whose dod_sql frequently DOES evaluate true later — the guard
-- exhausted retries before the work landed, and nothing back-fills the row.
-- Completed work is permanently recorded as failure, corrupting every
-- progress signal built on this table (e.g. sample issue 9898: dod_sql for
-- duval/franklin/broward gold certification now evaluates true, and issue
-- 9892's stripe-meter DoD now evaluates true despite a stale "human-gated,
-- do not re-fire" note).
--
-- Fix: a companion function, cc_redispatch_reconcile(), re-checks a bounded
-- batch of blocked rows per call and promotes the ones whose dod_sql now
-- returns true. cc_redispatch_tick() calls it once per tick (existing active-
-- row logic is otherwise untouched). 92 one-shot TRIAGE:* rows are excluded
-- by design — they are blocked-by-design artifacts, not failed shard work.
--
-- Safety: dod_sql is stored, dynamically-executed SQL — untrusted input.
-- cc_redispatch_reconcile() defends in layers:
--   1. Shape check: dod_sql must start with SELECT and contain no statement
--      chaining (no ';' followed by further non-whitespace). Anything else
--      is rejected without execution and logged to last_error. (NB: uses \y
--      for word-boundary — Postgres ARE regex treats \b as backspace, not
--      word-boundary; using \b here silently rejects every legitimate
--      dod_sql, which is exactly what happened on the first pass of this
--      migration and was caught before rollout — see git history.)
--   2. Always executed as `select (dod_sql)::boolean` — forces the untrusted
--      text into a scalar subexpression, which alone defeats top-level
--      multi-statement tricks and data-modifying CTEs (`WITH x AS (DELETE
--      ...) SELECT ...` is not valid inside that position).
--   3. transaction_read_only is forced ON for the duration of the EXECUTE,
--      via a savepoint that is *always* rolled back afterward (see the
--      forced-rollback pattern below). This blocks writes even when they
--      arrive indirectly through a function call inside the SELECT (e.g.
--      `SELECT some_function_that_inserts()`), which layers 1-2 cannot
--      catch. Verified live: a nested INSERT via function call raises
--      "cannot execute INSERT in a read-only transaction" and is caught.
--      NOTE: an earlier draft of this migration used SET LOCAL ROLE to a
--      restricted reader role instead. That does NOT work here — Postgres
--      unconditionally disallows SET ROLE / RESET ROLE anywhere in the call
--      stack of a SECURITY DEFINER function (verified live via error 42501
--      "cannot set parameter \"role\" within security-definer function"),
--      and this function must be callable both directly and from inside
--      cc_redispatch_tick() (also SECURITY DEFINER). transaction_read_only
--      has no such restriction.
--   4. Per-row exception handling + statement_timeout so one bad dod_sql
--      (error or slow query) cannot abort the batch or stall the tick.
-- Batch size is capped (default 40 rows/tick) so reconciliation cannot stall
-- the jobid 232 cron tick (*/20 * * * *).

ALTER TABLE public.cc_redispatch_guard
  ADD COLUMN IF NOT EXISTS reconciled_at timestamptz,
  ADD COLUMN IF NOT EXISTS resolved_via text;

CREATE OR REPLACE FUNCTION public.cc_redispatch_reconcile(p_batch_size int DEFAULT 40)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'extensions', 'vault'
AS $function$
declare
  g record;
  v_done boolean;
  v_err text;
  v_promoted jsonb := '[]'::jsonb;
  v_checked int := 0;
  v_errored int := 0;
begin
  for g in
    select * from cc_redispatch_guard
    where status = 'blocked'
      and task_label NOT LIKE 'TRIAGE:%'   -- one-shot escalation artifacts, not shard work
    order by reconciled_at asc nulls first, issue_number
    limit greatest(p_batch_size, 0)
  loop
    v_done := null;
    v_err := null;

    if g.dod_sql !~* '^\s*select\y' or g.dod_sql ~ ';\s*\S' then
      update cc_redispatch_guard
        set reconciled_at = now(),
            last_error = 'reconcile: dod_sql failed shape check (not a single SELECT)'
        where issue_number = g.issue_number;
      v_errored := v_errored + 1;
      v_checked := v_checked + 1;
      continue;
    end if;

    -- Forced-rollback sandbox: SET LOCAL changes made inside this block are
    -- only guaranteed to revert if the block exits via exception, so we
    -- always raise one at the end (even on success) to force the rollback,
    -- then classify by the marker message. plpgsql variables (v_done, v_err)
    -- are NOT part of the transactional state and survive the rollback.
    begin
      set local statement_timeout = '5000ms';
      set local transaction_read_only = on;
      execute 'select ('||g.dod_sql||')::boolean' into v_done;
      raise exception using errcode = 'P0001', message = '__gtm22e_reconcile_sandbox_commit__';
    exception when others then
      if SQLERRM = '__gtm22e_reconcile_sandbox_commit__' then
        v_err := null;
      else
        v_err := left(SQLERRM, 300);
        v_done := false;
      end if;
    end;

    if v_done then
      update cc_redispatch_guard
        set status = 'delivered',
            delivered_at = now(),
            reconciled_at = now(),
            resolved_via = 'reconciliation',
            last_error = null
        where issue_number = g.issue_number;
      v_promoted := v_promoted || jsonb_build_array(
        jsonb_build_object('issue', g.issue_number, 'task_label', g.task_label));
    else
      update cc_redispatch_guard
        set reconciled_at = now(),
            last_error = case when v_err is not null then 'reconcile: '||v_err else last_error end
        where issue_number = g.issue_number;
      if v_err is not null then
        v_errored := v_errored + 1;
      end if;
    end if;

    v_checked := v_checked + 1;
  end loop;

  return jsonb_build_object(
    'reconciled_at', now(),
    'checked', v_checked,
    'errored', v_errored,
    'promoted', v_promoted
  );
end
$function$;

CREATE OR REPLACE FUNCTION public.cc_redispatch_tick()
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'extensions', 'vault'
AS $function$
declare
  g record; v_done boolean; v_fired jsonb; v_actions jsonb := '[]'::jsonb; v_gh int;
  v_reconcile jsonb;
begin
  v_reconcile := public.cc_redispatch_reconcile();

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
