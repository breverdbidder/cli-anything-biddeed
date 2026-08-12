-- GOLD STANDARD shard-5 (dispatch 5d78eb23): taylor C/D live regression fix.
--
-- ROOT CAUSE (confirmed live, 2026-08-12): 3 taylor foreclosure rows
-- (23-597 CA, 25-210 CA, 26-042 CA) had parity_status='matched_clean' but
-- parity_source='taylor_clerk_foreclosure' -- missing the 'tier1:' prefix
-- that pencil_dod_evaluate_county's C/D filters require to recognize a
-- matched_clean row (see migration 20260810_gold_standard_shard3_lake_
-- clerk_ssot_cd_recognition.sql for the filter definition). These 3 rows
-- were scraped by a generic pass that never ran the tier1 parity-verify
-- step, so taylor C collapsed from 100% (11/11, prior sessions) to 45.5%
-- (5/11) and D from 100% to 72.7% (8/11) once the denominator's true
-- composition was exposed -- NOT because the underlying data was wrong.
--
-- FIX: independently re-verified all 3 rows against taylorclerk.com's own
-- live first-party REST API (wp-json/kma/v1/foreclosures, Civitek-backed,
-- unauthenticated, HTTP 200, no Cloudflare) field-by-field:
--   23-597 CA: our auction_date=2026-10-13, judgment_amount=92079.12
--              vs clerk sale_date="Oct 13, 2026 11:00 am", amount=92079.12 -- exact match
--   25-210 CA: our auction_date=2026-08-27, judgment_amount=463269.10,
--              address="116 Ridge RD, Perry FL 32348"
--              vs clerk sale_date="Aug 27, 2026 11:00 am", amount=463269.10,
--              address="116 Ridge RD, Perry FL 32348" -- exact match
--   26-042 CA: our auction_date=2026-08-27, judgment_amount=897101.35
--              vs clerk sale_date="Aug 27, 2026 11:00 am", amount=897101.35 -- exact match
-- All 3 are genuine clean matches against an independent authoritative
-- source; only the parity_source label was missing the tier1: convention.
-- Re-stamped parity_source (data-only UPDATE, applied live via PostgREST
-- PATCH, mirrored here for repo history) and parity_checked_at=now().
--
-- RESULT: taylor D 72.7%->100.0% (PASS). C 45.5%->72.7% -- still correctly
-- FAIL: the remaining 3-row gap (25-014 CA, TDA 26-031, TDA 26-032) are
-- legitimately clerk-cancelled/redeemed sales, parity_status=
-- CLERK_SSOT_CANCELLED, which by the same Aug-10 migration's explicit
-- design counts toward matched_any (D) but NOT matched_clean (C) -- a
-- cancelled sale is "the same class as matched_divergent, not a
-- no-divergence-ever clean match" per that migration's own comment. This
-- is a structural, by-design floor on C for this county, not a bug.

UPDATE multi_county_auctions
SET parity_source = 'tier1:gold_standard_shard5_desoto_taylor_5d78eb23:taylorclerk.com_kma_v1_foreclosures_live_20260812',
    parity_checked_at = '2026-08-12T08:00:00+00:00'
WHERE county = 'taylor'
  AND case_number IN ('23-597 CA', '25-210 CA', '26-042 CA')
  AND parity_status = 'matched_clean';
