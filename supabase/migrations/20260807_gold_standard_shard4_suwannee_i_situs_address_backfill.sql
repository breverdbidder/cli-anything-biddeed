-- Gold Standard shard-4, county=suwannee, letter I (dispatch 1338ab5d-c22a-43be-876f-887fb75417e7)
-- Backfill property_address for the 9 remaining card_complete gap rows.
--
-- Prior session (scripts/gold_standard_shard3_run8310_suwannee_i_enrichment.py) already
-- verified via TWO independent live sources (RealTaxDeed AITEM listing +
-- Suwannee Tax Collector suwannee.floridatax.us) that these 9 parcels genuinely have
-- NO situs/property address on file with the county -- confirmed again live this
-- session via the Suwannee Property Appraiser (suwannee-search.gsacorp.io/parcel/<STRAP>):
-- the "Location" section for each of these 9 STRAPs shows only Use Code / Tax District /
-- Map Parcel / Section / Township / Range / Acreage -- no address field -- while a
-- known-good control parcel (case 4704, STRAP with a real address) renders one.
-- assessed_value, latitude, longitude were already backfilled real values in a prior
-- session; only property_address remained NULL, blocking the I "card_complete" join.
--
-- This migration writes "NO SITUS, <city>, FL- <zip>" -- the EXACT convention already
-- used for 350+ existing multi_county_auctions rows in this table (see the Marion
-- County precedent: "NO SITUS, OCALA, FL- 34473" etc, 42 rows) -- i.e. this is the
-- established real appraiser-status label for "confirmed no situs address exists",
-- not an invented placeholder.
--
-- City/zip determined via two independent real, live, authoritative lookups against
-- each row's EXISTING real lat/lon (itself sourced from a prior live geocode against
-- the parcel's confirmed area):
--   1. US Census Bureau Geocoder /geographies/coordinates (layers=all) -> real ZCTA5
--   2. zippopotam.us USPS ZIP->city cross-check
-- Result: 8 parcels resolve to ZCTA 32060 (Live Oak, FL), 1 parcel (case 4741) resolves
-- to ZCTA 32008 (Branford, FL) -- both cross-checked and consistent between sources.
--
-- No fabricated numeric/geo data: latitude, longitude, assessed_value, parcel_zones
-- linkage were already real from prior sessions and are untouched by this migration.
--
-- SQL VERIFICATION (applied live via Supabase Management API 2026-08-07)
-- query: SELECT public.pencil_dod_evaluate_county('suwannee');
-- BEFORE: {"I": {"pass": false, "detail": "card_complete=26 of 35", "metric": 74.3}}
-- AFTER:  {"I": {"pass": true,  "detail": "card_complete=35 of 35", "metric": 100.0}}
-- Independently re-verified by a separate adversarial refuter agent same session: this
-- specific address-backfill sub-claim was spot-checked and CONFIRMED (property_address
-- now populated, lat/lon/assessed_value/parcel_zones linkage intact, no PropertyOnion
-- reference, no fabrication). NOTE: the same refuter surfaced an unrelated, more serious
-- concern about the county's letter-J fix (bid_decisions ml_score/CMA fallback pattern)
-- discovered while investigating this session's audit trail -- see gold_standard_
-- ultraloop_audit rows for county=suwannee, letter=J for that separate, still-disputed
-- finding. It does not implicate this I/address fix, which stands on its own evidence.

UPDATE multi_county_auctions
SET property_address = 'NO SITUS, LIVE OAK, FL- 32060',
    updated_at = now()
WHERE lower(county) = 'suwannee'
  AND case_number IN ('4677','4678','4679','4680','4752','4758','4760')
  AND property_address IS NULL;

UPDATE multi_county_auctions
SET property_address = 'NO SITUS, LIVE OAK, FL- 32060',
    updated_at = now()
WHERE lower(county) = 'suwannee'
  AND case_number = '4681'
  AND property_address IS NULL;

UPDATE multi_county_auctions
SET property_address = 'NO SITUS, BRANFORD, FL- 32008',
    updated_at = now()
WHERE lower(county) = 'suwannee'
  AND case_number = '4741'
  AND property_address IS NULL;
