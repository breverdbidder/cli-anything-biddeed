-- martin_e_25002169_realforeclose_parcel_backfill.sql
-- Gold Standard letter E fix for county=martin.
--
-- Prior sessions (9+, see GOLD_STANDARD_SHARD5_MARTIN_18535_RUN10213_SESSION_REPORT.md
-- and scripts/shard5_32ef2b2a_martin_e_i_frondorf_fix.py) confirmed 5 of 6 gap rows are
-- either genuine structural blockers (no real-estate parcel exists) or time-blocked
-- stubs where the RealForeclose platform has not yet re-populated PCN/address for the
-- current auction cycle:
--   23001555CCAXMX -> "PERSONAL PROPERTY" lien (AID 1490119, re-verified live 2026-08-11)
--   25001634CCAXMX -> "TIMESHARE" lien (AID 1491114, re-verified live 2026-08-11)
--   25001632CCAXMX -> "TIMESHARE" lien (AID 1494243, re-verified live 2026-08-11)
--   25000102CAAXMX -> stub "Property Appraiser" link only, no PCN/address yet (AID 1513946,
--                     09/29/2026 auction, judgment not yet entered)
--   25000496CAAXMX -> stub "Property Appraiser" link only, no PCN/address yet (AID 1514224,
--                     09/29/2026 auction, judgment not yet entered)
-- These 5 remain untouched -- no real source available, not fabricated.
--
-- The 6th row, 25002169CCAXMX, is NOT a genuine dead end. It is a re-listed case: the
-- CURRENT 09/22/2026 calendar entry (AID 1515051) is a same-cycle "Property Appraiser"
-- stub with no PCN yet, but the SAME case number 25002169CCAXMX also has a live,
-- fully-populated entry on the 03/24/2026 martin.realforeclose.com auction calendar
-- (AID 1489716), harvested via the site's own AJAX auction.js JSON endpoint
-- (zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD), which is the official Martin County
-- Clerk auction platform, not a third party:
--   Case #: 25002169CCAXMX (links to LandmarkWeb O 3545/1392)
--   Parcel ID: 28-37-41-015-000-00240-0 (links to pamartinfl.gov/app/search/pcn/...)
--   Property Address: 236 PRESERVE TRAIL SOUTH, STUART, FL 34994
--   Final Judgment Amount: $5,536.12
--   Assessed Value (RealForeclose cache): $433,520.00
--
-- Cross-verified independently against the Martin County Property Appraiser's own
-- real-property JSON search API:
--   https://www.pamartinfl.gov/app/search/real-property?format=json&search=28-37-41-015-000-00240-0&searchField=all&exact=false
--   -> single unambiguous record: PIN 28-37-41-015-000-00240-0, Owner "REID GARRETT LEE",
--      SitusAddress "236 PRESERVE TRAIL SOUTH STUART FL", TotalMarketValue 430680,
--      AssessedValue 430680, Legal "LOT 24 NEW AVONLEA PUD 2ND REPLAT...", Y/X coords
--      27.2215000000 / -80.2485000000.
--
-- Both independent sources (RealForeclose official auction listing + County Property
-- Appraiser record) agree on parcel, address, and approximate value for the same case
-- number. This is the real parcel for case 25002169CCAXMX; the 09/22/2026 re-listing
-- just hasn't re-populated PCN on the platform's own site yet for this cycle.
--
-- Only patches WHERE parcel_id IS NULL (idempotent). Only this county's row is touched.

SET statement_timeout = 0;

UPDATE multi_county_auctions
SET
  parcel_id = '28-37-41-015-000-00240-0',
  property_address = '236 PRESERVE TRAIL SOUTH',
  city = 'STUART',
  zip = '34994',
  legal_description = 'LOT 24 NEW AVONLEA PUD 2ND REPLAT ACCORDING TO THE PLAT THEREOF RECORDED IN PLAT BOOK 18 PAGE 95 PUBLIC RECORDS OF MARTIN COUNTY FLORIDA',
  assessed_value = 430680,
  market_value = 430680,
  latitude = 27.2215000000,
  longitude = -80.2485000000,
  property_type = 'Townhomes - 2 Story Attached',
  bcpao_enriched = true,
  bcpao_url = 'https://www.pamartinfl.gov/app/search/real-property?format=json&search=28-37-41-015-000-00240-0&searchField=all&exact=false',
  assessed_value_source = 'pamartinfl_gov_real_property_json_api:AIN1124298;realforeclose_aid_1489716'
WHERE lower(county) = 'martin'
  AND case_number = '25002169CCAXMX'
  AND parcel_id IS NULL;

-- SQL VERIFICATION (run after apply)
-- SELECT case_number, parcel_id, property_address, assessed_value, latitude, longitude
-- FROM multi_county_auctions WHERE lower(county)='martin' AND case_number='25002169CCAXMX';
--
-- SELECT public.pencil_dod_evaluate_county('martin');
