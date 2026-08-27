-- Gold Standard shard-11 (2nd firing continuation): st_lucie letter I fix
-- zoning-substrate gap: 7 parcels had real property_address/lat/lng/assessed_value
-- in multi_county_auctions but were NOT linked to any zone_code in parcel_zones
-- (checked live against v_zoning_gold_standard_card).
--
-- BEFORE (live pencil_dod_evaluate_county('st_lucie'), 2026-08-27):
--   "I": {"pass": false, "detail": "card_complete=233 of 249", "metric": 93.6}
--
-- Evidence — all 7 parcels verified via real GIS/appraiser sources, cross-checked
-- by matching PropertyID/PARCEL_ID + exact street address + assessed value:
--
-- 1. account 59099 = 1633 SE SHEPARD LN, PORT SAINT LUCIE FL 34983
--    Source: City of Port St. Lucie RE_PARCELS_WEB FeatureServer, PropertyID=59099
--    https://services1.arcgis.com/YdUP5V6WwzeG8T8r/arcgis/rest/services/RE_PARCELS_WEB/FeatureServer/0/query?where=PropertyID=59099
--    -> ADDRESS "1633 SE SHEPARD LN", TotalAssessedValue 285800 (matches DB assessed_value 285800.0)
--    -> ZOLEGEND "RS-2", ZONING "SINGLE-FAMILY RESIDENTIAL"
--
-- 2. account 54593 = 858 SE KENDALL AVE, PORT SAINT LUCIE FL 34983
--    Source: same RE_PARCELS_WEB FeatureServer, PropertyID=54593
--    https://services1.arcgis.com/YdUP5V6WwzeG8T8r/arcgis/rest/services/RE_PARCELS_WEB/FeatureServer/0/query?where=PropertyID=54593
--    -> ADDRESS "858 SE KENDALL AVE", TotalAssessedValue 340300 (matches DB 340300.0)
--    -> ZOLEGEND "RS-2", ZONING "SINGLE-FAMILY RESIDENTIAL"
--
-- 3. account 102963 = 466 SW BELMONT CIR, PORT SAINT LUCIE FL 34953
--    Source: same RE_PARCELS_WEB FeatureServer, PropertyID=102963
--    https://services1.arcgis.com/YdUP5V6WwzeG8T8r/arcgis/rest/services/RE_PARCELS_WEB/FeatureServer/0/query?where=PropertyID=102963
--    -> ADDRESS "466 SW BELMONT CIR" (exact match to DB address)
--    -> ZOLEGEND "RS-2", ZONING "SINGLE-FAMILY RESIDENTIAL"
--
-- 4. account 73889 = 3742 SW KARIN ST, PORT SAINT LUCIE FL 34953
--    Source: same RE_PARCELS_WEB FeatureServer, PropertyID=73889
--    https://services1.arcgis.com/YdUP5V6WwzeG8T8r/arcgis/rest/services/RE_PARCELS_WEB/FeatureServer/0/query?where=PropertyID=73889
--    -> ADDRESS "3742 SW KARIN ST" (exact match to DB address)
--    -> ZOLEGEND "RS-2", ZONING "SINGLE-FAMILY RESIDENTIAL"
--
-- 5. account 113913 = 1872 SE ENFIELD AVE, PORT SAINT LUCIE FL 34952
--    Source: same RE_PARCELS_WEB FeatureServer, PropertyID=113913
--    https://services1.arcgis.com/YdUP5V6WwzeG8T8r/arcgis/rest/services/RE_PARCELS_WEB/FeatureServer/0/query?where=PropertyID=113913
--    -> ADDRESS "1872 SE ENFIELD AVE", TotalAssessedValue 327700 (matches DB 327700.0)
--    -> ZOLEGEND "RS-1", ZONING "SINGLE-FAMILY RESIDENTIAL"
--
-- 6. account 118013 = 1675 SE GREEN ACRES CIR KK102, PORT SAINT LUCIE FL 34952
--    Source: same RE_PARCELS_WEB FeatureServer, PropertyID=118013
--    https://services1.arcgis.com/YdUP5V6WwzeG8T8r/arcgis/rest/services/RE_PARCELS_WEB/FeatureServer/0/query?where=PropertyID=118013
--    -> ADDRESS "1675 SE GREEN ACRES CIR UNIT KK102", TotalAssessedValue 125100 (matches DB 125100.0)
--    -> ZOLEGEND "RM-11", ZONING "MULTIPLE FAMILY RESIDENTIAL" (multifamily condo unit, consistent with KK102 designation)
--
-- 7. account 143836 = 3307 AVENUE K, unincorporated St. Lucie County FL (zip 34947 per source; DB shows 34950)
--    NOT in Port St. Lucie (RE_PARCELS_WEB query for PropertyID=143836 returned NO MATCH,
--    confirming it is outside city limits) -> jurisdiction 1400 (unincorporated).
--    Cross-verified via TWO independent sources at the DB's exact lat/lng (27.460011, -80.35926):
--      a) St. Lucie County unincorporated Zoning MapServer (point-in-polygon hit):
--         https://slcgis.stlucieco.gov/hosting/rest/services/LandUse/Zoning/MapServer/0/query
--         -> Zoned "RS-4", Parcel_num "240570100890008",
--            WebLink https://library.municode.com/fl/st._lucie_county/codes/land_development_code?nodeId=CHIIIZODI_3.01.00ZODIUSRE_3.01.03ZODI
--      b) FL Statewide Cadastral (point-in-polygon hit, same coordinates):
--         https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query
--         -> CO_NO 66 (St. Lucie), PARCEL_ID "2405-701-0089-000-8" (same parcel number, different
--            formatting, matches Parcel_num above), PHY_ADDR1 "3307 AVENUE K", OWN_NAME "Williams April N"
--            (matches independent WebSearch result), DOR_UC "001" (single-family residential,
--            consistent with RS-4 zoning)

BEGIN;

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, future_land_use, source, created_at)
VALUES
  ('59099',  '59099',  953,  'RS-2',  'SINGLE-FAMILY RESIDENTIAL', NULL, 'st_lucie_psl_re_parcels_web_arcgis_propertyid_20260827', now()),
  ('54593',  '54593',  953,  'RS-2',  'SINGLE-FAMILY RESIDENTIAL', NULL, 'st_lucie_psl_re_parcels_web_arcgis_propertyid_20260827', now()),
  ('102963', '102963', 953,  'RS-2',  'SINGLE-FAMILY RESIDENTIAL', NULL, 'st_lucie_psl_re_parcels_web_arcgis_propertyid_20260827', now()),
  ('73889',  '73889',  953,  'RS-2',  'SINGLE-FAMILY RESIDENTIAL', NULL, 'st_lucie_psl_re_parcels_web_arcgis_propertyid_20260827', now()),
  ('113913', '113913', 953,  'RS-1',  'SINGLE-FAMILY RESIDENTIAL', NULL, 'st_lucie_psl_re_parcels_web_arcgis_propertyid_20260827', now()),
  ('118013', '118013', 953,  'RM-11', 'MULTIPLE FAMILY RESIDENTIAL', NULL, 'st_lucie_psl_re_parcels_web_arcgis_propertyid_20260827', now()),
  ('143836', '143836', 1400, 'RS-4',  'Residential, Single-Family', NULL, 'st_lucie_county_slcgis_unincorporated_zoning_plus_fl_gio_cadastral_crosscheck_20260827', now())
ON CONFLICT DO NOTHING;

COMMIT;
