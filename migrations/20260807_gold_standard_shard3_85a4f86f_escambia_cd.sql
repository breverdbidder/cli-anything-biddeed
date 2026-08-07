-- GOLD STANDARD shard-3 (dispatch 85a4f86f-993f-40c0-9095-47ac8d01a6e5) — escambia C/D
-- Distinguished a FRESH batch of 55 NULL-parity rows (created 2026-08-05/06, last_seen
-- 2026-08-07) from the already-documented-and-deferred 64-row batch in
-- migrations/20260705_escambia_cd_parity.sql (shared last_seen_at=2026-07-04T15:27:25Z).
-- The fresh batch is 2 new foreclosure cases (auction 2026-08-18) and 53 new tax_deed cases
-- (auction 2027-01-06) that simply had never been run through the existing parity matcher —
-- realforeclose_aids for escambia was last scraped 2026-07-29, stale relative to these
-- newly-listed auctions.
--
-- No new SQL/function needed — public.refresh_escambia_parity_v1() (unmodified, from the
-- 20260705 migration) already implements the correct case-number-then-parcel_id join; it
-- just needed fresh source data in realforeclose_aids. Live-harvested both dates, then re-ran
-- the function.
--
-- 20 tax_deed rows remain deferred: exhaustively checked (max_pages=60) against all 6
-- currently-exposed live realtaxdeed.com auction dates and confirmed genuinely absent —
-- same redemption/withdrawal pattern documented for the original 64. Not required for PASS.
--
-- Result (adversarially verified): C/D 87.9% -> 95.6%, PASS.

-- Executed live (not re-runnable from this file alone — requires live network harvest):
--   python3 scripts/realforeclose_aids_paginated_harvest.py escambia realforeclose.com escambia 08/18/2026
--   python3 scripts/realforeclose_aids_paginated_harvest.py escambia realtaxdeed.com escambia 01/06/2027
-- Harvest result: foreclosure parsed=4 inserted=4; tax_deed parsed=60 inserted=60.

SET statement_timeout = 0;

SELECT * FROM public.refresh_escambia_parity_v1();
-- Result: (case_number, 35 rows_updated), (parcel_id, 0 rows_updated)
