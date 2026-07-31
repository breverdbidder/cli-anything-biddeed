-- Gold Standard shard-5 orange I regression fix (property card completeness), 2026-07-31.
--
-- Context (VERIFIED live via pencil_dod_evaluate_county('orange') at session start):
--   I BEFORE this migration: 92.2% (card_complete=808 of 876) -- FAIL (needs >=95%,
--   i.e. >=833/876). Orange county was previously certified 10/10 with I=95.1%
--   (791/832 rows). It REGRESSED because 44 new tax_deed auction rows were ingested
--   (832 -> 876 total) without card-completeness enrichment (geocode + zoning link).
--   This is a P0 regression per campaign rules.
--
-- I's SQL requires, per auction row (from pencil_dod_evaluate_county source):
--   property_address IS NOT NULL
--   AND COALESCE(latitude, po_latitude) IS NOT NULL
--   AND COALESCE(longitude, po_longitude) IS NOT NULL
--   AND COALESCE(assessed_value, market_value) IS NOT NULL
--   AND parcel_id resolves to a row in v_zoning_gold_standard_card (parcel_zones.zone_code
--       IS NOT NULL, joined via jurisdictions)
--
-- DIAGNOSIS (full failing set re-queried live this session, not the 24-row sample given
-- in the dispatch brief -- 62 failing rows found, joined the same way the evaluator does):
--   - 13 rows: parcel_id present but property_address/assessed_value/lat/lon ALL NULL.
--     All are "Auction Status: Redeemed" tax_deed cases (2019-19214, 2023-14339,
--     2024-16593, 2024-19467, 2024-1954, 2024-19590, 2024-19591, 2024-19597, 2024-3976,
--     2024-4596, 2024-7619, 2024-798, 2024-8888) -- RealTaxDeed's own source only ever
--     published "Redeemed / Parcel ID / Opening Bid", never a full property card, because
--     the tax certificate was paid off before the case reached a sale card. Checked their
--     parcel_ids against Orange County Property Appraiser's live GIS parcel roll
--     (ocgis4.ocfl.net/arcgis/rest/services/Public_Base/MapServer/32, has LATITUDE/
--     LONGITUDE/SITUS/TOTAL_ASSD fields) -- ZERO matches for all 13 parcel_ids (confirmed
--     via exact match AND section/township/range LIKE-prefix wildcard scan -- these
--     section/township/range tracts have no records in the appraiser roll layer at all).
--     Also checked FL DOR Statewide Cadastral FeatureServer (CO_NO=48) -- zero matches.
--     GENUINELY BLOCKED this session: no address/value/geo obtainable from any
--     authoritative free source.
--   - 33 rows: parcel_id = 'TIMESHARE' / 'MULTIPLE PARCELS' / NULL, generic county-centroid
--     placeholder lat/lon (28.5383/-81.3792) and a flat placeholder assessed_value
--     (153846.15 / 200000.0 / 33028.69, repeated across many rows). These are bulk
--     timeshare-interest foreclosure filings (Orange Lake / Westgate / Marriott Vacation
--     Club style cases) that do not correspond to a single discrete parcel. Structurally
--     unresolvable to a single GIS parcel -- GENUINELY BLOCKED, same finding as the prior
--     orange-I session (dispatch c40bb245, 2026-07-18) which hit the identical pattern.
--   - 10 rows: real parcel_id + real property_address + real assessed_value, but missing
--     lat/lon. Geocoded all 10 via the US Census Bureau public geocoder
--     (geocoding.geo.census.gov/geocoder/locations/onelineaddress, free, no key,
--     authoritative TIGER/Line source):
--       * 6 matched with a full house-number address (2024-2520, 2024-3264, 2024-3639,
--         2024-3990, 2024-4622, 2024-9753).
--       * 4 did NOT match (2024-4272 "W COLONIAL DR", 2024-4795 "PARK RIDGE GOTHA RD",
--         2024-6645 "INTERNATIONAL DR S", 2024-801 "OAK ST") -- all four are street-NAME
--         -only addresses with no house number (right-of-way / unaddressed acreage
--         tracts). Cross-checked all 4 parcel_ids against Orange County's own GIS parcel
--         roll (Public_Base/MapServer/32) and FL DOR Statewide Cadastral -- zero matches
--         in both, confirming these section/township/range tracts are not carried in
--         either standard tax-roll dataset. GENUINELY BLOCKED this session.
--   - 6 rows: real parcel_id + real address/value/lat/lon already populated, but
--     parcel_id does not resolve in parcel_zones (the actual I blocker for these rows is
--     zoning-link coverage, not missing geo/value). Spatial point-in-polygon queried each
--     row's stored (or newly-geocoded) lat/lon against the live Orange County GIS zoning
--     layer (ocgis4.ocfl.net/arcgis/rest/services/InfoMap_Public_Layers/MapServer/138,
--     "Zoning" layer, fields ZONING/ZONETYPE/JURISDICTION) -- same authoritative source
--     used successfully in the prior orange-I session (dispatch c40bb245):
--       * 012429851611403 (2024-12649): JURISDICTION=Unincorporated, ZONING="RSTD R-1"
--         -> normalizes to existing code 'R-1' (already present in zoning_districts for
--         jurisdiction_id=625, matches the "RSTD " prefix-stripping convention already
--         established by 707 pre-existing parcel_zones rows for this jurisdiction).
--       * 262327915200710 (2024-1316): JURISDICTION=Unincorporated, ZONING="P-D"
--         -> existing code 'P-D'.
--       * 052228605209010 (2024-3639, geocoded above): point-in-polygon at the exact
--         geocoded coordinate returned zero features (edge-of-polygon miss); a tight
--         ~5m envelope query around the point returned exactly ONE unambiguous polygon,
--         ZONING="R-1AA", JURISDICTION=Unincorporated.
--       * 132228613214070 (2024-3990, geocoded above): same edge-of-polygon miss at the
--         exact point; tight ~5m envelope returned exactly ONE unambiguous polygon,
--         ZONING="R-3", JURISDICTION=Unincorporated (code already exists).
--       * 252228642412010 (2024-4622, geocoded above): ~50m envelope query returned 4
--         polygon fragments, ALL with ZONING="R-1" (unambiguous), JURISDICTION=
--         Unincorporated (code already exists).
--       * 322229900420110 (2024-9753, geocoded above): ~50m envelope query returned 3
--         polygon fragments, ALL with ZONING="R-1" (unambiguous), JURISDICTION=
--         Unincorporated (code already exists).
--     zone_name is left NULL for the one net-new code (R-1AA) per the established,
--     accepted NULL-zone_name pattern in this pipeline (does not gate the I criterion,
--     which only requires zone_code IS NOT NULL).
--
--   Two additional candidate rows were investigated and are LEFT BLOCKED (not guessed):
--     - 2018-12288 (parcel_id 172329895709330) and 2024-2224 (parcel_id 042128709800060):
--       spatial query resolves to JURISDICTION=Orlando/Apopka, ZONING="CITY" -- a
--       placeholder code meaning "annexed, city-tracked", not a usable subzone from this
--       county layer (same finding as the prior session for other Orlando-annexed
--       parcels). Would require Orlando's/Apopka's own GIS, not available this session.
--     - 2023-16096 (parcel_id 162231807902030): had the generic county-centroid
--       placeholder lat/lon (28.5383/-81.3792) despite a real street address. Re-geocoded
--       "1910 PARK MANOR DR, ORLANDO, FL 32817" via US Census Bureau (matched:
--       28.570647521501, -81.225555757968) but the zoning spatial query at that point
--       returned ZERO features (data gap in the county's own zoning layer at that exact
--       location). GENUINELY BLOCKED -- left alone rather than fabricate a zone_code or
--       overwrite the current (bad) lat/lon with an unlinkable one.
--     - 2023-17380 (parcel_id 222232071234026, "14TH AVE, ORLANDO"): street-name-only
--       address, Census geocoder returned zero matches. GENUINELY BLOCKED.
--     - 272128981920000 (2024-3264, geocoded to 28.636336787088/-81.50043034297 above):
--       zoning spatial query is AMBIGUOUS at every tested buffer radius (multiple
--       candidate zone codes P-D / A-1 / IND-1/IND-5 / CITY within ~50m, single feature
--       at ~10m buffer returns ZERO). Per the NEVER-FABRICATE guardrail, no zone_code is
--       assigned for this parcel. Lat/lon IS backfilled below (real, sourced, harmless)
--       but this row remains card_complete=false pending a future session with a tighter
--       source (e.g. Orlando/Apopka municipal GIS or OCPA parcel-specific zoning field).
--
-- NET RESULT: 6 of the 62 failing rows are fully closed (real parcel_id + real
-- address/value/geo/zone, all VERIFIED from live authoritative sources, zero fabrication).
-- 808 + 6 = 814 -> 814/876 = 92.9%, still below the 95% gate. The remaining 56 rows are
-- GENUINELY BLOCKED this session (33 timeshare/multi-parcel structural, 13 redeemed-
-- with-zero-PA-record, 4 street-name-only unaddressed tracts, 2 CITY-placeholder-zone,
-- 3 zoning-layer data gaps / ambiguous-boundary, 1 zero-zoning-feature-at-point). I
-- therefore remains FAIL after this migration -- see closing report for the honest
-- before/after and the residual gap list. This migration still applies the 6 verified
-- fixes because they are correct, sourced, and net-positive, and because leaving them
-- unapplied would not change the FAIL verdict but would waste verified research.
--
-- Idempotency: parcel_zones has no unique constraint on parcel_id alone (only on
-- (tax_account, jurisdiction_id)), so every INSERT below is guarded by a NOT EXISTS
-- check against parcel_id, matching the pattern used in the prior orange-I fix script
-- (scripts/gs_shard1_c40bb245_orange_i.py). UPDATE statements to multi_county_auctions
-- are guarded by "WHERE latitude IS NULL AND longitude IS NULL" so they only ever fill
-- gaps, never overwrite existing data. No UPDATE/DELETE/DROP/TRUNCATE outside these
-- guarded, targeted statements. No cron jobs touched.

BEGIN;

-- Step 1: ensure zoning_districts has the one net-new code needed (R-1AA) for
-- jurisdiction_id=625 (Orange County Unincorporated). zoning_districts.name is NOT NULL
-- in this schema (discovered live this session -- the prior orange-I script's NULL-name
-- assumption does not hold here), so name is set to the code itself (no fabricated
-- ordinance-derived name, consistent with NEVER-FABRICATE -- 'R-1AA' is the verified
-- GIS-sourced code, reused verbatim as the display name).
INSERT INTO zoning_districts (jurisdiction_id, code, name)
SELECT 625, 'R-1AA', 'R-1AA'
WHERE NOT EXISTS (
  SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 625 AND code = 'R-1AA'
);

-- Step 2: backfill lat/lon for the 6 geocoded rows (guarded -- only fills NULLs).
-- Source: US Census Bureau public geocoder (geocoding.geo.census.gov), exact
-- onelineaddress match, fetched live this session (2026-07-31).
UPDATE multi_county_auctions
SET latitude = 28.595188687177, longitude = -81.535925521429
WHERE county = 'orange' AND parcel_id = '052228605209010'
  AND latitude IS NULL AND longitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 28.580236993707, longitude = -81.467835106398
WHERE county = 'orange' AND parcel_id = '132228613214070'
  AND latitude IS NULL AND longitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 28.54308636289, longitude = -81.461307644685
WHERE county = 'orange' AND parcel_id = '252228642412010'
  AND latitude IS NULL AND longitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 28.528465185773, longitude = -81.438376421212
WHERE county = 'orange' AND parcel_id = '322229900420110'
  AND latitude IS NULL AND longitude IS NULL;

-- These 2 also get lat/lon backfilled (real, sourced) even though their zone link is
-- blocked/ambiguous this session -- harmless, does not move I but is correct data.
UPDATE multi_county_auctions
SET latitude = 28.677618331485, longitude = -81.497806706753
WHERE county = 'orange' AND parcel_id = '102128910401091'
  AND latitude IS NULL AND longitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 28.636336787088, longitude = -81.50043034297
WHERE county = 'orange' AND parcel_id = '272128981920000'
  AND latitude IS NULL AND longitude IS NULL;

-- Step 3: insert parcel_zones rows for the 6 confirmed zone-linkage fixes, idempotent
-- (NOT EXISTS guard on parcel_id). Source: live Orange County GIS ArcGIS REST
-- (InfoMap_Public_Layers/MapServer/138, "Zoning" layer, spatial point-in-polygon /
-- tight-envelope query against each row's own lat/lon), fetched live this session
-- (2026-07-31).
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '012429851611403', 625, 'R-1',
  'orange_county_gis_InfoMap_Public_Layers_MapServer_138_Zoning (spatial point-in-polygon, JURISDICTION=Unincorporated, ZONING=RSTD R-1 normalized to R-1, shard5-orange-i-regression-fix, 2026-07-31)'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '012429851611403');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '262327915200710', 625, 'P-D',
  'orange_county_gis_InfoMap_Public_Layers_MapServer_138_Zoning (spatial point-in-polygon, JURISDICTION=Unincorporated, ZONING=P-D, shard5-orange-i-regression-fix, 2026-07-31)'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '262327915200710');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '052228605209010', 625, 'R-1AA',
  'us_census_bureau_geocoder_onelineaddress + orange_county_gis_InfoMap_Public_Layers_MapServer_138_Zoning (tight ~5m envelope point-in-polygon, JURISDICTION=Unincorporated, ZONING=R-1AA, shard5-orange-i-regression-fix, 2026-07-31)'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '052228605209010');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '132228613214070', 625, 'R-3',
  'us_census_bureau_geocoder_onelineaddress + orange_county_gis_InfoMap_Public_Layers_MapServer_138_Zoning (tight ~5m envelope point-in-polygon, JURISDICTION=Unincorporated, ZONING=R-3, shard5-orange-i-regression-fix, 2026-07-31)'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '132228613214070');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '252228642412010', 625, 'R-1',
  'us_census_bureau_geocoder_onelineaddress + orange_county_gis_InfoMap_Public_Layers_MapServer_138_Zoning (~50m envelope point-in-polygon, 4 unambiguous R-1 fragments, JURISDICTION=Unincorporated, shard5-orange-i-regression-fix, 2026-07-31)'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '252228642412010');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '322229900420110', 625, 'R-1',
  'us_census_bureau_geocoder_onelineaddress + orange_county_gis_InfoMap_Public_Layers_MapServer_138_Zoning (~50m envelope point-in-polygon, 3 unambiguous R-1 fragments, JURISDICTION=Unincorporated, shard5-orange-i-regression-fix, 2026-07-31)'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '322229900420110');

COMMIT;

-- Verification (run after apply): SELECT public.pencil_dod_evaluate_county('orange');
-- Expected I movement: card_complete 808 -> 814 of 876 (92.2% -> 92.9%). Remains FAIL
-- (needs >=95%, i.e. >=833/876) -- 19 more genuinely-sourced rows needed, none available
-- this session per the diagnosis above. No other letter (A-J) touched by this migration.
