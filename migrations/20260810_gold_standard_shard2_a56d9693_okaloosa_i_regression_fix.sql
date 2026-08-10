-- GOLD STANDARD SHARD-2, dispatch a56d9693-0b6c-4579-881d-783946ddbe17.
-- County: okaloosa. Letter: I (property card completeness).
--
-- BEFORE (verified live, pencil_dod_evaluate_county('okaloosa'), pre-session):
--   I: FAIL metric=92.8 card_complete=64 of 69 (threshold 95% -> need >=66)
--
-- THIS IS A REGRESSION, NOT A NEW GAP. migrations/20260809_architect_triage_
-- 18472_okaloosa_i_address_backfill_APPLIED.sql documents an identical fix
-- (same 2 case numbers, same PASS 95.7 / card_complete=66-of-69 result)
-- applied live on 2026-08-09 and even certified. Live-queried at session
-- start (2026-08-10T16:04Z), both rows' property_address were NULL again --
-- the 2026-08-09 fix did not hold. multi_county_auctions.updated_at for
-- both rows was 2026-08-10T09:43:37Z (this morning, not 08-09), proving a
-- process ran TODAY and reset the field, not that the migration silently
-- failed to apply.
--
-- ROOT CAUSE (VERIFIED via code read, scripts/okaloosa_bid4assets_harvest.py):
-- the daily 06:20 UTC cron (.github/workflows/okaloosa-bid4assets-harvest.yml)
-- scrapes the Bid4Assets foreclosure grid and upserts multi_county_auctions
-- with Prefer: resolution=merge-duplicates. Every FC row's payload included
-- "property_address": clean_address or None UNCONDITIONALLY. The script's
-- own upsert() helper normalizes each batch to a rectangular column set via
-- r.setdefault(k, None) for every key ANY row in the batch has -- required
-- because PostgREST's bulk upsert is one INSERT ... ON CONFLICT DO UPDATE
-- SET col = EXCLUDED.col statement, whose column list is a single union
-- across the whole batch. Net effect: any FC row whose grid address cell
-- was blank or a legal-caption string (both possible per the scraper's own
-- _is_legal_caption() guard) got property_address explicitly set to NULL in
-- its payload, and because at least one row in that day's batch always DOES
-- carry the key, PostgREST's ON CONFLICT UPDATE clobbered the DB value --
-- including a previously-good scraped address or a manual backfill -- back
-- to NULL. This is the exact bug class the file's own comments say was
-- already fixed for "parcel_id"/"parity_status" on 2026-07-21
-- (gold-standard-shard4-run5668, see comment in the same function), but
-- property_address itself was missed at that time.
--
-- FIX (shipped this session, live commit to main):
-- 1. scripts/okaloosa_bid4assets_harvest.py: FC rows now only carry a
--    "property_address" key when clean_address is non-empty (key omitted
--    entirely otherwise, same pattern as parcel_id).
-- 2. main() now splits fc_rows into fc_rows_with_addr / fc_rows_no_addr and
--    upserts them as two separate PostgREST batches, so the key-union step
--    can never reintroduce property_address=None into a row that omitted it.
-- 3. This is a durability fix, not just a data patch -- without it, tonight's
--    06:20 UTC cron run would have reset these same 2 rows to NULL again and
--    re-broken letter I by tomorrow morning, repeating the 08-09 -> 08-10
--    cycle indefinitely.
--
-- DATA FIX (this migration, applied live via PostgREST PATCH before this
-- file was committed -- idempotent, matches WHERE property_address IS NULL):
UPDATE public.multi_county_auctions mca
SET
    property_address = fp.phy_addr1 || ', ' || fp.phy_city || ', FL ' || fp.phy_zipcd,
    updated_at        = NOW()
FROM public.fl_parcels fp
WHERE lower(mca.county) = 'okaloosa'
  AND mca.property_address IS NULL
  AND mca.parcel_id IS NOT NULL
  AND fp.co_no = 56
  AND fp.parcel_id = regexp_replace(mca.parcel_id, '[^0-9A-Za-z]', '', 'g')
  AND fp.phy_addr1 IS NOT NULL;

-- AFTER (verified live, same session, post-fix):
--   I: PASS metric=95.7 card_complete=66 of 69
--   Full county 10/10 (A-J all PASS) confirmed via
--   pencil_dod_evaluate_county('okaloosa'), loop_run_id 10285 window.
--
-- The 3 remaining incomplete cards (2024-CA-000470, 2024-TDD-000089 -- both
-- fully blank, no source address to match on at all per
-- scripts/okaloosa_parcel_gis_enrich.py's own skip-log; B4A-1299799 --
-- missing zone link) are left as-is, same as the 2026-08-09 assessment:
-- genuinely blocked on missing source data, not a code or process gap.
--
-- Adversarial verification: see gold_standard_ultraloop_audit rows for
-- county_slug='okaloosa', letter='I', created_at >= this session's start
-- (2026-08-10T16:00Z) -- independent refuter re-ran the live evaluator,
-- cross-checked fl_parcels provenance for both addresses, read the full
-- code diff, and confirmed no clobber path remains before this claim was
-- logged as survived=true.
