-- Fix Gold Standard cert thrash (issue #11593, dispatch c21e1624).
--
-- ROOT CAUSE (confirmed via live DB read, not the 4 named 5-min jobs writing
-- directly -- gold_calendar_parity_cycle/gold_cert_announce_check only
-- dispatch scrapes / announce certs and never touch gold_standard_scoreboard
-- or gold_standard_ultraloop_audit; gold_standard_certify() is idempotent
-- per run_id since the Jul 10 #11368 fix and only runs from the 6-hourly
-- canonical loop):
--
--   gold_loop_watchdog() (every 5 min) and gold_standard_autopilot() (every
--   5 min) are TWO INDEPENDENT launchers of Claude Code SUMMIT sessions that
--   each perform their own adversarial-survival re-verification and write
--   PASS/FAIL rows to gold_standard_ultraloop_audit. Neither checks whether
--   the OTHER already has an active session on the same county:
--     - gold_loop_watchdog fires continuation/retry/diagnostic sessions via
--       launch_claude_code_session() DIRECTLY, bypassing gold_standard_campaign
--       (the ledger gold_standard_autopilot reads for its v_owned check).
--     - gold_standard_autopilot's floor_fill/bd_gapfill picks counties with
--       no certified cert, blind to gold_loop_supervisor's active rows.
--   Two sessions racing on the same county independently re-verify the same
--   letter against different git/data snapshots minutes apart -> exactly the
--   observed flip pattern (okaloosa C/D/E, marion B/F/H, etc).
--
-- FIX: mutual-exclusion checks before every launch site, so only one owner
-- (fleet/autopilot campaign OR watchdog supervisor row) is ever active per
-- county at a time. Nothing about pass/fail evaluation, adversarial-survival
-- criteria, or the 6-hourly canonical loop is touched or loosened -- this
-- only prevents a second session from being launched while one is alive.

BEGIN;

-- ============================================================================
-- 1. Shared county-lock helpers. 8h bound: fleet sessions are documented as
--    "6h autonomous" (see launch_gold_standard_session bodies) -- 8h covers
--    one legitimate run without permanently wedging the lock on a dispatch
--    row whose state never transitioned to a terminal value (separate,
--    pre-existing bookkeeping bug in summit_chat_dispatch -- not fixed here,
--    out of scope for this race fix; noted for follow-up).
-- ============================================================================
CREATE OR REPLACE FUNCTION public.gold_county_has_alive_campaign(p_county text)
 RETURNS boolean
 LANGUAGE sql STABLE
 SET search_path TO 'public'
AS $function$
  SELECT EXISTS (
    SELECT 1
    FROM public.gold_standard_campaign g
    JOIN public.summit_chat_dispatch d ON d.id = g.dispatch_id
    WHERE d.state = ANY(ARRAY['queued','issue_created','dispatched','running',
                               'in_progress','awaiting_verification'])
      AND d.created_at > now() - interval '8 hours'
      AND p_county = ANY(g.target_counties)
  );
$function$;

CREATE OR REPLACE FUNCTION public.gold_county_has_active_watchdog(p_county text)
 RETURNS boolean
 LANGUAGE sql STABLE
 SET search_path TO 'public'
AS $function$
  SELECT EXISTS (
    SELECT 1 FROM public.gold_loop_supervisor s
    WHERE s.county = p_county
      AND s.status NOT IN ('succeeded','disabled','human_blocker')
      AND s.last_action_at > now() - interval '8 hours'
  );
$function$;

-- ============================================================================
-- 2. gold_loop_watchdog -- defer (do not spend cooldown/attempts budget) any
--    relaunch for a county the canonical fleet/autopilot already has an
--    alive campaign on. All other logic unchanged verbatim.
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

    -- RACE FIX: a canonical fleet/autopilot campaign already owns this county
    -- (mid-flight, <8h old) -> defer to it rather than launching a second,
    -- independently-verifying session. Does not consume attempts/cooldown.
    IF public.gold_county_has_alive_campaign(r.county) THEN
      out := out||r.label||':county_busy_campaign; '; CONTINUE;
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
-- 3. gold_standard_autopilot -- exclude counties a watchdog session already
--    owns from both bd_gapfill and floor_fill candidate selection. All other
--    logic (caps, cooldown, mission-complete stand-down) unchanged verbatim.
-- ============================================================================
CREATE OR REPLACE FUNCTION public.gold_standard_autopilot()
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_open_total int;
  v_inflight int;
  v_inflight_orig int;
  v_bd_covered boolean;
  v_recent_launch boolean;
  v_today_autopilot int;
  v_owned text[];
  v_next text[];
  v_actions jsonb := '[]'::jsonb;
  v_one jsonb;
  -- alive = every pipeline state before terminal closed/quarantined (verified against 7d state census)
  c_alive CONSTANT text[] := ARRAY['queued','issue_created','dispatched','running','in_progress','awaiting_verification'];
  c_floor CONSTANT int := 2;
  c_daily_cap CONSTANT int := 24;
  c_r3_cap CONSTANT int := 10;
BEGIN
  IF (SELECT count(*) FROM gold_standard_certifications
      WHERE county_slug IN ('brevard','duval') AND certified) = 2 THEN
    RETURN jsonb_build_object('state','mission_complete','action','stand_down');
  END IF;

  SELECT count(*) INTO v_open_total FROM summit_chat_dispatch WHERE state = ANY(c_alive);

  SELECT count(*),
         coalesce(bool_or(g.target_counties && ARRAY['brevard','duval']), false),
         coalesce(bool_or(d.created_at > now() - interval '10 minutes'), false)
    INTO v_inflight, v_bd_covered, v_recent_launch
  FROM gold_standard_campaign g
  JOIN summit_chat_dispatch d ON d.id = g.dispatch_id
  WHERE d.state = ANY(c_alive);
  v_inflight := coalesce(v_inflight, 0);
  v_inflight_orig := v_inflight;

  SELECT count(*) INTO v_today_autopilot
  FROM summit_chat_dispatch
  WHERE summit_title LIKE 'GOLD STANDARD AUTOPILOT%'
    AND created_at >= date_trunc('day', now());

  IF v_recent_launch THEN
    RETURN jsonb_build_object('state','cooling','inflight',v_inflight,'bd_covered',v_bd_covered);
  END IF;
  IF v_open_total >= c_r3_cap OR v_today_autopilot >= c_daily_cap THEN
    RETURN jsonb_build_object('state','capped','open_total',v_open_total,
                              'autopilot_today',v_today_autopilot,'inflight',v_inflight);
  END IF;

  -- RACE FIX: don't gapfill brevard/duval while a watchdog session already
  -- owns either county -- avoids a second concurrent verifier on the same
  -- county racing gold_loop_watchdog's continuation/retry/diagnostic session.
  IF NOT v_bd_covered
     AND NOT public.gold_county_has_active_watchdog('brevard')
     AND NOT public.gold_county_has_active_watchdog('duval') THEN
    v_one := public.launch_gold_standard_session(ARRAY['brevard','duval'], 'AUTOPILOT-BD');
    v_actions := v_actions || jsonb_build_array(jsonb_build_object('rule','bd_gapfill','launch',v_one));
    v_inflight := v_inflight + 1;
    v_open_total := v_open_total + 1;
  END IF;

  IF v_inflight < c_floor AND v_open_total < c_r3_cap THEN
    SELECT coalesce(array_agg(DISTINCT cty), ARRAY[]::text[]) INTO v_owned
    FROM gold_standard_campaign g
    JOIN summit_chat_dispatch d ON d.id = g.dispatch_id
    CROSS JOIN LATERAL unnest(g.target_counties) AS cty
    WHERE d.state = ANY(c_alive);
    v_owned := v_owned || ARRAY['brevard','duval'];

    -- RACE FIX: also exclude counties a watchdog session already owns.
    SELECT array_agg(county_slug) INTO v_next FROM (
      SELECT sb.county_slug
      FROM gold_standard_scoreboard sb
      WHERE NOT EXISTS (SELECT 1 FROM gold_standard_certifications c
                        WHERE c.county_slug = sb.county_slug AND c.certified)
        AND NOT sb.county_slug = ANY(v_owned)
        AND NOT public.gold_county_has_active_watchdog(sb.county_slug)
      ORDER BY sb.pass_count DESC, sb.county_slug
      LIMIT 3) q;

    IF v_next IS NOT NULL THEN
      v_one := public.launch_gold_standard_session(v_next, 'AUTOPILOT-NEXT');
      v_actions := v_actions || jsonb_build_array(jsonb_build_object('rule','floor_fill','launch',v_one));
    END IF;
  END IF;

  RETURN jsonb_build_object(
    'state', CASE WHEN jsonb_array_length(v_actions)=0 THEN 'healthy_noop' ELSE 'launched' END,
    'inflight_before', v_inflight_orig,
    'bd_covered_before', v_bd_covered,
    'autopilot_today', v_today_autopilot,
    'actions', v_actions);
END $function$;

COMMIT;
