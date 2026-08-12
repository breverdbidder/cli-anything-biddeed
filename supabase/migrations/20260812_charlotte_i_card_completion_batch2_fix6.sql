-- Gold Standard: charlotte-I card_complete fix, batch 2 (Task #6 FIX phase)
-- Prior migration (20260811_charlotte_i_card_completion_ch_I_8d4cd6c7.sql) fixed the
-- first 40 rows (max case 26-0090). This batch fixes 11 NEW tax_deed rows scraped
-- after that fix ran (cases 26-0091..26-0098, 26-0061, 26-0065, 25001313CA), none of
-- which overlap the prior migration's fixed set.
--
-- Source: live query against Charlotte County ArcGIS parcel layer, same endpoint and
-- field mapping (ACCOUNT/zoningcode/propertyaddress/assessedvalue) as the prior
-- applied migration used:
--   https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query?where=ACCOUNT='<parcel>'
-- All 11 parcel_ids returned live features; centroid of returned polygon geometry used
-- for lat/lon. Verified zero pre-existing rows in parcel_zones for all 11 parcel_ids,
-- and RSF5/MHC/RSF3.5 already have zoning_districts category rows for jurisdiction 813
-- (no G-metric side effects from this batch).
--
-- Residual structural blocker (unchanged, documented in prior migration too): 3 rows
-- (25000748CA, 25001710CA, 25002081CC) have parcel_id='MULTIPLE PARCELS' — genuinely
-- bundle multiple tax parcels per foreclosure case, cannot satisfy a single-parcel
-- zone-link join by design. Not addressed here; not fixable without a schema change to
-- support many-to-one parcel linkage, out of scope for this dispatch.
--
-- Expected result: I metric moves from 162/176 (92.0%) to 173/176 (98.3%), clearing the
-- pass threshold (>=95%, i.e. >=168/176).

BEGIN;

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, source)
VALUES
  ('412004431007', '412004431007', 813, 'MHC',    'charlotte_county_agis3_zoning_live_shard_ch_I_fix6_batch2:https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query?where=ACCOUNT=''412004431007'''),
  ('412009105005', '412009105005', 813, 'MHC',    'charlotte_county_agis3_zoning_live_shard_ch_I_fix6_batch2:https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query?where=ACCOUNT=''412009105005'''),
  ('412021130011', '412021130011', 813, 'MHC',    'charlotte_county_agis3_zoning_live_shard_ch_I_fix6_batch2:https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query?where=ACCOUNT=''412021130011'''),
  ('412022478005', '412022478005', 813, 'RSF5',   'charlotte_county_agis3_zoning_live_shard_ch_I_fix6_batch2:https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query?where=ACCOUNT=''412022478005'''),
  ('412024181005', '412024181005', 813, 'RSF5',   'charlotte_county_agis3_zoning_live_shard_ch_I_fix6_batch2:https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query?where=ACCOUNT=''412024181005'''),
  ('412024401011', '412024401011', 813, 'RSF5',   'charlotte_county_agis3_zoning_live_shard_ch_I_fix6_batch2:https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query?where=ACCOUNT=''412024401011'''),
  ('412025130017', '412025130017', 813, 'RSF5',   'charlotte_county_agis3_zoning_live_shard_ch_I_fix6_batch2:https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query?where=ACCOUNT=''412025130017'''),
  ('412025355026', '412025355026', 813, 'RSF5',   'charlotte_county_agis3_zoning_live_shard_ch_I_fix6_batch2:https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query?where=ACCOUNT=''412025355026'''),
  ('412304376011', '412304376011', 813, 'MHC',    'charlotte_county_agis3_zoning_live_shard_ch_I_fix6_batch2:https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query?where=ACCOUNT=''412304376011'''),
  ('412121434007', '412121434007', 813, 'RSF3.5', 'charlotte_county_agis3_zoning_live_shard_ch_I_fix6_batch2:https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query?where=ACCOUNT=''412121434007'''),
  ('402213280004', '402213280004', 813, 'RSF3.5', 'charlotte_county_agis3_zoning_live_shard_ch_I_fix6_batch2:https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query?where=ACCOUNT=''402213280004''')
ON CONFLICT DO NOTHING;

-- COALESCE-guarded: never overwrites existing non-null data.
UPDATE multi_county_auctions SET latitude = COALESCE(latitude, 26.937257), longitude = COALESCE(longitude, -82.306260) WHERE county='charlotte' AND case_number='26-0091';
UPDATE multi_county_auctions SET assessed_value = COALESCE(assessed_value, 90305) WHERE county='charlotte' AND case_number='26-0091';

UPDATE multi_county_auctions SET latitude = COALESCE(latitude, 26.929380), longitude = COALESCE(longitude, -82.319016) WHERE county='charlotte' AND case_number='26-0092';

UPDATE multi_county_auctions SET latitude = COALESCE(latitude, 26.899018), longitude = COALESCE(longitude, -82.314243) WHERE county='charlotte' AND case_number='26-0093';
UPDATE multi_county_auctions SET assessed_value = COALESCE(assessed_value, 72915) WHERE county='charlotte' AND case_number='26-0093';

UPDATE multi_county_auctions SET latitude = COALESCE(latitude, 26.888484), longitude = COALESCE(longitude, -82.291659) WHERE county='charlotte' AND case_number='26-0094';
UPDATE multi_county_auctions SET latitude = COALESCE(latitude, 26.895251), longitude = COALESCE(longitude, -82.264289) WHERE county='charlotte' AND case_number='26-0095';
UPDATE multi_county_auctions SET latitude = COALESCE(latitude, 26.893610), longitude = COALESCE(longitude, -82.261346) WHERE county='charlotte' AND case_number='26-0096';
UPDATE multi_county_auctions SET latitude = COALESCE(latitude, 26.883703), longitude = COALESCE(longitude, -82.264509) WHERE county='charlotte' AND case_number='26-0097';
UPDATE multi_county_auctions SET latitude = COALESCE(latitude, 26.873744), longitude = COALESCE(longitude, -82.268249) WHERE county='charlotte' AND case_number='26-0098';

UPDATE multi_county_auctions SET latitude = COALESCE(latitude, 26.932231), longitude = COALESCE(longitude, -82.017259) WHERE county='charlotte' AND case_number='26-0061';
UPDATE multi_county_auctions SET latitude = COALESCE(latitude, 26.891294), longitude = COALESCE(longitude, -82.209475) WHERE county='charlotte' AND case_number='26-0065';
UPDATE multi_county_auctions SET latitude = COALESCE(latitude, 26.997339), longitude = COALESCE(longitude, -82.060434) WHERE county='charlotte' AND case_number='25001313CA';

COMMIT;
