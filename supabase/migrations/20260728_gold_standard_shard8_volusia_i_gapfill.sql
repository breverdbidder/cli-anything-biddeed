-- Gold Standard shard-8 (volusia/union), dispatch 0f3837ab, letter I gapfill.
--
-- BASELINE (VERIFIED live 2026-07-28 via pencil_dod_evaluate_county('volusia')):
--   I: card_complete=361 of 387 (93.3%), FAIL (threshold 95%). auctions_total grew
--   387 (from 378 at the 20260724_gold_standard_shard5_volusia_i_gapfill.sql
--   baseline) while the zoned-parcel pool stayed at 361 -- same recurring pattern:
--   new auctions arrive faster than the spatial-join sweep covers them.
--
-- DIAGNOSIS: of the 26 not-yet-zoned rows, 5 carry upstream scrape-placeholder
-- parcel_ids ("Property Appraiser" x3, "TIMESHARE", "MULTIPLE PARCELS") -- not
-- real parcel numbers, left untouched (not fabricated). The remaining 21 rows
-- (20 distinct parcel_ids) are real 12-digit Volusia PINs simply missing from
-- parcel_zones.
--
-- FIX: re-ran scripts/gold_standard_shard10_volusia_zoning_spatial_join.py (same
-- proven pattern: real parcel geometry -> polygon centroid -> point-in-polygon
-- against maps1.vcgov.org/arcgis/rest/services/CountywideZoning/MapServer) against
-- the 20 real (non-junk) missing parcel_ids. 9 resolved to real zone codes with
-- real GIS-derived centroids (outSR=4326 re-query, same 9 pids). 2 had no zoning-
-- layer intersect, 9 had no matching parcel geometry in this GIS layer at all --
-- genuine data gaps (older case numbers, e.g. 03722-18, 07194-18 -- likely
-- replatted/consolidated parcels no longer in this PID format), disclosed as a
-- residual, not fabricated.
--
-- Applied live via Supabase Management API SQL endpoint (direct psql auth fails
-- in this session's environment, same as documented in prior shard sessions --
-- SUPABASE_DB_PASSWORD does not authenticate against the pooler; only :443
-- egress is open). This is a pure data backfill (no schema change), consistent
-- with the "simple backfills don't need `supabase db push`" precedent used
-- throughout this campaign.
--
-- EXPECTED RESULT: I: card_complete 361 -> 370 of 387, 93.3% -> 95.6%, FAIL -> PASS.
-- E/G: unaffected (E already 100%, parcel_id was already set on all 387 rows;
-- G already PASS at 97.3%, these 9 parcels add a small numerator/denominator
-- bump to the zoning KPI view but do not change the PASS/FAIL verdict).
SET statement_timeout = 0;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, effective_date)
VALUES
  ('631504110580', 885,  'RMH',  'RES (Residential)',        'gold_standard_shard8_volusia_gis_spatial_join_gapfill:maps1.vcgov.org/CountywideZoning:2026-07-28', CURRENT_DATE),
  ('694405000770', 1511, 'R-3',  'RES (Residential)',        'gold_standard_shard8_volusia_gis_spatial_join_gapfill:maps1.vcgov.org/CountywideZoning:2026-07-28', CURRENT_DATE),
  ('701702050180', 823,  'R-1A', 'RES (Residential)',        'gold_standard_shard8_volusia_gis_spatial_join_gapfill:maps1.vcgov.org/CountywideZoning:2026-07-28', CURRENT_DATE),
  ('702706003470', 823,  'PD',   'PUD (Planned Unit Dev)',   'gold_standard_shard8_volusia_gis_spatial_join_gapfill:maps1.vcgov.org/CountywideZoning:2026-07-28', CURRENT_DATE),
  ('791306000690', 1511, 'R-3',  'RES (Residential)',        'gold_standard_shard8_volusia_gis_spatial_join_gapfill:maps1.vcgov.org/CountywideZoning:2026-07-28', CURRENT_DATE),
  ('802209030050', 1139, 'RPUD', 'RES (Residential)',        'gold_standard_shard8_volusia_gis_spatial_join_gapfill:maps1.vcgov.org/CountywideZoning:2026-07-28', CURRENT_DATE),
  ('803431060510', 1139, 'R-4',  'RES (Residential)',        'gold_standard_shard8_volusia_gis_spatial_join_gapfill:maps1.vcgov.org/CountywideZoning:2026-07-28', CURRENT_DATE),
  ('803435050110', 1139, 'R-4',  'RES (Residential)',        'gold_standard_shard8_volusia_gis_spatial_join_gapfill:maps1.vcgov.org/CountywideZoning:2026-07-28', CURRENT_DATE),
  ('911105000360', 897,  'A',    'AGR (Agriculture)',        'gold_standard_shard8_volusia_gis_spatial_join_gapfill:maps1.vcgov.org/CountywideZoning:2026-07-28', CURRENT_DATE)
ON CONFLICT DO NOTHING;

-- Real GIS-derived centroid coordinates (EPSG:4326), same source query as above,
-- outSR=4326. Not geocoded from address text -- computed from the actual parcel
-- polygon geometry returned by the county's own GIS server.
UPDATE multi_county_auctions SET latitude = 29.119244038137413, longitude = -80.98586888650443
  WHERE county = 'volusia' AND parcel_id = '631504110580' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 29.07746515753999,  longitude = -81.34232026296655
  WHERE county = 'volusia' AND parcel_id = '694405000770' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 29.027151385934598, longitude = -81.31817501544862
  WHERE county = 'volusia' AND parcel_id = '701702050180' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.993763842105356, longitude = -81.28024033406619
  WHERE county = 'volusia' AND parcel_id = '702706003470' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 29.015946468160536, longitude = -81.3391092484019
  WHERE county = 'volusia' AND parcel_id = '791306000690' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.909647346251298, longitude = -81.29890814742488
  WHERE county = 'volusia' AND parcel_id = '802209030050' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.873078503365836, longitude = -81.30672064172198
  WHERE county = 'volusia' AND parcel_id = '803431060510' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.880182687744448, longitude = -81.28341103575221
  WHERE county = 'volusia' AND parcel_id = '803435050110' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 28.85440071407227,  longitude = -81.18611952805003
  WHERE county = 'volusia' AND parcel_id = '911105000360' AND latitude IS NULL;

-- Verification (run after applying):
--   SELECT public.pencil_dod_evaluate_county('volusia');
--   Expect I.pass=true, I.metric>=95.0, I.detail='card_complete=370 of 387'.
