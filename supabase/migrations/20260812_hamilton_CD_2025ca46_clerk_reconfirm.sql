-- Hamilton C/D fix: 2025-CA-46 is live on hamiltonclerk.com/foreclosures/ today,
-- was mis-flagged PHANTOM_NOT_ON_CLERK from a stale 2026-07-18 check.
-- Live re-verification 2026-08-12 confirms 1:1 match to existing DB row:
--   Case No. 2025-CA-46; NewRez LLC vs. Allen Murphy, et al.
--   Judgment amount: $609,173.11
--   Property address: 520 NW Rodman LN, Jennings, FL 32053
--   DATE OF SALE – AUGUST 12, 2026 (matches auction_date)
-- Source: https://hamiltonclerk.com/foreclosures/ (HTTP 200, no Turnstile),
-- fetched live 2026-08-12T08:22Z.
--
-- Scope: hamilton county only, single row by id. Does not touch cron jobs
-- 109/111/115 or gold-standard-loop-* scoring jobs.
--
-- Impact: C/D move 16/21 (76.2%) -> 17/21 (81.0%). Does NOT clear >=95% gate.
-- Remaining 4 rows (2021-CA-46, 2023-CA-41, 2024-CA-19, 2025-CA-37) stay
-- BLOCKED — zero live evidence on hamiltonclerk.com as of 2026-08-12,
-- Firecrawl account exhausted (-10/1000 credits, HTTP 402 confirmed live),
-- myfloridacounty ORI query step remains Turnstile/session-token gated.
--
-- ADVERSARIAL VERIFY NOTE (gold_standard_ultraloop_audit ids 14891/14892,
-- survived=true, dispatch a1884f7f): the refuter independently confirmed
-- these numbers today, but flagged that migration 20260810_..._216c5868_
-- hamilton.sql (2 days prior) already documents a C/D baseline of 17/21
-- with the SAME 4 residual cases listed here — implying 2025-CA-46 may
-- already have been matched_clean on 2026-08-10 and this "fix" re-derives
-- a state already reached, rather than discovering something new. No
-- audit-log table exists to prove whether the 08-10 baseline was wrong or
-- 2025-CA-46 silently regressed since. Flagging for the next session to
-- investigate — not a correctness issue with today's write, which is
-- independently confirmed accurate against the live clerk source.

UPDATE public.multi_county_auctions
SET
  parity_status = 'matched_clean',
  parity_checked_at = '2026-08-12T08:22:49Z',
  parity_source = 'tier1:hamilton_gold_standard_20260812_live_reharvest:foreclosure:2026-08-12'
WHERE id = 'd355fc2e-be22-4fe2-b9df-689105f93411'
  AND county = 'hamilton'
  AND case_number = '2025-CA-46';
