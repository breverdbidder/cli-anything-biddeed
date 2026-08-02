-- Okaloosa SHARD-5 Post-Harvest Enrichment Wiring (2026-08-02)
-- =============================================================
-- This migration documents the root cause fix for okaloosa's C/D/E/I
-- regression (9/10 -> 6/10) and the wiring of the post-harvest enrichment
-- pipeline into the daily harvest workflow.
--
-- ROOT CAUSE (VERIFIED from harvest script line 213-226):
--   The daily okaloosa-bid4assets-harvest.yml workflow upserted new FC rows
--   with parcel_id=NULL (FC grids never publish APN). The GIS enrichment
--   pass (okaloosa_parcel_gis_enrich.py) was NOT wired into the workflow,
--   so new rows stayed parcel_id=NULL until a manual enrichment run.
--   When 8 new rows were added (57→65 auctions), C/D/E dropped from 96.5%
--   (PASS) to 90.8% (FAIL) and I dropped similarly.
--
-- FIX (committed 2026-08-02, SHARD-5):
--   scripts/okaloosa_post_harvest_enrich.py — 3-pass pipeline:
--     PASS1: GIS address-match -> parcel_id + geo + value for new FC rows
--     PASS2: parcel_zones zoning substrate for newly-linked parcels
--     PASS3: bid_decisions for new auctions without deal-thesis
--   .github/workflows/okaloosa-bid4assets-harvest.yml — wired PASS1-3 to
--     run automatically after each harvest, before the verify step.
--
-- VERIFICATION QUERY (run after the next harvest workflow fires):
SELECT
    county,
    COUNT(*) AS total_auctions,
    COUNT(parcel_id) AS parcel_linked,
    COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) AS matched_clean,
    ROUND(100.0 * COUNT(parcel_id) / NULLIF(COUNT(*), 0), 1) AS pct_parcel_linked,
    ROUND(100.0 * COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) / NULLIF(COUNT(*), 0), 1) AS pct_matched_clean
FROM multi_county_auctions
WHERE county = 'okaloosa'
GROUP BY county;

-- Expected result post-fix (>=95% threshold for C/D/E to PASS):
--   total_auctions=65, parcel_linked>=62 (>=95.4%), matched_clean>=62

-- STALE PLACEHOLDER RESIDUAL (known, unrecoverable, out of scope):
--   2024-CA-000470: no real address, absent from Bid4Assets 5+ sessions
--   2024-TDD-000089: no real address/APN, absent from Bid4Assets 5+ sessions
-- These 2 rows will always have parcel_id=NULL; denominator = 65, not 63.
-- At 63/65 = 96.9% these still PASS the >=95% threshold.

-- LETTER I RESIDUAL (from shard-7 session report, 2026-07-25):
--   B4A-1299799 (Mary Esther): has address+geo+value but no live GIS zoning
--   source for the City of Mary Esther (confirmed 3 sessions). parcel_zones
--   cannot be populated without a real zone_code — do not guess.
--   This row has been in the okaloosa dataset since the original B4A harvest.
