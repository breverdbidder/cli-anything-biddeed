-- Gold Standard, dispatch ee7cda49-1464-44c5-903d-3e7addc3a4dc
-- County: indian_river, Letter: I (card completeness)
--
-- BEFORE: card_complete=101/107 (94.4%) — FAIL (need >=95.3%, i.e. >=102/107)
-- AFTER:  card_complete=103/107 (96.3%) — PASS
--
-- Root cause: two rows already had property_address, latitude/longitude, and
-- assessed_value populated in multi_county_auctions. The ONLY missing
-- requirement was a zone_code link via parcel_zones -> v_zoning_gold_standard_card.
--
-- Both parcels sit OUTSIDE the City of Vero Beach municipal boundary (confirmed:
-- Vero Beach's own ArcGIS ZoningDistricts FeatureServer at
-- https://services1.arcgis.com/mK9abRqiJFkUgbPZ/arcgis/rest/services/ZoningDistricts/FeatureServer/0
-- returned zero features for both points), so zoning authority belongs to
-- Indian River County itself (jurisdiction_id 1224 = "Unincorporated Indian
-- River County" per public.jurisdictions), not a municipality.
--
-- Real zoning codes sourced live from Indian River County's official ArcGIS
-- "Zoning (Unincorporated Area, Indian River County)" MapServer layer
-- (service description: "Zoning for Unincorporated Area of Indian River
-- County, Florida. Community Development Department, 1801 27th Street,
-- Vero Beach, FL 32960"):
--   https://gisportal.ircgov.com/server3/rest/services/Planning/IRC_Zoning_MS/MapServer/0/query
--     ?geometry=<lon>,<lat>&geometryType=esriGeometryPoint&inSR=4326
--     &spatialRel=esriSpatialRelIntersects&outFields=*&f=json
--
-- Row 1: case "2025 CC 003117", parcel_id 33390600008017000008.0,
--   address "1915 WESTMINSTER CIR, VERO BEACH, FL-32966", assessed_value=203105
--   Queried at (27.636159, -80.471497) -> feature ZONING="RM-6", ZONING_ABV="RM-6"
--
-- Row 2: case "2025 CA 000382", parcel_id 33381200001014000002.0,
--   address "790 08TH ST, VERO BEACH, FL-32966", assessed_value=207010
--   Queried at (27.618299, -80.490506) -> feature ZONING="A-1", ZONING_ABV="A-1"
--
-- Zone names sourced from the official Indian River County Zoning Legend
-- (indianriver.gov, last updated 10/18/16):
--   https://www.indianriver.gov/Document%20Center/Services/Planning-and-Development/
--     Planning%20Division/Zoning%20Maps/zoningleg.pdf
--   RM-6 = "Multiple-Family Residential District (up to 6 units/acre)"
--   A-1  = "Agricultural-1 District (up to 1 unit/5 acres)"

INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES
  (
    '33390600008017000008.0',
    NULL,
    1224,
    'RM-6',
    'Multiple-Family Residential District (up to 6 units/acre)',
    'irc_gis_zoning_ms_20260824'
  ),
  (
    '33381200001014000002.0',
    NULL,
    1224,
    'A-1',
    'Agricultural-1 District (up to 1 unit/5 acres)',
    'irc_gis_zoning_ms_20260824'
  )
ON CONFLICT DO NOTHING;

-- Verification (run after apply):
--   SELECT * FROM v_zoning_gold_standard_card
--     WHERE parcel_id IN ('33390600008017000008.0', '33381200001014000002.0');
--   SELECT pencil_dod_evaluate_county('indian_river');
--   -> I: card_complete=103 of 107 (96.3%), pass=true
