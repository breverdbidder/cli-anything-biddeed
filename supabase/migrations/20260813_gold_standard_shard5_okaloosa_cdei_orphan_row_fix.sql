-- Gold Standard shard-5: Okaloosa County C/D/E/I orphan-row fix (dispatch 12557b2c)
--
-- Baseline (verified live 2026-08-13 via pencil_dod_evaluate_county('okaloosa')):
--   C=69/74 (93.2%) FAIL, D=69/74 (93.2%) FAIL, E=69/74 (93.2%) FAIL, I=68/74 (91.9%) FAIL
--   All four letters are dragged down by the SAME set of orphan rows
--   (parity_status IS NULL AND parcel_id IS NULL).
--
-- 5 orphan rows identified. 3 resolved below via real-source lookups. 2 left
-- as documented gaps (see closing comment at bottom of file) — BLANK > WRONG.
--
-- ============================================================================
-- ROW 1: case_number = '2025-CA-003305-F'
-- Source of truth for address confirmation: bid4assets.com landing-page-search
-- API (POST https://www.bid4assets.com/sheriffsales/landingpagesearch,
-- CourtCase=2025-CA-003305-F) -> AuctionID 1309072, Address "938 CLAEVEN CIR,,
-- FORT WALTON BEACH, FL 32547", Defendant "Capps, Chandler Blake & United
-- States Of America...". Already-correct address in DB, confirmed not corrupted.
-- Parcel match: Okaloosa GIS ArcGIS MapServer query
-- (https://okgis.myokaloosa.com/arcgis/rest/services/Land-Ownership/
-- Parcels_with_Addressing/MapServer/121/query?where=SITE_ADDR LIKE
-- '938 CLAEVEN%') -> exact 1-row match: PIN 03-2S-24-1665-0000-0720,
-- OWNER "CAPPS CHANDLER" (matches bid4assets defendant surname), SITE_ADDR
-- "938 CLAEVEN CIR FORT WALTON BEACH FL 32547", ASSEDVAL 275871.0.
-- Lat/long = centroid of the returned parcel polygon (outSR=4326).
-- ============================================================================
UPDATE multi_county_auctions
SET
  parcel_id = '03-2S-24-1665-0000-0720',
  latitude = 30.44493,
  longitude = -86.642097,
  assessed_value = 275871.0,
  parity_status = 'matched_clean',
  parity_source = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:gold_standard_shard5_12557b2c'
WHERE county = 'okaloosa' AND case_number = '2025-CA-003305-F';

-- ============================================================================
-- ROW 2: case_number = '2024CA002521F'
-- Source of truth for address confirmation: bid4assets.com landing-page-search
-- API (CourtCase=2024CA002521F) -> AuctionID 1309073, Address "1681 West
-- Highway 98, Unit 8,, MARY ESTHER, FL 32569", Defendant "MORGAN, CAYLA & ...".
-- Already-correct address in DB, confirmed not corrupted.
-- Parcel match: Okaloosa GIS ArcGIS MapServer query
-- (where=SITE_ADDR LIKE '1681%HWY 98%') -> 22 units in the "SOIGNE T/H"
-- townhome complex; disambiguated by unit number ("UNIT 8") AND owner name
-- match ("MORGAN CAYLA" matches bid4assets defendant "MORGAN, CAYLA" exactly)
-- -> PIN 14-2S-25-2312-0000-0080, SITE_ADDR "1681 W HWY 98 UNIT 8 MARY ESTHER
-- FL 32569", ASSEDVAL 112605.0. Lat/long = centroid of returned parcel polygon.
-- ============================================================================
UPDATE multi_county_auctions
SET
  parcel_id = '14-2S-25-2312-0000-0080',
  latitude = 30.411193,
  longitude = -86.728246,
  assessed_value = 112605.0,
  parity_status = 'matched_clean',
  parity_source = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:gold_standard_shard5_12557b2c'
WHERE county = 'okaloosa' AND case_number = '2024CA002521F';

-- ============================================================================
-- ROW 3: case_number = '2025CA000724C'
-- property_address was CORRUPTED in DB: "130 Fort Lauderdale, FL 33309"
-- (Fort Lauderdale is Broward County, clearly wrong).
-- Root cause confirmed at the SOURCE (not our scrape's fault): bid4assets.com
-- auction detail page https://www.bid4assets.com/auction/index/1309075
-- "Item Specifics - Parcel Information" table itself shows a truncated
-- Address field: "130<br />Fort Lauderdale, FL 33309" -- the street name was
-- never populated by the seller/bid4assets, only the leading house number
-- "130" survived, plus a stray "Fort Lauderdale, FL 33309" fragment.
-- Real address recovered via the auction detail page's Legal Description +
-- Defendant fields, which were NOT truncated: "LOT 7, SOUTHERN OAKS,
-- ACCORDING TO THE MAP OR PLAT THEREOF... PLAT BOOK 30, PAGE(S) 42 AND 43,
-- ... OKALOOSA COUNTY, FLORIDA", Defendant "BLAKE, TYRONE I, II".
-- Cross-referenced against Okaloosa GIS ArcGIS MapServer
-- (where=OWNER LIKE '%BLAKE%TYRONE%') -> exact 1-row match: PIN
-- 30-4N-22-1350-0000-0070, OWNER "BLAKE TYRONE I II" (exact defendant-name
-- match), LEGL1 "SOUTHERN OAKS" (exact legal-description match), real
-- SITE_ADDR "6012 COLTON BLAINE CT CRESTVIEW FL 32539", ASSEDVAL 210340.0.
-- property_address corrected from the corrupted value to the real GIS
-- site address. Lat/long = centroid of returned parcel polygon.
-- ============================================================================
UPDATE multi_county_auctions
SET
  property_address = '6012 COLTON BLAINE CT, CRESTVIEW, FL 32539',
  parcel_id = '30-4N-22-1350-0000-0070',
  latitude = 30.809695,
  longitude = -86.4758,
  assessed_value = 210340.0,
  parity_status = 'matched_clean',
  parity_source = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:gold_standard_shard5_12557b2c'
WHERE county = 'okaloosa' AND case_number = '2025CA000724C';

-- ============================================================================
-- DOCUMENTED GAPS (BLANK > WRONG — not fixed this session, no fabrication):
--
-- case_number = '2024-CA-000470' (foreclosure) and
-- case_number = '2024-TDD-000089' (tax_deed):
--   Both rows have property_address=NULL, data_source=NULL, created_at =
--   2026-07-05 09:12:04 -- i.e. BOTH predate the current bid4assets scraper
--   pipeline (data_source='bid4assets_scrape:SHARD3-OKALOOSA-V1'), which
--   first populated Okaloosa rows on 2026-07-19. Their case-number formats
--   (dashed "YYYY-CA-NNNNNN" / "YYYY-TDD-NNNNNN") do not match either the
--   current scraper's format (e.g. "2024CA002521F") or the current tax-deed
--   format (e.g. "B4A-1288197"), indicating they are legacy seed/stub rows
--   from an earlier pipeline iteration with no recoverable source pointer.
--   Attempted and exhausted this session:
--     1. bid4assets.com landingpagesearch API, multiple case-number format
--        variants (with/without dashes, with/without C/F suffix) -> zero
--        results for both case numbers.
--     2. Okaloosa Clerk of Court ClerkQuest case search
--        (clerkapps2.okaloosaclerk.com/clerkquest) -> search form is gated
--        by Cloudflare Turnstile; not scriptable without solving a live
--        interactive challenge.
--     3. okaloosa.realforeclose.com (the legacy foreclosure-sale platform
--        referenced by okaloosaclerk.com help docs) -> domain now redirects
--        to the generic Realauction.com vendor marketing site; service has
--        been retired/migrated to bid4assets, confirming these two cases
--        predate that migration.
--     4. floridapublicnotices.com legal-notice search (Playwright-driven,
--        JS-rendered React app) -> search input did not filter results
--        (returned generic unrelated notices from other counties); no
--        working automatable search path found in this session.
--   No UPDATE issued for these two rows. Leaving parity_status,
--   property_address, parcel_id, latitude, longitude, assessed_value NULL
--   is the honest state — fabricating any of these values is prohibited.
-- ============================================================================
