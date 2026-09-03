-- Pencil DOD, county=indian_river, letter I (property_card_complete)
--
-- BEFORE: card_complete=108/114 (94.7%) — FAIL (need >=95%, i.e. >=109/114)
-- AFTER:  card_complete=109/114 (95.6%) — PASS
--
-- Root cause: case '2023 CA 000637', parcel_id '31391900001598000026.0',
-- address "171 SPRING VALLEY AVE, SEBASTIAN, FL 32958" already had
-- property_address, latitude/longitude (27.775327, -80.458761), and
-- assessed_value (224699) populated in multi_county_auctions. The ONLY
-- missing requirement was a zone_code link via parcel_zones ->
-- v_zoning_gold_standard_card.
--
-- This parcel sits INSIDE the City of Sebastian municipal boundary.
-- Indian River County's own unincorporated zoning MapServer layer returns
-- ZONING="MUNI" with comment "Contact the City of Sebastian for Zoning" for
-- this point, confirming the parcel is outside county zoning authority and
-- belongs to jurisdiction_id 936 ("Sebastian" per public.jurisdictions),
-- NOT 1224 (Unincorporated Indian River County).
--
-- Real zone code sourced live from the City of Sebastian's own ArcGIS
-- hosted Zoning FeatureServer (org id NkT47EHQsmn9GxB3, discovered via the
-- City's public "City of Sebastian Zoning Web Map"
-- https://www.arcgis.com/home/item.html?id=ddca4e65cef745a0a73dabdca26aeb6d):
--   https://services3.arcgis.com/NkT47EHQsmn9GxB3/arcgis/rest/services/Zoning/FeatureServer/0/query
--     ?geometry=-80.458761,27.775327&geometryType=esriGeometryPoint&inSR=4326
--     &spatialRel=esriSpatialRelIntersects&outFields=*&f=json
--
-- Query at (27.775327, -80.458761) -> feature ZONING="RS-10",
-- ZONE_NAME="Residential Single-Family 1du/10,000ft2"
-- (Municode_L field on the feature cites:
--  https://library.municode.com/fl/sebastian/codes/land_development_code?nodeId=CHIIDIGERE_ARTVZODIRE_S54-2-5.2.3SIMIREDIRS )
--
-- BLOCKED (out of scope for this dispatch, left untouched, only needed 1 row):
--   case '2026-0007TD', parcel_id '33390100052005000202.0' (Vero Beach, RM-10/12
--   zoning already present from a prior session) — still missing assessed_value
--   AND market_value. Address "1100 PONCE DE LEON CIR, VERO BEACH, FL- 32960"
--   with no unit number resolves to a large multi-unit condo complex (units
--   N102, E304, E306, #203, etc. all sold at very different prices) — could
--   not determine which unit's parcel this is without risking a wrong/fabricated
--   value. Indian River County's own Parcels_MS/Parcels2_MS ArcGIS MapServer
--   returned a point-in-polygon match (PP_PIN '33390100052005000000.0', trailing
--   digits differ from stored '...202.0') but all LAND_VALUE/BLDG_VALUE/CAMA_VALUE
--   fields were NULL in that service. ircpa.org has no public parcel API (404 on
--   probe). Not resolved — logging as BLOCKED rather than fabricating a value.
--   Cases '2025 CA 000325', '2025 CA 000731', '2025 CC 002873' all carry garbage
--   parcel_id placeholders ('MULTIPLE PARCELS' / 'Property Appraiser') from a
--   prior bad scrape and were not attempted — resolving them requires first
--   identifying the real parcel from the court docket, out of scope here.

INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES
  (
    '31391900001598000026.0',
    NULL,
    936,
    'RS-10',
    'Residential Single-Family 1du/10,000ft2',
    'sebastian_arcgis_zoning_20260903'
  )
ON CONFLICT DO NOTHING;
