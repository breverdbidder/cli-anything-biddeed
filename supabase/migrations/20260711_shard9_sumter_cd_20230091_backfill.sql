-- ============================================================
-- Sumter C/D fix — 2023-CA-000091 tier1 live-clerk parity match
-- Dispatch: ddbb047c-3aca-44b8-821a-58a26d127732 (Gold Standard shard-9, run3679)
-- Counties: sumter only
-- ============================================================
--
-- CONTEXT: a prior session's migration
-- (20260711_shard9_sumter_cd_clerk_live_match.sql, commit 5becdf0f) set
-- parity_status='matched_clean' + parity_source LIKE 'tier1%%' for 10 of 11
-- sumter rows, deliberately EXCLUDING 2023-CA-000091 (auction_date
-- 2026-01-08, cancelled foreclosure) because "no archived Jan-2026
-- foreclosure sale listing could be found live this session" at that time.
-- This left C/D at matched_clean=10 of 11 = 90.9% (fail, needs >=95%).
--
-- THIS SESSION: re-attempted live and found the source. The row's own
-- pre-existing source_url field (populated by an even earlier scrape)
-- points to the exact per-sale-date PDF listing, which is STILL live:
--
--   https://www.sumterclerk.com/index.cfm?a=Files.Serve&File_id=5FABE843-72E7-4A6C-81F2-1401CB098DA0
--   (HTTP 200 via redirect, 66749 bytes, PDF, fetched live 2026-07-11)
--   "SUMTER COUNTY CIRCUIT CIVIL FORECLOSURE SALE LISTING SALE DATE: 01/08/2026"
--   "CLERICUS - Foreclosure Sale List Pg -1  Run Date - 1/6/2026"
--
-- Extracted text confirms EXACT match to our DB row on every field:
--   Case Number:      2023-CA-000091            (matches)
--   Plaintiff:         Wilmington Savings Fund Society  (matches)
--   Defendant/Owner:   VOORMAN, CECILIA A         (matches owner_name)
--   Amt of Final Judgment: $292,243.05            (matches judgment_amount)
--   Address:           2621 CARIBE DR, THE VILLAGE, FL 32162  (matches)
--   Status:            SALE CANCELLED             (matches auction_status='cancelled')
--
-- This is the identical genuine identity/status cross-check pattern used
-- for the other 10 rows (case number, party names, amount, address, and
-- disposition status independently confirmed live against the Clerk's own
-- authoritative published record) -- not a dollar-amount reconciliation
-- and not PropertyOnion. Satisfies parity_status='matched_clean' with
-- parity_source LIKE 'tier1%%' per the pencil_dod_evaluate_county C/D
-- definition.
--
-- NOTE: this row also carries parity_scope='archive_no_source_truth' and
-- is_operational=false from a prior session's housekeeping pass (marking
-- it as an old/archived case). We do NOT clear those flags here -- they
-- are orthogonal to parity_status/parity_source and the C/D SQL definition
-- does not filter on parity_scope or is_operational, only on
-- parity_status/parity_source. Leaving them as-is.
-- ============================================================

SET statement_timeout = 0;

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source  = 'tier1:sumterclerk_live_calendar:foreclosure:2026-07-11'
WHERE lower(county) = 'sumter'
  AND case_number = '2023-CA-000091';

-- ── Verification ─────────────────────────────────────────────────────────────

SELECT case_number, parity_status, parity_source
FROM multi_county_auctions
WHERE lower(county) = 'sumter'
ORDER BY case_number;
