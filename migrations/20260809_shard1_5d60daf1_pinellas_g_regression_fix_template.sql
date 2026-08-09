-- GOLD STANDARD SHARD-1 (dispatch 5d60daf1, loop run 10108) — pinellas G regression investigation
-- STATUS: TEMPLATE — to be executed by a session with live Supabase credentials
--
-- DIAGNOSIS (INFERRED from brief data, not yet VERIFIED against live DB):
-- pinellas G was PASS (98.9%) on 2026-07-24 (dispatch 8d7de4ab, confirmed live).
-- Run 10108 brief shows G FAIL (density=93.9%, far=, pk1000=).
-- auctions_total changed: 393 (Jul-24) -> 423 (Aug-09) = 30 new auctions ingested.
-- Root cause hypothesis: 30 new auctions lack parcel_zones rows, dropping G coverage.
-- At 93.9% with 423 total: 423 * 0.939 = 397 have coverage. 423 - 397 = 26 without coverage.
--
-- FIX PLAN (execute this session, then verify):
-- Step 1: Identify the 30 new auctions lacking parcel_zones
-- Step 2: Fetch their lat/lon from multi_county_auctions
-- Step 3: Point-in-polygon query against Pinellas GIS
--         (egis.pinellas.gov or maps.largo.com ArcGIS zoning layer)
-- Step 4: Insert parcel_zones rows with real zone codes
-- Step 5: Verify G metric returns to >=95% via pencil_dod_evaluate_county('pinellas')
--
-- REFERENCE: The Jul-24 session (8d7de4ab) used these sources:
--   - egis.pinellas.gov Accela Address Points
--   - maps.largo.com ArcGIS (countywide Pinellas PA tax-roll data)
--   - Scripts: supabase/migrations/20260724_shard5_pinellas_i_real_parcel_geo_zone_fix.sql
--              supabase/migrations/20260724b_shard5_pinellas_i_g_regression_correction.sql
--
-- PRECAUTION (from 8d7de4ab session self-caught regression):
--   Any parcel_zones insert with a zone_code that has no matching zoning_districts row
--   will cause G to REGRESS because v_zoning_district_applicability defaults FAR/parking
--   to "applicable" (via COALESCE(..., true)), zeroing out G for uncovered zone codes.
--   ALWAYS verify zoning_districts row exists for the zone_code before inserting parcel_zones.

SET statement_timeout = 0;

-- Step 1: Find auctions missing parcel_zones (the G gap)
-- Run this first to understand the scope:
/*
SELECT mca.case_number, mca.parcel_id, mca.property_address, mca.lat, mca.lon,
       mca.created_at
FROM multi_county_auctions mca
LEFT JOIN parcel_zones pz ON pz.parcel_id = mca.parcel_id
  OR pz.tax_account = mca.parcel_id
WHERE mca.county = 'pinellas'
  AND pz.parcel_id IS NULL
  AND mca.parcel_id IS NOT NULL
ORDER BY mca.created_at DESC;
*/

-- Step 2: Count total vs covered (verify the regression hypothesis):
/*
SELECT
  COUNT(*) AS total_pinellas,
  COUNT(pz.parcel_id) AS with_zone_coverage,
  ROUND(COUNT(pz.parcel_id)::numeric / COUNT(*) * 100, 1) AS pct_covered
FROM multi_county_auctions mca
LEFT JOIN parcel_zones pz ON pz.parcel_id = mca.parcel_id
WHERE mca.county = 'pinellas';
*/

-- Step 3: Run point-in-polygon via Pinellas GIS
-- Use Python script: scripts/gs_shard1_pinellas_g_zone_backfill.py
-- (created by this session — see that file for implementation)

-- Step 4: After inserting parcel_zones, verify G metric:
-- SELECT public.pencil_dod_evaluate_county('pinellas');
-- Expected: G metric should return to >=95%

-- Step 5: Log to gold_standard_ultraloop_audit
-- INSERT INTO gold_standard_ultraloop_audit (dispatch_id, ultraloop_mode, county_slug, letter,
--   claim, refuter_evidence, survived)
-- VALUES ('5d60daf1-d8e8-4157-b699-b4410b18dc77', 'fallback', 'pinellas', 'G',
--   'pinellas G regression: 30 new auctions ingested since Jul-24 without parcel_zones. Fix: inserted zone codes via Pinellas GIS point-in-polygon for all coverage gaps.',
--   '{"before_metric": 93.9, "after_metric": <fill>, "rows_inserted": <fill>}'::jsonb,
--   true);
