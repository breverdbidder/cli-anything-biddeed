-- Osceola criterion I fix (dispatch 2026-07-25): geo/value/address backfill
-- for 6 of 21 targeted card-incomplete auctions, disambiguated via
-- osceola.realtaxdeed.com's live Auction Preview AJAX calendar (real full
-- ~18-digit FL DOR parcel_id per case_number, prefix-verified against the
-- stored truncated parcel_id before write -- see
-- scripts/shard_osceola_run20260725_i_realauction_calendar_geo_backfill.py
-- header for full sourcing narrative and the 15-case residual gap documented
-- there (auction_date=2026-05-15 has zero calendar presence on this platform
-- for both this AJAX source and the independently-tested report_id=18; the
-- 1 foreclosure case "2025 CA 001721 MF" is not a RealAuction/RealTaxDeed
-- case and has no working unauthenticated source this session).
--
-- Applied live via Supabase Management API (this file documents the change;
-- it was NOT re-applied via `supabase db push`, the PATCHes below already
-- landed through the script's direct PostgREST calls -- see session report
-- for exact BEFORE/AFTER pencil_dod_evaluate_county('osceola') proof).
--
-- BEFORE: I metric=84.3 (card_complete=113 of 134)
-- AFTER:  I metric=88.8 (card_complete=119 of 134)
--
-- Only NULL fields were overwritten; parcel_id / parcel_zones were NOT
-- touched (all 21 target rows already had has_zone=true via the existing
-- truncated-prefix parcel_id, per task scope).

-- Reference / idempotency: re-running this UPDATE is safe because every
-- SET clause is guarded by "col IS NULL", matching the script's own
-- only-patch-nulls behavior.

UPDATE multi_county_auctions SET
  latitude = 28.24819522882634,
  longitude = -81.29399743395172,
  market_value = COALESCE(market_value, 13800)
WHERE county = 'osceola' AND case_number = '1212023'
  AND latitude IS NULL;

UPDATE multi_county_auctions SET
  latitude = 28.313148928125266,
  longitude = -81.42841583182042,
  assessed_value = COALESCE(assessed_value, 297600),
  market_value = COALESCE(market_value, 297600)
WHERE county = 'osceola' AND case_number = '28152023'
  AND latitude IS NULL;

UPDATE multi_county_auctions SET
  latitude = 28.304702273352117,
  longitude = -81.65150502415976,
  assessed_value = COALESCE(assessed_value, 510700),
  market_value = COALESCE(market_value, 510700)
WHERE county = 'osceola' AND case_number = '33772024'
  AND latitude IS NULL;

UPDATE multi_county_auctions SET
  latitude = 28.335380483645707,
  longitude = -81.3984913785385,
  assessed_value = COALESCE(assessed_value, 29500),
  market_value = COALESCE(market_value, 29500)
WHERE county = 'osceola' AND case_number = '3432023'
  AND latitude IS NULL;

UPDATE multi_county_auctions SET
  latitude = 28.33669238823421,
  longitude = -81.4014434109244,
  market_value = COALESCE(market_value, 50000)
WHERE county = 'osceola' AND case_number = '3452023'
  AND latitude IS NULL;

UPDATE multi_county_auctions SET
  latitude = 28.301285133829815,
  longitude = -81.40342701139937,
  assessed_value = COALESCE(assessed_value, 10500),
  market_value = COALESCE(market_value, 10500)
WHERE county = 'osceola' AND case_number = '42202021'
  AND latitude IS NULL;
