-- GOLD STANDARD shard11, dispatch dd396ee4-e383-45ea-8953-5ad92fb1c1af, county=leon.
-- Re-attempt of the C/D fix that was reverted in commit fd836669 (prior session:
-- "9-row C/D harvest lacked verification metadata and a migration file").
--
-- This migration is the ledger of that verification. Live harvest was re-run in
-- this session against leon.realforeclose.com (foreclosure, dates 2026-07-10,
-- 2026-07-15, 2026-07-20, 2026-07-22) and leon.realtaxdeed.com (tax_deed, date
-- 2026-08-19) via scripts/gold_standard_shard11_leon_cd_i_ajax_harvest.py
-- (which wraps the proven scripts/shard2_run2450_ajax_realforeclose_harvest.py
-- AJAX decoder). All 5 live calendar fetches returned 200 OK with non-zero
-- parsed items (2, 1, 3, 2, 2 respectively -- 8 foreclosure + 2 tax_deed = 10
-- items parsed across the 5 fetches, one date returning 2 items where only 1
-- was a shard target).
--
-- Independent match evidence per row (case_number exact match AND, for 8 of 9
-- rows, exact match on parcel_id/property_address/assessed_value already on
-- file in multi_county_auctions -- i.e. these are not new claims, they are the
-- SAME facts appearing on the live third-party auction calendar, which is what
-- parity is supposed to certify). Each row's parity_source below embeds the
-- distinct RealForeclose/RealTaxDeed internal auction-item id ("aid") returned
-- by the live AJAX endpoint plus the harvest timestamp, so this claim can be
-- independently re-checked by re-querying the same aid.
--
-- Row 9 (case 2025 CA 001324, aid 1507507) parsed successfully for case_number
-- and judgment_amount but the parcel-appraiser-link decode hit a known parser
-- gap (anchor text "Property Appraiser" instead of the parcel number -- see
-- is_real_parcel_id() in the harvest script) so parcel_id/address/value were
-- NOT available from this source and are NOT backfilled for that row. It still
-- gets parity_status='matched_clean' because the case_number match itself is
-- real and independent (this is a C/D fix, not an I fix) -- it will NOT
-- contribute to I.
--
-- SET statement_timeout = 0 per shard11 dispatch heavy-SQL convention.
SET statement_timeout = 0;

-- Foreclosure rows (leon.realforeclose.com), matched 2026-07-10T17:42Z
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard11_run3645_ajax_harvest:foreclosure:2026-07-10:aid1505104:verified2026-07-10T17:42Z'
WHERE county = 'leon' AND case_number = '2025 CA 001966' AND parity_status IS NULL;

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard11_run3645_ajax_harvest:foreclosure:2026-07-15:aid1507117:verified2026-07-10T17:42Z'
WHERE county = 'leon' AND case_number = '2025 CA 002129' AND parity_status IS NULL;

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard11_run3645_ajax_harvest:foreclosure:2026-07-20:aid1503497:verified2026-07-10T17:42Z'
WHERE county = 'leon' AND case_number = '2025 CA 001807' AND parity_status IS NULL;

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard11_run3645_ajax_harvest:foreclosure:2026-07-20:aid1505441:verified2026-07-10T17:42Z'
WHERE county = 'leon' AND case_number = '2024 CA 000319' AND parity_status IS NULL;

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard11_run3645_ajax_harvest:foreclosure:2026-07-20:aid1505596:verified2026-07-10T17:42Z'
WHERE county = 'leon' AND case_number = '2025 CA 000634' AND parity_status IS NULL;

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard11_run3645_ajax_harvest:foreclosure:2026-07-22:aid1507507:verified2026-07-10T17:42Z'
WHERE county = 'leon' AND case_number = '2025 CA 001324' AND parity_status IS NULL;

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard11_run3645_ajax_harvest:foreclosure:2026-07-22:aid1499650:verified2026-07-10T17:42Z'
WHERE county = 'leon' AND case_number = '2025 CA 000765' AND parity_status IS NULL;

-- Tax deed rows (leon.realtaxdeed.com), matched 2026-07-10T17:42Z
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard11_run3645_ajax_harvest:tax_deed:2026-08-19:aid1509809:verified2026-07-10T17:42Z'
WHERE county = 'leon' AND case_number = '16-0785' AND parity_status IS NULL;

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard11_run3645_ajax_harvest:tax_deed:2026-08-19:aid1509808:verified2026-07-10T17:42Z'
WHERE county = 'leon' AND case_number = '14-0367' AND parity_status IS NULL;
