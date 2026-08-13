-- Gold Standard shard-3, dispatch 59758c8a-8d8d-48f7-843d-5e2c6844fbf9
-- County: indian_river, Letter: I (card completeness)
--
-- BEFORE: card_complete=100/106 (94.3%) — FAIL (need >=95%)
-- AFTER:  card_complete=101/106 (95.3%) — PASS
--
-- Root cause: case "2025 CA 000701" (parcel_id 33391000034000000001.0) already had
-- property_address, latitude/longitude, and assessed_value populated in
-- multi_county_auctions. The ONLY missing requirement was a zone_code link via
-- parcel_zones -> v_zoning_gold_standard_card. This parcel sits inside the City of
-- Vero Beach municipal boundary (confirmed via IRC's unincorporated-county zoning
-- ArcGIS layer returning ZONING=MUNI at this point, meaning zoning authority belongs
-- to the City of Vero Beach, not the county).
--
-- Real zoning code sourced live from the City of Vero Beach's official ArcGIS
-- ZoningDistricts FeatureServer, queried by spatial intersection at the auction
-- row's own lat/lon (27.6305147330895, -80.4197143106104):
--   https://services1.arcgis.com/mK9abRqiJFkUgbPZ/arcgis/rest/services/ZoningDistricts/FeatureServer/0/query
--     ?geometry=-80.4197143106104,27.6305147330895&geometryType=esriGeometryPoint
--     &inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&f=json
--   -> feature OBJECTID=15581, Code="R-1A", Description="Residential Single Family"
--
-- Also captured the companion Future Land Use code from the City's
-- ZoningFutureLandUse FeatureServer at the same point (Code="RL", "Residential Low")
-- for the future_land_use column.
--
-- jurisdiction_id 882 = "Vero Beach" (county='Indian River') per public.jurisdictions.

INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, future_land_use, source)
VALUES (
  '33391000034000000001.0',
  NULL,
  882,
  'R-1A',
  'Residential Single Family',
  'RL',
  'vero_beach_arcgis_zoningdistricts_20260813'
)
ON CONFLICT DO NOTHING;

-- Verification (run after apply):
--   SELECT * FROM v_zoning_gold_standard_card WHERE parcel_id = '33391000034000000001.0';
--   SELECT pencil_dod_evaluate_county('indian_river');
--   -> I: card_complete=101 of 106 (95.3%), pass=true
