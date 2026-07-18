-- GOLD STANDARD shard-7 (dispatch 7066f088), county=jefferson.
--
-- Enrichment follow-up to 20260718_gold_standard_shard7_jefferson_a_taxdeed_ingest.sql.
-- That migration inserted 2 real tax-deed cases (26-TD-04, 26-TD-05) to fix
-- letter A, which correctly (not a bug) dropped C/D/I/J since the 2 new rows
-- had no address enrichment beyond the clerk PDF's site address.
--
-- This migration backfills real assessed_value/market_value/lat/long for
-- both parcels from the FL GIO statewide cadastral (fl_parcels table,
-- co_no=43 -- verified live this session to be the correct Jefferson-County
-- rows in this table despite the table's own co_no column not matching FL
-- DOR's standard numbering; municipality/city + exact parcel_id + exact
-- street address all cross-match the clerk PDF, confirming same real
-- parcels). Same "fl_gio_cadastral_corroboration" methodology already used
-- for jefferson's original foreclosure row (data_source
-- jefferson_clerk_official+nominatim_geocode_real_address, parity_source
-- ...fl_gio_cadastral_corroboration_20260711).
--
-- Zoning (letter I's zone_code requirement) is NOT resolved by this
-- migration -- parcel_zones has exactly 1 zoned parcel for jefferson
-- countywide (the original R-1A foreclosure parcel under Monticello town
-- jurisdiction_id=817); confirming whether these 2 rural acreage parcels
-- fall under unincorporated Jefferson's A-1 Agricultural district
-- (jurisdiction_id=1259) requires a real jurisdiction-boundary check that
-- was not completed this session (fl_parcels' own municipality field reads
-- "MONTICELLO" for effectively all of rural Jefferson County -- it is a
-- mailing-address/post-office field, not an incorporation boundary, so it
-- is NOT reliable evidence either way). Left unresolved rather than guessed
-- -- I remains FAIL for jefferson pending real verification.

UPDATE multi_county_auctions
SET assessed_value = 34124, market_value = 62793,
    latitude = 30.3405219, longitude = -84.0454923,
    assessed_value_source = 'fl_gio_cadastral_corroboration_20260718'
WHERE lower(county) = 'jefferson' AND case_number = '26-TD-04';

UPDATE multi_county_auctions
SET assessed_value = 133627, market_value = 210701,
    latitude = 30.4337643, longitude = -83.9868766,
    assessed_value_source = 'fl_gio_cadastral_corroboration_20260718'
WHERE lower(county) = 'jefferson' AND case_number = '26-TD-05';

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:jeffersonclerk_pending_taxdeed_pdf_scrape+fl_gio_cadastral_corroboration_20260718'
WHERE lower(county) = 'jefferson' AND case_number IN ('26-TD-04', '26-TD-05');
