-- SHARD-10 calhoun (dispatch d0d45cbc-e63c-43a7-a634-baf9b247210a): letter I address backfill.
--
-- DIAGNOSIS (live-verified 2026-07-24): pencil_dod_evaluate_county('calhoun') showed
-- I=28.6% (card_complete=2 of 7). Root cause isolated by direct query: all 7 calhoun
-- auctions already have real lat/lng, an assessed/market value, and a linked+zoned
-- parcel_id (v_zoning_gold_standard_card, zone_code populated by the 2026-07-11g
-- migration) -- the ONLY missing card field across the 5 failing rows was
-- property_address (NULL). Note: a comment in 20260711g_..._density_backfill.sql
-- claimed this migration already flipped I to 7/7 (100%) as a side effect of purging
-- 20 orphaned parcel_zones rows -- that claim does NOT hold today; re-verified live
-- via pencil_dod_evaluate_county immediately before this migration, still 2 of 7.
-- Logged as a discrepancy, not silently trusted.
--
-- FIX: the 5 rows carry real, already-verified lat/lng (sourced from calhoun_clerk_scrape,
-- passing E/G checks). Reverse-geocoded each coordinate via OpenStreetMap Nominatim
-- (public API, no key) to obtain a real street-level address. All 5 results independently
-- confirm the coordinate falls inside Calhoun County, FL -- consistent with existing data,
-- not fabricated. Two of the five (171 OF 2023, 268 OF 2023) are road-level only (no
-- house number returned by the geocoder) -- expected for rural unaddressed parcels;
-- kept as-is rather than inventing a house number. Source noted in this file, not a new
-- DB column (matches existing convention -- no per-field provenance column exists on
-- multi_county_auctions; prior calhoun migrations documented source in the migration
-- file body only).
--
-- pencil_dod_evaluate_county('calhoun') before -> after (adversarially verified live,
-- see session report):
--   I: card_complete=2 of 7 (28.6%, FAIL) -> card_complete=7 of 7 (100.0%, PASS)
--   A/C/D/E/G/H/J: unchanged (already passing)
--   B/F: unchanged, still FAIL/null -- verified live via calhounclerk.com foreclosure
--     page, tax-deed-sales page, tax-deed-surplus overbid list (39 records, none match
--     our 7 parcel_ids), and the WP REST API (wp-json/wp/v2/taxdeeds) for 171 OF 2023
--     specifically (sale date passed 2026-07-09, clerk site still reports status=
--     "scheduled" -- no sale has posted). No calhoun auction has actually closed;
--     genuinely blocked on real-world accrual, not a pipeline bug. Out of scope for
--     this migration per HARD GUARDRAILS (no fabricated sold_amount).

BEGIN;

UPDATE multi_county_auctions
SET property_address = '21798 Apalache Road FL 32438',
    zip = '32438'
WHERE lower(county) = 'calhoun' AND case_number = '621 OF 2026';

UPDATE multi_county_auctions
SET property_address = 'Azalea Drive Blountstown FL 32424',
    city = 'Blountstown',
    zip = '32424'
WHERE lower(county) = 'calhoun' AND case_number = '171 OF 2023';

UPDATE multi_county_auctions
SET property_address = '19399 Fred Barfield Lane FL 32424',
    zip = '32424'
WHERE lower(county) = 'calhoun' AND case_number = '227 OF 2024';

UPDATE multi_county_auctions
SET property_address = '10500 SR 73 Frink FL 32430',
    city = 'Frink',
    zip = '32430'
WHERE lower(county) = 'calhoun' AND case_number = '546 OF 2024';

UPDATE multi_county_auctions
SET property_address = 'Sheard Road New Hope FL',
    city = 'New Hope'
WHERE lower(county) = 'calhoun' AND case_number = '268 OF 2023';

COMMIT;
