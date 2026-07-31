-- COST-FIX-5 Deployment A: Gemini-gates-CC for stuck-at-ceiling Gold Standard
-- counties. dispatch_id: f96318aa-8325-4497-b72a-de26c7eaa7ba
-- chat_session: cost-fix-gemini-correct-use-202607311437
--
-- LIVE-DB EVIDENCE (2026-07-31, read before writing this migration):
--   15 counties are pass_count=10 AND NOT certified: bay, duval, franklin,
--   hendry, hillsborough, lafayette, nassau, orange, palm_beach, pasco,
--   polk, santa_rosa, st_johns, volusia, walton. consecutive_non_gold runs
--   as high as 93 (walton), 90 (santa_rosa), 80 (polk) — dozens of 5-min
--   ticks re-selecting the same stuck counties for a blind 6h CC session
--   that cannot fix a guard-not-running or adversarial-survival problem by
--   re-running the same 10-criteria loop again.
--
-- gold_standard_autopilot()'s floor_fill rule (ORDER BY pass_count DESC)
-- is the blind-dispatch site: pass_count=10 counties always sort first, so
-- floor_fill keeps re-picking the same handful of stuck counties. This adds
-- a diagnosis gate ONLY for pass_count=10 candidates: gold-standard-guard-
-- diagnose (Gemini Flash, $0, <5s) is called synchronously via
-- extensions.http() for each stuck candidate; a county is excluded from
-- v_next this tick when the diagnosis says requires_code_fix=false (nothing
-- a CC session can do right now — e.g. calendar-parity guard just hasn't
-- run yet). requires_code_fix=true dispatches its own CC issue directly
-- (see the edge function) and is ALSO excluded from v_next, since a session
-- is already in flight for it.
--
-- Fails open: any error calling the edge function (network, vault secret
-- missing, non-200) is caught and treated as "no diagnosis available" ->
-- county is NOT excluded, i.e. floor_fill behaves exactly as it did before
-- this migration. This migration can never cause fewer sessions to be
-- launched than before due to a diagnosis-call failure, only equal or fewer
-- due to a successful requires_code_fix=false diagnosis.
--
-- Counties with pass_count<10 are never gated — they're still climbing and
-- a normal session is the correct action, matching pre-existing behavior.

BEGIN;

CREATE OR REPLACE FUNCTION public.gold_standard_guard_diagnose_gather(p_county_slug text)
 RETURNS jsonb
 LANGUAGE sql STABLE
 SET search_path TO 'public'
AS $function$
  SELECT jsonb_build_object(
    'county_slug', p_county_slug,
    'pass_count', (SELECT pass_count FROM public.gold_standard_scoreboard WHERE county_slug = p_county_slug),
    'parity_ok', (SELECT passed FROM public.gold_standard_precert_guards
                   WHERE county_slug ILIKE p_county_slug AND guard_type = 'calendar_parity'
                   ORDER BY created_at DESC LIMIT 1),
    'denom_ok', NULL,
    'letters_survived', (
      SELECT count(*) FROM (
        SELECT DISTINCT ON (letter) letter, survived
        FROM public.gold_standard_ultraloop_audit
        WHERE county_slug = p_county_slug AND created_at > now() - interval '7 days'
        ORDER BY letter, created_at DESC
      ) latest WHERE latest.survived
    ),
    'failing_letters', (
      SELECT coalesce(jsonb_agg(latest.letter ORDER BY latest.letter), '[]'::jsonb) FROM (
        SELECT DISTINCT ON (letter) letter, survived
        FROM public.gold_standard_ultraloop_audit
        WHERE county_slug = p_county_slug AND created_at > now() - interval '7 days'
        ORDER BY letter, created_at DESC
      ) latest WHERE NOT latest.survived
    ),
    'consecutive_non_gold', (SELECT consecutive_non_gold FROM public.gold_standard_certifications WHERE county_slug = p_county_slug)
  );
$function$;

COMMENT ON FUNCTION public.gold_standard_guard_diagnose_gather(text) IS
  'Gathers the gold-standard-guard-diagnose edge function request payload for one county. Read-only.';

CREATE OR REPLACE FUNCTION public.gold_standard_guard_diagnose_call(p_county_slug text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'extensions', 'vault'
AS $function$
DECLARE
  v_key   text;
  v_payload jsonb;
  v_resp  extensions.http_response;
BEGIN
  SELECT decrypted_secret INTO v_key FROM vault.decrypted_secrets WHERE name = 'router_proxy_key';
  IF v_key IS NULL THEN
    RETURN jsonb_build_object('error', 'router_proxy_key not in vault');
  END IF;

  v_payload := public.gold_standard_guard_diagnose_gather(p_county_slug);

  PERFORM extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS', '15000');

  SELECT * INTO v_resp FROM extensions.http((
    'POST',
    'https://mocerqjnksmhcjzxrewo.supabase.co/functions/v1/gold-standard-guard-diagnose',
    ARRAY[extensions.http_header('X-Router-Key', v_key)],
    'application/json',
    v_payload::text
  )::extensions.http_request);

  IF v_resp.status <> 200 THEN
    RETURN jsonb_build_object('error', 'non_200', 'status', v_resp.status, 'body', left(v_resp.content, 500));
  END IF;

  RETURN v_resp.content::jsonb;
EXCEPTION WHEN OTHERS THEN
  RETURN jsonb_build_object('error', SQLERRM);
END;
$function$;

COMMENT ON FUNCTION public.gold_standard_guard_diagnose_call(text) IS
  'Synchronous call to gold-standard-guard-diagnose edge fn for one county. Fails open (returns {error:...} jsonb, never raises) so callers can treat any error as "no diagnosis available".';

-- gold_standard_autopilot(): gate floor_fill candidate selection so
-- pass_count=10 counties are excluded when a fresh diagnosis says
-- requires_code_fix=false. Everything else (bd_gapfill, caps, cooldown,
-- watchdog-ownership race-fix checks) is untouched.
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
  v_stuck_skip text[] := ARRAY[]::text[];
  v_actions jsonb := '[]'::jsonb;
  v_one jsonb;
  v_diag jsonb;
  v_stuck record;
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

    -- COST-FIX-5: for every not-yet-excluded pass_count=10 candidate, ask
    -- gold-standard-guard-diagnose whether a CC session can even help. A
    -- clean requires_code_fix=false diagnosis excludes the county from
    -- this tick's v_next (it either got its own dispatch, or nothing a
    -- session can fix right now). Any error -> no exclusion (fail open).
    FOR v_stuck IN
      SELECT sb.county_slug
      FROM gold_standard_scoreboard sb
      WHERE sb.pass_count = 10
        AND NOT EXISTS (SELECT 1 FROM gold_standard_certifications c
                        WHERE c.county_slug = sb.county_slug AND c.certified)
        AND NOT sb.county_slug = ANY(v_owned)
        AND NOT public.gold_county_has_active_watchdog(sb.county_slug)
    LOOP
      v_diag := public.gold_standard_guard_diagnose_call(v_stuck.county_slug);
      IF v_diag ? 'diagnosis' AND (v_diag->'diagnosis'->>'requires_code_fix') = 'false' THEN
        v_stuck_skip := v_stuck_skip || v_stuck.county_slug;
      ELSIF v_diag ? 'diagnosis' AND (v_diag->'diagnosis'->>'requires_code_fix') = 'true' THEN
        -- own dispatch already fired by the edge fn -- exclude from floor_fill too
        v_stuck_skip := v_stuck_skip || v_stuck.county_slug;
        v_actions := v_actions || jsonb_build_array(jsonb_build_object(
          'rule','guard_diagnose','county',v_stuck.county_slug,'diagnosis',v_diag->'diagnosis'));
      END IF;
    END LOOP;

    -- RACE FIX: also exclude counties a watchdog session already owns.
    SELECT array_agg(county_slug) INTO v_next FROM (
      SELECT sb.county_slug
      FROM gold_standard_scoreboard sb
      WHERE NOT EXISTS (SELECT 1 FROM gold_standard_certifications c
                        WHERE c.county_slug = sb.county_slug AND c.certified)
        AND NOT sb.county_slug = ANY(v_owned)
        AND NOT sb.county_slug = ANY(v_stuck_skip)
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
    'guard_diagnose_skipped', v_stuck_skip,
    'actions', v_actions);
END $function$;

COMMIT;
