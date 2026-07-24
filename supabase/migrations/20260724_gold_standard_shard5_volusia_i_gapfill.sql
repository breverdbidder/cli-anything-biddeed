-- Gold Standard shard-5 (volusia) dispatch ee5042ee, letter I gapfill.
--
-- BASELINE (VERIFIED live 2026-07-24 via pencil_dod_evaluate_county('volusia')):
--   I: card_complete=357 of 378 (94.4%), FAIL (threshold 95%). auctions_total grew
--   378 (from 373 at the 20260723_gold_standard_shard10_volusia_zoning_i_fix.sql
--   baseline) while the zoned-parcel pool stayed at 357 -- 21 auctions never got a
--   parcel_zones row from the prior spatial-join pass, and multi_county_auctions.
--   parcel_id for those rows was either a real parcel not yet run through the join
--   script, or upstream junk ('Property Appraiser' / 'MULTIPLE PARCELS' / 'TIMESHARE'
--   placeholder values that were never real parcel_ids -- left untouched, not
--   fabricated).
--
-- FIX: re-ran scripts/gold_standard_shard10_volusia_zoning_spatial_join.py (same
-- proven pattern: real parcel geometry -> polygon centroid -> point-in-polygon
-- against maps1.vcgov.org/arcgis/rest/services/CountywideZoning/MapServer) against
-- the 15 real (non-junk) missing parcel_ids. 4 resolved to real zone codes (2 had no
-- zoning-layer intersect, 9 had no matching parcel geometry in this GIS layer --
-- genuine data gaps, not fabricated). The 4 resolved rows also needed lat/lng: the
-- ArcGIS layer 0 query was re-run with outSR=4326 (WGS84) for the same 4 parcels to
-- get real geometry-derived centroid coordinates (assessed_value was already present
-- on all 4 rows, so only latitude/longitude were blocking letter I's geo/value gate).
--
-- Applied live via PostgREST (psql direct connection auth fails in this session's
-- environment, same as documented in prior shard sessions -- SUPABASE_DB_PASSWORD
-- does not authenticate against the pooler). This is a pure data backfill (no schema
-- change), consistent with the "simple backfills don't need `supabase db push`"
-- precedent used throughout this campaign.
--
-- RESULT (VERIFIED live via pencil_dod_evaluate_county('volusia') post-application):
--   I: card_complete 357 -> 361 of 378, 94.4% -> 95.5%, FAIL -> PASS.
--   E: unaffected (already 100%, parcel_id was already set on all 378 rows).
SET statement_timeout = 0;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, effective_date)
VALUES
  ('412402000240', 1511, 'MH-4A', 'MH (Mobile Home)', 'gold_standard_shard5_volusia_gis_spatial_join_gapfill:maps1.vcgov.org/CountywideZoning:2026-07-24', CURRENT_DATE),
  ('632001000260', 885, 'A', 'AGR (Agriculture)', 'gold_standard_shard5_volusia_gis_spatial_join_gapfill:maps1.vcgov.org/CountywideZoning:2026-07-24', CURRENT_DATE),
  ('801403070030', 1511, 'R-4', 'RES (Residential)', 'gold_standard_shard5_volusia_gis_spatial_join_gapfill:maps1.vcgov.org/CountywideZoning:2026-07-24', CURRENT_DATE),
  ('920702020110', 1511, 'OUR', 'RES (Residential) - Osteen Urban Residential', 'gold_standard_shard5_volusia_gis_spatial_join_gapfill:maps1.vcgov.org/CountywideZoning:2026-07-24', CURRENT_DATE)
ON CONFLICT DO NOTHING;

-- Real GIS-derived centroid coordinates (EPSG:4326), same source query as above,
-- outSR=4326. Not geocoded from address text -- computed from the actual parcel
-- polygon geometry returned by the county's own GIS server.
UPDATE multi_county_auctions SET latitude = 29.273394045929532, longitude = -81.1303125423095
  WHERE county = 'volusia' AND parcel_id = '412402000240' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 29.10197481941737, longitude = -81.02428594186368
  WHERE county = 'volusia' AND parcel_id = '632001000260' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.92839712292453, longitude = -81.29750213254665
  WHERE county = 'volusia' AND parcel_id = '801403070030' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.846744479283565, longitude = -81.15793312497897
  WHERE county = 'volusia' AND parcel_id = '920702020110' AND latitude IS NULL;

-- Verification (run after applying):
--   SELECT public.pencil_dod_evaluate_county('volusia');
--   Expect I.pass=true, I.metric>=95.0, I.detail='card_complete=361 of 378'.
