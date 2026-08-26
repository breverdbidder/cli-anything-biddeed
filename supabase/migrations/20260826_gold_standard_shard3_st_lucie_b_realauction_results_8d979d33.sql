-- Gold Standard shard-3, dispatch 8d979d33-c6a4-4c6f-adfe-cd9f700cd117: st_lucie B fix
--
-- DOCUMENTATION-ONLY RECORD. Direct psql/db push is not available in this
-- environment (pooler password auth fails; no exec_sql RPC). All statements
-- below were executed live via PostgREST (see
-- scripts/gold_standard_shard3_st_lucie_bf_realauction_results_8d979d33.py)
-- and are recorded here verbatim for audit trail per repo convention. Do NOT
-- expect this file to be re-applied by `supabase db push`.
--
-- ROOT CAUSE (confirmed live 2026-08-26T16:18 UTC):
--   Since this morning's close-out session (commit 513e64c7, 08:32 UTC,
--   which left st_lucie B at PASS 100.0, verified=2/closed_sold=2), two new
--   rows landed via the realauction_winner_harvest pipeline
--   (sold_amount_source='realauction_bidhistory_modal:st_lucie:2026-08-25'):
--     - 2025CA000041 (1438 SE MARISOL LN, Port St. Lucie) sold_amount=153500.00
--     - 2025CA000119 (1392 SW INGRASSINA AVE, Port St. Lucie) sold_amount=237100.00
--   Neither had a matching independent row in foreclosure_outcomes, so
--   verified_outcomes stayed at 2 while closed_sold rose to 4:
--     B = 2/4 = 50.0%  (FAIL, canon requires 95-105%)
--
-- FIX: fetched stlucie.realforeclose.com's own "Auction Results Report"
--   (report_id=18, the RealAuction platform's post-sale ledger, independent
--   of the pre-sale bidhistory-modal winner harvest that populated
--   sold_amount) via an authenticated session (REALFORECLOSE_EMAIL/
--   REALFORECLOSE_PASSWORD, already available in this environment). Matched
--   by exact case_number; both target cases were confirmed "Sold" in the
--   report with amounts EXACTLY matching our existing sold_amount:
--     2025CA000041: report shows TWO "Sold" entries for this case number --
--       02/17/2026 $179,000.00 (parcel cell "3420-745-0019-000-3") and
--       08/25/2026 $153,500.00 (parcel cell "108540") -- i.e. the case was
--       re-auctioned after an earlier sale. Disambiguated by matching the
--       report's sale_date to our stored auction_date (2026-08-25) rather
--       than picking arbitrarily -- confirmed the $153,500.00 event is the
--       correct match (exact amount + exact parcel_id "108540" match).
--     2025CA000119: single "Sold" entry, 08/25/2026, $237,100.00 -- exact
--       match to our sold_amount.
--
-- INDEPENDENCE: data_source='tier1:realforeclose_results_report:st_lucie' is
--   NOT ILIKE '%promote%', not PropertyOnion-derived, and is a genuinely
--   distinct pipeline stage (RealAuction's own post-sale report backend)
--   from the pre-sale bidhistory-modal scrape that populated sold_amount on
--   multi_county_auctions in the first place.

-- 1) INSERT independent outcome rows (executed via PostgREST POST
--    /rest/v1/foreclosure_outcomes, Prefer: return=minimal):
INSERT INTO public.foreclosure_outcomes
  (case_number, county, sale_type, winning_bid, outcome, auction_status,
   auction_date, data_source, source_url, enriched_at)
VALUES
  ('2025CA000041', 'st_lucie', 'foreclosure', 153500.00, 'SOLD', 'Sold',
   '2026-08-25', 'tier1:realforeclose_results_report:st_lucie',
   'https://stlucie.realforeclose.com/index.cfm?Zaction=admin&Zmethod=REPORT&report_id=18',
   '2026-08-26T16:20:09Z'),
  ('2025CA000119', 'st_lucie', 'foreclosure', 237100.00, 'SOLD', 'Sold',
   '2026-08-25', 'tier1:realforeclose_results_report:st_lucie',
   'https://stlucie.realforeclose.com/index.cfm?Zaction=admin&Zmethod=REPORT&report_id=18',
   '2026-08-26T16:20:09Z');

-- 2) PATCH multi_county_auctions to mark tier1_authoritative confirmation
--    for the 3 matched rows (report round-trip re-confirmed all 3
--    closed_sold foreclosure rows that appear in the results report; the
--    4th, 2025CA000393, already had an independent outcome row from a prior
--    session and does not appear in this report's live date-range window):
UPDATE public.multi_county_auctions
SET tier1_sold_amount = 261100.00, tier1_sale_status = 'sold',
    tier1_authoritative = true, tier1_verified_at = '2026-08-26T16:20:09Z'
WHERE id = '4e6894d9-c36d-4233-8579-6ba98b5c7bb7'; -- 2025CA001029

UPDATE public.multi_county_auctions
SET tier1_sold_amount = 153500.00, tier1_sale_status = 'sold',
    tier1_authoritative = true, tier1_verified_at = '2026-08-26T16:20:09Z'
WHERE id = '60710531-4238-4414-8342-b99ae3c13224'; -- 2025CA000041

UPDATE public.multi_county_auctions
SET tier1_sold_amount = 237100.00, tier1_sale_status = 'sold',
    tier1_authoritative = true, tier1_verified_at = '2026-08-26T16:20:09Z'
WHERE id = '8398084f-e7aa-4834-84ae-812522fdc048'; -- 2025CA000119

-- SQL VERIFICATION
-- SELECT public.pencil_dod_evaluate_county('st_lucie');
-- BEFORE (2026-08-26T16:18:49Z, live):
--   {"B":{"pass":false,"metric":50.0,"detail":"verified=2 closed_sold=4"},
--    "C":{"pass":false,"metric":77.3,"detail":"matched_clean=187"},
--    "auctions_total":242}
-- AFTER (2026-08-26T16:20:10Z, live):
--   {"A":{"pass":true,"metric":120,"detail":"fc=120 td=122"},
--    "B":{"pass":true,"metric":100.0,"detail":"verified=4 closed_sold=4"},
--    "C":{"pass":false,"metric":77.3,"detail":"matched_clean=187"},
--    "D":{"pass":true,"metric":96.3,"detail":"matched_any=233"},
--    "E":{"pass":true,"metric":97.1,"detail":"parcel_linked=235"},
--    "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=4 closed_sold=4"},
--    "G":{"pass":true,"metric":97.1,"detail":"density=97.1"},
--    "H":{"pass":true,"metric":0.0,"detail":"hours since last_seen (SLA 48h)"},
--    "I":{"pass":true,"metric":96.3,"detail":"card_complete=233 of 242"},
--    "J":{"pass":true,"metric":100.0,"detail":"deal_complete=242"},
--    "county":"st_lucie","auctions_total":242}
--
-- Result: st_lucie 8/10 -> 9/10 (B fixed FAIL 50.0 -> PASS 100.0). No
-- regressions on A/D/E/F/G/H/I/J.

-- ============================================================================
-- LETTER C: RECONFIRMED STRUCTURAL (no fix attempted, no data-fixable gap)
-- ============================================================================
-- Live parity_status breakdown for st_lucie (242 rows, 2026-08-26T16:25 UTC):
--   matched_clean            123
--   PARITY_OK                 64   } C numerator = 187 (matches evaluator's
--                                    matched_clean=187 exactly)
--   CLERK_SSOT_CANCELLED       45  -- real, county-verified cancelled tax-deed
--                                     sales (case format 26-NNN, auction_status
--                                     ='CANCELLED' on every one sampled).
--                                     Counts toward D's numerator (matched_any)
--                                     but is DELIBERATELY excluded from C's
--                                     numerator by the evaluator's own
--                                     documented formula (matched_clean
--                                     definition does not include
--                                     CLERK_SSOT_CANCELLED).
--   matched_divergent           1  -- case 2025CA001832: RealForeclose's own
--                                     Auction Results Report lists this case
--                                     under parcel cell "MULTIPLE PARCELS"
--                                     (confirmed live 2026-08-26 -- sold
--                                     07/22/2026 for $290,100.00, winner
--                                     "IBANEZ, JESUS A", matching our stored
--                                     winning_bidder/auction_date exactly).
--                                     Our schema stores one parcel_id per row
--                                     (24840); the case genuinely spans
--                                     multiple parcels per the county's own
--                                     platform. This was deliberately marked
--                                     matched_divergent (not matched_clean) on
--                                     2026-07-18 (scripts/apply_shard11_run4870_
--                                     real_fixes.py) specifically because of
--                                     this real single-vs-multi-parcel
--                                     conflict -- re-verified today via a
--                                     fresh live report fetch, still correct.
--                                     Forcing this to matched_clean/PARITY_OK
--                                     would fabricate a "clean" status on a
--                                     case with a known, real data-model
--                                     mismatch -- refused per guardrail #2.
--   NULL                         9  -- all 9 are genuinely FUTURE auctions
--                                     (auction_date 2026-09-01 / 09-09 / 09-15,
--                                     auction_status='upcoming', all in the
--                                     future relative to session date
--                                     2026-08-26). No clerk/RealAuction result
--                                     can exist yet for a scheduled auction --
--                                     not a data gap, a timing fact.
--
-- CEILING MATH (worked live this session, a fresh angle vs. the 08:32 UTC
-- close-out's "live acclaim cross-check of all 44 cancelled cases"):
--   Current C numerator:                         123 + 64       = 187 (77.3%)
--   Max achievable if ALL 9 future rows resolve
--     clean once their auctions occur (best case,
--     cannot be forced today) and the 1 divergent
--     row is left correctly classified:           123 + 64 + 9  = 196 (81.0%)
--   C pass bar (>=95% of 242):                                    230 (95.0%)
--   Gap even in the best-case future scenario: 230 - 196 = 34 rows short.
--
-- The 45 CLERK_SSOT_CANCELLED rows are the actual ceiling: they are real,
-- clerk-verified cancellations (re-confirmed structurally correct this
-- session via live report cross-check of the one ambiguous case), and the
-- evaluator's own C formula (by design) does not count them toward
-- matched_clean while they remain in the shared 242-row denominator. This is
-- the 8th+ independent session to reach this exact structural conclusion
-- (see commits 433fb7fa, 9d96d950, 74ec5289, 8b604627, a64bd476, and
-- 513e64c7 earlier today). No further per-county C work is recommended on
-- st_lucie without a canon-level change to the C formula (e.g. whether
-- CLERK_SSOT_CANCELLED should be excluded from the denominator, not just the
-- numerator).
