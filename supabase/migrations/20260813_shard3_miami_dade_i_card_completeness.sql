-- Gold Standard shard-3, dispatch 59758c8a-8d8d-48f7-843d-5e2c6844fbf9, county miami_dade, letter I
-- BEFORE: I card_complete=485/511 (94.9%) FAIL (need >=95.1%)
-- AFTER:  I card_complete=492/511 (96.3%) PASS
--
-- Root cause: 7 auction rows had real property_address + assessed_value + parcel_id
-- (already sourced from prior scraping) but were missing latitude/longitude AND had
-- no matching row in parcel_zones (required for the I "card complete" join via
-- v_zoning_gold_standard_card, since gold_standard.county is stored as 'miami dade'
-- with a space, not 'miami_dade').
--
-- Fix, in two real-sourced steps:
--   1. Forward-geocoded the 7 existing property_address values via the free US
--      Census Geocoder (geocoding.geo.census.gov) to obtain real lat/lon.
--   2. Looked up each folio's authoritative zoning via Miami-Dade County's public
--      ArcGIS REST services (gisweb.miamidade.gov/arcgis/rest/services/
--      MD_LandInformation/MapServer/19 "Municipal Zoning" for incorporated
--      municipalities, /18 "County Zoning" for unincorporated county), confirmed by
--      spatial point-in-polygon query using each parcel's real X/Y from layer 24
--      "Property @ PaGis". Inserted the resulting real zone_code into parcel_zones,
--      and a matching zoning_districts row (category classification only, no
--      fabricated setback/FAR/density numbers) so the v_zoning_gold_standard_kpi_v3
--      applicability calc (used by letter G) does not regress.
--
-- Two other originally-flagged candidate rows (2026A00187 folio 01-4104-013-0290,
-- 2026A00192 folio 30-3112-023-0720) were investigated and found to be GENUINELY
-- BLOCKED: both are tiny vacant-land parcels with NO assigned street address,
-- confirmed independently via (a) Miami-Dade Property Appraiser API SiteAddress
-- field (empty) and (b) Miami-Dade GIS layer 24 TRUE_SITE_ADDR field (NULL).
-- No real address exists to fill without fabrication -- left untouched.
--
-- Letter I is scoped to case_number-exact UPDATEs only; no blanket writes.

-- Step 1: real zoning from Miami-Dade authoritative GIS (parcel_zones)
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, effective_date) VALUES
  ('24-5205-059-0800', 1053, 'PUD-1', 'Ocean Club PUD', 'miamidade_gis_municipal_zoning_layer19', CURRENT_DATE),
  ('02-3211-023-0880', 960,  'RM-3',  'Multifamily, High Intensity', 'miamidade_gis_municipal_zoning_layer19', CURRENT_DATE),
  ('31-2211-073-0040', 1055, 'MUR',   'Mixed Use Residential', 'miamidade_gis_municipal_zoning_layer19', CURRENT_DATE),
  ('23-3209-037-0280', 1660, 'RM-40', 'Medium Density Multiple Family Residential District', 'miamidade_gis_municipal_zoning_layer19', CURRENT_DATE),
  ('06-2230-059-1410', 849,  'R-6',   'Multi-Family Residential MF:750 SF', 'miamidade_gis_municipal_zoning_layer19', CURRENT_DATE),
  ('30-1231-083-0150', 626,  'RU-4L', 'Limited Apartment House District, 23 units/net acre', 'miamidade_gis_county_zoning_layer18', CURRENT_DATE),
  ('30-1231-018-1060', 626,  'RU-4M', 'Modified Apartment House District, 35.9 units/net acre', 'miamidade_gis_county_zoning_layer18', CURRENT_DATE)
ON CONFLICT DO NOTHING;

-- Step 2: zoning_districts category rows so G (FAR/density/parking applicability)
-- does not regress -- only inserted where a (jurisdiction_id, code) row didn't
-- already exist (RU-4L, RU-4M, RM-3, R-6, MUR were already present).
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description) VALUES
  (1053, 'PUD-1', 'Ocean Club PUD', 'residential', 'Planned Unit Development, residential multi-family (RMF land use), Key Biscayne'),
  (1660, 'RM-40', 'Medium Density Multiple Family Residential District', 'residential', 'North Bay Village medium density multi-family residential')
ON CONFLICT DO NOTHING;

-- Step 3: real Census-geocoded lat/lon, scoped by exact case_number
UPDATE multi_county_auctions SET latitude=25.686911461815, longitude=-80.163189186766
  WHERE lower(county)='miami_dade' AND case_number='2025-016565-CA-01';
UPDATE multi_county_auctions SET latitude=25.83633030962,  longitude=-80.120815392473
  WHERE lower(county)='miami_dade' AND case_number='2025-016017-CA-01';
UPDATE multi_county_auctions SET latitude=25.942772532697, longitude=-80.121150993731
  WHERE lower(county)='miami_dade' AND case_number='2025-013100-CA-01';
UPDATE multi_county_auctions SET latitude=25.844678512169, longitude=-80.146696567688
  WHERE lower(county)='miami_dade' AND case_number='2025-021836-CA-01';
UPDATE multi_county_auctions SET latitude=25.884633246839, longitude=-80.194327168743
  WHERE lower(county)='miami_dade' AND case_number='2025-021988-CA-01';
UPDATE multi_county_auctions SET latitude=25.958778665268, longitude=-80.183520769775
  WHERE lower(county)='miami_dade' AND case_number='2025-009898-CA-01';
UPDATE multi_county_auctions SET latitude=25.961821998337, longitude=-80.181831201298
  WHERE lower(county)='miami_dade' AND case_number='2025-017868-CA-01';

-- Verification (run live, not part of migration):
--   SELECT * FROM pencil_dod_evaluate_county('miami_dade');
--   BEFORE: I {"pass": false, "detail": "card_complete=485 of 511", "metric": 94.9}
--   AFTER:  I {"pass": true,  "detail": "card_complete=492 of 511", "metric": 96.3}
--   G unaffected by regression: {"pass": true, "detail": "density=99.3 far=100.0 pk1000=100.0", "metric": 99.3}
