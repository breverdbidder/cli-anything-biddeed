-- GOLD STANDARD shard-5 okaloosa (dispatch 3e3cd4b2, loop run 8310)
-- Fixes C/D/E/I. All 4 remaining criteria advance from this single migration.
--
-- Baseline (LIVE, pencil_dod_evaluate_county('okaloosa') before this run):
--   C=90.8 matched_clean=59/65  D=90.8 matched_any=59/65
--   E=92.3 parcel_linked=60/65  I=90.8 card_complete=59 of 65
--
-- Root cause: 6 rows null on parity_status; 5 rows null on parcel_id.
-- Of those, 2 (2024-CA-000470, 2024-TDD-000089) are documented stale
-- placeholder seed rows with NO property_address at all -- confirmed
-- unrecoverable across 6+ prior okaloosa sessions. Left untouched.
--
-- The other 4 are real rows, resolved live this session:
--
--   2019CA000617F: already had parcel_id (00-2S-22-0699-0000-1030), only
--     missing parity_status. Re-verified live against
--     okgis.myokaloosa.com Land-Ownership/Parcels_with_Addressing/121 --
--     single feature, SITE_ADDR "662 HARBOR BLVD UNIT 1030 DESTIN FL 32541"
--     matches the row's stored address exactly. Stamped matched_clean.
--
--   2022CA002082C (221 SOUTHVIEW DR, CRESTVIEW): single-match GIS query
--     -> PIN 05-2N-23-2323-000B-0020, TOTALAPPR=168878, ASSEDVAL=162945.
--     Zone resolved via Crestview city zoning FeatureServer (real city
--     jurisdiction match): ZONE=R-2.
--
--   2024CA001006C (4622 DOVE WAY, CRESTVIEW): single-match GIS query
--     -> PIN 24-3N-22-2460-0009-0050, TOTALAPPR=239493, ASSEDVAL=239493.
--     NOT found in Crestview's city zoning FeatureServer (0 features) --
--     despite the Crestview mailing address this parcel is outside the
--     city's zoning layer. Point-in-polygon against the county's own
--     unincorporated zoning layer (Planning-Development/Zoning/MapServer/25)
--     resolves it: ZNGPY_ZONE=AA.
--
--   2025-CA-003025-C (3413 Skymaster Ct, CRESTVIEW): single-match GIS query
--     -> PIN 11-3N-23-1000-000A-0040, TOTALAPPR=184177, ASSEDVAL=122351.
--     Crestview's FLU/zoning FeatureServer returns ZONE=COU/FLU=COU for
--     this PIN -- an ambiguous "under County jurisdiction" FLU marker, not
--     an actual zoning code. Did NOT use it. Point-in-polygon against the
--     county unincorporated zoning layer (same as above) resolves the real
--     code: ZNGPY_ZONE=R-1. Used the county value instead of the
--     ambiguous city FLU marker.
--
-- All GIS lookups were single-result matches (no guessing among multiple
-- candidates). Lat/lon are FeatureServer polygon-ring centroids in WGS84
-- (outSR=4326, queried directly -- not manually reprojected).
--
-- Expected result (verify via pencil_dod_evaluate_county after apply):
--   C: matched_clean 59+4=63/65 = 96.9%  (>=95 threshold)   PASS
--   D: matched_any   59+4=63/65 = 96.9%  (>=95 threshold)   PASS
--   E: parcel_linked 60+3=63/65 = 96.9%  (>=95 threshold)   PASS
--   I: card_complete 59+3=62/65 = 95.4%  (>=95 threshold)   PASS
--
-- Residual (documented, untouched, real-data-only):
--   2024-CA-000470, 2024-TDD-000089 -- no property_address, no parcel_id,
--   confirmed absent from source platforms across prior sessions.
--   B4A-1299799 (Mary Esther, tax_deed) -- address/geo/value present, but
--   no live GIS zoning source exists for Mary Esther (confirmed 2026-07-24,
--   not re-probed this session; not needed for I to pass with margin).
--
-- Date: 2026-08-02

SET statement_timeout = 0;

-- ── 2019CA000617F: parity_status only (parcel_id + card fields already present) ──
UPDATE multi_county_auctions
SET
    parity_status      = 'matched_clean',
    parity_source      = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:shard5_okaloosa_20260802',
    parity_confidence  = 0.85,
    parity_checked_at  = NOW(),
    updated_at         = NOW()
WHERE county = 'okaloosa'
  AND case_number = '2019CA000617F';

-- ── 2022CA002082C: parcel + geo + value + parity (Crestview city zoning R-2) ──
UPDATE multi_county_auctions
SET
    parcel_id          = '05-2N-23-2323-000B-0020',
    latitude            = 30.703738989914598,
    longitude           = -86.57510346466282,
    assessed_value      = 162945.0,
    market_value        = 168878.0,
    parity_status       = 'matched_clean',
    parity_source       = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:shard5_okaloosa_20260802',
    parity_confidence   = 0.85,
    parity_checked_at   = NOW(),
    updated_at          = NOW()
WHERE county = 'okaloosa'
  AND case_number = '2022CA002082C';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '05-2N-23-2323-000B-0020', 871, 'R-2', 'crestview_gis:zoning_and_flu_featureserver:0'
WHERE NOT EXISTS (
    SELECT 1 FROM parcel_zones WHERE parcel_id = '05-2N-23-2323-000B-0020' AND jurisdiction_id = 871
);

-- ── 2024CA001006C: parcel + geo + value + parity (county unincorp zoning AA) ──
UPDATE multi_county_auctions
SET
    parcel_id          = '24-3N-22-2460-0009-0050',
    latitude            = 30.74720875371299,
    longitude           = -86.40552072675709,
    assessed_value      = 239493.0,
    market_value        = 239493.0,
    parity_status       = 'matched_clean',
    parity_source       = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:shard5_okaloosa_20260802',
    parity_confidence   = 0.85,
    parity_checked_at   = NOW(),
    updated_at          = NOW()
WHERE county = 'okaloosa'
  AND case_number = '2024CA001006C';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '24-3N-22-2460-0009-0050', 1407, 'AA', 'okaloosa_gis:planning-development/zoning:25'
WHERE NOT EXISTS (
    SELECT 1 FROM parcel_zones WHERE parcel_id = '24-3N-22-2460-0009-0050' AND jurisdiction_id = 1407
);

-- ── 2025-CA-003025-C: parcel + geo + value + parity (county unincorp zoning R-1) ──
UPDATE multi_county_auctions
SET
    parcel_id          = '11-3N-23-1000-000A-0040',
    latitude            = 30.7684747128663,
    longitude           = -86.51124255387244,
    assessed_value      = 122351.0,
    market_value        = 184177.0,
    parity_status       = 'matched_clean',
    parity_source       = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:shard5_okaloosa_20260802',
    parity_confidence   = 0.85,
    parity_checked_at   = NOW(),
    updated_at          = NOW()
WHERE county = 'okaloosa'
  AND case_number = '2025-CA-003025-C';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '11-3N-23-1000-000A-0040', 1407, 'R-1', 'okaloosa_gis:planning-development/zoning:25'
WHERE NOT EXISTS (
    SELECT 1 FROM parcel_zones WHERE parcel_id = '11-3N-23-1000-000A-0040' AND jurisdiction_id = 1407
);

-- ── VERIFICATION COUNTS ──────────────────────────────────────────────────────
SELECT
    parity_status,
    COUNT(*) AS row_count
FROM multi_county_auctions
WHERE county = 'okaloosa'
GROUP BY parity_status
ORDER BY row_count DESC;

SELECT
    COUNT(*)                                                          AS total,
    COUNT(*) FILTER (WHERE parcel_id IS NOT NULL)                     AS has_parcel_id,
    COUNT(*) FILTER (WHERE parity_status = 'matched_clean'
                       AND parity_source LIKE 'tier1%')               AS matched_clean_tier1
FROM multi_county_auctions
WHERE county = 'okaloosa';
