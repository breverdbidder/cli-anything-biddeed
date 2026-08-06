-- ARCHITECT TRIAGE issue #18299 (dispatch 2216af88, okaloosa gold-standard shard-5)
-- Partial C/D/E/I fix. Does NOT cross the 95% threshold this session -- see
-- decision_log entry (session auto-triage-issue-18299-202608062220) for the
-- full accounting of why the remaining gap is genuinely blocked right now.
--
-- Baseline (LIVE, pencil_dod_evaluate_county('okaloosa') at session start):
--   C=91.3 matched_clean=63/69  D=91.3 matched_any=63/69
--   E=91.3 parcel_linked=63/69  I=89.9 card_complete=62 of 69
--
-- Root cause: denominator grew from 65 (as of the 2026-08-02 10/10 fix,
-- commit 31f38047) to 69 -- 4 new auction rows arrived since certification,
-- 2 of which are genuinely resolvable and 2 of which are bot/paywall-gated
-- (see residual note below). Plus 2 pre-existing dead rows already
-- documented unrecoverable in 31f38047 remain untouched.
--
-- Resolved live this session (2 real rows, single-match GIS queries only):
--
--   2025-CA-002558-C (808 SILVER TIP TRL, CRESTVIEW): single-match query
--     against okgis.myokaloosa.com Land-Ownership/Parcels_with_Addressing/121
--     -> PIN 35-3N-24-1001-000B-0190, ASSEDVAL=383440, TOTALAPPR=383440.
--     Zone resolved via Crestview's Zoning_and_FLU FeatureServer
--     (services9.arcgis.com/zvdDL6ILvlkPNTg8/.../Zoning_and_FLU/FeatureServer/0),
--     same PIN, single feature: ZONE=R-2.
--
--   2025-CA-002235-F (308 MIRACLE STRIP PKWY SW UNIT 35B, FORT WALTON BEACH):
--     single-match query (exact unit designation) against the same okgis
--     parcel/addressing layer -> PIN 23-2S-24-0962-0000-035B, ASSEDVAL=155000,
--     TOTALAPPR=155000. Zone resolved via Fort Walton Beach's own zoning
--     service (gis.fwb.org/arcgis/rest/services/Maps/Zoning/MapServer/0),
--     single feature: Zoning=MX-2 (Mixed-Use High) -- consistent with 8+
--     other units in the same condo complex already on file in parcel_zones.
--
-- Both points returned ZERO features from the county's own unincorporated
-- zoning layer (Planning-Development/Zoning/MapServer/25) -- correctly
-- routed to city-jurisdiction zoning instead, not guessed.
--
-- Expected result after this migration (verify via pencil_dod_evaluate_county):
--   C: matched_clean 63+2=65/69 = 94.2%  (still < 95 threshold)   FAIL (closer)
--   D: matched_any   63+2=65/69 = 94.2%  (still < 95 threshold)   FAIL (closer)
--   E: parcel_linked 63+2=65/69 = 94.2%  (still < 95 threshold)   FAIL (closer)
--   I: card_complete 62+2=64/69 = 92.8%  (still < 95 threshold)   FAIL (closer)
-- 69 rows needs 66/69 (95.65%) to cross -- 3 more resolved rows, not 2.
-- Genuinely improves the metric; does not certify. Do not report as PASS.
--
-- Residual (documented, NOT fabricated, real access blockers -- see BLOCKED
-- comment on issue #18299 for the human-action ask):
--   2026-CA-000706-C, 2026-CC-001083-C -- zero property_address on file.
--     bid4assets.com auction pages 1306148/1306146 return HTTP 403 to
--     WebFetch and HTTP 302-to-empty-body to a plain curl w/ browser UA
--     (anonymous preview gate). FIRECRAWL_API_KEY in this runner returned
--     HTTP 402 "Insufficient credits" on scrape attempt -- confirmed live,
--     not assumed. Needs either an authenticated bid4assets session or
--     topped-up Firecrawl credits (spend action) before an address can be
--     recovered at all.
--   2024-CA-000470, 2024-TDD-000089 -- pre-existing stale placeholder rows,
--     no property_address, confirmed unrecoverable across 6+ prior okaloosa
--     sessions (documented in commit 31f38047). Left untouched.
--
-- Date: 2026-08-06

SET statement_timeout = 0;

-- ── 2025-CA-002558-C: parcel + geo + value + parity (Crestview zoning R-2) ──
UPDATE multi_county_auctions
SET
    parcel_id          = '35-3N-24-1001-000B-0190',
    latitude            = 30.723049295324813,
    longitude           = -86.62540649193853,
    assessed_value      = 383440.0,
    market_value        = 383440.0,
    parity_status       = 'matched_clean',
    parity_source       = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:architect_triage_18299_20260806',
    parity_confidence   = 0.85,
    parity_checked_at   = NOW(),
    updated_at          = NOW()
WHERE county = 'okaloosa'
  AND case_number = '2025-CA-002558-C';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '35-3N-24-1001-000B-0190', 871, 'R-2', 'crestview_gis:zoning_and_flu_featureserver:0'
WHERE NOT EXISTS (
    SELECT 1 FROM parcel_zones WHERE parcel_id = '35-3N-24-1001-000B-0190' AND jurisdiction_id = 871
);

-- ── 2025-CA-002235-F: parcel + geo + value + parity (Fort Walton Beach zoning MX-2) ──
UPDATE multi_county_auctions
SET
    parcel_id          = '23-2S-24-0962-0000-035B',
    latitude            = 30.405372233771292,
    longitude           = -86.6321022117947,
    assessed_value      = 155000.0,
    market_value        = 155000.0,
    parity_status       = 'matched_clean',
    parity_source       = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:architect_triage_18299_20260806',
    parity_confidence   = 0.85,
    parity_checked_at   = NOW(),
    updated_at          = NOW()
WHERE county = 'okaloosa'
  AND case_number = '2025-CA-002235-F';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '23-2S-24-0962-0000-035B', 854, 'MX-2', 'fwb_gis:maps/zoning:0'
WHERE NOT EXISTS (
    SELECT 1 FROM parcel_zones WHERE parcel_id = '23-2S-24-0962-0000-035B' AND jurisdiction_id = 854
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
