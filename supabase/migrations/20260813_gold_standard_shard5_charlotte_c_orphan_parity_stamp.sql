-- Gold Standard: Charlotte County, letter C (parity clean-match rate)
-- Session: 2026-08-13
--
-- STARTING STATE (verified live via pencil_dod_evaluate_county('charlotte')):
--   C: FAIL, metric=88.8%, matched_clean=158 of auctions_total=178
--   Threshold to PASS: >=95% (169 rows)
--
-- PARITY_STATUS BREAKDOWN (verified live, county='charlotte'):
--   matched_clean         : 158
--   CLERK_SSOT_CANCELLED  : 17   (genuinely cancelled/redeemed per Charlotte Clerk
--                                 SSOT -- counts toward matched_any/D, never eligible
--                                 for matched_clean/C by definition)
--   NULL (never stamped)  : 3    (case_number 25001313CA, 25001661CA, 24001026CA)
--
-- ROOT CAUSE of the 3 NULL rows: verified live these are all tier1_authoritative=true,
-- sale_type='foreclosure', sold_amount IS NULL rows that were never run through the
-- parity-stamping step. Peer charlotte rows with the same shape (sold_amount NULL,
-- auction_status in upcoming/completed/sold) are routinely stamped matched_clean via
-- a live AJAX harvest against charlotte.realforeclose.com (RealAuction platform),
-- exact-case-number match -- see scripts/shard8_charlotte_litmus_run.py and
-- scripts/shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py
-- (harvest_date_paginated + exact_match_and_promote), which this migration re-runs
-- by hand for exactly these 3 orphan rows.
--
-- LIVE VERIFICATION (this session, 2026-08-13): ran harvest_date_paginated() against
-- charlotte.realforeclose.com for auction dates 08/12/2026 and 08/13/2026 (the two
-- dates these 3 rows fall on). All 3 case numbers were found live on the official
-- RealAuction calendar with parcel_id exactly matching our DB record:
--
--   case_number | auction_date | live parcel_id | db parcel_id | match
--   24001026CA  | 08/13/2026   | 412002411019   | 412002411019 | MATCH
--   25001313CA  | 08/12/2026   | 402213280004   | 402213280004 | MATCH
--   25001661CA  | 08/13/2026   | 402210303005   | 402210303005 | MATCH
--
-- No divergence found for any of the 3 -- each is a genuine active/recently-completed
-- foreclosure auction on the county's own calendar, not a phantom or mismatched row.
-- Stamped matched_clean per the same convention used by every other charlotte row
-- that clears parity via live-calendar confirmation rather than a literal
-- sold-amount comparison (verified other charlotte matched_clean rows routinely
-- carry sold_amount IS NULL, e.g. case_number 24000008CC, 24001356CC, 24001604CC).
--
-- STRUCTURAL CEILING FINDING (evidence, not an evaluator change):
--   auctions_total              = 178
--   CLERK_SSOT_CANCELLED (fixed)= 17   (never eligible for matched_clean by definition
--                                        -- a cancelled auction was never a clean
--                                        sale-amount/calendar match)
--   max possible matched_clean  = 178 - 17 = 161
--   max possible C metric       = 161 / 178 = 90.4%
--   PASS threshold              = 95.0% (169 rows)
--   => Charlotte C CANNOT reach PASS under the current evaluator definition, no
--      matter how many of the remaining rows are correctly parity-stamped, unless
--      the evaluator's auctions_total denominator is redefined to exclude rows that
--      are structurally cancelled (a canon/evaluator-definition question, explicitly
--      OUT OF SCOPE for this migration -- pencil_dod_evaluate_county is a read-only
--      guardrail per CLAUDE.md gold-standard brief and was NOT modified).
--
-- This migration only fixes the 3 orphan rows (158 -> 161 matched_clean). It does
-- NOT and cannot flip C to PASS; that is an honest, expected outcome given the
-- structural ceiling above.

BEGIN;

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:charlotte_realforeclose_live_recheck_20260813:ch_CD_orphan_fix'
WHERE county = 'charlotte'
  AND case_number = '24001026CA'
  AND parity_status IS NULL;

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:charlotte_realforeclose_live_recheck_20260813:ch_CD_orphan_fix'
WHERE county = 'charlotte'
  AND case_number = '25001313CA'
  AND parity_status IS NULL;

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:charlotte_realforeclose_live_recheck_20260813:ch_CD_orphan_fix'
WHERE county = 'charlotte'
  AND case_number = '25001661CA'
  AND parity_status IS NULL;

COMMIT;
