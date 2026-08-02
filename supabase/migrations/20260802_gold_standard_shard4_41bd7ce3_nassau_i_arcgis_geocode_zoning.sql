-- GOLD STANDARD shard-4 (dispatch 41bd7ce3) — nassau C/D fresh-check + I fix.
--
-- Baseline (VERIFIED, live, 2026-08-02, pencil_dod_evaluate_county('nassau')):
-- 7/10. C FAIL 91.9% (matched_clean=34/37), D FAIL 91.9% (matched_any=34/37),
-- I FAIL 91.9% (card_complete=34 of 37). A/B/E/F/G/H/J passing, untouched.
--
-- ROOT CAUSE (VERIFIED): 3 rows shared by all three failing letters:
--   452025CA000241CAAXYX (foreclosure, sale 2026-08-06)
--   452025CA000281CAAXYX (foreclosure, sale 2026-08-13)
--   452026XX000003TDAXYX (tax_deed,   sale 2026-08-04)
-- All 3 already had real parcel_id/address/assessed_value from a genuine
-- realforeclose ingest. Gap was: parity_status/parity_source never set, and
-- latitude/longitude were NULL (also blocking I), plus no parcel_zones row
-- existed for these 3 parcels (a separate, previously-undocumented I blocker).
--
-- C/D INVESTIGATION RESULT: NOT fixable this pass, correctly residual.
-- public.refresh_parity_tier1_outcomes() only sets parity_status/parity_source
-- for rows with auction_status IN (redeemed,completed,sold,cancelled,canceled)
-- matched against a real row in tax_deed_outcomes/foreclosure_outcomes. All 3
-- rows have auction_status='upcoming' with sale dates still in the future
-- (2026-08-04/06/13; server now()=2026-08-02 at diagnosis time). Confirmed
-- live: foreclosure_outcomes/tax_deed_outcomes contain zero rows for these
-- case numbers (normalize_case_number join). Ran
-- refresh_parity_tier1_outcomes('nassau') live post-fix: 0 matched_clean,
-- 0 matched_divergent — confirms no outcome exists yet to match. This is a
-- genuine timing gap (auctions haven't happened), not a data-quality gap.
-- No parity_status/parity_source written by hand — the campaign rule requires
-- these to be set ONLY by refresh_parity_tier1_outcomes(), never hand-written.
--
-- I FIX (VERIFIED, applied): real geocode + real zoning district for all 3
-- parcels via Nassau County Property Appraiser's own ArcGIS REST service
-- (verified live, cert CN=*.ncpafl.com, service accessible at
-- maps.ncpafl.com/ncflpa_arcgis/rest/services/nassau/GoMaps4_Citrix/MapServer/0
-- "Land Parcels Report"), queried by exact PIN match on the parcel's STRAP:
--   26-2N-28-0552-0025-0000 -> ADDRESS_1='32428 POND PARKE PL',
--     CITY_NAME='FERNANDINA BEACH', ZoningDistrict='PUD',
--     Municipality='Unincorporated Nassau County' (matches our existing
--     property_address exactly, confirming the correct parcel)
--   37-1N-25-0000-0019-0010 -> ADDRESS_1='43761 RATLIFF ROAD',
--     CITY_NAME='CALLAHAN', ZoningDistrict='OR',
--     Municipality='Unincorporated Nassau County'
--   33-2N-25-0000-0001-0010 -> ADDRESS_1='545605 US HWY 1',
--     CITY_NAME='CALLAHAN', ZoningDistrict='OR',
--     Municipality='Unincorporated Nassau County'
-- Lat/long: queried the same MapServer layer with returnGeometry=true and
-- outSR=4326 (WGS84) to get each parcel's true polygon boundary reprojected
-- from the county's native spatial reference, then computed the polygon
-- centroid (shoelace formula) locally — NOT the layer's own "Latitude"/
-- "Longitude" attribute fields, which are stored in a projected coordinate
-- system (large XY values, not decimal degrees) despite the field names.
-- Centroids sanity-check against known town locations (Fernandina Beach
-- ~30.6N/-81.5W, Callahan ~30.5N/-81.8W).
-- This same ArcGIS source (ncpafl_arcgis_land_parcels) was already used by a
-- prior shard to backfill nassau's other 34 parcel_zones rows — this fix is
-- consistent with that existing, already-verified pattern, not a new method.
--
-- zone_code PUD and OR both already exist in zoning_districts for
-- jurisdiction_id=1508 (Unincorporated Nassau County) with existing
-- zone_standards rows (ids 4922, 4921) — this insert is purely additive
-- (new parcel_zones rows only), no zoning_districts/zone_standards writes,
-- zero effect on G.
--
-- assessed_value was already present pre-existing on all 3 rows (not
-- fabricated this session). market_value intentionally left NULL for the
-- tax_deed row (452026XX000003TDAXYX) — the ncpafl ArcGIS layer's JUSTVAL/
-- APPRVAL fields are assessed/appraised values, not a market-value figure,
-- so writing one in would be inventing a number the source doesn't provide.
-- Confirmed via evaluator source (pg_get_functiondef) that I's value gate is
-- COALESCE(assessed_value, market_value) IS NOT NULL — assessed_value alone
-- is sufficient, so this is not a blocker.

-- 1. Real lat/long (polygon centroid, WGS84, from ncpafl.com ArcGIS).
UPDATE multi_county_auctions
SET latitude = 30.61160789089553, longitude = -81.5378694458941, updated_at = now()
WHERE county = 'nassau' AND case_number = '452025CA000241CAAXYX' AND latitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 30.510886945738516, longitude = -81.79662128378341, updated_at = now()
WHERE county = 'nassau' AND case_number = '452025CA000281CAAXYX' AND latitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 30.552955493285243, longitude = -81.80071975577549, updated_at = now()
WHERE county = 'nassau' AND case_number = '452026XX000003TDAXYX' AND latitude IS NULL;

-- 2. Real zone_code linkage via parcel_zones (jurisdiction 1508 =
--    Unincorporated Nassau County; PUD/OR both pre-existing districts).
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '26-2N-28-0552-0025-0000', 1508, 'PUD', 'Planned Unit Development',
       'gold_standard_shard4_41bd7ce3_20260802:ncpafl_arcgis_land_parcels_144'
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones WHERE parcel_id = '26-2N-28-0552-0025-0000' AND jurisdiction_id = 1508
);

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '37-1N-25-0000-0019-0010', 1508, 'OR', 'Open Rural',
       'gold_standard_shard4_41bd7ce3_20260802:ncpafl_arcgis_land_parcels_144'
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones WHERE parcel_id = '37-1N-25-0000-0019-0010' AND jurisdiction_id = 1508
);

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '33-2N-25-0000-0001-0010', 1508, 'OR', 'Open Rural',
       'gold_standard_shard4_41bd7ce3_20260802:ncpafl_arcgis_land_parcels_144'
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones WHERE parcel_id = '33-2N-25-0000-0001-0010' AND jurisdiction_id = 1508
);

-- 3. C/D fresh-check: run the canonical matcher (idempotent, no-op expected
--    given all 3 rows are still auction_status='upcoming' with no outcome
--    row yet). Included for campaign-protocol compliance and to leave the
--    live confirmation in the migration history.
SELECT * FROM public.refresh_parity_tier1_outcomes('nassau');

-- 4. Diagnostic snapshot. NOTE: the ULTRALOOP audit rows for this fix
--    (letters I/C/D, dispatch 41bd7ce3-a9f5-465d-99a1-a3ed447d8ce4) were
--    already inserted live via the REST API during this session (ids
--    12094, 12095, 12096) — not repeated here to avoid duplicate rows on
--    migration replay.
DO $$
DECLARE
  v_after jsonb;
BEGIN
  SELECT public.pencil_dod_evaluate_county('nassau') INTO v_after;
  RAISE NOTICE 'Nassau I AFTER: %', v_after->'I';
  RAISE NOTICE 'Nassau C AFTER (residual, unchanged expected): %', v_after->'C';
  RAISE NOTICE 'Nassau D AFTER (residual, unchanged expected): %', v_after->'D';
  RAISE NOTICE 'Nassau G AFTER (regression check): %', v_after->'G';
END $$;
