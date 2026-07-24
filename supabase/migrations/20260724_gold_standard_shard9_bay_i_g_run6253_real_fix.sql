-- GOLD STANDARD shard-9 (bay), loop run 6253, dispatch 0c4df455-e5d2-4d65-9237-0d35132b0e53
-- Session date: 2026-07-24. All statements below were ALREADY APPLIED LIVE via the Supabase
-- Management API (mgmt_sql.py) during this session, before this file was committed. This file
-- is the record, per the repo's established gold-standard session pattern.
--
-- CONTEXT: issue #13872's FIRST attempt (branch claude/issue-13872-20260724-1602, commits
-- c03f3f35/afbc266b/a560a8e1/9cf777c8) proposed a blanket "NULL/mca_only rows with a
-- parcel_id -> matched_clean" promotion for C/D plus INFERRED filler data for I (R-1 default
-- zone_code for every gap parcel, city-centroid lat/lon, county-median assessed_value fallback
-- applied broadly). That branch was NEVER merged to main and its SQL was NEVER applied to the
-- live DB (the PR comment says so explicitly: "UNTESTED -- will post after apply"). This
-- migration does NOT reuse that approach. C/D/J were independently found to already be PASS
-- live (verified real, see gold_standard_ultraloop_audit ids 9582/9583/9585) via unrelated
-- prior real AJAX-harvest and bid_decisions-generator sessions -- no action needed there.
-- This migration covers the I and G work actually done this session.
--
-- I: 68.0% -> 97.2% (121 -> 173 of 178 card_complete)
--   1. Ran scripts/gold_standard_shard9_bay_run6253_i_fix.py (committed on main via commit
--      8d5dc646, never previously executed) live: 5 parcel_zones rows inserted via
--      gis.baycountyfl.gov TEST_Parcels+Land_Use_Planning MapServer (real ArcGIS fetch),
--      5 geo backfills. 5 rows NOT_FOUND left alone (BLANK > WRONG).
--   2. Supplemental point-in-polygon zoning-only pass for 14 rows that already had
--      address/geo/value but lacked zone_code: 10 successfully zoned via the same live
--      Land_Use_Planning point lookup, 4 left blank (ambiguous "See FLU(SPR)" needing a
--      jurisdiction not yet in the lookup map -- resolved in step 3 instead).
--   3. Discovered SUB_ZONING=8 on gis.baycountyfl.gov Land_Use_Planning = Springfield, FL
--      (jurisdictions.id=984, pre-existing row, previously just missing from this pipeline's
--      6-code jurisdiction map). Inserted the 4 deferred parcels as real zone_code='See FLU'
--      rows for jurisdiction_id=984.
--   Residual 5 unresolved I rows are genuine junk (parcel_id='TIMESHARE' x2, ='Property
--   Appraiser' x2 -- placeholder scraper artifacts, not real parcels -- and one Mexico Beach
--   parcel, 04875-080-0000, whose ID format TEST_Parcels' A1RENUM field does not match).
--   Left blank on purpose.
--
-- G: 96.5% (stale baseline) -> regressed to 57.4% as a direct side effect of the I work above
--   (every newly-zoned parcel enters G's denominator; most of the new zone codes had no
--   zoning_districts/zone_standards row yet, which the applicability view treats as
--   "applicable but missing" rather than N/A). Two genuinely-N/A districts fixed this session:
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, far_regulated, density_regulated, pk1000_regulated)
VALUES
  (873, 'See FLU', 'See Future Land Use (deferred, no fixed zone)', 'Deferred',
   'gis.baycountyfl.gov Land_Use_Planning layer returns ZONING=See FLU Label=See FLU(LH) for these parcels -- Lynn Haven has no fixed zoning district assigned, the city defers to the FLU map instead. No dimensional standards exist to look up (genuinely N/A, not unknown).',
   false, false, false),
  (984, 'See FLU', 'See Future Land Use (deferred, no fixed zone)', 'Deferred',
   'gis.baycountyfl.gov Land_Use_Planning layer returns ZONING=See FLU Label=See FLU(SPR) for these parcels -- Springfield has no fixed zoning district assigned, the city defers to the FLU map instead. No dimensional standards exist to look up (genuinely N/A, not unknown).',
   false, false, false)
ON CONFLICT DO NOTHING;

-- parcel_zones inserts from the I-fix passes (idempotent, ON CONFLICT DO NOTHING; the live
-- session used SELECT-before-INSERT so these are safe to replay).
INSERT INTO parcel_zones (jurisdiction_id, parcel_id, zone_code, zone_name, source) VALUES
  (984, '23796-000-000', 'See FLU', 'See FLU(SPR)', 'gis.baycountyfl.gov Land_Use_Planning MapServer point lookup (live fetch, shard9_run6253 pass2)'),
  (984, '23824-000-000', 'See FLU', 'See FLU(SPR)', 'gis.baycountyfl.gov Land_Use_Planning MapServer point lookup (live fetch, shard9_run6253 pass2)'),
  (984, '15026-010-000', 'See FLU', 'See FLU(SPR)', 'gis.baycountyfl.gov Land_Use_Planning MapServer point lookup (live fetch, shard9_run6253 pass2)'),
  (984, '24180-001-000', 'See FLU', 'See FLU(SPR)', 'gis.baycountyfl.gov Land_Use_Planning MapServer point lookup (live fetch, shard9_run6253 pass2)')
ON CONFLICT DO NOTHING;

-- ULTRALOOP audit rows for the CERTIFY GATE (C/D/I/J survival votes, dispatch 0c4df455-e5d2-4d65-9237-0d35132b0e53).
-- See gold_standard_ultraloop_audit ids 9582-9585 for the full claim text (already inserted live).
