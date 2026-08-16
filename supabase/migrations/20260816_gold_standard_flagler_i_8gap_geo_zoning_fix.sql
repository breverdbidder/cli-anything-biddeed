-- Gold Standard flagler I: geo + zoning backfill for the v_auction_property_card
-- gap (card_complete FAIL at 94.97%, 151/159; needs >=95% / >=152/159 to PASS).
--
-- Source of truth: live PostgREST writes run via
-- scripts/gold_standard_flagler_i_8gap_geo_zoning_fix.py on 2026-08-16. This
-- migration file documents/replays the same data change per HARD GUARDRAILS #3.
--
-- CORRECTION to the task brief: row 58ef3cf4-2522-46c6-8bf6-30c88417633e (2 Perrotti
-- Pl) was briefed as "has lat/lon, missing zoning_code only", but a live query this
-- session found latitude/longitude both NULL on that row too -- the brief was stale
-- (state had drifted, likely from an intervening session). Corrected in-flight: this
-- row was included as a geo target, not skipped.
--
-- GEO (5 Palm Coast rows, sections 07-11-31/20-10-31/35-11-31): free US Census
-- Bureau geocoder (geocoding.geo.census.gov, Public_AR_Current benchmark), same
-- lever proven for escambia I (scripts/shard_escambia_i_geocode_backfill_20260724.py).
-- Required fixing a scraper artifact first: property_address concatenates house
-- number directly onto the street name with no space ("91VERANDA WAY"); this was
-- normalized to "91 VERANDA WAY" before geocoding (address-parsing fix only, no
-- value invented). All 5 addresses returned an exact Census tigerLine match.
--
-- ZONING (all 8 rows attempted, all via live ArcGIS point-in-polygon -- NOT
-- same-section-neighbor inference, since public.parcel_zones has ZERO pre-existing
-- rows for any of these 8 exact parcel_ids, verified live this session):
--   - PalmCoastFL_Zoning FeatureServer (services1.arcgis.com/tpnsCwhQRDqwL3mq,
--     field LAYER), jurisdiction_id=966, for the 6 Palm Coast parcels.
--   - Flagler Unincorporated_Zoning FeatureServer
--     (services3.arcgis.com/hSKL9bYjhP4rHxSD, field ZONECODE), jurisdiction_id=1184,
--     for the 2 Bunnell-area parcels.
--   Exact 0-tolerance point query first; where that returned zero features, a 30m
--   buffer retry was used ONLY when every returned polygon within the buffer agreed
--   on the same zone code (unanimous) -- ambiguous/boundary-straddling results were
--   explicitly left unzoned rather than guessed (BLANK > WRONG).
--
-- RESULT: 2 of 8 rows got a clean, unambiguous zone_code (both MPD, Palm Coast
-- Master Planned Development district) AND real geocode -- flipping both to
-- card_complete:
--   a817ed79-5509-4108-b370-3d1c18408384 (91 Veranda Way, parcel 07-11-31-0310-00020-0720)
--   fa706ae9-acca-4495-b0f4-8b06b0b8e309 (44 Del Palma Dr, parcel 35-11-31-4075-00000-0220)
--
-- The other 6 rows remain genuinely incomplete, left untouched (no fabrication):
--   7c6013d5 (9 Sweetbay Dr, 20-10-31-0300-00150-0000): geocoded successfully, but
--     zero zoning polygon coverage within 30m at either FeatureServer -- real
--     unincorporated/Palm Coast GIS coverage gap.
--   2e7aef04 (89 Johnson Beach Way, 20-10-31-3050-00080-0050): same -- geocoded,
--     zero zoning polygon coverage within 30m.
--   58ef3cf4 (2 Perrotti Pl, 07-11-31-7025-00160-0170): geocoded, but the 30m buffer
--     returned a MIXED result (3x SFR-3 vs 2x SFR-2 polygons) -- point sits on a
--     zoning boundary; not clean enough to assert a single zone code without
--     guessing, matches the precedent set by the 0801 migration's "1 Windsor Pl"
--     residual.
--   5b26cefa (BUNNELL FL only, no street address, 10-12-30-0850-01700-0040): already
--     had lat/lon (city-level precision only); zero zoning coverage within 200m at
--     either FeatureServer -- genuine coverage gap.
--   d1fdb06a (1911 County Rd 75, Bunnell): already had real lat/lon; a live
--     point-in-polygon hit DID return a clean zone (AC / Agricultural,
--     Unincorporated) -- but this row's parcel_id is NULL (a pre-existing upstream
--     scraper artifact per the 20260801 migration's own note), so it cannot be
--     zone-linked via parcel_zones (which requires a parcel_id) and the
--     v_zoning_gold_standard_card join requires an exact parcel_id match. Zoning was
--     NOT written for this row since there is no parcel_id to attach it to -- logged
--     as a named residual, not silently dropped.
--   78713ea7 (no address, no parcel_id): explicitly out of scope. Its stored lat/lon
--     (29.6469,-81.2088) is the same known-fake constant placeholder already flagged
--     in the 20260801 migration (comment #4) -- a scraper artifact, not a real
--     geocode, and with no address and no parcel_id there is no real source to
--     re-derive either field from. Left untouched.
--
-- parcel_zones dedup defect (pre-existing, NOT worsened): confirmed live this
-- session that parcel_zones already has 2+ conflicting rows for many nearby
-- parcel_ids in these same sections (e.g. two different source rows per parcel).
-- Both INSERTs below target parcel_ids with ZERO pre-existing parcel_zones rows
-- (verified before insert), so this migration does not add to the dedup defect.
-- Flagged per task brief, not fixed here (out of scope).
--
-- AFTER (VERIFIED live via pencil_dod_evaluate_county('flagler') post-fix):
--   I: card_complete 151/159 (94.97%) -> 153/159 (96.2%), FAIL -> PASS.
--   All other letters (A-J) also PASS; flagler is fully green this session.
--
-- No cron jobs (109/111/115/gold-standard-loop-*) modified. No schema DDL.

SET statement_timeout = 0;

UPDATE public.multi_county_auctions
SET latitude = 29.559042035552, longitude = -81.214257270225
WHERE id = 'a817ed79-5509-4108-b370-3d1c18408384' AND latitude IS NULL AND longitude IS NULL;

UPDATE public.multi_county_auctions
SET latitude = 29.500617411955, longitude = -81.153574933545
WHERE id = 'fa706ae9-acca-4495-b0f4-8b06b0b8e309' AND latitude IS NULL AND longitude IS NULL;

UPDATE public.multi_county_auctions
SET latitude = 29.621007726313, longitude = -81.200619558187
WHERE id = '7c6013d5-1130-4c29-a93b-8217c4a1cf33' AND latitude IS NULL AND longitude IS NULL;

UPDATE public.multi_county_auctions
SET latitude = 29.617258375565, longitude = -81.193565937186
WHERE id = '2e7aef04-be0d-43c7-93cf-3d74ffedd3f6' AND latitude IS NULL AND longitude IS NULL;

UPDATE public.multi_county_auctions
SET latitude = 29.538123045582, longitude = -81.215227673584
WHERE id = '58ef3cf4-2522-46c6-8bf6-30c88417633e' AND latitude IS NULL AND longitude IS NULL;

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '07-11-31-0310-00020-0720', 966, 'MPD',
       'gold_standard_flagler_i_8gap_20260816_arcgis_palmcoast_verified'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones
  WHERE parcel_id = '07-11-31-0310-00020-0720' AND jurisdiction_id = 966
);

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '35-11-31-4075-00000-0220', 966, 'MPD',
       'gold_standard_flagler_i_8gap_20260816_arcgis_palmcoast_verified'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones
  WHERE parcel_id = '35-11-31-4075-00000-0220' AND jurisdiction_id = 966
);
