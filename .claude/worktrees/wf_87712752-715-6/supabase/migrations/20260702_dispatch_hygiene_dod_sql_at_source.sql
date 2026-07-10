-- DISPATCH HYGIENE: populate dod_sql at source in every summit_chat_dispatch creator.
-- trg_auto_register_cc_guard (deployed Jul1) inserts guardless dispatches into
-- cc_redispatch_guard as inert status='needs_dod' rows whenever dod_sql is NULL/empty
-- at the moment a dispatch flips to state='dispatched'. This migration makes every
-- creator supply its own SQL-checkable Definition of Done at queue time, and backfills
-- the 24-row needs_dod backlog that accumulated before the fix.
--
-- Inventory (pg_proc scan for INSERT INTO summit_chat_dispatch, Jul2 2026):
--   direct inserters: launch_claude_code_session, cairn_ask, cairn_supervisor_scan,
--                      enqueue_ducklake_archive
--   indirect via launch_claude_code_session: launch_gold_standard_session (x2 overloads,
--                      also reached via launch_gold_standard_fleet + gold_standard_autopilot),
--                      gold_loop_watchdog, duval_loop_watchdog
--   confirmed NOT dispatch creators (state='dispatched' transition only, dod_sql already
--   carries through untouched): everest_worker_phase1/2/3, everest_dispatch_tick,
--   verify_awaiting_summit, cc_redispatch_tick (retries the SAME guard row — no new
--   insert, so it already inherits dod_sql), gold_standard_certify (writes
--   gold_standard_certifications only, never dispatches).
--
-- Honesty V3: every dod_sql below is a cheap single SELECT against an indexed/small
-- table (gold_standard_certifications, detective_runs, supervisor_log,
-- ducklake_archive_runs) or the loop-supervisor's own pre-existing health_sql —
-- no scans of multi_county_auctions or other large tables.

BEGIN;

-- ============================================================================
-- 1. launch_claude_code_session — the shared dispatch primitive. Add an optional
--    trailing p_dod_sql param (non-breaking: existing positional callers unaffected).
-- ============================================================================
CREATE OR REPLACE FUNCTION public.launch_claude_code_session(
  p_title text,
  p_body text,
  p_repo text DEFAULT 'breverdbidder/cli-anything-biddeed'::text,
  p_priority text DEFAULT 'p1'::text,
  p_workflow text DEFAULT 'cc-runner-ghonly.yml'::text,
  p_dod_sql text DEFAULT NULL
)
 RETURNS TABLE(dispatch_id uuid, phase1_processed_id uuid, phase1_action text, phase1_detail text)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'net', 'vault', 'extensions'
AS $function$
DECLARE
  v_id       uuid;
  v_body     text;
  v_priority text;
BEGIN
  IF p_title IS NULL OR btrim(p_title) = '' THEN
    RAISE EXCEPTION 'launch_claude_code_session: title is required';
  END IF;
  IF p_body IS NULL OR btrim(p_body) = '' THEN
    RAISE EXCEPTION 'launch_claude_code_session: body is required';
  END IF;
  IF p_workflow IS NULL OR p_workflow NOT LIKE '%.yml' THEN
    RAISE EXCEPTION 'launch_claude_code_session: target_workflow must end in .yml (got %)', p_workflow;
  END IF;
  IF p_repo IS NULL OR p_repo NOT LIKE '%/%' THEN
    RAISE EXCEPTION 'launch_claude_code_session: repo must be owner/name (got %)', p_repo;
  END IF;

  v_priority := lower(coalesce(nullif(btrim(p_priority),''),'p1'));
  IF v_priority NOT IN ('p0','p1','normal') THEN v_priority := 'p1'; END IF;

  -- cc-runner-ghonly.yml reads the issue body as the Claude prompt via `gh issue view`.
  -- The @claude prefix is retained as harmless belt-and-suspenders for any issue-trigger path.
  v_body := CASE WHEN p_body ILIKE '%@claude%' THEN p_body
                 ELSE '@claude' || E'\n\n' || p_body END;

  INSERT INTO public.summit_chat_dispatch
    (chat_session_id, ai_architect_model, summit_title, summit_body,
     target_repo, target_workflow, priority, state,
     dispatch_inputs, touches_prod_web, verification_scope, max_attempts, dod_sql)
  VALUES
    ('architect-' || to_char(now(),'YYYYMMDD"T"HH24MISS'),
     'claude-opus-4-8',
     p_title, v_body,
     p_repo, p_workflow, v_priority, 'queued',
     '{}'::jsonb, false, 'supabase_only', 3, nullif(btrim(p_dod_sql), ''))
  RETURNING id INTO v_id;

  RETURN QUERY
    SELECT v_id, w.processed_id, w.action, w.detail
    FROM public.everest_worker_phase1_create_issue() w;
END;
$function$;

-- ============================================================================
-- 2. launch_gold_standard_session() — no-arg overload. DoD = at least one target
--    county reaches gold_standard_certifications.certified.
-- ============================================================================
CREATE OR REPLACE FUNCTION public.launch_gold_standard_session()
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_brief text; v_body text; v_dispatch uuid; v_run bigint; v_targets text[]; v_dod_sql text;
BEGIN
  SELECT max(loop_run_id) INTO v_run FROM gold_standard_county_status;
  v_brief := public.gold_standard_session_brief(3);

  SELECT array_agg(county_slug) INTO v_targets FROM (
    SELECT sb.county_slug FROM gold_standard_scoreboard sb
    LEFT JOIN gold_standard_certifications c ON c.county_slug = sb.county_slug AND c.certified
    WHERE c.county_slug IS NULL ORDER BY sb.pass_count DESC, sb.county_slug LIMIT 3) q;

  v_dod_sql := format(
    'SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications WHERE county_slug = ANY(%L::text[]) AND certified)',
    v_targets);

  SELECT replace(body, '{{TARGETS}}', coalesce(v_brief,'(scoreboard unavailable — query gold_standard_scoreboard directly)'))
    INTO v_body FROM public.gold_standard_brief_template WHERE id = 1;

  SELECT dispatch_id INTO v_dispatch
  FROM public.launch_claude_code_session(
    p_title := 'GOLD STANDARD CAMPAIGN: ' || array_to_string(v_targets, ', ') || ' — daily 6h autonomous A-J session (SHIP TO MAIN)',
    p_body  := v_body,
    p_priority := 'p1',
    p_dod_sql := v_dod_sql);

  INSERT INTO public.gold_standard_campaign (dispatch_id, target_counties, brief_excerpt, loop_run_at_launch)
  VALUES (v_dispatch, v_targets, left(coalesce(v_brief,''), 500), v_run);

  RETURN jsonb_build_object('dispatch_id', v_dispatch, 'targets', to_jsonb(v_targets), 'loop_run', v_run);
END $function$;

-- ============================================================================
-- 3. launch_gold_standard_session(p_targets, p_shard_label) — sharded overload.
--    Same DoD pattern, scoped to the shard's own target_counties.
-- ============================================================================
CREATE OR REPLACE FUNCTION public.launch_gold_standard_session(p_targets text[] DEFAULT NULL::text[], p_shard_label text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_brief text; v_body text; v_dispatch uuid; v_run bigint; v_targets text[]; v_dod_sql text;
BEGIN
  SELECT max(loop_run_id) INTO v_run FROM gold_standard_county_status;

  IF p_targets IS NULL THEN
    SELECT array_agg(county_slug) INTO v_targets FROM (
      SELECT sb.county_slug FROM gold_standard_scoreboard sb
      LEFT JOIN gold_standard_certifications c ON c.county_slug = sb.county_slug AND c.certified
      WHERE c.county_slug IS NULL ORDER BY sb.pass_count DESC, sb.county_slug LIMIT 3) q;
  ELSE
    v_targets := p_targets;
  END IF;

  v_dod_sql := format(
    'SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications WHERE county_slug = ANY(%L::text[]) AND certified)',
    v_targets);

  v_brief := public.gold_standard_session_brief_for(v_targets)
    || E'\n\n## PARALLEL-FLEET RULES (multiple sessions run concurrently)\n'
    || '- You own ONLY the counties above. Never touch another shard''s counties, their rows, or their county-specific files.'
    || E'\n- Shared code paths (scraper framework, shared SQL functions): git pull --rebase before EVERY push to main; on conflict, rebase and retry. Keep commits small and county-scoped where possible.'
    || E'\n- Shared migrations: name them with your shard counties (e.g. <county>_<purpose>) to avoid collisions.'
    || E'\n- Do not run public.gold_standard_loop() mid-session (other shards are working); for verification use SELECT public.pencil_dod_evaluate_county(''<county>'') per county. Run the full loop + certify ONLY in your close-out if no other session is mid-flight, otherwise skip loop and report per-county evaluations.';

  SELECT replace(body, '{{TARGETS}}', v_brief) INTO v_body
  FROM public.gold_standard_brief_template WHERE id = 1;

  SELECT dispatch_id INTO v_dispatch
  FROM public.launch_claude_code_session(
    p_title := 'GOLD STANDARD ' || coalesce(p_shard_label,'SHARD') || ': ' || array_to_string(v_targets, ', ') || ' — parallel 6h session (SHIP TO MAIN)',
    p_body  := v_body,
    p_priority := 'p1',
    p_dod_sql := v_dod_sql);

  INSERT INTO public.gold_standard_campaign (dispatch_id, target_counties, brief_excerpt, loop_run_at_launch)
  VALUES (v_dispatch, v_targets, coalesce(p_shard_label,'shard') || ': ' || left(coalesce(v_brief,''), 450), v_run);

  RETURN jsonb_build_object('dispatch_id', v_dispatch, 'targets', to_jsonb(v_targets), 'shard', p_shard_label);
END $function$;

-- ============================================================================
-- 4. gold_loop_watchdog — DoD = the supervisor row's own health_sql/target_op/
--    target_val (its scoreboard criterion), reused verbatim across continuation,
--    retry, and diagnostic relaunches (all three chase the same target metric).
-- ============================================================================
CREATE OR REPLACE FUNCTION public.gold_loop_watchdog()
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'net', 'vault', 'extensions'
AS $function$
DECLARE r record; cur numeric; improved boolean; advanced boolean; out text := ''; v_dod_sql text;
BEGIN
  FOR r IN SELECT * FROM public.gold_loop_supervisor
           WHERE status NOT IN ('succeeded','disabled','human_blocker') ORDER BY id LOOP
    BEGIN EXECUTE r.health_sql INTO cur;
    EXCEPTION WHEN OTHERS THEN
      UPDATE public.gold_loop_supervisor SET last_action='health_sql_error',
        notes=format('health err: %s', SQLERRM), updated_at=now() WHERE id=r.id;
      out := out||r.label||':health_err; '; CONTINUE;
    END;

    v_dod_sql := format('(%s) %s %s', r.health_sql, r.target_op, r.target_val);

    -- success
    IF (r.target_op='>=' AND cur>=r.target_val) OR (r.target_op='<=' AND cur<=r.target_val) THEN
      UPDATE public.gold_loop_supervisor SET status='succeeded', last_metric=cur, last_progress_at=now(),
        last_action='completed', notes=format('target met: %s', cur), updated_at=now() WHERE id=r.id;
      out := out||r.label||':SUCCEEDED('||cur||'); '; CONTINUE;
    END IF;

    -- live progress -> never interrupt
    improved := (r.last_metric IS NULL)
             OR (r.target_op='>=' AND cur>r.last_metric)
             OR (r.target_op='<=' AND cur<r.last_metric);
    IF improved THEN
      UPDATE public.gold_loop_supervisor SET last_metric=cur, last_progress_at=now(),
        status=CASE WHEN status='diagnosing' THEN 'diagnosing' ELSE 'healthy' END,
        last_action='progress', notes=format('metric -> %s (target %s %s)', cur, r.target_op, r.target_val),
        updated_at=now() WHERE id=r.id;
      out := out||r.label||':progress('||cur||'); '; CONTINUE;
    END IF;

    -- still inside the no-movement grace window
    IF now()-r.last_progress_at < make_interval(mins => r.stall_minutes) THEN
      out := out||r.label||':waiting('||cur||'); '; CONTINUE;
    END IF;

    -- diagnosing leash
    IF r.status='diagnosing' THEN
      IF now()-r.last_action_at > make_interval(mins => r.stall_minutes*2) THEN
        UPDATE public.gold_loop_supervisor SET status='exhausted', last_action='diag_timeout',
          notes='diagnostic did not resolve', updated_at=now() WHERE id=r.id;
        out := out||r.label||':diag_timeout; ';
      ELSE out := out||r.label||':diagnosing; '; END IF;
      CONTINUE;
    END IF;

    -- cooldown applies to any re-launch
    IF r.last_action_at IS NOT NULL AND now()-r.last_action_at < make_interval(mins => r.cooldown_minutes) THEN
      out := out||r.label||':cooldown; '; CONTINUE;
    END IF;

    -- did the metric ADVANCE since the last launch? (=> prior session worked, just walled at 5h)
    advanced := r.metric_at_last_launch IS NOT NULL AND (
                 (r.target_op='>=' AND cur > r.metric_at_last_launch) OR
                 (r.target_op='<=' AND cur < r.metric_at_last_launch));

    IF advanced THEN
      -- CONTINUATION: chain the next session, do NOT spend the failure budget
      BEGIN
        PERFORM public.launch_claude_code_session(r.mission_title||' (continuation)',
          r.mission_body, r.repo, 'p0', r.workflow, v_dod_sql);
        UPDATE public.gold_loop_supervisor SET attempts=0, metric_at_last_launch=cur,
          last_action='continuation', last_action_at=now(), last_progress_at=now(), status='supervising',
          notes=format('session ended after progress to %s (likely 5h wall) -> chained continuation', cur),
          updated_at=now() WHERE id=r.id;
        out := out||r.label||':CONTINUATION('||cur||'); ';
      EXCEPTION WHEN OTHERS THEN
        UPDATE public.gold_loop_supervisor SET last_action='cont_error', notes=SQLERRM, updated_at=now() WHERE id=r.id;
        out := out||r.label||':cont_err; ';
      END; CONTINUE;
    END IF;

    -- ZERO progress since last launch -> real failure path (bounded)
    IF r.attempts < r.max_attempts THEN
      BEGIN
        PERFORM public.launch_claude_code_session(r.mission_title||' (retry '||(r.attempts+1)||')',
          r.mission_body, r.repo, 'p0', r.workflow, v_dod_sql);
        UPDATE public.gold_loop_supervisor SET attempts=r.attempts+1, metric_at_last_launch=cur,
          last_action='refired', last_action_at=now(), status='supervising',
          notes=format('no-progress retry %s @ %s', r.attempts+1, cur), updated_at=now() WHERE id=r.id;
        out := out||r.label||':REFIRED('||(r.attempts+1)||'); ';
      EXCEPTION WHEN OTHERS THEN
        UPDATE public.gold_loop_supervisor SET last_action='refire_error', notes=SQLERRM, updated_at=now() WHERE id=r.id;
        out := out||r.label||':refire_err; ';
      END; CONTINUE;
    END IF;

    IF NOT r.diagnostic_fired AND r.diagnostic_body IS NOT NULL THEN
      BEGIN
        PERFORM public.launch_claude_code_session('DIAGNOSE '||r.label||' — root-cause + repair or escalate',
          r.diagnostic_body, r.repo, 'p0', r.workflow, v_dod_sql);
        UPDATE public.gold_loop_supervisor SET diagnostic_fired=true, status='diagnosing',
          last_action='diagnostic_fired', last_action_at=now(), metric_at_last_launch=cur,
          notes='no-progress retries exhausted -> diagnostic dispatched', updated_at=now() WHERE id=r.id;
        out := out||r.label||':DIAGNOSTIC; ';
      EXCEPTION WHEN OTHERS THEN
        UPDATE public.gold_loop_supervisor SET last_action='diag_launch_error', notes=SQLERRM, updated_at=now() WHERE id=r.id;
        out := out||r.label||':diag_err; ';
      END; CONTINUE;
    END IF;

    UPDATE public.gold_loop_supervisor SET status='exhausted', last_action='escalate',
      notes='retry+diagnostic both made zero progress', updated_at=now() WHERE id=r.id;
    out := out||r.label||':EXHAUSTED; ';
  END LOOP;
  RETURN COALESCE(NULLIF(out,''),'no active rows');
END;
$function$;

-- ============================================================================
-- 5. duval_loop_watchdog — DoD = the supervisor's own success_target threshold
--    against foreclosure_outcomes, reused across retry and diagnostic relaunches.
-- ============================================================================
CREATE OR REPLACE FUNCTION public.duval_loop_watchdog()
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'net', 'vault', 'extensions'
AS $function$
DECLARE s public.duval_loop_supervisor; cur int; v_dod_sql text;
BEGIN
  SELECT * INTO s FROM public.duval_loop_supervisor WHERE id=1;
  IF NOT FOUND THEN RETURN 'no supervisor row'; END IF;
  -- terminal: human_blocker is the ONLY one that needs a person, and it arrives WITH a diagnosis
  IF s.status IN ('succeeded','disabled','human_blocker') THEN RETURN 'terminal:'||s.status; END IF;

  SELECT count(*) INTO cur FROM public.foreclosure_outcomes
   WHERE county ILIKE 'duval' AND data_source='duval_realforeclose';

  v_dod_sql := format(
    '(SELECT count(*) FROM public.foreclosure_outcomes WHERE county ILIKE ''duval'' AND data_source=''duval_realforeclose'') >= %s',
    s.success_target);

  -- progress beats everything
  IF cur > s.last_count THEN
    UPDATE public.duval_loop_supervisor SET last_count=cur, last_progress_at=now(),
       status=CASE WHEN status='diagnosing' THEN 'healthy' ELSE 'healthy' END,
       last_action='progress', notes=format('rows %s->%s', s.last_count, cur), updated_at=now() WHERE id=1;
    RETURN format('progress %s->%s', s.last_count, cur);
  END IF;

  IF cur >= s.success_target THEN
    UPDATE public.duval_loop_supervisor SET status='succeeded', last_action='completed',
       notes=format('target met: %s rows', cur), updated_at=now() WHERE id=1;
    RETURN format('succeeded: %s rows', cur);
  END IF;

  -- still inside the climbing window => wait
  IF now() - s.last_progress_at < make_interval(mins => s.stall_minutes) THEN
    RETURN format('waiting: %s rows', cur);
  END IF;

  -- TIER 2: a diagnostic agent is already working -> give it a longer leash, don't pile on
  IF s.status='diagnosing' THEN
    IF now() - s.last_action_at > make_interval(mins => s.stall_minutes*2) THEN
      UPDATE public.duval_loop_supervisor SET status='exhausted', last_action='diag_timeout',
         notes='diagnostic agent did not resolve or report back', updated_at=now() WHERE id=1;
      RETURN 'diagnostic timed out -> exhausted';
    END IF;
    RETURN 'diagnosing';
  END IF;

  -- TIER 1: simple re-fire for transient/concurrency
  IF s.attempts < s.max_attempts THEN
    IF s.last_action_at IS NOT NULL AND now()-s.last_action_at < make_interval(mins => s.cooldown_minutes) THEN
      RETURN 'cooldown';
    END IF;
    BEGIN
      PERFORM public.launch_claude_code_session(
        s.mission_title||' (retry '||(s.attempts+1)||')', s.mission_body, s.mission_repo, 'p0', s.mission_workflow, v_dod_sql);
      UPDATE public.duval_loop_supervisor SET attempts=s.attempts+1, last_action='refired',
         last_action_at=now(), status='supervising',
         notes=format('re-fired attempt %s @ %s rows', s.attempts+1, cur), updated_at=now() WHERE id=1;
      RETURN format('RE-FIRED attempt %s', s.attempts+1);
    EXCEPTION WHEN OTHERS THEN
      UPDATE public.duval_loop_supervisor SET last_action='refire_error',
         notes=format('launch error: %s', SQLERRM), updated_at=now() WHERE id=1;
      RETURN 'refire_error: '||SQLERRM;
    END;
  END IF;

  -- TIER 2 entry: simple retries exhausted -> fire a DIAGNOSTIC agent (not a human)
  IF NOT s.diagnostic_fired AND s.diagnostic_body IS NOT NULL THEN
    BEGIN
      PERFORM public.launch_claude_code_session(
        'DIAGNOSE Duval RealForeclose loop — root-cause + repair or escalate',
        s.diagnostic_body, s.mission_repo, 'p0', s.mission_workflow, v_dod_sql);
      UPDATE public.duval_loop_supervisor SET diagnostic_fired=true, status='diagnosing',
         last_action='diagnostic_fired', last_action_at=now(),
         notes=format('retries exhausted @ %s rows -> diagnostic agent dispatched', cur), updated_at=now() WHERE id=1;
      RETURN 'DIAGNOSTIC AGENT DISPATCHED';
    EXCEPTION WHEN OTHERS THEN
      UPDATE public.duval_loop_supervisor SET last_action='diag_launch_error',
         notes=format('diag launch error: %s', SQLERRM), updated_at=now() WHERE id=1;
      RETURN 'diag_launch_error: '||SQLERRM;
    END;
  END IF;

  -- TIER 3: only now, after retry + AI diagnosis both failed
  UPDATE public.duval_loop_supervisor SET status='exhausted', last_action='escalate',
     notes=format('retry+diagnostic both failed @ %s rows', cur), updated_at=now() WHERE id=1;
  RETURN 'EXHAUSTED -> human (retry+diagnostic both failed)';
END;
$function$;

-- ============================================================================
-- 6. cairn_ask — direct inserter. DoD = a detective_runs row landed for this
--    summit_id with a final_marker.
-- ============================================================================
CREATE OR REPLACE FUNCTION public.cairn_ask(p_slug text, p_question text, p_priority text DEFAULT 'normal'::text)
 RETURNS uuid
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_summit_id uuid := gen_random_uuid();
BEGIN
    INSERT INTO summit_chat_dispatch (
        id, summit_title, summit_body, target_repo, target_workflow,
        state, priority, ai_architect_model,
        evidence_schema_version, verification_scope,
        attempt_number, max_attempts, dispatch_inputs, dod_sql
    ) VALUES (
        v_summit_id,
        'CAIRN-' || p_slug || ': ' || LEFT(p_question, 80),
        E'# CAIRN Investigation\n\n## Question\n' || p_question ||
        E'\n\n## Protocol\nCAIRN v1 — see dispatch_inputs.system_prompt for full discipline.\n\n## Acceptance\n- detective_runs row inserted with OVERALL_MARKER\n- summit state=closed with delivery_proof\n- eg14_passed=true if zero honesty violations',
        'breverdbidder/cli-anything-biddeed',
        'claude-code-direct.yml',
        'queued',
        p_priority,
        'claude-sonnet-4-5',
        'v1.0',
        'supabase_only',
        0,
        3,
        jsonb_build_object(
            'summit_id',         v_summit_id::text,
            'cairn_type',        'investigation',
            'cairn_slug',        p_slug,
            'question',          p_question,
            'system_prompt',     cairn_child_system(),
            'max_iterations',    15,
            'write_to_table',    'detective_runs',
            'budget_usd',        3.00,
            'runner_tier',       'Tier1 Sonnet 4.6 Max OAuth',
            'smart_router_url',  'http://127.0.0.1:8317',
            'work_repo',         'breverdbidder/cli-anything-biddeed',
            'branch',            'chat-autonomous/cairn',
            'acceptance_criteria', jsonb_build_array(
                'detective_runs row inserted with final_marker',
                'summit state=closed with delivery_proof',
                'eg14_passed=true if zero honesty violations',
                'cost_usd ~= 0 on T1 Max OAuth'
            ),
            'karpathy_tags',     jsonb_build_array('V')
        ),
        format('SELECT EXISTS (SELECT 1 FROM detective_runs WHERE summit_id = %L::uuid AND final_marker IS NOT NULL)', v_summit_id)
    );
    RETURN v_summit_id;
END;
$function$;

-- ============================================================================
-- 7. cairn_supervisor_scan — direct inserter for the self-heal dispatch. DoD =
--    a supervisor_log row landed for the original failed summit with a resolved
--    retry_outcome. (The immediate-quarantine branch inserts no dispatch, so it
--    needs no dod_sql.)
-- ============================================================================
CREATE OR REPLACE FUNCTION public.cairn_supervisor_scan()
 RETURNS integer
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_failed        record;
    v_sup_count     int := 0;
    v_sup_id        uuid;
    v_attempts      int;
BEGIN
    FOR v_failed IN
        SELECT s.*
        FROM summit_chat_dispatch s
        WHERE s.summit_title LIKE 'CAIRN-%'
          AND s.summit_title NOT LIKE 'CAIRN-SUPERVISOR-%'
          AND (
              s.state = 'failed'
              OR (s.state = 'queued' AND s.created_at < now() - INTERVAL '10 minutes' AND s.picked_up_at IS NULL)
              OR (s.state = 'picked_up' AND s.picked_up_at < now() - INTERVAL '30 minutes')
              OR s.quarantine_reason IS NOT NULL
          )
          AND NOT EXISTS (
              SELECT 1 FROM supervisor_log sl
              WHERE sl.failed_summit_id = s.id
                AND sl.created_at > now() - INTERVAL '30 minutes'
                AND sl.retry_outcome IN ('queued','closed')
          )
    LOOP
        SELECT count(*) INTO v_attempts FROM supervisor_log WHERE failed_summit_id = v_failed.id;

        IF v_attempts >= 3 THEN
            UPDATE summit_chat_dispatch
            SET quarantine_reason = COALESCE(quarantine_reason, 'supervisor_3_attempts_exceeded'),
                quarantine_diagnosis = 'supervisor gave up after 3 retries; needs human architect review (logged, not pinged)'
            WHERE id = v_failed.id;

            INSERT INTO supervisor_log (failed_summit_id, classification, fix_applied, retry_outcome, escalated_to_ariel)
            VALUES (v_failed.id, 'permanent_quarantine', 'max_attempts_exceeded', 'quarantined', false);
            CONTINUE;
        END IF;

        v_sup_id := gen_random_uuid();
        INSERT INTO summit_chat_dispatch (
            id, summit_title, summit_body, target_repo, target_workflow,
            state, priority, ai_architect_model,
            evidence_schema_version, verification_scope,
            attempt_number, max_attempts, dispatch_inputs, dod_sql
        ) VALUES (
            v_sup_id,
            'CAIRN-SUPERVISOR-' || v_failed.id::text,
            E'# CAIRN Supervisor Investigation\n\nA CAIRN investigation failed. Diagnose and self-heal.\n\nDo NOT notify Ariel. Only VERIFIED successes reach him.',
            'breverdbidder/cli-anything-biddeed',
            'chat-bypass-no-workflow',  -- WAS 'claude-code-direct.yml' (disabled, caused 13-day runaway)
            'queued',
            'p0',
            'claude-sonnet-4-5',
            'v1.0',
            'supabase_only',
            0,
            1,
            jsonb_build_object(
                'summit_id',                 v_sup_id::text,
                'cairn_type',                'supervisor',
                'failed_summit_id',          v_failed.id::text,
                'failed_summit_title',       v_failed.summit_title,
                'failed_last_error',         v_failed.last_error,
                'failed_quarantine_reason',  v_failed.quarantine_reason,
                'failed_state',              v_failed.state,
                'failed_attempt_number',     v_failed.attempt_number,
                'original_question',         v_failed.dispatch_inputs->>'question',
                'system_prompt',             cairn_supervisor_system(),
                'prior_supervisor_attempts', v_attempts,
                'max_iterations',            10,
                'write_to_table',            'supervisor_log',
                'budget_usd',                2.00,
                'runner_tier',               'Tier1 Sonnet 4.6 Max OAuth',
                'smart_router_url',          'http://127.0.0.1:8317',
                'work_repo',                 'breverdbidder/cli-anything-biddeed',
                'branch',                    'chat-autonomous/cairn-supervisor',
                'do_not_notify_ariel',       true,
                'routing_note',              'chat-bypass since 2026-05-06 postmortem; pickup by next chat session'
            ),
            format('SELECT EXISTS (SELECT 1 FROM supervisor_log WHERE failed_summit_id = %L::uuid AND retry_outcome IN (''queued'',''closed''))', v_failed.id)
        );

        v_sup_count := v_sup_count + 1;
    END LOOP;

    RETURN v_sup_count;
END;
$function$;

-- ============================================================================
-- 8. enqueue_ducklake_archive — direct inserter. Generate the dispatch id up
--    front so dod_sql can reference the linked ducklake_archive_runs row.
-- ============================================================================
CREATE OR REPLACE FUNCTION public.enqueue_ducklake_archive(p_cutoff_days integer DEFAULT 90, p_dry_run boolean DEFAULT true, p_target_repo text DEFAULT 'breverdbidder/cli-anything-biddeed'::text)
 RETURNS TABLE(run_id bigint, dispatch_id uuid)
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_run_id      bigint;
  v_dispatch_id uuid := gen_random_uuid();
  v_cutoff      date := (now() - (p_cutoff_days || ' days')::interval)::date;
  v_uri         text := format('r2://zw-archive/multi_county_auctions/cutoff=%s/', v_cutoff);
BEGIN
  -- 1. dispatch row
  INSERT INTO public.summit_chat_dispatch (
    id, summit_title, summit_body, target_repo, target_workflow,
    dispatch_inputs, state, ai_architect_model, priority, dod_sql
  ) VALUES (
    v_dispatch_id,
    format('DuckLake archive: multi_county_auctions cutoff=%s', v_cutoff),
    format('Archive rows older than %s days from public.multi_county_auctions to DuckLake (Postgres catalog + R2 parquet). dry_run=%s.', p_cutoff_days, p_dry_run),
    p_target_repo,
    'ducklake-archive-snapshot.yml',
    jsonb_build_object(
      'cutoff_date', v_cutoff,
      'dry_run',     p_dry_run,
      'source_table','public.multi_county_auctions',
      'parquet_uri', v_uri,
      'honesty',     'UNTESTED'
    ),
    'queued', 'claude-opus-4-7', 'normal',
    format('SELECT EXISTS (SELECT 1 FROM public.ducklake_archive_runs WHERE dispatch_id = %L::uuid AND state = ''completed'')', v_dispatch_id)
  );

  -- 2. bookkeeping row, linked to dispatch
  INSERT INTO public.ducklake_archive_runs (
    source_table, cutoff_date, state, dispatch_id
  ) VALUES (
    'public.multi_county_auctions', v_cutoff, 'queued', v_dispatch_id
  ) RETURNING id INTO v_run_id;

  RETURN QUERY SELECT v_run_id, v_dispatch_id;
END
$function$;

-- ============================================================================
-- 9. Backlog triage — the 24 needs_dod rows that accumulated before this fix.
--    All 24 trace to launch_gold_standard_session (GOLD STANDARD SHARD-N titles).
--    Backfill dod_sql from gold_standard_campaign.target_counties (derivable in
--    every case); mark 'delivered' with an evidence note where a target county
--    is already certified, else 'active' so cc_redispatch_tick picks them up.
--    Idempotent: only touches rows still in status='needs_dod'.
-- ============================================================================
WITH backlog AS (
  SELECT g.issue_number,
         c.target_counties,
         format('SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications WHERE county_slug = ANY(%L::text[]) AND certified)',
                c.target_counties) AS derived_dod_sql,
         EXISTS (
           SELECT 1 FROM unnest(c.target_counties) cty
           JOIN public.gold_standard_certifications gc ON gc.county_slug = cty AND gc.certified
         ) AS already_delivered
  FROM public.cc_redispatch_guard g
  JOIN public.summit_chat_dispatch d ON d.github_issue_number = g.issue_number
  JOIN public.gold_standard_campaign c ON c.dispatch_id = d.id
  WHERE g.status = 'needs_dod'
)
UPDATE public.cc_redispatch_guard g
SET dod_sql    = backlog.derived_dod_sql,
    status     = CASE WHEN backlog.already_delivered THEN 'delivered' ELSE 'active' END,
    delivered_at = CASE WHEN backlog.already_delivered THEN now() ELSE g.delivered_at END,
    last_error = CASE WHEN backlog.already_delivered
                       THEN format('TRIAGE %s: backfilled dod_sql from gold_standard_campaign; already satisfied — county in %s already certified',
                                    to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS"Z"'), backlog.target_counties)
                       ELSE format('TRIAGE %s: backfilled dod_sql from gold_standard_campaign target_counties %s; status->active for cc_redispatch_tick',
                                    to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS"Z"'), backlog.target_counties)
                  END
FROM backlog
WHERE g.issue_number = backlog.issue_number
  AND g.status = 'needs_dod';

COMMIT;
