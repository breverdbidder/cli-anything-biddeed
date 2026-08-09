-- ARCHITECT TRIAGE for issue #18471 (dispatch auto-triage-issue-18471-202608092220)
--
-- DoD: SELECT EXISTS (SELECT 1 FROM gold_standard_certifications WHERE
-- county_slug = ANY('{jefferson}') AND certified) -- confirmed still false
-- live. This is NOT a bug and will correctly stay false until the
-- 2026-08-19 tax-deed sale happens and the weekly clerk scraper
-- (shard-jefferson-clerk-scraper.yml, Mon 08:30Z) picks up the results,
-- resolving letters B/F. 14+ independent firings (dispatches
-- 675aa97f/0f9adc6e/35b72237/21147d7e/6c6d08c3 and 20+ duplicate daily-wave
-- issues since 2026-07-14) all converge on the same structural blocker:
-- case 25-CA-164's sold_amount is gated behind a live Cloudflare Turnstile
-- challenge on the only two systems that carry it (Civitek OCRS,
-- myfloridacounty.com -- confirmed unbypassable via curl/WebFetch/Playwright
-- across 3+ independent sessions), and cases 26-TD-04/26-TD-05 have not
-- reached their 2026-08-19 auction date yet. gold_standard_county_blockers
-- already records exactly this (blocked_until=2026-08-25T10:00Z).
--
-- REAL BUG FOUND (verified live via Supabase REST): jefferson was
-- re-dispatched TWICE on 2026-08-09 alone -- chat_session
-- architect-20260809T080000 -> issue #18378 (08:00Z) and
-- architect-20260809T160000 -> issue #18471 (16:00Z, the issue this triage
-- was raised for) -- despite the blocker row existing since 2026-08-03.
-- Root cause: launch_gold_standard_fleet() (the 3x/daily 00:00/08:00/16:00Z
-- wave dispatcher that produces these 'architect-<ts>' SUMMIT sessions)
-- excludes certified / alive-campaign / active-watchdog / gate-ready
-- counties from its shard candidate ranking, but has NO predicate against
-- gold_standard_county_blockers -- unlike gold_standard_autopilot() (fixed
-- 20260803_jefferson_autopilot_blocked_until_gate.sql), which already
-- excludes blocked counties in both of its selection queries. Every 8h wave
-- keeps re-picking jefferson (8/10, therefore not gate-ready) and
-- re-deriving the identical negative result at full 6h session cost. The
-- prior session (dispatch 6c6d08c3, issue #18471 close-out comment) flagged
-- this exact gap as a recommendation; this migration implements it instead
-- of re-flagging it a 15th time.
--
-- FIX: add the identical NOT EXISTS (gold_standard_county_blockers ...
-- blocked_until > now()) predicate already proven safe in
-- gold_standard_autopilot() to launch_gold_standard_fleet()'s candidate
-- query. Fails safe: an empty/missing blockers table changes nothing (NOT
-- EXISTS on zero rows is always true). No change to shard count, per-shard
-- size, stagger sleep, or any existing filter.

CREATE OR REPLACE FUNCTION public.launch_gold_standard_fleet(p_shards integer DEFAULT 5, p_per_shard integer DEFAULT 3)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_result jsonb := '[]'::jsonb; v_one jsonb; i int; v_targets text[];
BEGIN
  FOR i IN 1..p_shards LOOP
    SELECT array_agg(county_slug) INTO v_targets FROM (
      SELECT county_slug, row_number() OVER (ORDER BY pass_count DESC, county_slug) AS rn
      FROM gold_standard_scoreboard sb
      WHERE NOT EXISTS (SELECT 1 FROM gold_standard_certifications c
                         WHERE c.county_slug = sb.county_slug AND c.certified)
        -- RACE FIX: don't re-launch a session on a county a prior fleet
        -- cycle (or watchdog) already has an alive session on.
        AND NOT public.gold_county_has_alive_campaign(sb.county_slug)
        AND NOT public.gold_county_has_active_watchdog(sb.county_slug)
        -- COST GATE: skip gate-ready counties -- 10/10 pass with both
        -- precert guards green means the only residual is
        -- adversarial_survival, which a CC session cannot fix.
        AND NOT (
          sb.pass_count = 10
          AND EXISTS (SELECT 1 FROM gold_standard_precert_guards g WHERE g.county_slug=sb.county_slug
                      AND g.guard_type='calendar_parity' AND g.passed AND g.created_at > now()-interval '7 days')
          AND EXISTS (SELECT 1 FROM gold_standard_precert_guards g WHERE g.county_slug=sb.county_slug
                      AND g.guard_type='denominator_integrity' AND g.passed AND g.created_at > now()-interval '7 days')
        )
        -- TIME-BLOCK GATE (2026-08-09, architect triage #18471): skip
        -- counties structurally blocked on a future real-world date (a
        -- scheduled sale, a weekly scraper cron) -- same predicate already
        -- used by gold_standard_autopilot(). Self-expiring via blocked_until.
        AND NOT EXISTS (SELECT 1 FROM public.gold_standard_county_blockers b
                        WHERE b.county_slug = sb.county_slug AND b.blocked_until > now())
    ) ranked
    WHERE (rn - 1) % p_shards = (i - 1) AND rn <= p_shards * p_per_shard;

    IF v_targets IS NOT NULL THEN
      v_one := public.launch_gold_standard_session(v_targets, 'SHARD-' || i);
      v_result := v_result || jsonb_build_array(v_one);
      PERFORM pg_sleep(3);  -- stagger dispatches
    END IF;
  END LOOP;
  RETURN jsonb_build_object('shards_launched', jsonb_array_length(v_result), 'sessions', v_result);
END $function$;
