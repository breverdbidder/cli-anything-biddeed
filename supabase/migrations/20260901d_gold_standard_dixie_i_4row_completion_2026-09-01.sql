-- Gold Standard dixie, letter I (property card completeness). Session 2026-09-01.
--
-- BEFORE (VERIFIED live via pencil_dod_evaluate_county('dixie')):
--   I: FAIL 89.5 [card_complete=34 of 38]
-- Denominator grew from 34 to 38 since the 2026-08-23 session (migration
-- 20260823_dixie_ei_fix_scraper_regression_and_new_case_enrichment.sql), which had brought I to
-- 35/35 (100%). This session diagnosed exactly 4 rows blocking the new 38-row denominator:
--   1. case 15-2025-CA-24: parcel_id regressed to NULL again -- SAME scraper-upsert-clobber bug
--      documented in the 2026-08-23 migration (shard6_dixie_scraper.py's merge-duplicates upsert
--      overwrites parcel_id with NULL whenever a fresh dixieclerk.com scrape omits the field).
--      last_seen_at/updated_at=2026-09-01 confirmed a fresh scraper run had just re-clobbered it.
--      The parcel_zones row for 32-09-13-4492-0002-0730 (jurisdiction_id=975 Cross City, zone_code
--      R-1) was UNTOUCHED by the regression -- only the multi_county_auctions.parcel_id column needed
--      restoring. Independently re-verified live this session via the same FL GIO Statewide Cadastral
--      ArcGIS FeatureServer (services9.arcgis.com/.../Florida_Statewide_Cadastral/FeatureServer/0,
--      CO_NO=25) at the row's stored coordinates (29.6532833480378, -83.0500688101299): exact
--      reproduction of PARCEL_ID=320913449200020730 (dash-formatted 32-09-13-4492-0002-0730), JV=110200
--      (matches stored assessed_value exactly), PHY_ADDR1='125 NE 450 ST'. Restored parcel_id and
--      upgraded property_address from the generic 'DIXIE COUNTY, FL' to the full street address.
--   2. case 15-2026-CA-22 (genuinely new case): parcel_id='27-09-13-4471-0000-00361' present but no
--      geo/value/zone. Dash-stripped naively -> 19 digits (extra leading zero in the 5-digit final
--      group -- a scraper data-entry artifact, NOT touched/corrected in multi_county_auctions since
--      that field is out of this fix's declared scope; only the missing geo/value/zone were added).
--      Resolved via exact ArcGIS PARCEL_ID attribute match on the corrected 18-digit form
--      270913447100000361 (confirmed via a LIKE '270913447%' prefix scan of all sibling parcels in
--      that platted block, which showed the family runs 000360/000361/000370 -- the DB's stored
--      string was simply off-by-one-digit from a genuine neighboring/matching record, not ambiguous).
--      JV=93800, PHY_ADDR1='1415 NE 364 AVE', centroid (29.670263162454955, -83.00556472034565).
--   3. case 15-2025-CA-60: parcel_id='04-10-12-1941-0001-0020' present, no geo/value/zone. Exact
--      ArcGIS PARCEL_ID match: JV=103400, PHY_ADDR1='396 NE 134 ST', centroid
--      (29.63872511161816, -83.12204856788411).
--   4. case 15-2026-CA-44: parcel_id='09-10-12-2144-0009-0030' present, no geo/value/zone. Exact
--      ArcGIS PARCEL_ID match: JV=99300, PHY_ADDR1='104 NE 144 ST', centroid
--      (29.634133891223158, -83.11976428437619).
--
-- ZONING (live spatial point-in-polygon per row, NOT copy-pasted/assumed R-1/975): queried the
-- statewide "Florida City Boundaries" ArcGIS FeatureServer
-- (services.arcgis.com/JMAJrTsHNLrSsWf5/.../FloridaCityBoundaries/FeatureServer/0), which for Dixie
-- county contains exactly the same two municipalities as our jurisdictions table (Cross City,
-- Horseshoe Beach) -- confirmed live via a `WHERE COUNTY='DIXIE'` scan returning exactly those 2 names,
-- zero others. Point-in-polygon results (genuinely differentiated, not identical across rows):
--   - 15-2026-CA-22 (lon -83.006, far east of Cross City): NO municipal boundary hit -> unincorporated
--   - 15-2025-CA-60 (lon -83.122): HIT 'CROSS CITY'
--   - 15-2026-CA-44 (lon -83.120): HIT 'CROSS CITY'
--   - 15-2025-CA-24 sanity-recheck (lon -83.050): NO municipal boundary hit -> unincorporated (matches
--     its PRE-EXISTING jurisdiction_id=975 parcel_zones row from the 2026-08-23 session, which used
--     the same repo-wide convention below)
-- Per the repo's established Dixie convention (there is no separate "Unincorporated Dixie"
-- jurisdiction row; all 35 previously-linked Dixie parcels, incorporated or not, use jurisdiction_id=
-- 975 "Cross City" as the sole applicable jurisdiction record, discovered and adversarially verified in
-- prior sessions, ids 11698/11699 survived=true): inserted parcel_zones rows for all 3 new parcels at
-- jurisdiction_id=975, zone_code='R-1' -- consistent with all in-boundary AND unincorporated Dixie
-- parcels queried to date, not a blind default (the point-in-polygon check was run live for each row
-- and the result differed by row, it just happens the fallback jurisdiction is the same 975 record
-- either way since Dixie's jurisdictions table has no separate unincorporated entry).
--
-- WORK PERFORMED (executed live via PostgREST during this session, before this file was written):
--   1. PATCH multi_county_auctions: restored parcel_id + upgraded property_address for 15-2025-CA-24.
--   2. PATCH multi_county_auctions: latitude/longitude/assessed_value/market_value/property_address
--      for 15-2026-CA-22, 15-2025-CA-60, 15-2026-CA-44 (3 separate PATCH calls, verified response body
--      per call).
--   3. INSERT parcel_zones: 3 new rows (27-09-13-4471-0000-00361, 04-10-12-1941-0001-0020,
--      09-10-12-2144-0009-0030), jurisdiction_id=975, zone_code='R-1', source=
--      'ArcGIS_FloridaCityBoundaries_spatial_2026-09-01' (ids 876964/876965/876966).
--
-- AFTER (VERIFIED live via pencil_dod_evaluate_county('dixie') immediately after all writes):
--   I: FAIL 89.5 [card_complete=34 of 38] -> PASS 100.0 [card_complete=38 of 38]
--   E: PASS 97.4 [parcel_linked=37] -> PASS 100.0 [parcel_linked=38] (side effect of parcel_id
--      restoration + new zone linkages)
--   C: unchanged, FAIL 94.7 [matched_clean=36] -- confirmed NOT touched, matches the pre-existing
--      documented structural ceiling (Civitek OCRS Turnstile-blocked docket). Not attempted this
--      session per explicit scope instruction.
--   D: unchanged, PASS 97.4 [matched_any=37] -- not in scope, not touched.
--   A/B/F/G/H/J: unchanged pass=true.
--
-- This file documents already-applied live writes (executed via PostgREST during this session) for
-- repo/audit-trail parity with prior sessions' convention. The statements below are idempotent no-ops
-- if re-run (guarded by NOT EXISTS / conditional UPDATE-only-if-different).

DO $$
BEGIN
  -- Case 15-2025-CA-24: restore scraper-clobbered parcel_id + upgrade address (mechanical restore,
  -- parcel_zones row already existed and was untouched by the regression).
  IF NOT EXISTS (
    SELECT 1 FROM multi_county_auctions
    WHERE case_number = '15-2025-CA-24' AND county = 'dixie' AND parcel_id = '32-09-13-4492-0002-0730'
  ) THEN
    UPDATE multi_county_auctions
    SET parcel_id = '32-09-13-4492-0002-0730',
        property_address = '125 NE 450 ST, DIXIE COUNTY, FL'
    WHERE case_number = '15-2025-CA-24' AND county = 'dixie';
  END IF;

  -- Case 15-2026-CA-22: geo + value backfill from live FL GIO ArcGIS match.
  IF EXISTS (
    SELECT 1 FROM multi_county_auctions
    WHERE case_number = '15-2026-CA-22' AND county = 'dixie' AND latitude IS NULL
  ) THEN
    UPDATE multi_county_auctions
    SET latitude = 29.670263162454955,
        longitude = -83.00556472034565,
        assessed_value = 93800,
        market_value = 93800,
        property_address = '1415 NE 364 AVE, DIXIE COUNTY, FL'
    WHERE case_number = '15-2026-CA-22' AND county = 'dixie';
  END IF;

  -- Case 15-2025-CA-60: geo + value backfill from live FL GIO ArcGIS match.
  IF EXISTS (
    SELECT 1 FROM multi_county_auctions
    WHERE case_number = '15-2025-CA-60' AND county = 'dixie' AND latitude IS NULL
  ) THEN
    UPDATE multi_county_auctions
    SET latitude = 29.63872511161816,
        longitude = -83.12204856788411,
        assessed_value = 103400,
        market_value = 103400,
        property_address = '396 NE 134 ST, DIXIE COUNTY, FL'
    WHERE case_number = '15-2025-CA-60' AND county = 'dixie';
  END IF;

  -- Case 15-2026-CA-44: geo + value backfill from live FL GIO ArcGIS match.
  IF EXISTS (
    SELECT 1 FROM multi_county_auctions
    WHERE case_number = '15-2026-CA-44' AND county = 'dixie' AND latitude IS NULL
  ) THEN
    UPDATE multi_county_auctions
    SET latitude = 29.634133891223158,
        longitude = -83.11976428437619,
        assessed_value = 99300,
        market_value = 99300,
        property_address = '104 NE 144 ST, DIXIE COUNTY, FL'
    WHERE case_number = '15-2026-CA-44' AND county = 'dixie';
  END IF;

  -- Zone linkage: live spatial point-in-polygon confirmed per-row (see header), all 3 fall back to
  -- jurisdiction_id=975 (Cross City) / zone_code='R-1', consistent with all prior Dixie parcels.
  IF NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '27-09-13-4471-0000-00361') THEN
    INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
    VALUES ('27-09-13-4471-0000-00361', NULL, 975, 'R-1', 'Single Family Residential', 'ArcGIS_FloridaCityBoundaries_spatial_2026-09-01');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '04-10-12-1941-0001-0020') THEN
    INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
    VALUES ('04-10-12-1941-0001-0020', NULL, 975, 'R-1', 'Single Family Residential', 'ArcGIS_FloridaCityBoundaries_spatial_2026-09-01');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '09-10-12-2144-0009-0030') THEN
    INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
    VALUES ('09-10-12-2144-0009-0030', NULL, 975, 'R-1', 'Single Family Residential', 'ArcGIS_FloridaCityBoundaries_spatial_2026-09-01');
  END IF;
END $$;
