-- SHARD-1: citrus criterion I (property-card completeness) fix
-- dispatch_id: 2c84de43-6561-42d3-b75d-ddbc4b04c305
-- Session: architect-20260702T080000 (gold standard shard-1: bradford, citrus, escambia)
--
-- Live baseline at session start (verified via pencil_dod_evaluate_county):
--   bradford: 10/10 all PASS (no action needed this session)
--   escambia: 10/10 all PASS -- the dispatch brief's stated baseline (5/10,
--     C/D/E/I/J failing) was stale; commit 4ccac3af (shard9, prior wave)
--     already closed it out. No action needed this session.
--   citrus: 9/10, only I failing (94.8%, card_complete=165 of 174)
-- This migration documents the citrus I fix only.
--
-- ROOT CAUSE (VERIFIED live via direct SQL against multi_county_auctions):
-- 9 rows failed the I join (property_address + latitude + longitude +
-- COALESCE(assessed_value,market_value) + parcel_id present, AND parcel_id
-- present in v_zoning_gold_standard_card with non-null zone_code). All 9
-- carried scraper placeholder parcel_id values ("MULTIPLE PARCELS",
-- "Property Appraiser", or a synthetic "CITRUS-<case_number>" string) instead
-- of a real Citrus County parcel number, and 3 tax-deed rows additionally had
-- a spurious ", $X,XXX.XX" delinquent-tax amount concatenated onto
-- property_address by the scraper. 165/174 = 94.8%; fixing exactly 3 of the
-- 9 rows crosses the 95% threshold (168/174 = 96.6%), so this migration
-- resolves only the 3 tax-deed cases -- the 6 foreclosure ("CA") cases with
-- MULTIPLE-PARCEL / non-numeric placeholder parcel_ids remain open for a
-- future session (not required to pass I, left untouched, not claimed fixed).
--
-- REAL PARCEL IDENTIFICATION (VERIFIED, independently confirmed by 3
-- adversarial refuter agents against live sources before this migration was
-- written):
--   Citrus Clerk of Court TaxSmartWeb (search.citrusclerk.org/TaxSmartWeb) is
--   a case-number-searchable tax-deed record system. POSTing
--   SearchForCase=<case> to /TaxSmartWeb/ followed by GET
--   /TaxSmartWeb/Home/GridSearchData?SearchType=Case%20%23 (same session
--   cookie) returns the case's clerk record id, certificate number, and the
--   authoritative county PARCEL ID string. /TaxSmartWeb/Home/Details?id=<id>
--   confirms case number, parcel ID, address, legal description, sale date.
--     2026-0134TD -> id=12385, cert 23-5450, PARCELID '18E19S28004A 00730 0085'
--     2026-0136TD -> id=12387, cert 23-0173, PARCELID '19E19S020020 00670 1390'
--     2026-0142TD -> id=12397, cert 19-0531, PARCELID '19E19S030010 00040 0120'
--
--   Citrus County BOCC "PublicData/LandDevelopment" MapServer (layer 0,
--   maps.citrusbocc.com/server/rest/services) carries both the county PARCEL
--   ID string (field PARCELID, irregularly double-spaced between section-
--   township-range and block/lot) and the internal integer ALTKEY that
--   multi_county_auctions.parcel_id already uses for every other citrus row
--   (verified: existing PASS rows store plain-integer ALTKEY, e.g. '3426452',
--   which round-trips through v_zoning_gold_standard_card.parcel_id). Queried
--   by PARCELID LIKE pattern (exact match fails on the double-space
--   formatting) to resolve ALTKEY, then by ALTKEY with returnGeometry=true,
--   outSR=4326 for the parcel polygon; latitude/longitude are the ring-vertex
--   average (same centroid method as the prior citrus I fix, run 1251):
--     2413298 <- PARCELID '18E19S28004A  00730 0085' (0134TD)
--     1643163 <- PARCELID '19E19S020020  00670 1390' (0136TD)
--     3316592 <- PARCELID '19E19S030010  00040 0120' (0142TD)
--
--   property_address: TaxSmartWeb's address, without the scraper's spurious
--   dollar-amount suffix. '0 NO ACCESS, HOMOSASSA, FL' for 0134TD is the
--   authentic TaxSmartWeb value (a landlocked/no-access parcel), not a data
--   defect.
--
-- ZONING (parcel_zones insert, required because v_zoning_gold_standard_card
-- requires the parcel to already exist in parcel_zones with a non-null
-- zone_code -- criterion I does not require zoning_districts/zone_standards
-- rows, only parcel_zones.zone_code):
--   Citrus County BOCC "ZONING_DESCR" MapServer (layer 0) resolves zoning by
--   spatial point-in-polygon at the parcel centroid (no usable key join to
--   LandDevelopment's ALTKEY/PARCELID was found on this layer). Returned:
--     2413298 -> HANSEN__PRCLZON_ZONING='RUR MH' ("RURAL RESIDENTIAL - MH ALLOWED")
--     1643163 -> HANSEN__PRCLZON_ZONING='MDR'    ("MEDIUM DENSITY RESIDENTIAL")
--     3316592 -> HANSEN__PRCLZON_ZONING='MDR'
--   'MDR' matches an existing ordinance-backed zoning_districts row for
--   jurisdiction 1327 (Unincorporated Citrus County) verbatim (id=11145,
--   far_applicable=false, pk1000_applicable=false), so those two inserts are
--   zero-risk to G. 'RUR MH' has no matching zoning_districts row (only
--   'RUR' exists, id=11141, same jurisdiction, far_applicable=false) --
--   inserting the raw 'RUR MH' code caused a live G REGRESSION (PASS
--   density=100.0 -> FAIL density=99.4/far=0.0/pk1000=0.0), because the
--   unmatched code left that one parcel counted as "FAR/parking-applicable
--   with no standard on file" in v_zoning_gold_standard_kpi_v3, dragging both
--   percentages from "no applicable parcels" (blank, effectively excluded)
--   to an explicit 0%. CAUGHT LIVE in-session (re-ran
--   pencil_dod_evaluate_county('citrus') immediately after every write) and
--   corrected by normalizing zone_code to 'RUR' with overlay_codes=ARRAY[
--   'MH'] -- 'MH ALLOWED' is a mobile-home-use overlay on the RUR district
--   per the county's own description text, not a distinct ordinance zoning
--   district, so this is a normalization to the existing ordinance-backed
--   code, not a fabricated value. G re-verified PASS (density=100.0) after
--   the correction, before this migration was written.
--
-- VERIFICATION (mandatory, HONESTY PROTOCOL): SELECT
-- public.pencil_dod_evaluate_county('citrus') live, before vs after:
--   BEFORE: I FAIL metric=94.8 "card_complete=165 of 174"; all other 9 PASS.
--   AFTER:  I PASS metric=96.6 "card_complete=168 of 174"; all other 9 still
--           PASS (G re-confirmed PASS density=100.0 after the RUR fix above).
--           citrus is 10/10 live.
-- Independently re-verified by 3 adversarial refuter subagents (ULTRALOOP
-- protocol: db-recompute, source-provenance, zoning-regression lenses) against
-- live Supabase + live TaxSmartWeb + live BOCC GIS before this file was
-- committed; see gold_standard_ultraloop_audit for the survived=true rows
-- this migration's application logs.
--
-- This migration is idempotent (WHERE clauses key on case_number; parcel_zones
-- insert is guarded by NOT EXISTS) so it is safe to apply even though the
-- underlying UPDATE/INSERT statements were already run live via the Supabase
-- Management API SQL endpoint during this session -- re-running it is a no-op.

UPDATE multi_county_auctions SET
  parcel_id = '2413298',
  property_address = '0 NO ACCESS, HOMOSASSA, FL',
  latitude = 28.7890071431865,
  longitude = -82.51686920259107,
  assessed_value_source = COALESCE(assessed_value_source, 'citrus_bocc_gis:shard1_i_fix'),
  updated_at = now()
WHERE lower(county) = 'citrus' AND case_number = '2026-0134TD'
  AND parcel_id IS DISTINCT FROM '2413298';

UPDATE multi_county_auctions SET
  parcel_id = '1643163',
  property_address = '3403 E ROGERS ST, INVERNESS, FL',
  latitude = 28.862078511436284,
  longitude = -82.37759045726534,
  assessed_value_source = COALESCE(assessed_value_source, 'citrus_bocc_gis:shard1_i_fix'),
  updated_at = now()
WHERE lower(county) = 'citrus' AND case_number = '2026-0136TD'
  AND parcel_id IS DISTINCT FROM '1643163';

UPDATE multi_county_auctions SET
  parcel_id = '3316592',
  property_address = '1975 E OLD COLONY LN, INVERNESS, FL',
  latitude = 28.859880805451883,
  longitude = -82.40150120352249,
  assessed_value_source = COALESCE(assessed_value_source, 'citrus_bocc_gis:shard1_i_fix'),
  updated_at = now()
WHERE lower(county) = 'citrus' AND case_number = '2026-0142TD'
  AND parcel_id IS DISTINCT FROM '3316592';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, overlay_codes, source)
SELECT * FROM (VALUES
  ('2413298', 1327, 'RUR', 'Rural Residential District', ARRAY['MH'], 'citrus_bocc_zoning_descr_gis:shard1_citrus_i_fix'),
  ('1643163', 1327, 'MDR', 'Medium Density Residential District', ARRAY[]::text[], 'citrus_bocc_zoning_descr_gis:shard1_citrus_i_fix'),
  ('3316592', 1327, 'MDR', 'Medium Density Residential District', ARRAY[]::text[], 'citrus_bocc_zoning_descr_gis:shard1_citrus_i_fix')
) AS v(parcel_id, jurisdiction_id, zone_code, zone_name, overlay_codes, source)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v.jurisdiction_id
);
