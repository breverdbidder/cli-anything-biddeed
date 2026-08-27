-- Gold Standard: lake county, letter I (property card completeness)
-- BEFORE (live pencil_dod_evaluate_county('lake')):
--   "I": {"pass": false, "detail": "card_complete=126 of 139", "metric": 90.6}
--
-- Task: 4 rows had real parcel_id/address/lat/lng/assessed_value but were not
-- zone-linked in v_zoning_gold_standard_card (parcel_zones.zone_code IS NULL),
-- which is what letter I's card_complete check requires. One row
-- (2024CA000927) also lacked market_value.
--
-- Research performed (all sources fetched live, URLs below):
--
-- 1. case 2024CA000927, parcel_id 052225010000001900, 6968 PERCH HAMMOCK LOOP
--    -> City Limits polygon confirms parcel centroid (28.60299, -81.84171) is
--       inside GROVELAND (jurisdictions.id=1030), not Leesburg.
--       https://gis.lakecountyfl.gov/lakegis/rest/services/OpenData/OpenData2/MapServer/3
--    -> Groveland Zoning layer returns ZoningCode="Planned Unit Develop" (PUD)
--       for that point, Acres=0.229 (matches single-family lot in Trinity
--       Lakes Phase 1 and 2 subdivision).
--       https://gis.lakecountyfl.gov/lakegis/rest/services/LocalGov/CityZoning/MapServer/3
--    -> Tax Parcels layer confirms ParcelNumber=052225010000001900,
--       TotalJustValue=436486 (matches our assessed_value exactly), and
--       provides the real market_value (FL "just value") for this parcel.
--       https://gis.lakecountyfl.gov/lakegis/rest/services/OpenData/OpenData1/FeatureServer/12
--
-- 2. case 2025CC009132, parcel_id 152226220000001700, "422 BALBOA BLVD,
--    LEESBURG, FL" (postal address only)
--    -> City Limits polygon confirms parcel centroid (28.57019, -81.70297) is
--       inside CLERMONT (jurisdictions.id=906), NOT Leesburg (835) despite
--       the postal city label in the address string. Verified via the exact
--       same centroid derived from the parcel's own polygon geometry.
--       https://gis.lakecountyfl.gov/lakegis/rest/services/OpenData/OpenData2/MapServer/3
--       https://gis.lakecountyfl.gov/lakegis/rest/services/OpenData/OpenData1/FeatureServer/12
--    -> Clermont Zoning layer returns ZoningCode="PUD PLANNED UNIT
--       DEVELOPMENT" for that point (Verde Ridge Unit 1 subdivision).
--       https://gis.lakecountyfl.gov/lakegis/rest/services/LocalGov/CityZoning/MapServer/1
--
-- 3. case 2026CA000434, parcel_id 221924085000000100, 1220 TUSKEGEE ST
--    -> Confirmed in LEESBURG (jurisdictions.id=835); Tax Parcels
--       SubdivisionName="MACEDONIA HEIGHTS, LEESBURG" and City Limits point
--       query both agree.
--    -> City of Leesburg's own zoning GIS (not Lake County's) returns an
--       EXACT ParcelNumber match: USE_ZONE="R-2", ORD_NO="00-01",
--       Status="Existing" (Jan 2000).
--       https://maps.leesburgflorida.gov/arcgis/rest/services/Planning_Zoning/P_Z_Layers/MapServer/1
--    -> Same source's Future Land Use sublayer, same exact ParcelNumber
--       match: FLU="LOW DENSITY".
--       https://maps.leesburgflorida.gov/arcgis/rest/services/Planning_Zoning/P_Z_Layers/MapServer/0
--    -> assessed_value/market_value were already populated (107621/107621),
--       no value fix needed for this row.
--
-- 4. case 2025CA002565, parcel_id 011926060000202200, 2106 HOLLYWOOD AVE
--    -> Confirmed in EUSTIS via City Limits polygon query.
--       https://gis.lakecountyfl.gov/lakegis/rest/services/OpenData/OpenData2/MapServer/3
--    -> Exhaustively searched for an Eustis zoning GIS layer: the county's
--       LocalGov/CityZoning MapServer (11 sublayers: Astatula, Clermont,
--       Fruitland Park, Groveland, Mount Dora, Tavares, Umatilla, Mascotte,
--       Minneola, Howey-in-the-Hills, Montverde) has NO Eustis entry; the
--       county's CityView/MapServer (layer group 28=EUSTIS) exposes only
--       layer 29 "Future Land Use" -- no Zoning sublayer exists there
--       either. City of Eustis Public Works' own ArcGIS org
--       (services5.arcgis.com/ANBLBO8KBjcOreMN) hosts "FLU" and "Design
--       District" feature services but no parcel zoning layer. No public
--       Eustis zoning GIS endpoint could be found.
--       https://gis.lakecountyfl.gov/lakegis/rest/services/CityView/MapServer
--       https://gis.lakecountyfl.gov/lakegis/rest/services/LocalGov/CityFLU/MapServer/2 (FLU="SR" only, not a zone_code)
--    -> STATUS: NO_FIX_FOUND for this row. BLANK > WRONG -- no zone_code
--       fabricated. This case remains card-incomplete.
--
-- AFTER (live pencil_dod_evaluate_county('lake'), same session):
--   "I": {"pass": false, "detail": "card_complete=129 of 139", "metric": 92.8}
--   (+3 rows fixed; 1 of the original 4 rows, 2025CA002565/Eustis, could not
--   be fixed and remains unlinked -- genuinely blocked, not fabricated.)

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, future_land_use, source, created_at)
VALUES
  ('052225010000001900', 1030, 'PUD', 'Planned Unit Development', NULL, 'lake_county_gis_arcgis', now()),
  ('152226220000001700', 906, 'PUD', 'PUD Planned Unit Development', NULL, 'lake_county_gis_arcgis', now()),
  ('221924085000000100', 835, 'R-2', NULL, 'LOW DENSITY', 'leesburg_fl_gis_arcgis', now());

UPDATE multi_county_auctions
SET market_value = 436486
WHERE case_number = '2024CA000927' AND lower(county) = 'lake';
