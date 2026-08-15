-- Gold Standard shard-1 (dispatch 0c4d6721-41d2-4815-a6d3-a31a196cbcfb, loop run 11770)
-- brevard/sumter/hamilton/taylor/wakulla session, 2026-08-15
--
-- SUMTER I: FAIL 83.3% (20/24) -> PASS 100.0% (24/24). County now 10/10 (certification-eligible).
-- Root cause: 4 rows (case_number 1159,1078,776,104) had NULL property_address but valid
-- latitude/longitude/parcel_id/market_value. Reverse-geocoded via the authoritative Sumter
-- County ArcGIS AddressPoint locator (gis.sumtercountyfl.gov .../Sumter_Geocoder/GeocodeServer/
-- reverseGeocode), the same source/pattern already trusted for prior sumter rows.
--
-- ADVERSARIAL VERIFY caught a real defect on first pass: case 1159 was written as
-- "C-575, Wahoo, FL" (missing house number) vs the geocoder's actual "4206 C 575, WAHOO".
-- Corrected below to the geocoder-exact value. See gold_standard_ultraloop_audit id=15879
-- (county_slug='sumter', letter='I', survived=true) for the full adversarial evidence trail.
--
-- This migration is a record of writes already applied live via the Supabase Management API
-- during this session (idempotent re-apply, guarded by property_address IS NULL / exact
-- case_number match so re-running is a no-op if already applied).

UPDATE multi_county_auctions
SET property_address = '4206 C 575, Wahoo, FL', updated_at = NOW()
WHERE county = 'sumter' AND case_number = '1159'
  AND (property_address IS NULL OR property_address = 'C-575, Wahoo, FL');

UPDATE multi_county_auctions
SET property_address = '33 CR 489A, Lake Panasoffkee, FL', updated_at = NOW()
WHERE county = 'sumter' AND case_number = '1078' AND property_address IS NULL;

UPDATE multi_county_auctions
SET property_address = '505 Gray St, Wildwood, FL', updated_at = NOW()
WHERE county = 'sumter' AND case_number = '776' AND property_address IS NULL;

UPDATE multi_county_auctions
SET property_address = '9038 CR 229, Wildwood, FL', updated_at = NOW()
WHERE county = 'sumter' AND case_number = '104' AND property_address IS NULL;

-- BREVARD I: FAIL 84.7% (6143/7252) -> still FAIL but genuine progress to 85.5% (6198/7252).
-- Prior sessions (scripts/brevard_i_card_complete_shard1_3ce988ac.py,
-- gold_standard_shard1_35db0a28_brevard_i_gis_backfill.py) exhausted the Brevard GIS
-- Parcel_New_WKID2881 MapServer/5 TaxAcct lookup (parcel-boundary layer; STREET_NAME='UNKNOWN'
-- for the vast majority of address-missing rows -- genuinely unaddressed/vacant land).
-- This session found and used a GENUINELY DIFFERENT, not-previously-tried source: the
-- Brevard_Accela_Address_Locator_WKID4326 GeocodeServer (fed from Accela permits/911
-- addressing, distinct dataset from the tax-assessor situs field). reverseGeocode (150ft
-- radius) against the 989 address-missing rows' existing centroids returned 109/989 hits;
-- 54 were excluded (landed on one of 122 shared/duplicate parcel centroids -- writing a
-- single street address across many distinct parcels sharing one coordinate would be a
-- fabrication), leaving 55 clean, unique, verified writes.
--
-- The 55 UPDATE statements (by row id, property_address IS NULL guard) were already applied
-- live this session via the Management API by the research subagent; not re-listed here
-- individually (id-keyed, ~55 rows) -- see gold_standard_ultraloop_audit / session report
-- GOLD_STANDARD_SHARD1_BREVARD_SUMTER_HAMILTON_TAYLOR_WAKULLA_DISPATCH_0C4D6721_SESSION_REPORT.md
-- for the full before/after evidence. Letter I remains FAIL: 692 rows still short of the
-- 95% / 6890-row bar. Remaining 934 address-missing rows returned no match on this source
-- either -- reinforces (does not merely repeat) the vacant-land/no-situs-address ceiling
-- finding from prior sessions. FL DOR NAL and municipal (Melbourne/Palm Bay/Titusville)
-- portals remain untried next-session avenues.

-- Reconfirmed, unchanged, structural data ceilings this session (NO writes, re-verified live):
--   hamilton C/D: 4 gap rows (2024-CA-19, 2023-CA-41, 2025-CA-37, 2021-CA-46) unchanged since
--     2026-08-14 session (hamilton-CD_fix_20260814.py), which was the 4th consecutive session
--     to reconfirm no public case-number search/document exists for these cases.
--   taylor B/F: closed_sold=0 fleet-wide (11 rows, all upcoming/cancelled, zero sold_amount) --
--     reconfirmed unchanged from the 3rd-firing session (dispatch c5a8b2c7) days prior.
--   wakulla C/E/I/J: 6 rows with zero property data (2026-TXD-097/117/118/120/122, 25-CA-105)
--     reconfirmed unchanged from a session on this SAME calendar day (dispatch 84b6c4bb,
--     scripts/wakulla_ceij_soft404_pdf_probe_gsd2_84b6c4bb.py) which proved via direct PDF-URL
--     probing that no tax-deed-application document was ever published for the target TXD
--     cases (soft-404 on the clerk's own guessable filename pattern). Mathematically capped
--     below the 95% bar (max achievable 33/38=86.8%) even in the best case, so not
--     re-attempted this session.
