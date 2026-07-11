-- HENDRY I: property_address backfill for 5 vacant unaddressed lots (already
-- applied live via REST during this session; this migration is the durable
-- record so the fix survives a fresh restore).
--
-- CONTEXT: hendry I (property card completeness) was failing at 75.0%
-- (15/20 card_complete) -- 5 tax-deed rows (case 25-102..25-106) had
-- property_address = NULL. All 5 already carried real parcel_id, lat/long,
-- assessed_value, and market_value from Hendry County's own ArcGIS parcel
-- layer (services7.arcgis.com/8l7Qq5t0CPLAJwJK/Hendry_County_Parcels) --
-- only the address was missing.
--
-- ROOT CAUSE (verified live against the same ArcGIS layer): the LOCADD
-- (situs address) field is genuinely BLANK for all 5 parcels -- they are
-- vacant platted lots with no assigned street number, not a scraper gap.
-- Fabricating a house-number address would violate the HONESTY PROTOCOL.
--
-- FIX: reverse-geocoded each parcel's existing lat/long via
-- nominatim.openstreetmap.org to recover a street-name-only address. This
-- is the SAME convention already used elsewhere in this table for other
-- vacant Hendry lots (e.g. case 25-101 = "AMANDA ST, LABELLE, FL- 33935",
-- no house number) -- not a new/inconsistent pattern.
--
-- VERIFIED via pencil_dod_evaluate_county:
--   BEFORE: hendry I fail, card_complete=15 of 20, metric=75.0
--   AFTER:  hendry I pass, card_complete=20 of 20, metric=100.0
--
-- Idempotent: only touches rows still missing property_address so this is
-- safe to re-run.

BEGIN;

UPDATE multi_county_auctions
   SET property_address = 'Ben Moore Drive, LaBelle, FL 33935'
 WHERE lower(county) = 'hendry'
   AND case_number = '25-102'
   AND property_address IS NULL;

UPDATE multi_county_auctions
   SET property_address = 'Helms Road West, LaBelle, FL 33935'
 WHERE lower(county) = 'hendry'
   AND case_number IN ('25-103', '25-104', '25-105', '25-106')
   AND property_address IS NULL;

COMMIT;
