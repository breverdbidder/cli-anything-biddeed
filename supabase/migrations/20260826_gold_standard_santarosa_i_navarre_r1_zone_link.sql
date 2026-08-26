-- Gold Standard shard-5 (dispatch 5f78fdfe-f751-4f2e-a9c3-88ac7640472f): santa_rosa letter I
-- (property card completeness) fix -- record of a live PostgREST write already applied
-- 2026-08-26 (this file documents it for repo audit-trail parity; psql/pooler auth was
-- unavailable this session per the standing constraint, so the INSERT below was executed via
-- PostgREST POST rather than `supabase db push` -- included here verbatim, idempotent via
-- ON CONFLICT DO NOTHING, safe to re-run).
--
-- BASELINE (confirmed live, session start): I = card_complete 114 of 121 (94.2%), FAIL.
-- Threshold >=95% (>=115/121). 7 gap rows identified, all blocked solely on one of:
-- missing parcel_id, missing address/geo, or (this fix's target) parcel_id present but not
-- joined to any public.parcel_zones row with a non-null zone_code in
-- v_zoning_gold_standard_card.
--
-- FIX: case_number=572026CA000134CAAXMX, parcel_id=01-2S-27-5710-00400-0032, address
-- "3102 HOLLEY POINT RD, NAVARRE, FL- 32566" (unincorporated Santa Rosa County -- Navarre is
-- a census-designated place, not an incorporated municipality). Real zone code sourced via a
-- live point-in-polygon query against Santa Rosa County's own zoning GIS service
-- (Community Planning, Zoning & Development Division):
--   https://cloud.santarosa.fl.gov/arcgis/rest/services/Hosted/Zoning/FeatureServer/0/query
--   at lat=30.449523, lon=-86.910656 -> district="R1", descriptio="Single Family Residential
--   District", fid=3236. "R1" already exists as a real zoning_districts row (id=11437) under
--   jurisdiction_id=1398 (Unincorporated Santa Rosa County), so this insert joins cleanly with
--   no orphan risk (unlike the companion Town of Jay "Mixed Use" attempt this same session,
--   which WAS an orphan and was reverted -- see
--   20260826_gold_standard_santarosa_g_jay_mixeduse_orphan_fix.sql for that finding).
--
-- VERIFIED (2026-08-26, adversarial verification pass): parcel_zones row id=871633 confirmed
-- live with exact parcel_id string match against multi_county_auctions.parcel_id (no
-- whitespace/case/dash drift), zone_code="R1" confirmed to join back to an existing
-- zoning_districts row for jurisdiction 1398. No duplicate rows created.
--
-- RESULT (after this fix + the Jay orphan revert in the companion migration):
--   I: PASS, card_complete=115 of 121 (95.0%) -- crosses the >=95% threshold.
--   santa_rosa now PASSES ALL 10 letters (A-J) per pencil_dod_evaluate_county, confirmed live
--   2026-08-26 (session close-out; full before/after JSON pasted in the session report).

-- parcel_zones has no unique constraint on (parcel_id, jurisdiction_id, zone_code), so this
-- guards idempotency explicitly rather than relying on ON CONFLICT.
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT
  '01-2S-27-5710-00400-0032',
  1398,
  'R1',
  'Single Family Residential District',
  'https://cloud.santarosa.fl.gov/arcgis/rest/services/Hosted/Zoning/FeatureServer/0/query point-in-polygon at 30.449523,-86.910656 -> district=R1, descriptio=Single Family Residential District, fid=3236 (Santa Rosa County Zoning FeatureServer, Community Planning Zoning & Development Division)'
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones
   WHERE parcel_id = '01-2S-27-5710-00400-0032' AND jurisdiction_id = 1398 AND zone_code = 'R1'
);
