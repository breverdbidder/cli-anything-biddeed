-- GOLD STANDARD escambia fixer session (2026-07-11): C/D tax-deed lane matcher.
--
-- CONFIRMED (VERIFIED live this session): escambia had 331 in-scope rows, 255
-- matched_clean (all FORECLOSURE lane) + 76 tax_deed rows with parity_status IS NULL
-- (auction_date spanning 2026-08-05..2026-12-02, 5 distinct future dates). No tier1
-- matcher had ever run against escambia.realtaxdeed.com (tax deed lane) for these rows.
--
-- Probed escambia.realtaxdeed.com live via the shared harvest_date_paginated() AJAX
-- helper (scripts/shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py) for all 5
-- target dates: got 60-61 live AITEM records per date (301 unique live tax-deed cases
-- total across the 5 dates), all real (case_number/parcel_id/auction_type=TAXDEED/
-- property_address/assessed_value populated). The calendar IS live and populated -- not
-- a structurally dead site.
--
-- Exact-match (case_number, normalized) against the 76 gap rows: only 3 matched --
-- 20f85b0a-1112-44ac-9d23-a4b74da38fe7 (case 2024 TD 003732, 2026-10-07) and
-- da2a548a-c47c-48f2-bc2b-3ab481eff60f (case 2024 TD 004756, 2026-10-07) and
-- 1279f88c-b9d0-466a-b95e-829b2deade2c (case 2024 TD 005012, 2026-12-02).
-- These 3 rows are promoted below via UPDATE mirroring the REST PATCH already executed
-- live via scripts/shard_escambia_cd_taxdeed_fix.py (this migration is the durable
-- record of that same write, idempotent via the WHERE guard).
--
-- HONEST GAP REPORT (checked, not invented): the remaining 73 of 76 gap rows were
-- checked against ALL 301 unique live case_numbers AND all live parcel_ids across the
-- 5 target dates -- ZERO overlap on either key. These specific TD case numbers
-- (e.g. 2024 TD 001944, 2024 TD 002003, ...) and their parcel_ids simply do not appear
-- anywhere on escambia.realtaxdeed.com's live calendar today. This is NOT a matcher bug
-- (the matcher successfully harvests and matches when a real live counterpart exists --
-- proof: the 3 promotions above, plus 221 pre-existing tax_deed matches from a prior
-- session's matcher). The 73 remaining rows are a genuine, currently-unmatchable gap --
-- likely cases that were pulled/redeemed/rescheduled off the county's TD calendar
-- between when our sweep first captured them and now. Per the SHIP GATE NEVER-LIE rule,
-- these are NOT forced to matched_clean. C/D moves from 255/331 (77.0%) to 258/331
-- (77.9%) -- real, but still short of the 95% target. Deferred: re-run this same
-- matcher periodically as escambia.realtaxdeed.com's calendar updates closer to each
-- auction date; TD calendars are commonly finalized only 1-3 weeks before the sale.

BEGIN;

UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1_realtaxdeed_escambia',
    parity_checked_at = now()
WHERE lower(county) = 'escambia'
  AND sale_type = 'tax_deed'
  AND parity_status IS NULL
  AND id IN (
    '20f85b0a-1112-44ac-9d23-a4b74da38fe7',
    'da2a548a-c47c-48f2-bc2b-3ab481eff60f',
    '1279f88c-b9d0-466a-b95e-829b2deade2c'
  );

COMMIT;
