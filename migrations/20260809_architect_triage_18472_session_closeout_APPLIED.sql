-- ARCHITECT TRIAGE issue #18472, dispatch_id 330611a5-1bca-4e9e-920b-dcdcf8e4c83d
-- (original shard-3 dispatch), architect session dispatch
-- 903d2fd2-12fb-4bde-b885-572977277fa1.
--
-- Records the ACTUAL, verified session outcome in gold_standard_campaign,
-- replacing the empty checkpoint the prior engineer session left behind
-- (criteria_passed='{}', exit_reason=NULL -- the MANDATORY SESSION CLOSE-OUT
-- from the dispatch brief never ran because the session ended without
-- shipping). Superscript: this UPDATE was ALREADY applied live via the
-- Supabase Management API this session; this file documents it for the repo
-- history. Values below are honest -- okaloosa is genuinely certified,
-- miami_dade I and lake C/I are genuinely still failing, not glossed over.

SET statement_timeout = 0;

UPDATE public.gold_standard_campaign
SET
    criteria_passed = jsonb_build_object(
        'okaloosa', jsonb_build_object(
            'A', true, 'B', true, 'C', true, 'D', true, 'E', true,
            'F', true, 'G', true, 'H', true, 'I', true, 'J', true,
            'score', 10,
            'notes', 'CERTIFIED live this session (architect triage #18472). I fixed via 2-row property_address backfill from fl_parcels (co_no=56): 64->66 of 69 (95.7%). gold_standard_certify() run twice (loop_run_id 10145, 10179), consecutive_gold=2, certified=true.'
        ),
        'lake', jsonb_build_object(
            'A', true, 'B', true, 'C', false, 'D', true, 'E', true,
            'F', true, 'G', true, 'H', true, 'I', false, 'J', true,
            'score', 8,
            'notes', 'NOT worked this session -- prior session migration for I (zoning_districts+parcel_zones) was verified insufficient even in best case (~90/118 vs 112/118 needed) so not applied; C has zero promotable NULL-parity rows live (verified), structural 7-row ceiling stands (JS-only Clerk SPA, Firecrawl exhausted until 2026-08-28).'
        ),
        'miami_dade', jsonb_build_object(
            'A', true, 'B', true, 'C', true, 'D', true, 'E', true,
            'F', true, 'G', true, 'H', true, 'I', false, 'J', true,
            'score', 9,
            'notes', 'C/D fixed live this session: 25 NULL-parity court-format rows promoted (466->491 of 491, 100%). I still FAIL (457/491, needs 467) -- geo/zoning enrichment gap not closed this session, flagged as next priority.'
        )
    ),
    criteria_total = 10,
    exit_reason = 'certified_okaloosa_partial_miami_dade_lake_pending',
    session_end_at = NOW()
WHERE dispatch_id = '330611a5-1bca-4e9e-920b-dcdcf8e4c83d';

-- Verification (run this to confirm the session outcome):
-- SELECT public.gold_standard_certify(); -- or check state directly:
-- SELECT county_slug, certified, consecutive_gold FROM public.gold_standard_certifications
--   WHERE county_slug IN ('okaloosa','lake','miami_dade');
--
-- DoD SQL (from #18472 / cc_redispatch_guard):
-- SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications
--   WHERE county_slug = ANY('{okaloosa,lake,miami_dade}'::text[]) AND certified);
-- -> TRUE (re-run and confirmed live 2026-08-09T22:38Z)
--
-- cc_redispatch_guard for issue 18472: status='delivered' (promoted via
-- public.cc_redispatch_reconcile(), resolved_via='reconciliation',
-- delivered_at=2026-08-09T22:38:50Z).
