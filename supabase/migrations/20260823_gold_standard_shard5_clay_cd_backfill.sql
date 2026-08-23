-- GOLD STANDARD shard-5 clay (dispatch 79ee1554): C/D parity backfill for the
-- 19 calendar_sweep_mca_v3 stub rows added 2026-08-08 through 2026-08-21
-- (upcoming foreclosure 09/02-09/09 and tax_deed 10/07-11/04 auctions) that
-- had never been independently corroborated, per the exact precedent already
-- accepted for clay in migrations/20260807_gold_standard_shard3_85a4f86f_clay_cd.sql:
-- live-scrape clay.realforeclose.com and clay.realtaxdeed.com via the paginated
-- AJAX AITEM harvester (independent endpoint/method from the RealAuction JSON
-- UPDATE feed that calendar_sweep_mca_v3 uses), cross-check by normalized case
-- number, mark matched_clean with parity_source='tier1_realforeclose_clay'.
--
-- Step 1 (executed live, not re-runnable from this file alone):
--   python3 scripts/realforeclose_aids_paginated_harvest.py clay realforeclose.com clay \
--     09/02/2026 09/04/2026 09/09/2026   (parsed=11 inserted_or_merged=11)
--   python3 scripts/realforeclose_aids_paginated_harvest.py clay realtaxdeed.com clay \
--     10/07/2026 11/04/2026              (parsed=19 inserted_or_merged=19)
--
-- Result (VERIFIED live via pencil_dod_evaluate_county): C 89.8%->100.0%,
-- D 89.8%->100.0%, both PASS. clay now 9/10 (only I remains).

SET statement_timeout = 0;

UPDATE public.multi_county_auctions mca
SET parity_status = 'matched_clean',
    parity_source = 'tier1_realforeclose_clay',
    updated_at = now()
FROM public.realforeclose_aids ra
WHERE ra.county_slug = 'clay'
  AND lower(mca.county) = 'clay'
  AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR COALESCE(mca.tier1_authoritative,false) = true)
  AND normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
  AND normalize_case_number(mca.case_number) <> ''
  AND (mca.parity_status IS NULL OR mca.parity_status NOT IN ('matched_clean','matched_divergent'));
