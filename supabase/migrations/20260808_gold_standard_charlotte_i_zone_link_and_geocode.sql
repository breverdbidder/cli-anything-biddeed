-- GOLD STANDARD charlotte county — criterion I (property card completeness) fix.
--
-- Baseline (VERIFIED, live, 2026-08-08, pencil_dod_evaluate_county('charlotte')):
-- I FAIL 94.4% (card_complete=118 of 125). All other letters (A-H, J) passing.
--
-- ROOT CAUSE (VERIFIED, diagnosed prior to this session, list supplied not
-- re-derived): 7 gap rows split into two categories.
--
-- Category 1 — 4 rows with REAL parcel_ids and complete address/value, but
-- with zero parcel_zones linkage (v_zoning_gold_standard_card requires
-- zone_code IS NOT NULL for the parcel):
--   25001246CA  parcel 402219280010  18479 POSTON AVE, PORT CHARLOTTE
--   25001544CA  parcel 402230282006  18632 ALPHONSE CIR, PORT CHARLOTTE
--   25000550CA  parcel 402214132001  1598 NOBLE TER, PORT CHARLOTTE
--   24001455CA  parcel 412001206005  11679 CLAREMONT DR, PORT CHARLOTTE
--     (also missing latitude/longitude)
--
-- Category 2 — 3 "MULTIPLE PARCELS" multi-parcel foreclosure cases with no
-- property_address (and for one, no geo/value either):
--   25000748CA, 25001710CA, 25002081CC
--
-- FIX (Category 1, VERIFIED, applied):
-- Real zoning sourced live from Charlotte County's own ArcGIS MapServer
-- (agis.charlottecountyfl.gov/arcgis/rest/services/Essentials/
--  CCGIS_Web_Layers2022/MapServer/44, layer name "Zoning" — county-wide
-- zoning polygons, distinct from layer 43 "City of Punta Gorda Zoning").
-- Queried by point-in-polygon (parcel's existing real lat/long) — all 4
-- parcels resolve to zone RSF3.5 (Residential Single Family, 3.5 du/ac):
--   402219280010 -> OBJECTID 1074 (point 26.98212,-82.1415079)
--   402230282006 -> OBJECTID 1074 (point 26.9680407,-82.1402595)
--   402214132001 -> OBJECTID 1614 (point 27.0017342,-82.0856106)
--   412001206005 -> OBJECTID 892  (point 26.94142520636,-82.262288456827,
--                    itself sourced from US Census Bureau geocoder
--                    (geocoding.geo.census.gov, TIGER address range match
--                    "11657-11687 CLAREMONT DR, PORT CHARLOTTE, FL 33981")
--                    since this row had no prior lat/long)
--
-- jurisdiction_id used: 813. This jurisdiction row's "name" column says
-- "Punta Gorda", but it is already the established umbrella jurisdiction for
-- ALL of Charlotte County's unincorporated zoning data in this schema —
-- verified live: it already holds 10 pre-existing RSF3.5 parcel_zones rows
-- for Port Charlotte/Englewood addresses (e.g. 18438 ARAPAHOE CIR PORT
-- CHARLOTTE, 6152 BOND ST ENGLEWOOD), and zoning_districts id=12685
-- (code=RSF3.5) already has real zone_standards (id=5161) sourced from
-- library.municode.com/fl/charlotte_county/codes/code_of_ordinances
-- Sec. 3-9-33(g) (Charlotte County Code of Ordinances, county-wide RSF
-- district standards) -- NOT a Punta Gorda municipal ordinance. A separate
-- "Unincorporated Charlotte County" jurisdiction (id 1769) was created and
-- then reverted within this session after this was discovered, to avoid a
-- duplicate umbrella row and a G-metric regression (see below).
--
-- REGRESSION CAUGHT AND FIXED (VERIFIED): the first attempt inserted the 4
-- new parcel_zones rows under a brand-new jurisdiction (1769) with no
-- matching zoning_districts/zone_standards, which caused v_zoning_gold_
-- standard_kpi_v3's far/pk1000 "applicable" denominators to count these 4
-- parcels while their standards were NULL, dropping G (density/far/parking
-- coverage) from PASS 95.6% to FAIL 0%. Live-diagnosed via pg_get_viewdef,
-- reverted (jurisdiction 1769 deleted, its 4 parcel_zones rows deleted),
-- and re-inserted under jurisdiction 813 where real RSF3.5 zone_standards
-- already exist. Re-verified live: G back to PASS 95.8% (slightly above the
-- pre-fix baseline of 95.6%), I now PASS 97.6%, zero other letters affected.
--
-- FIX (Category 2, INVESTIGATED, NOT applied — reported honestly):
-- 25000748CA, 25001710CA, 25002081CC are "MULTIPLE PARCELS" foreclosure
-- cases with a real source_url (charlotte.realforeclose.com AID=1490257 /
-- 1495707 / 1507632 respectively). The RealForeclose auction-detail pages
-- require an authenticated session (plain fetch returns only the public
-- splash/login page, no case data). The Charlotte Clerk's case-search portal
-- (clerkportal.charlotteclerk.com) is behind Cloudflare's managed challenge
-- and blocks unauthenticated automated fetches (HTTP 403 / JS challenge).
-- clerkecertify.com's search form is JS/AJAX-driven and could not be
-- completed without a working browser-automation tool. Firecrawl (the
-- campaign's sanctioned scraper for exactly this class of site) returned
-- HTTP 402 "Insufficient credits" this session. browser-use CLI is not
-- installed in this sandbox. No public web search hit surfaced either case
-- number. Per campaign guardrails (PropertyOnion is litmus-only, never an
-- authoritative write source, and fabricating an address to flip a metric
-- is explicitly banned as "ghost-success"), these 3 rows were left
-- UNTOUCHED. This is reported as a tooling-access gap for this session, not
-- a proven "no address exists" structural gap — a future session with a
-- working Firecrawl balance or browser-automation tool should retry via the
-- clerk portal / RealForeclose authenticated session before concluding no
-- single controlling address exists for these multi-parcel cases.

-- 1. Real zone_code linkage via parcel_zones (jurisdiction 813; RSF3.5
--    already exists there with real zone_standards from the county
--    ordinance, id 12685/5161 — purely additive parcel_zones rows).
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, effective_date)
SELECT '402219280010', 813, 'RSF3.5', 'Residential Single Family 3.5 du/ac',
       'agis.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/44 (Zoning) OBJECTID 1074, queried by point 26.98212,-82.1415079',
       CURRENT_DATE
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '402219280010' AND jurisdiction_id = 813);

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, effective_date)
SELECT '402230282006', 813, 'RSF3.5', 'Residential Single Family 3.5 du/ac',
       'agis.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/44 (Zoning) OBJECTID 1074, queried by point 26.9680407,-82.1402595',
       CURRENT_DATE
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '402230282006' AND jurisdiction_id = 813);

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, effective_date)
SELECT '402214132001', 813, 'RSF3.5', 'Residential Single Family 3.5 du/ac',
       'agis.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/44 (Zoning) OBJECTID 1614, queried by point 27.0017342,-82.0856106',
       CURRENT_DATE
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '402214132001' AND jurisdiction_id = 813);

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, effective_date)
SELECT '412001206005', 813, 'RSF3.5', 'Residential Single Family 3.5 du/ac',
       'agis.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/44 (Zoning) OBJECTID 892, queried by point 26.94142520636,-82.262288456827 (US Census geocode)',
       CURRENT_DATE
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '412001206005' AND jurisdiction_id = 813);

-- 2. Real lat/long for the one row that had none (US Census Bureau
--    geocoder, TIGER address range match on the property's existing real
--    address).
UPDATE multi_county_auctions
SET latitude = 26.94142520636, longitude = -82.262288456827, updated_at = now()
WHERE county = 'charlotte' AND case_number = '24001455CA' AND latitude IS NULL;

-- 3. Diagnostic snapshot — leave the live confirmation in migration history.
DO $$
DECLARE
  v_after jsonb;
BEGIN
  SELECT public.pencil_dod_evaluate_county('charlotte') INTO v_after;
  RAISE NOTICE 'Charlotte I AFTER: %', v_after->'I';
  RAISE NOTICE 'Charlotte G AFTER (regression check): %', v_after->'G';
END $$;
