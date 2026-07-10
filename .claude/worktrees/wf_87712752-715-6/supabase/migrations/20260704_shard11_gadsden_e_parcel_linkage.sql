-- SHARD-11 (clay, okeechobee, alachua, gadsden): gadsden E parcel linkage fix
-- dispatch_id: 18aeb9b9-8281-4991-aa6c-f5e4422d0c6d
-- Session: architect-20260704T160000
--
-- ROOT CAUSE (CONFIRMED live): gadsden's real property data was NOT missing
-- from fl_parcels -- it was mislabeled by co_no. fl_parcels.co_no=20 (the
-- code public.fl_counties correctly assigns to Gadsden per FL DOR standard
-- codes) actually contains CLAY COUNTY data (Orange Park, Middleburg, Green
-- Cove Springs, Fleming Island, Keystone Heights -- all verified Clay
-- County cities, one row even literally has phy_city='Clay County').
-- Gadsden's real parcels (Quincy, Chattahoochee, Havana, Greensboro, Gretna)
-- are stored under fl_parcels.co_no=30 instead. This is the same systemic
-- +10 co_no shift already independently discovered for Franklin
-- (co_no=19 -> actually Citrus; real Franklin data at co_no=29) in
-- SHARD10_RUN2886_SESSION_REPORT.md. The fleet-wide co_no remap is NOT
-- attempted here -- same reasoning as that report: touching the shared
-- fl_parcels/fl_counties co_no mapping is high-blast-radius (affects every
-- county's E/I metric, not just this shard's four), so it is flagged for a
-- dedicated cross-shard fix session, not patched incidentally here.
--
-- FIX (narrow, this shard's data only): of gadsden's 16 parcel_id-less
-- auction rows, 10 carry real street addresses (the other 6 are
-- legal-description-only -- "Section 3, Township 3 North", "4 Parcels",
-- "Lot 35, Block A of Tobacco Rd", etc. -- and are NOT matchable to a single
-- parcel by address; left unlinked, not guessed). For those 10, queried
-- fl_parcels WHERE co_no=30 for an EXACT house-number + street-name match
-- (not fuzzy/nearest-address -- a few houses down is a different parcel and
-- owner). All 10 found exact matches (verified below); two carry a minor
-- street-suffix variance vs. the auction listing (Mount Pleasant Rd vs. MT
-- PLEASANT RD; N. Oak Rd vs. N OAK DR) but exact house number + street name
-- + correct zip/city for the auction's stated city, so treated as
-- high-confidence matches, not guesses:
--   23000820CA  924 Bethel St, Chattahoochee       -> 2-03-3N-6W-0000-00342-0200
--   24000687CA  4164 Mount Pleasant Rd, Quincy     -> 2-12-3N-5W-0000-00111-0200
--   24000726CA  121 Squirrel Ln, Quincy            -> 2-07-3N-2W-0000-00133-0100
--   25000121CA  310 Holly Circle, Quincy           -> 3-16-2N-3W-0785-00000-0120
--   25000126CA  121 Lantern Ln, Havana             -> 3-14-2N-2W-0565-0000E-0070
--   25000148CA  208 S. Love St, Quincy             -> 3-07-2N-3W-0730-00000-1711
--   25000484CA  211 N. Oak Rd, Chattahoochee       -> 1-31-4N-5W-0000-00144-0000
--   25000580CA  511 Hopkins Landing Rd, Quincy     -> 6-04-1S-4W-0000-00341-0100
--   25000896CA  540 Old Federal Rd, Quincy         -> 4-01-1N-5W-0000-00331-0100
--   25000943CA  1726 Kemp Rd, Havana               -> 2-25-3N-2W-0000-00343-0200
--
-- VERIFIED live before/after via pencil_dod_evaluate_county('gadsden'):
--   BEFORE: E parcel_linked=7  (30.4%%) FAIL
--   AFTER:  E parcel_linked=17 (73.9%%) FAIL (still below 95%% threshold --
--           real, partial progress; remaining 6 rows are legal-description-
--           only and structurally unmatchable by address)
-- I did NOT move (30.4%%, still 7/23) -- card_complete additionally requires
-- parcel_id IN v_zoning_gold_standard_card WHERE zone_code IS NOT NULL, and
-- gadsden's parcel_zones table only covers the original 7 tax-deed parcels.
-- Extending zoning coverage to these 10 newly-linked parcels needs real
-- Gadsden zoning-ordinance/jurisdiction data (not attempted here -- would
-- repeat the guessed-zone-code ghost-success pattern the G/I playbook
-- explicitly bans). No other letter changed (confirmed identical: A=7
-- B=null C=0 D=0 F=null G=100 H~0 J=100).

SET statement_timeout = 0;

UPDATE multi_county_auctions SET parcel_id = CASE case_number
  WHEN '23000820CA' THEN '2-03-3N-6W-0000-00342-0200'
  WHEN '24000687CA' THEN '2-12-3N-5W-0000-00111-0200'
  WHEN '24000726CA' THEN '2-07-3N-2W-0000-00133-0100'
  WHEN '25000121CA' THEN '3-16-2N-3W-0785-00000-0120'
  WHEN '25000126CA' THEN '3-14-2N-2W-0565-0000E-0070'
  WHEN '25000148CA' THEN '3-07-2N-3W-0730-00000-1711'
  WHEN '25000484CA' THEN '1-31-4N-5W-0000-00144-0000'
  WHEN '25000580CA' THEN '6-04-1S-4W-0000-00341-0100'
  WHEN '25000896CA' THEN '4-01-1N-5W-0000-00331-0100'
  WHEN '25000943CA' THEN '2-25-3N-2W-0000-00343-0200'
  END,
  updated_at = now()
WHERE lower(county) = 'gadsden'
  AND case_number IN ('23000820CA','24000687CA','24000726CA','25000121CA',
                       '25000126CA','25000148CA','25000484CA','25000580CA',
                       '25000896CA','25000943CA');
