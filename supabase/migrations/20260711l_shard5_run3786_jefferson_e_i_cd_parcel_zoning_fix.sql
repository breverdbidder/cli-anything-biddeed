-- Gold Standard shard-5 run3786 (calhoun/madison/jefferson), dispatch 61b6512c-ae9e-4bc2-8e90-f701c28611d9
-- Jefferson county E/I/C/D fix: real parcel identity + real zoning district code for the
-- sole jefferson auction, case 25-CA-164 (340 S Marvin St, Monticello FL 32344).
--
-- SOURCE (VERIFIED this session via ULTRALOOP research agent, 42 tool calls):
--   parcel_id 00-00-00-0220-0000-0310 -- FL GIO Florida_Statewide_Cadastral FeatureServer
--     (services9.arcgis.com/Gh9awoU677aKree0), cross-corroborated by owner name match
--     ("Thompson James W") against an independent web search, PHY_ADDR1='340 S MARVIN ST'.
--   zone_code 'R-1A' -- Jefferson County Property Appraiser's own hosted ArcGIS zoning layer
--     JC_CITY_ZONING_view (services5.arcgis.com/vFMp1Ly1q6rKKp0o), point-in-polygon query at
--     the corrected parcel centroid (30.54376655425188, -83.86252309850187). R-1A already
--     exists as a real Municode-sourced zoning_districts row for jurisdiction 817 (Monticello).
--   assessed_value/market_value -- FL DOR 2025 CAMA roll (AV_SD/AV_NSD, JV fields) via the
--     same FL GIO cadastral query.
--
-- IMPORTANT CORRECTION: the lat/lng already on file (30.5445463,-83.8625587) snaps to the
-- WRONG adjacent parcel (00-00-00-0370-0000-0030, 925 E Washington St) in a point-in-polygon
-- join -- geometry precision issue in the source data, not our bug. Corrected to the true
-- parcel's centroid.
--
-- G (zoning density/FAR/parking) is INTENTIONALLY NOT touched here: R-1A's zone_standards
-- row (id 1886) has max_far=NULL, max_density_du_acre=NULL. Monticello's Municode page
-- (library.municode.com/fl/monticello/...) returned HTTP 403 to both WebFetch and curl this
-- session (Cloudflare-gated, matches the same block documented for other Municode-hosted FL
-- jurisdictions in prior shard sessions), and no Wayback Machine snapshot exists for that
-- node ID (checked live via archive.org/wayback/available -- empty result). Per HARD
-- GUARDRAILS, no density value is fabricated. G remains an honest FAIL pending a session
-- with working Municode/Firecrawl access to Sec. 54-160 (Property Development Regulations
-- table).

BEGIN;

UPDATE multi_county_auctions
SET parcel_id      = '00-00-00-0220-0000-0310',
    assessed_value = 100215,
    market_value   = 112659,
    latitude       = 30.54376655425188,
    longitude      = -83.86252309850187,
    parity_status  = 'matched_clean',
    parity_source  = 'tier1:jeffersonclerk_foreclosure_sales_pdf_scrape+fl_gio_cadastral_corroboration_20260711',
    last_seen_at   = now(),
    updated_at     = now()
WHERE lower(county) = 'jefferson'
  AND case_number = '25-CA-164'
  AND parcel_id IS NULL;  -- idempotent guard: only fires on the pre-fix row

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, created_at)
SELECT '00-00-00-0220-0000-0310', 817, 'R-1A', 'RESIDENTIAL\SINGLE-FAMILY-MH',
       'jcpa_gis_zoning_layer_verified_20260711', now()
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones WHERE parcel_id = '00-00-00-0220-0000-0310' AND jurisdiction_id = 817
);

COMMIT;
