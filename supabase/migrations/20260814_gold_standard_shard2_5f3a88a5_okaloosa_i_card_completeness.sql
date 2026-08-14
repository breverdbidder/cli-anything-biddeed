-- Gold Standard shard-2 (dispatch 5f3a88a5, loop run 11435): okaloosa letter I fix
--
-- BEFORE (pencil_dod_evaluate_county('okaloosa'), LIVE-VERIFIED this session):
--   I: card_complete=68 of 75 (90.7%) -- FAIL (needs >=95%)
--   All other letters (A,B,C,D,E,F,G,H,J) already PASS.
--
-- Diagnosis (fresh, direct query against v_zoning_gold_standard_card join logic,
-- matching pencil_dod_evaluate_county's exact SQL): 7 rows failed I's
-- address+geo+value+zoned-parcel test:
--   1. 2024-CA-000470   (foreclosure) -- no parcel_id at all. Documented dead
--      legacy placeholder stub row across 3+ prior sessions. NOT touched.
--   2. 2024-TDD-000089  (tax_deed)    -- same as above. NOT touched.
--   3. 2025-CA-003304-C (foreclosure) -- NEW row (created 2026-08-14, today).
--      Had address only, no parcel_id/geo/value. FIXED (see below).
--   4. 2024CA002521F    (foreclosure) -- had parcel_id+geo+value, missing zone
--      match. Address label says "Mary Esther" but actual coordinates
--      (30.411193,-86.728246) resolve to city_code=UNINCORPORATED via the
--      Admin-Boundaries layer, and the county zoning layer (layer 25) returns
--      exactly 1 feature (R-2) at that point. FIXED (see below).
--   5. 2025-CA-003305-F (foreclosure) -- had parcel_id+geo+value, missing zone
--      match. city_code=UNINCORPORATED, county zoning layer 25 -> zone SR
--      (1 feature). FIXED (see below).
--   6. 2025CA000724C    (foreclosure) -- had parcel_id+geo+value (address field
--      itself is a bad geocode "130 Fort Lauderdale, FL 33309" but parcel_id +
--      lat/lon are real Okaloosa coordinates), missing zone match.
--      city_code=UNINCORPORATED, county zoning layer 25 -> zone R-1
--      (1 feature). FIXED (see below).
--   7. B4A-1299799      (tax_deed)    -- Mary Esther, 37 MARY ESTHER DR.
--      Re-confirmed LIVE this session: Admin-Boundaries layer returns
--      city_code=MARY ESTHER at these exact coordinates (30.4136595651453,
--      -86.6784010179419), and the county zoning layer (25) returns 0
--      features there (point is inside Mary Esther's incorporated limits,
--      outside county unincorporated zoning coverage). No zoning GIS source
--      exists for Mary Esther (re-probed LocalGovernment/Mary_Esther_EnerGov/
--      MapServer this session and in the prior WP4 session -- no zoning
--      layer). Left UNRESOLVED, not touched (do not guess a zone_code).
--
-- Fix for row 3 (2025-CA-003304-C): exact-address match against
-- okgis.myokaloosa.com Land-Ownership/Parcels_with_Addressing/MapServer/121
-- (SITE_ADDR = '211 GRAND KEY LOOP E DESTIN FL 32541') -> PIN
-- '00-2S-22-1125-0000-0490', TOTALAPPR=ASSEDVAL=1068609, polygon-ring
-- centroid (30.386616011490542, -86.41944723332847). city_code=DESTIN via
-- Admin-Boundaries layer 99. Destin zoning (LocalGovernment/Destin_EnerGov/
-- MapServer/6, field Zone_ABBR) -> 'ROI-TD' (1 feature,
-- "Residential, Office, Institutional - Tourist Development" district).
--
-- Fixes for rows 4/5/6: parcel_zones insert only (address/geo/value already
-- present), county zoning layer (Planning-Development/Zoning/MapServer/25,
-- field ZNGPY_ZONE) queried live at each row's stored lat/lon, jurisdiction_id
-- 1407 = "Unincorporated Okaloosa County" (pre-existing jurisdictions row).
--
-- SIDE EFFECT / RESIDUAL (letter G): inserting the Destin ROI-TD parcel_zones
-- row surfaced that jurisdiction_id=923 (Destin) has NO zoning_districts row
-- for code 'ROI-TD' (Destin's other codes -- CBR, GRMU, HDR, MDR-V, TCMU,
-- DELADECO_ART* -- are populated, ROI-TD is not). This parcel is
-- FAR/density/parking-"applicable" with zero coverage, which measurably moved
-- G from 97.1% -> 94.4%/96.2%/80.0% (min 80.0%, now FAIL). Per hard guardrail
-- #4 (a value is CONFIRMED only from real ordinance/GIS primary-source text
-- with a pinpoint citation -- guessed standards = banned), no zone_standards
-- row was fabricated for ROI-TD. This is logged as a residual, not fixed in
-- this migration: closing the ROI-TD standards gap requires pulling Destin's
-- Land Development Code (Article 7) for the actual max_far/density/parking
-- figures, which is out of bounded scope for this I-focused session.
--
-- AFTER (pencil_dod_evaluate_county('okaloosa'), LIVE-VERIFIED this session):
--   I: card_complete=72 of 75 (96.0%) -- PASS (was 68/75, 90.7%, FAIL)
--   E: parcel_linked=73 of 75 (97.3%) -- incidental improvement (was 72/75,
--      96.0%) from the 2025-CA-003304-C parcel_id backfill. Still PASS either way.
--   G: min(density,far,pk1000)=80.0% -- regressed to FAIL (was 97.1% PASS).
--      See residual note above. NOT fixed in this migration.
--
-- Env used: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (REST + RPC only --
-- pooler psql confirmed still failing this session, per dispatch instructions).
-- County scope: okaloosa ONLY.

BEGIN;

-- Row 3: 2025-CA-003304-C -- parcel_id + geo + value backfill from Okaloosa
-- Property Appraiser GIS exact address match.
UPDATE multi_county_auctions
SET parcel_id = '00-2S-22-1125-0000-0490',
    latitude = 30.386616011490542,
    longitude = -86.41944723332847,
    assessed_value = 1068609.0,
    market_value = 1068609.0
WHERE county = 'okaloosa' AND case_number = '2025-CA-003304-C';

-- parcel_zones inserts (rows 3, 4, 5, 6): real primary-source GIS zoning,
-- one live point-in-polygon query per parcel this session.
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
VALUES
  ('00-2S-22-1125-0000-0490', 923,  'ROI-TD', 'okgis.myokaloosa.com:LocalGovernment/Destin_EnerGov/MapServer/6:shard2_okaloosa_5f3a88a5'),
  ('03-2S-24-1665-0000-0720', 1407, 'SR',     'okaloosa_gis:planning-development/zoning:25:shard2_okaloosa_5f3a88a5'),
  ('30-4N-22-1350-0000-0070', 1407, 'R-1',    'okaloosa_gis:planning-development/zoning:25:shard2_okaloosa_5f3a88a5'),
  ('14-2S-25-2312-0000-0080', 1407, 'R-2',    'okaloosa_gis:planning-development/zoning:25:shard2_okaloosa_5f3a88a5')
ON CONFLICT DO NOTHING;

COMMIT;
