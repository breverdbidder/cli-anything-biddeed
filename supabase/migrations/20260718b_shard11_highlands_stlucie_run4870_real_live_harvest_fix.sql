-- SHARD-11 run4870 (continuation, 3rd session): highlands + st_lucie C/D/E fix
-- dispatch_id: c7a1fa1a-c246-477c-80b0-aaa93b75e4c0
-- Session: architect-20260718T160000 (3rd firing — first session with real Supabase creds)
--
-- SUPERSEDES: supabase/migrations/20260718_shard11_highlands_stlucie_cd_ei_fix.sql
-- That earlier migration was NEVER APPLIED (prior two sessions had no DB credentials —
-- see SHARD11_RUN4870_HIGHLANDS_STLUCIE_SESSION_REPORT.md). Its approach (blanket-promote
-- any row with a parcel_id or property_address to matched_clean) is REJECTED here as
-- unverified ghost-success risk. Every row touched below was individually confirmed
-- against a LIVE re-harvest of the county's own RealForeclose/RealTaxDeed AJAX calendar
-- (scripts/shard2_run2450_ajax_realforeclose_harvest.py, run live 2026-07-18) or a live
-- US Census Bureau geocoder lookup (geocoding.geo.census.gov, no key required, free).
--
-- This file is NOT executable via `supabase db push` in this environment (the Supabase
-- Postgres pooler rejected the SUPABASE_DB_PASSWORD in the runner env, and the
-- api.supabase.com database/query Management API endpoint returned HTTP 403 from
-- Cloudflare). All updates below were therefore applied LIVE via PostgREST REST PATCH
-- calls (same net effect, confirmed row-by-row with Prefer: return=representation, then
-- reconfirmed via SELECT public.pencil_dod_evaluate_county(...)). This file is committed
-- as the durable, idempotent SQL record of that work and is safe to re-run.
--
-- BASELINE (VERIFIED live, 2026-07-18T~19:40Z, before this session's writes):
--   highlands: C=81.7% (matched_clean=147/180)  D=81.7% (matched_any=147/180)
--   st_lucie:  C=88.2% (matched_clean=82/93)     D=88.2%                        E=94.6% (parcel_linked=88/93)
--
-- RESULT (VERIFIED live via pencil_dod_evaluate_county RPC, same session):
--   highlands: C=83.9% matched_clean=151  D=83.9%  -- still FAIL; genuine partial gain, see note below
--   st_lucie:  C=97.8% matched_clean=91   D=100.0% matched_any=93   E=97.8% parcel_linked=91  -- all PASS
--
-- HIGHLANDS NOTE (HONEST, non-fabricated): of the 31 rows with parity_status IS NULL
-- (all on far-future tax-deed sale dates 2026-08-05/08-12/08-19), a live re-harvest of
-- highlands.realtaxdeed.com for those 3 dates returned 78 distinct live case numbers.
-- Only 4 of our 31 gap rows matched a live case_number AND parcel_id. The remaining 27
-- genuinely do not appear on the live calendar under any case_number or parcel_id we
-- hold -- consistent with the shard10/run3645 finding that far-future tax-deed calendars
-- narrow via redemption/cancellation between initial calendar_sweep ingest and the
-- present. Those 27 rows are deliberately left parity_status=NULL rather than promoted:
-- doing otherwise would be exactly the ghost-success pattern this migration supersedes.
-- Real resolution requires re-checking closer to the sale date or a Highlands Clerk
-- redemption-status lookup -- flagged as next-session work, not solved here.

SET statement_timeout = 0;

-- ═══════════════════════════════════════════════════════════════════════════
-- HIGHLANDS: C/D — 4 rows verified live (case_number AND parcel_id both match
-- the live highlands.realtaxdeed.com AJAX calendar for their sale date)
-- ═══════════════════════════════════════════════════════════════════════════
UPDATE multi_county_auctions
SET parity_status     = 'matched_clean',
    parity_source     = 'tier1_live_realtaxdeed_ajax_verified_20260718',
    parity_checked_at = NOW()
WHERE lower(county) = 'highlands'
  AND case_number IN ('25000686', '25000726', '25000736', '25000735')
  AND parity_status IS DISTINCT FROM 'matched_clean';

-- ═══════════════════════════════════════════════════════════════════════════
-- ST_LUCIE: C/D — 10 rows verified live against stlucie.realforeclose.com
-- for auction dates 07/22/2026 and 07/29/2026 (case_number + parcel_id/address match)
-- ═══════════════════════════════════════════════════════════════════════════
UPDATE multi_county_auctions
SET parity_status     = 'matched_clean',
    parity_source     = 'tier1_live_realforeclose_ajax_verified_20260718',
    parity_checked_at = NOW()
WHERE lower(county) = 'st_lucie'
  AND case_number IN (
      '2024CA000939', '2025CA000428', '2025CA001395', '2025CA000094',
      '2025CC002579', '2024CC002112', '2025CA000758', '2025CA002822',
      '2025CC004638', '2025CA002588'
  )
  AND parity_status IS DISTINCT FROM 'matched_clean';

-- 2 genuinely divergent cases: live RealForeclose shows parcel_id="MULTIPLE PARCELS"
-- (a multi-parcel foreclosure) conflicting with our single-parcel row (2025CA001832),
-- or the case has no resolvable single-parcel/address data live (2024CA000214, which
-- was PREVIOUSLY mismarked matched_clean by an earlier session -- corrected here).
UPDATE multi_county_auctions
SET parity_status     = 'matched_divergent',
    parity_source     = 'tier1_live_realforeclose_ajax_divergent_multiple_parcels_20260718',
    parity_checked_at = NOW()
WHERE lower(county) = 'st_lucie'
  AND case_number IN ('2025CA001832', '2024CA000214')
  AND parity_status IS DISTINCT FROM 'matched_divergent';

-- ═══════════════════════════════════════════════════════════════════════════
-- ST_LUCIE: E / I — real assessed_value + parcel_id backfill read directly off
-- the live RealForeclose AJAX auction-item feed (16 value backfills, 3 parcel_id
-- backfills; no fallback/median/synthetic values used anywhere)
-- ═══════════════════════════════════════════════════════════════════════════
UPDATE multi_county_auctions SET assessed_value = 409200.0 WHERE lower(county)='st_lucie' AND case_number='2024CA000939' AND assessed_value IS DISTINCT FROM 409200.0;
UPDATE multi_county_auctions SET assessed_value = 587861.0 WHERE lower(county)='st_lucie' AND case_number='2025CA000428' AND assessed_value IS DISTINCT FROM 587861.0;
UPDATE multi_county_auctions SET assessed_value = 112500.0 WHERE lower(county)='st_lucie' AND case_number='2025CA001395' AND assessed_value IS DISTINCT FROM 112500.0;
UPDATE multi_county_auctions SET assessed_value = 249700.0 WHERE lower(county)='st_lucie' AND case_number='2025CA000094' AND assessed_value IS DISTINCT FROM 249700.0;
UPDATE multi_county_auctions SET assessed_value = 334600.0 WHERE lower(county)='st_lucie' AND case_number='2025CC002579' AND assessed_value IS DISTINCT FROM 334600.0;
UPDATE multi_county_auctions SET assessed_value = 167100.0 WHERE lower(county)='st_lucie' AND case_number='2024CC002112' AND assessed_value IS DISTINCT FROM 167100.0;
UPDATE multi_county_auctions SET assessed_value = 335100.0 WHERE lower(county)='st_lucie' AND case_number='2025CA000758' AND assessed_value IS DISTINCT FROM 335100.0;
UPDATE multi_county_auctions SET assessed_value = 131174.0 WHERE lower(county)='st_lucie' AND case_number='2025CA002822' AND assessed_value IS DISTINCT FROM 131174.0;
UPDATE multi_county_auctions SET assessed_value = 109284.0 WHERE lower(county)='st_lucie' AND case_number='2025CC004638' AND assessed_value IS DISTINCT FROM 109284.0;
UPDATE multi_county_auctions SET assessed_value = 56335.0  WHERE lower(county)='st_lucie' AND case_number='2025CA002588' AND assessed_value IS DISTINCT FROM 56335.0;
UPDATE multi_county_auctions SET assessed_value = 208700.0 WHERE lower(county)='st_lucie' AND case_number='2023CA002858' AND assessed_value IS DISTINCT FROM 208700.0;
UPDATE multi_county_auctions SET assessed_value = 172690.0 WHERE lower(county)='st_lucie' AND case_number='2023CA002350' AND assessed_value IS DISTINCT FROM 172690.0;
UPDATE multi_county_auctions SET assessed_value = 339900.0 WHERE lower(county)='st_lucie' AND case_number='2025CA001088' AND assessed_value IS DISTINCT FROM 339900.0;
UPDATE multi_county_auctions SET assessed_value = 366632.0 WHERE lower(county)='st_lucie' AND case_number='2025CA001294' AND assessed_value IS DISTINCT FROM 366632.0;
UPDATE multi_county_auctions SET assessed_value = 299100.0 WHERE lower(county)='st_lucie' AND case_number='2025CA002292' AND assessed_value IS DISTINCT FROM 299100.0;
UPDATE multi_county_auctions SET assessed_value = 231100.0 WHERE lower(county)='st_lucie' AND case_number='2025CA002297' AND assessed_value IS DISTINCT FROM 231100.0;

UPDATE multi_county_auctions SET parcel_id = '3089' WHERE lower(county)='st_lucie' AND case_number='2025CA000094' AND parcel_id IS DISTINCT FROM '3089';
UPDATE multi_county_auctions SET parcel_id = '1826' WHERE lower(county)='st_lucie' AND case_number='2025CC004638' AND parcel_id IS DISTINCT FROM '1826';
UPDATE multi_county_auctions SET parcel_id = '5481' WHERE lower(county)='st_lucie' AND case_number='2023CA000239' AND parcel_id IS DISTINCT FROM '5481';

-- ═══════════════════════════════════════════════════════════════════════════
-- ST_LUCIE: I — real per-address geocoding via US Census Bureau geocoder
-- (geocoding.geo.census.gov/geocoder, free, no API key, TIGER/Line authoritative).
-- 10 of 11 addresses resolved; "1303 PEPPERTREE TRL, FORT PIERCE, FL 34950" did not
-- resolve against TIGER and is left NULL rather than fabricated with a county centroid.
-- ═══════════════════════════════════════════════════════════════════════════
UPDATE multi_county_auctions SET latitude = 27.333796454609,  longitude = -80.370468513418 WHERE lower(county)='st_lucie' AND case_number='2024CA000939' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 27.30661499604,   longitude = -80.448090503078 WHERE lower(county)='st_lucie' AND case_number='2025CA000428' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 27.414954633613,  longitude = -80.328738594305 WHERE lower(county)='st_lucie' AND case_number='2025CA001395' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 27.542977171174,  longitude = -80.393148778462 WHERE lower(county)='st_lucie' AND case_number='2025CA000094' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 27.433914568051,  longitude = -80.329318233862 WHERE lower(county)='st_lucie' AND case_number='2025CA001832' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 27.323770813329,  longitude = -80.452003152398 WHERE lower(county)='st_lucie' AND case_number='2025CC002579' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 27.433409506943,  longitude = -80.380925485082 WHERE lower(county)='st_lucie' AND case_number='2025CA000758' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 27.27202493959,   longitude = -80.371962331141 WHERE lower(county)='st_lucie' AND case_number='2025CA002822' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 27.553100110097,  longitude = -80.405330944384 WHERE lower(county)='st_lucie' AND case_number='2025CC004638' AND latitude IS NULL;
UPDATE multi_county_auctions SET latitude = 27.284234327488,  longitude = -80.357974647473 WHERE lower(county)='st_lucie' AND case_number='2025CA002588' AND latitude IS NULL;

-- ═══════════════════════════════════════════════════════════════════════════
-- Verification (run in the same session that applies this)
-- ═══════════════════════════════════════════════════════════════════════════
SELECT public.pencil_dod_evaluate_county('highlands');
SELECT public.pencil_dod_evaluate_county('st_lucie');
