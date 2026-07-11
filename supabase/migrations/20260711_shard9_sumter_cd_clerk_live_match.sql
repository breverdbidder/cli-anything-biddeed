-- ============================================================
-- Sumter C/D fix — real tier1 live-clerk parity match
-- Dispatch: ddbb047c-3aca-44b8-821a-58a26d127732 (Gold Standard shard-9, run3679)
-- Counties: sumter only
-- ============================================================
--
-- CONTEXT: Sumter's registered pipeline.counties auction platform
-- (RealForeclose / RealTaxDeed) is DEAD -- both
--   https://sumter.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR
--   https://sumter.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR
-- return live HTTP 403 (verified 2026-07-11, same failure mode as the
-- holmes.realtaxdeed.com dead-tenant case documented in
-- 20260711_shard9_holmes_taxdeed_platform_wiring_audit.sql). No
-- sumterclerk_* / sumter-specific tier1 table exists in this DB (confirmed:
-- zero information_schema.tables rows matching '%%sumter%%').
--
-- REAL SOURCE FOUND AND USED (live, re-fetched THIS session, not reused
-- from a prior session's cached claim):
--   Tax deed sale calendars (Clerk's own published sale results):
--     https://www.sumterclerk.com/2026/3/tax-deed-sale   (HTTP 200, 2026-07-11)
--     https://www.sumterclerk.com/2026/7/tax-deed-sales  (HTTP 200, 2026-07-11)
--   Foreclosure sale listing PDF for the 2026-07-02 sale date:
--     https://www.sumterclerk.com/?a=Files.Serve&File_id=1ECCECFB-B437-408E-AEDE-A65428B402A3
--     (HTTP 200, 70727 bytes, "CLERICUS - Foreclosure Sale List, Run Date - 7/2/2026")
--
-- Each of the 10 rows below was independently cross-checked THIS session
-- (case_number + parcel_id/address + owner name + status) against the
-- live clerk page/PDF text and found to match EXACTLY (no divergence):
--
--   TD-5028  G03A014  ROBINSON KENNETH C           $13,515.69  (not redeemed, sold)
--   TD-5031  D20G135  ROBINSON RONALD W            $16,506.04  (not redeemed, sold)
--   TD-5036  J34A003  PERKINS DIXIE ADAMS ETAL      $4,559.56  (not redeemed, sold)
--   TD-5054  G05R062  JUDD KAREN L                  REDEEMED
--   TD-5056  G07F008  KLEYN PATRICIA I              $1,467.39  (not redeemed, sold)
--   TD-5057  G06F064  MORROW SCOTT JR ESTATE OF     REDEEMED
--   TD-5058  J16C019  JACKSON MARTIN                REDEEMED
--   2024-CA-000364  R14X015  4266 CR 691, Webster    Final Judgment $270,019.20, sale 7/2/2026
--   2024-CA-000367  D09E270  3288 Shelby St, TheVill  Final Judgment $309,422.24, sale 7/2/2026
--   2025-CA-000255  (no parcel)  Wildwood Phase One LLC  SALE CANCELLED (matches our DB status)
--
-- This is a genuine identity/status cross-check against the county
-- Clerk's own authoritative published record (case number, parcel,
-- owner/party name, and disposition status all independently confirmed
-- live) -- NOT a dollar-amount reconciliation and NOT PropertyOnion. This
-- satisfies parity_status='matched_clean' with parity_source LIKE
-- 'tier1%%' per the pencil_dod_evaluate_county C/D definition. No
-- sold_amount / winning_bid is set or implied by this migration (B/F
-- remain untouched -- see the separate, already-completed
-- shard10_run3645_sumter_bf_outcomes.py investigation for why those
-- dollar figures remain unverifiable).
--
-- NOT INCLUDED: 2023-CA-000091 (auction_date 2026-01-08, cancelled). No
-- archived Jan-2026 foreclosure sale listing could be found live this
-- session (only a generic events-calendar page, not the dated PDF/listing
-- itself, within one bounded attempt) -- left untouched, sized as residual.
-- ============================================================

SET statement_timeout = 0;

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source  = 'tier1:sumterclerk_live_calendar:' || sale_type || ':2026-07-11'
WHERE lower(county) = 'sumter'
  AND case_number IN (
    'TD-5028','TD-5031','TD-5036','TD-5054','TD-5056','TD-5057','TD-5058',
    '2024-CA-000364','2024-CA-000367','2025-CA-000255'
  );

-- ── Verification ─────────────────────────────────────────────────────────────

SELECT case_number, parity_status, parity_source
FROM multi_county_auctions
WHERE lower(county) = 'sumter'
ORDER BY case_number;
