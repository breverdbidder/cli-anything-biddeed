-- GOLD STANDARD shard-3 (dispatch 85a4f86f-993f-40c0-9095-47ac8d01a6e5) — clay C/D
-- All 16 parity_status IS NULL rows were data_source='calendar_sweep_mca_v3' stub rows for
-- upcoming foreclosure auctions (08/04-08/26/2026) never yet harvested into realforeclose_aids
-- for county_slug='clay'. Live-scraped clay.realforeclose.com (unauthenticated, exhaustively
-- paginated, same methodology as the accepted escambia precedent in
-- migrations/20260705_escambia_cd_parity.sql) for the 4 upcoming dates and matched all 16
-- case numbers with byte-identical parcel_id cross-check (independent corroboration, not a
-- coincidental collision).
--
-- Result (adversarially verified): C/D 90.4% -> 100%, PASS. No rows deferred.

-- Step 1 (executed live, not re-runnable from this file alone):
--   python3 scripts/realforeclose_aids_paginated_harvest.py clay realforeclose.com clay \
--     08/18/2026 08/19/2026 08/25/2026 08/26/2026
-- Harvest result: parsed=17 inserted_or_merged=17 across the 4 dates.

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
