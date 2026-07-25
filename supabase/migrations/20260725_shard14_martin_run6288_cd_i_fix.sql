-- Gold Standard shard-14 martin (loop run 6288, dispatch a9cb3cc1-eda1-4a56-9a53-dedf15803742).
-- C/D/I fixes -- EXECUTED live via the Supabase Management API / PostgREST during this
-- session (SUPABASE_DB_PASSWORD confirmed stale, same known issue as every prior
-- shard session this week). This migration documents the already-applied changes for
-- the repo's audit trail; it is idempotent and safe to (re)run.
--
-- BEFORE (live, session start): C FAIL 94.7 (36/38), D FAIL 94.7 (36/38),
--   I FAIL 86.8 (33/38), E FAIL 92.1 (35/38, unchanged all session -- see below).
-- AFTER (live, verified): C PASS 97.4 (37/38), D PASS 97.4 (37/38),
--   I FAIL 92.1 (35/38, structurally capped by the same 3 rows blocking E).
--
-- 1) C/D: case 25000316CAAXMX (foreclosure, auction_date 2026-07-30) had
--    parity_status/parity_source NULL -- never harvested. Live AJAX harvest against
--    martin.realforeclose.com (AUCTIONDATE=07/30/2026) confirmed the case on the
--    live calendar and promoted it to matched_clean.
--    (2024-001-TD-MARTIN, tax_deed 2026-08-15, remains mca_only -- the county's
--    realtaxdeed.com calendar returns 0 items for that date, same finding as the
--    2026-07-18 session; the sale is 3+ weeks out and likely not yet posted. Left
--    unmatched, not fabricated.)
--
-- 2) I: case 25000442CAAXMX carried a garbage parcel_id literal 'Property Appraiser'
--    (a known fleet-wide AITEM-decoder parser artifact, see
--    scripts/shard14_martin_bay_alachua_lake_cd_e_i_fix.py's is_real_parcel_id()).
--    Repaired to the real parcel_id '19-37-41-000-000-00520-7', verified via an exact
--    address/lat/lon/assessed_value match against a different martin row
--    (case 25002267CCAXMX, same physical property, already zoned B-1 in
--    v_zoning_gold_standard_card).
--
-- 3) I: case 25000316CAAXMX's parcel (55-38-41-311-000-00050-0, 659 SW Glen Crest Way,
--    Stuart FL) was missing lat/lon and had no zoning linkage. Geocoded via the free
--    US Census geocoder (real government address-point data). Point-in-polygon against
--    Martin County's own live ArcGIS zoning layer
--    (geoweb.martin.fl.us/.../Administrative_Areas/MapServer/8) returned ZONING='COR-2'.
--    Real dimensional/setback standards recovered from Martin County LDR Table 3.12.1 /
--    3.12.2 (Municode, Playwright-rendered fetch -- static WebFetch 403s this SPA).
--    far_regulated/pk1000_regulated explicitly set false (no FAR or parking-per-area
--    figure exists anywhere in COR-2's own dimensional tables -- same reasoning class
--    as the fleet's existing B-1 precedent for this same county) to avoid the
--    category-default G regression documented in a prior martin session. G reconfirmed
--    PASS 100.0 live after this insert, no regression.
--
-- Residual (unchanged, out of scope): martin E's 3 NULL-parcel-id rows
-- (23001555CCAXMX, 25001632CCAXMX, 25001634CCAXMX) remain structurally blocked by a
-- CAPTCHA on court.martinclerk.com/Home.aspx/Search, re-confirmed live this session
-- (single fresh probe) after 3 prior sessions' exhaustive 8+-method investigation
-- (Landmark Web login wall, RealForeclose 403, KBForeclosures no match, exact-string
-- web search, UniCourt 405). I is capped at 92.1% (35/38) until this clears -- the
-- only remaining path is a manual Clerk records request (RecordRequest@martinclerk.com,
-- $1/page), out of scope for automated sessions.

BEGIN;

UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard14_a9cb3cc1_run6288_ajax_harvest:foreclosure:2026-07-30',
    latitude = 27.113805390348,
    longitude = -80.26155326757,
    updated_at = NOW()
WHERE county = 'martin'
  AND case_number = '25000316CAAXMX'
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR latitude IS NULL);

UPDATE public.multi_county_auctions
SET parcel_id = '19-37-41-000-000-00520-7',
    updated_at = NOW()
WHERE county = 'martin'
  AND case_number = '25000442CAAXMX'
  AND lower(parcel_id) = 'property appraiser';

INSERT INTO public.zoning_districts
    (jurisdiction_id, code, name, category, ordinance_section,
     density_regulated, far_regulated, pk1000_regulated)
SELECT 1331, 'COR-2', 'Commercial Office/Residential District (COR-2)', 'commercial',
       'LDR Table 3.12.1 / Table 3.12.2, Div. 2 Standard Zoning Districts',
       true, false, false
WHERE NOT EXISTS (
    SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 1331 AND code = 'COR-2'
);

INSERT INTO public.zone_standards
    (zoning_district_id, max_density_du_acre, max_lot_coverage_pct, min_lot_sqft,
     max_height_ft, front_setback_ft, rear_setback_ft, side_setback_ft,
     source_url, ordinance_section)
SELECT d.id, 10.00, 40, 10000, 30, 25, 20, 10,
       'https://library.municode.com/fl/martin_county/codes/land_development_regulations_?nodeId=LADERE_ART3ZODI_DIV2STZODI',
       'Table 3.12.1 (Dimensional Standards), Table 3.12.2 (Structure Setbacks, story 1)'
FROM public.zoning_districts d
WHERE d.jurisdiction_id = 1331 AND d.code = 'COR-2'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards s WHERE s.zoning_district_id = d.id);

INSERT INTO public.parcel_zones (jurisdiction_id, parcel_id, zone_code, zone_name)
SELECT 1331, '55-38-41-311-000-00050-0', 'COR-2', 'Commercial Office/Residential District (COR-2)'
WHERE NOT EXISTS (
    SELECT 1 FROM public.parcel_zones
    WHERE jurisdiction_id = 1331 AND parcel_id = '55-38-41-311-000-00050-0' AND zone_code = 'COR-2'
);

COMMIT;
