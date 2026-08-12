-- GOLD STANDARD SHARD-3, dispatch 7be9b60b-f0fa-46e5-8890-af8cb0499ce4.
-- County: okaloosa. Letters: C, D, E, I. Result: okaloosa 6/10 -> 10/10 (VERIFIED live).
--
-- Applied LIVE via PostgREST (SUPABASE_SERVICE_ROLE_KEY) during this session --
-- this file documents the exact writes for the repo history / migration trail.
-- Both fixes are real GIS/parcel-record lookups, never fabricated data.
--
-- BEFORE (this session, live pencil_dod_evaluate_county('okaloosa')):
--   C=94.4 (matched_clean=67) D=94.4 (matched_any=67) E=94.4 (parcel_linked=67)
--   I=93.0 (card_complete=66 of 71)
-- AFTER (VERIFIED live, same function, same session):
--   C=97.2 (69) D=97.2 (69) E=97.2 (69) I=95.8 (68 of 71) -- ALL PASS, 10/10.
--
-- ROOT CAUSE: 4 rows added by the daily bid4assets harvest never got GIS
-- enrichment (parcel_id/address/geo/value/zoning), pulling C/D/E/I below the
-- 95% threshold as the denominator (71) grew. Two of the four were resolved
-- this session with high-confidence real-record matches (below); the other
-- two (2024-TDD-000089, 2025-CA-002286-F -- see RESIDUAL) remain open for a
-- future session -- already below the 95% floor so not blocking this session.
--
-- SELF-CORRECTION LOGGED HONESTLY: fix 2 was FIRST applied to the wrong case
-- (2024-CA-000470) because bid4assets auction 1308924's defendant name was
-- misattributed during research. auction_url 1308924 actually belongs to
-- case 2025-CA-002286-F, not 2024-CA-000470 (confirmed by re-querying
-- multi_county_auctions.auction_url per case_number). Caught before session
-- close via a git-pull cross-check, reverted the wrong write on
-- 2024-CA-000470 (all 9 touched fields set back to NULL), and re-applied the
-- verified data to the correct case, 2025-CA-002286-F. 2024-CA-000470 has no
-- real fix this session -- it remains genuinely BLOCKED (zero identifying
-- data of any kind on file: no address, no owner/defendant name, no
-- case-specific source_url).
--
-- FIX 1: case 2025-CA-002291-C -- already had property_address
-- "3664 GRADY JOHNSON RD, CRESTVIEW, FL 32539" from the harvest. Resolved via
-- direct address match against Okaloosa County's own parcel/addressing layer:
--   https://okgis.myokaloosa.com/arcgis/rest/services/Land-Ownership/
--   Parcels_with_Addressing/MapServer/121/query?where=SITE_ADDR LIKE '3664 GRADY%'
-- Single confident feature match: PIN=18-3N-22-0000-0001-002M,
-- ASSEDVAL=45905, TOTALAPPR=48530, centroid lat=30.75319132359789
-- lon=-86.48818331917006 (vertex-mean of returned WGS84 polygon ring, same
-- convention as scripts/okaloosa_parcel_gis_enrich.py).
-- Jurisdiction resolved UNINCORPORATED via Admin-Boundaries/MapServer/99
-- (ICLPY_CITY_CODE). Zone resolved via County Zoning layer -- NOTE the
-- service's layer IDs have moved since the 2026-07-19 script was written
-- (docstring said MapServer/28; live introspection this session found
-- "County Zoning" is now MapServer id 25, field ZNGPY_ZONE) -- ZNGPY_ZONE='AA',
-- an existing code in okaloosa's zoning_districts vocabulary (jurisdiction_id
-- 1407 = Unincorporated Okaloosa County), zero new-district risk.
--
-- FIX 2: case 2025-CA-002286-F -- bid4assets.com/auction/index/1308924
-- ("Lender Asset Liquidators, LLC et al vs. Ayers, Rhonda Leigh et al",
-- county=Okaloosa -- confirmed this is the case whose auction_url column
-- matches) lists Defendant "Ayers, Rhonda Leigh et al" but the platform's own
-- Address field is literally "FL" (no street address on the source itself).
-- Queried Okaloosa's parcel/addressing layer by OWNER LIKE 'AYERS RHONDA%' ->
-- single confident match: PIN=07-1S-22-1080-0003-0120, SITE_ADDR="1008
-- BAYSHORE DR NICEVILLE FL 32578", OWNER="AYERS RHONDA L" (name match:
-- Rhonda Leigh / Rhonda L), ASSEDVAL=128796, TOTALAPPR=135540. INDEPENDENTLY
-- cross-confirmed via Niceville's own zoning GIS (gis.nicevillefl.gov/
-- server/rest/services/Zoning/MapServer/0/query, point-in-polygon at the
-- parcel centroid) which returned the IDENTICAL PIN "07-1S-22-1080-0003-0120"
-- with HOUSE_NO=1008 STREET=BAYSHORE ST_MD=DR -- exact reproduction from a
-- fully independent data source, high confidence. Jurisdiction: Niceville
-- (incorporated, per Admin-Boundaries city-limits layer), zone
-- Zoning_2015='R-1' (existing code, jurisdiction_id 948 = Niceville, source
-- pattern niceville_gis:zoning:0).
--
-- Idempotent: guarded by NOT EXISTS / re-runnable UPDATE by case_number.

SET statement_timeout = 0;

-- FIX 1: 2025-CA-002291-C
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '18-3N-22-0000-0001-002M', 1407, 'AA',
       'okaloosa_gis:planning-development/zoning:25:ZNGPY_ZONE;point_in_polygon;dispatch=7be9b60b'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones WHERE parcel_id = '18-3N-22-0000-0001-002M'
);

UPDATE public.multi_county_auctions
SET
    parcel_id = '18-3N-22-0000-0001-002M',
    assessed_value = 45905.0,
    market_value = 48530.0,
    latitude = 30.75319132359789,
    longitude = -86.48818331917006,
    assessed_value_source = 'okaloosa_gis:land-ownership/parcels_with_addressing:121:ASSEDVAL/TOTALAPPR;dispatch=7be9b60b',
    parity_status = 'matched_clean',
    parity_source = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:dispatch_7be9b60b',
    updated_at = now()
WHERE lower(county) = 'okaloosa' AND case_number = '2025-CA-002291-C';

-- FIX 2: 2025-CA-002286-F (CORRECT case for the Ayers/Niceville record --
-- NOT 2024-CA-000470, which was reverted after a same-session self-catch).
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '07-1S-22-1080-0003-0120', 948, 'R-1',
       'niceville_gis:zoning:0;point_in_polygon;dispatch=7be9b60b'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones WHERE parcel_id = '07-1S-22-1080-0003-0120'
);

UPDATE public.multi_county_auctions
SET
    property_address = '1008 BAYSHORE DR, NICEVILLE, FL 32578',
    parcel_id = '07-1S-22-1080-0003-0120',
    assessed_value = 128796.0,
    market_value = 135540.0,
    latitude = 30.50837841991998,
    longitude = -86.4798876446332,
    assessed_value_source = 'okaloosa_gis:land-ownership/parcels_with_addressing:121:owner_name_match(AYERS RHONDA L, defendant per bid4assets.com/auction/index/1308924);cross_confirmed:nicevillefl.gov/zoning:0;dispatch=7be9b60b',
    parity_status = 'matched_clean',
    parity_source = 'tier1:okaloosa_gis_arcgis_owner_name_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:dispatch_7be9b60b',
    updated_at = now()
WHERE lower(county) = 'okaloosa' AND case_number = '2025-CA-002286-F';

-- Explicit revert record for the mis-targeted write (2024-CA-000470 left
-- exactly as it was before this session -- all NULL, genuinely BLOCKED):
UPDATE public.multi_county_auctions
SET
    property_address = NULL, parcel_id = NULL, assessed_value = NULL,
    market_value = NULL, latitude = NULL, longitude = NULL,
    assessed_value_source = NULL, parity_status = NULL, parity_source = NULL,
    updated_at = now()
WHERE lower(county) = 'okaloosa' AND case_number = '2024-CA-000470'
  AND parcel_id = '07-1S-22-1080-0003-0120'; -- only reverts if the mistaken write is still present (idempotent no-op otherwise)

-- RESIDUAL (not fabricated, left for a future session -- already below the
-- 95% floor for C/D/E/I so not blocking this session's 10/10):
--   2024-CA-000470: zero identifying data of any kind (no address, no
--     owner/defendant name, no case-specific source_url beyond the generic
--     okaloosa.realforeclose.com listing page). Genuinely BLOCKED.
--   2024-TDD-000089: same situation as 2024-CA-000470 -- generic
--     realforeclose.com source_url only, nothing case-specific on file.
--
-- SQL VERIFICATION (run after applying):
-- SELECT public.pencil_dod_evaluate_county('okaloosa');
-- Expected: C/D/E >= 95 (69/71 = 97.2), I >= 95 (68/71 = 95.8), all PASS.
