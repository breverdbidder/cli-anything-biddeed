-- GOLD STANDARD SHARD-4: madison county — session close-out
-- dispatch_id: 41a3461b-eb27-47b1-95a5-845316deadf2
-- chat_session: architect-20260808T160000
-- loop run: 9805
-- Session date: 2026-08-08
--
-- RESULT: ZERO metric movement. Madison 7/10, unchanged.
-- A/B/F remain genuinely blocked — 7th consecutive session confirmation.
--
-- CONFIRMED BLOCKERS (HONESTY PROTOCOL: VERIFIED per prior sessions):
--   A: madison.realtaxdeed.com — "no properties on the list of tax deeds at this time"
--      Confirmed: 2026-07-10, 07-24, 07-25, 07-31, 08-08. td=0 will not move until
--      Madison County schedules an actual tax deed sale.
--   B: 3 upcoming foreclosure cases, none closed. 2 vanished cases (21-36-CA, 24-62-CA)
--      unreachable — madisonclerk.com/orisearch/40 is JS POST-gated (Cloudflare/CAPTCHA).
--      No independent outcome data source exists.
--   F: Same root cause as B. tier1_sold=0, closed_sold=0.
--
-- PASSING CRITERIA PRESERVED: C=100, D=100, E=100, G=100, H=PASS, I=100, J=100
--
-- No DB writes made to multi_county_auctions, bid_decisions, zoning_*, or outcomes tables.
-- No fabricated data. BLANK > WRONG — this is the honest state.

SET statement_timeout = 0;

-- ── Mandatory session close-out ───────────────────────────────────────────────
-- Per the session brief: write progress to gold_standard_campaign before exit.
--
-- NOTE: This UPDATE targets the dispatch row via the summit_chat_dispatch
-- processing order. If the dispatch_id row is not found (e.g., different table
-- structure), the UPDATE is a no-op and does not corrupt existing data.

UPDATE public.gold_standard_campaign
SET
  criteria_passed = '{
    "A": false,
    "B": false,
    "C": true,
    "D": true,
    "E": true,
    "F": false,
    "G": true,
    "H": true,
    "I": true,
    "J": true
  }'::jsonb,
  criteria_total  = 10,
  exit_reason     = 'timeout',
  session_end_at  = now()
WHERE dispatch_id = '41a3461b-eb27-47b1-95a5-845316deadf2'::uuid;

-- ── Verification evidence (DO NOT execute — SQL comments for audit trail) ────
--
-- Expected output of SELECT public.pencil_dod_evaluate_county('madison'):
-- {
--   "A": {"pass": false, "metric": 0, "detail": "fc=5 td=0"},
--   "B": {"pass": false, "metric": null, "detail": "verified=0 closed_sold=0"},
--   "C": {"pass": true, "metric": 100.0},
--   "D": {"pass": true, "metric": 100.0},
--   "E": {"pass": true, "metric": 100.0},
--   "F": {"pass": false, "metric": null, "detail": "tier1_sold=0 closed_sold=0"},
--   "G": {"pass": true, "metric": 100.0},
--   "H": {"pass": true},
--   "I": {"pass": true, "metric": 100.0},
--   "J": {"pass": true, "metric": 100.0},
--   "auctions_total": 5
-- }
--
-- Why A is blocked: SELECT COUNT(*) FROM multi_county_auctions
--   WHERE county='madison' AND auction_type='tax_deed';
--   → returns 0. madisonclerk.com tax-deed-sales page has no listings.
--   Until Madison schedules an actual tax deed sale, td=0 is correct.
--
-- Why B/F are blocked: SELECT COUNT(*) FROM multi_county_auctions
--   WHERE county='madison' AND sold_amount IS NOT NULL;
--   → returns 0. All 5 madison rows are upcoming/scheduled foreclosures.
--   No closed case outcomes exist in any independent source.

-- ── Escalation record ─────────────────────────────────────────────────────────
-- Per the 2026-07-31 session (dispatch 0f07f453), the remaining lever for B/F
-- is a PHONE CALL to the Madison County Clerk (850-973-1500) to confirm the
-- disposition of the 2 vanished cases (21-36-CA, 24-62-CA).
-- This cannot be automated. Owner action required.
-- Case names: Toby Ray Earnhardt (21-36-CA), Rutha Brown (24-62-CA).
