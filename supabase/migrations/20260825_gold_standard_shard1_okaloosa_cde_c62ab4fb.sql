-- Gold Standard shard-1 (dispatch c62ab4fb-a4c9-4bcd-bedb-89db50b4f5f2): okaloosa
-- letters C/D/E
--
-- BEFORE (pencil_dod_evaluate_county('okaloosa'), LIVE-VERIFIED this session,
-- pre-fix):
--   C: matched_clean=76 of 83 (91.6%) -- FAIL (need >=95.2%, i.e. >=79/83)
--   D: matched_any=76 of 83 (91.6%) -- FAIL
--   E: parcel_linked=76 of 83 (91.6%) -- FAIL
--   (Denominator grew 82->83 vs. the 2026-08-24 dispatch 691cd31e session,
--   which had already moved C/D/E 72->76/82. This confirms the same root
--   cause documented across 4+ prior sessions: okaloosa-bid4assets-harvest.yml
--   adds new rows without running scripts/okaloosa_parcel_gis_enrich.py
--   afterward. The workflow-file fix remains out of reach for a CC session
--   [GH App token lacks `workflows` scope, per architect triage 18472].)
--
-- ROOT CAUSE PER UNLINKED ROW (9 rows with parcel_id IS NULL at session
-- start, live-queried against multi_county_auctions):
--
-- FIXED (1 row, real GIS-sourced parcel_id + geo + value, exact SITE_ADDR
-- match against okgis.myokaloosa.com Land-Ownership/Parcels_with_Addressing
-- MapServer/121, same pattern as scripts/okaloosa_parcel_gis_enrich.py and
-- every prior okaloosa session cited above):
--   1. 2025-CA-002563-C (FC, created 2026-08-25 -- brand new row from today's
--      bid4assets harvest cron, auction_url bid4assets.com/auction/1310902).
--      Address "408 TRITON STREET, CRESTVIEW, FL 32536" exact-matched PIN
--      12-3N-24-1501-000C-0070 (SITE_ADDR "408 TRITON ST CRESTVIEW FL 32536",
--      TOTALAPPR=ASSEDVAL=334508, owner MILLER JACOB D & LESLEY A). Row
--      already carried a geocoded lat/lon (30.776743,-86.593964) from the
--      harvest cron; live polygon-ring vertex-mean centroid from the same
--      GIS query (30.77676583862667,-86.5939220149854) matches within
--      ~0.00003 deg, confirming correct parcel. Cross-checked Crestview's own
--      Zoning_and_FLU FeatureServer for this PIN (ZONE=R-2) as a bonus
--      corroboration of address correctness -- not written to any table this
--      session (letter G/I zoning-linkage is out of this dispatch's scope).
--
-- NOT FIXED -- genuine structural/data-availability gaps, all re-confirmed
-- LIVE this session with at least one lever not previously attempted (BLANK
-- > WRONG, no value guessed):
--   - 2024-CA-000470 (FC) / 2024-TDD-000089 (TD): zero address/geo/value
--     fields since creation 2026-07-05. Both point only to
--     okaloosa.realforeclose.com / okaloosa.realtaxdeed.com, both of which
--     return HTTP 403 on direct fetch (re-confirmed this session). NEW LEVER
--     TRIED: WebSearch for both exact case numbers (no case-specific results
--     returned by either general web search or targeted clerk-site query) and
--     WebFetch against okaloosaclerk.com's search endpoint (also 403).
--     Firecrawl was the next planned lever but the account returned
--     "Insufficient credits" for this session (api.firecrawl.dev/v1/search),
--     so it could not be exercised as a workaround for the Cloudflare gate.
--     Documented dead legacy placeholder stub rows across 6+ prior sessions;
--     still dead today.
--   - 2025-CA-002286-F2 ("Lot 12, Block 3, GREY MOSS POINT"): re-confirmed
--     live this session that PIN 07-1S-22-1080-0003-0120 (LEGL1 "GREY MOSS
--     POINT S/D", LEGL2 "LOT 12 BLK 3") is the exact legal-description match
--     -- but that PIN is already assigned as the parcel_id on the case's own
--     base row 2025-CA-002286-F (whose stored property_address text, "Lot 50
--     Delaware Plantations Subdivision", does not match this PIN's real legal
--     description either). This is a pre-existing discrepancy from a prior
--     session's owner-name match (2026-08-12 dispatch 7be9b60b), not
--     introduced this session. Assigning the same PIN to F2 would create a
--     duplicate-parcel assignment across two case rows in the same suit --
--     not a real, distinct fact -- so left unfixed.
--   - 2025-CA-002286-F3 ("Condominium Unit D-311, SUMMER BREEZE"): NEW LEVER
--     TRIED this session -- WebSearch confirms "Summer Breeze" condominiums
--     are located in Miramar Beach, FL, which is in Walton County, not
--     Okaloosa County. This corroborates F5's own address text (below) that
--     the 2025-CA-002286 case bundle spans multiple counties. No Okaloosa GIS
--     match exists (re-confirmed 0 results for "SUMMER BREEZ%"/"D-311" against
--     LEGL1/LEGL2 this session) because the parcel is not in this county.
--     Correctly out of okaloosa's scope; not fabricated.
--   - 2025-CA-002286-F4 ("Lot 24 of UNRECORDED DELAWARE PLANTATION
--     SUBDIVISION PHASE TWO"): re-confirmed 0 GIS matches for "DELAWARE" in
--     LEGL1/LEGL2/LEGL3 this session -- consistent with the row's own text
--     ("unrecorded" plat would not carry an official platted legal
--     description in the county appraiser's GIS).
--   - 2025-CA-002286-F5 ("SECTION 8, TOWNSHIP 3 NORTH, RANGE 21 WEST, WALTON
--     COUNTY, FLORIDA"): row's own text explicitly names Walton County, not
--     Okaloosa -- confirmed out of this county's scope, consistent with the
--     F3 Walton-County finding above.
--   NEW LEVER TRIED for all 6 unlinked rows above: bid4assets.com/auction/
--   {1309792,1309797,1309798,1309799} (F2-F5's individual per-case listing
--   pages) via WebFetch -- 403 Forbidden (Cloudflare-gated), and Firecrawl
--   scrape blocked by exhausted account credits this session (see above).
--
-- AFTER (pencil_dod_evaluate_county('okaloosa'), LIVE-VERIFIED this session):
--   C: matched_clean=77 of 83 (92.8%) -- STILL FAIL (need >=79/83)
--   D: matched_any=77 of 83 (92.8%) -- STILL FAIL
--   E: parcel_linked=77 of 83 (92.8%) -- STILL FAIL
-- This session narrows the gap by 1 row (of the 3 needed to flip C/D/E) via
-- one genuinely new row created by today's harvest cron. The 6-row residual
-- (2 dead stubs, 4 multi-parcel-bundle rows with a cross-county/duplicate-
-- parcel conflict) is a real structural ceiling given data sources reachable
-- this session -- consistent with the extensive multi-session failure
-- history on this exact letter set (dispatches 7be9b60b, f3702b8e, shard9
-- run6080, shard2 5f3a88a5, shard4 691cd31e).
--
-- Env used: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (PostgREST REST + RPC
-- only). County scope: okaloosa ONLY. This file documents the PATCH already
-- applied via PostgREST this session; it is NOT executed via psql.

BEGIN;

-- Row 1: 2025-CA-002563-C -- parcel_id + geo + value + parity backfill
-- (Crestview, GIS exact-address match).
UPDATE multi_county_auctions
SET parcel_id = '12-3N-24-1501-000C-0070',
    latitude = 30.77676583862667,
    longitude = -86.5939220149854,
    assessed_value = 334508.0,
    market_value = 334508.0,
    parity_status = 'matched_clean',
    parity_source = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:shard1_c62ab4fb_okaloosa'
WHERE county = 'okaloosa' AND case_number = '2025-CA-002563-C';

COMMIT;
