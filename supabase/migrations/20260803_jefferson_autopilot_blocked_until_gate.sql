-- Gold Standard shard-3 jefferson (dispatch 35b72237-0368-4e53-a134-c638d24b1638,
-- issue #17643, chat_session architect-20260803T160000)
--
-- ROOT CAUSE FOUND (not previously investigated by any of jefferson's 13+ prior
-- letter-level firings): jefferson has been re-dispatched a fresh 6h SUMMIT
-- session on EVERY daily wave since 2026-07-14 (20+ open GitHub issues,
-- confirmed live via `gh issue list --search "jefferson gold standard"`),
-- because gold_standard_autopilot() (cron 161, */5 * * * *) has ZERO concept
-- of a county being structurally blocked pending a future real-world date.
-- Its floor_fill selector (added in 20260731i_cost_fix_5_gemini_guard_diagnose.sql)
-- only gates pass_count=10 candidates via a Gemini diagnosis call; counties
-- below 10/10 -- like jefferson at 8/10 -- are blindly re-picked every tick
-- once no session currently owns them.
--
-- jefferson B/F have been confirmed genuinely blocked across 13+ independent
-- firings (dispatch 675aa97f/#17031 alone: firings 1-11, gold_standard_ultraloop_audit
-- ids 11502-11509, 11694-11696, plus 12018/12019, 12346/12347 from firings on
-- adjacent dispatches through 2026-08-02): the sole closed case (25-CA-164)
-- has its sold_amount gated behind a live Cloudflare Turnstile challenge on
-- the only two systems that carry it (Civitek OCRS, myfloridacounty.com
-- official records) -- confirmed via curl, WebFetch, and real headless-
-- Chromium/Playwright sessions across 3 separate firings, not a technical
-- bug to route around. The other two cases (26-TD-04/05) have auction_date
-- 2026-08-19, which has not occurred yet. Every prior firing reached this
-- same conclusion and explicitly recommended suspending re-dispatch until
-- the date passes -- no mechanism existed to act on that recommendation, so
-- the fleet has burned 20+ full 6h sessions re-deriving it.
--
-- FIX: a minimal, county-scoped, self-expiring suppression table + a single
-- added predicate in gold_standard_autopilot()'s two selection queries. No
-- change to cron 161's schedule/trigger (guardrail: don't modify cron jobs
-- 109/111/115 or gold-standard-loop-* scoring jobs -- this is none of those,
-- it's a CREATE OR REPLACE of the function the cron calls). Fails safe: an
-- empty/missing blockers table changes nothing (NOT EXISTS on zero rows is
-- always true), and blockers self-expire via blocked_until so a county is
-- never permanently excluded by a stale row.

BEGIN;

CREATE TABLE IF NOT EXISTS public.gold_standard_county_blockers (
  county_slug             TEXT PRIMARY KEY,
  blocked_until            TIMESTAMPTZ NOT NULL,
  blocked_letters          TEXT[] NOT NULL,
  reason                   TEXT NOT NULL,
  created_by_dispatch_id   UUID,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.gold_standard_county_blockers IS
  'Date-gated suppression for gold_standard_autopilot() floor_fill dispatch selection. A row here excludes county_slug from new SUMMIT dispatches until blocked_until, so counties genuinely blocked on a future real-world event (a scheduled sale date, a weekly scraper cron) are not re-dispatched a fresh 6h session every wave to re-derive the same conclusion. Self-expiring by design -- do not treat as a permanent county exclusion list.';

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

    FOR v_stuck IN
      SELECT sb.county_slug
      FROM gold_standard_scoreboard sb
      WHERE sb.pass_count = 10
        AND NOT EXISTS (SELECT 1 FROM gold_standard_certifications c
                        WHERE c.county_slug = sb.county_slug AND c.certified)
        AND NOT sb.county_slug = ANY(v_owned)
        AND NOT public.gold_county_has_active_watchdog(sb.county_slug)
        AND NOT EXISTS (SELECT 1 FROM public.gold_standard_county_blockers b
                        WHERE b.county_slug = sb.county_slug AND b.blocked_until > now())
    LOOP
      v_diag := public.gold_standard_guard_diagnose_call(v_stuck.county_slug);
      IF v_diag ? 'diagnosis' AND (v_diag->'diagnosis'->>'requires_code_fix') = 'false' THEN
        v_stuck_skip := v_stuck_skip || v_stuck.county_slug;
      ELSIF v_diag ? 'diagnosis' AND (v_diag->'diagnosis'->>'requires_code_fix') = 'true' THEN
        v_stuck_skip := v_stuck_skip || v_stuck.county_slug;
        v_actions := v_actions || jsonb_build_array(jsonb_build_object(
          'rule','guard_diagnose','county',v_stuck.county_slug,'diagnosis',v_diag->'diagnosis'));
      END IF;
    END LOOP;

    SELECT array_agg(county_slug) INTO v_next FROM (
      SELECT sb.county_slug
      FROM gold_standard_scoreboard sb
      WHERE NOT EXISTS (SELECT 1 FROM gold_standard_certifications c
                        WHERE c.county_slug = sb.county_slug AND c.certified)
        AND NOT sb.county_slug = ANY(v_owned)
        AND NOT sb.county_slug = ANY(v_stuck_skip)
        AND NOT public.gold_county_has_active_watchdog(sb.county_slug)
        AND NOT EXISTS (SELECT 1 FROM public.gold_standard_county_blockers b
                        WHERE b.county_slug = sb.county_slug AND b.blocked_until > now())
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

-- Suppress jefferson re-dispatch until the weekly clerk-scraper cron has had
-- a chance to pick up the 2026-08-19 tax-deed sale results (next scheduled
-- run after that date is Monday 2026-08-24; a few hours' buffer added).
INSERT INTO public.gold_standard_county_blockers
  (county_slug, blocked_until, blocked_letters, reason, created_by_dispatch_id)
VALUES (
  'jefferson',
  '2026-08-24 12:00:00+00',
  ARRAY['B','F'],
  '13+ firings across dispatches 675aa97f(#17031)/0f9adc6e and 20+ duplicate '
  'daily-wave issues (2026-07-14 through 2026-08-03) all converged on the same '
  'structural blocker: case 25-CA-164 sold_amount is gated behind a live '
  'Cloudflare Turnstile challenge on the only two systems that carry it '
  '(Civitek OCRS, myfloridacounty.com), confirmed unbypassable via curl, '
  'WebFetch, and real headless-Chromium/Playwright across 3 separate firings; '
  'cases 26-TD-04/26-TD-05 have auction_date=2026-08-19 which has not occurred. '
  'shard-jefferson-clerk-scraper.yml (weekly, healthy) will pick up both once '
  'published -- re-dispatching before then re-derives an identical negative '
  'result at full 6h session cost. See gold_standard_ultraloop_audit ids '
  '11502-11509, 11694-11696, 12018-12019, 12346-12347.',
  '35b72237-0368-4e53-a134-c638d24b1638'
)
ON CONFLICT (county_slug) DO UPDATE SET
  blocked_until = EXCLUDED.blocked_until,
  blocked_letters = EXCLUDED.blocked_letters,
  reason = EXCLUDED.reason,
  created_by_dispatch_id = EXCLUDED.created_by_dispatch_id,
  created_at = now();

COMMIT;
