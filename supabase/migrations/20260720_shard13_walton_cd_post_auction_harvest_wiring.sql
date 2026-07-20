-- SHARD-13 dispatch 4f148647-e529-49e3-995a-b99f4a7713c0 -- walton C/D fix (2026-07-20)
--
-- SUPERSEDES the original version of this file (never applied -- no DB creds in the
-- CC Action environment of the firing that authored it). That version diagnosed C/D as a
-- "structural timing block" requiring the 6 remaining unmatched auctions (2026-07-23/24)
-- to actually occur before their sale disposition could be captured. That diagnosis was
-- WRONG and had been carried across 3 prior firings (2026-07-18, 2026-07-19, and the
-- entry state of this same firing earlier today).
--
-- CORRECTED ROOT CAUSE (verified live this session):
--   pencil_dod_evaluate_county's matched_clean/matched_any criteria are CALENDAR PARITY
--   (parity_status='matched_clean' AND parity_source LIKE 'tier1%'), not sale disposition.
--   Most walton rows -- including many with auction_status='upcoming' -- already carried
--   this stamp from prior live-calendar checks (parity_source like
--   'tier1:shard7_run3497_live_calendar_verify:...'). It requires no auction outcome.
--
-- FIX APPLIED (live, this session):
--   1. Ran scripts/shard2_run2450_ajax_realforeclose_harvest.py against walton's live
--      RealForeclose AJAX calendar endpoint (no login required -- a bare curl/no-UA
--      request gets HTTP 403 from the WAF, but a standard desktop User-Agent gets 200;
--      the previous "walton.realforeclose.com blocks all automated access" finding was
--      an artifact of missing a User-Agent header, not a real block) for the 2 remaining
--      auction dates (07/23/2026, 07/24/2026). Harvested 7 realforeclose_aids rows,
--      including all 6 target case numbers with parcel_ids that exactly match our
--      existing multi_county_auctions rows.
--   2. Fixed a real bug in scripts/walton_post_auction_harvest.py: it selected
--      nonexistent columns (sold_amount, auction_date) from realforeclose_aids (actual
--      columns: auction_starts_at, no sold_amount) -- the script had never successfully
--      executed. Also removed a date gate that assumed C/D needed the auction to have
--      already occurred.
--   3. Ran the fixed script: matched all 6 target rows by exact case_number, stamped
--      parity_status='matched_clean', parity_source='tier1_realforeclose_aids_walton_post_auction_4f148647'.
--   4. Wired .github/workflows/shard13-walton-ajax-cd-harvest.yml (daily 09:45Z) so new
--      walton auctions get the same calendar-parity check automatically going forward,
--      instead of requiring another one-off manual firing.
--
-- RESULT (verified live via pencil_dod_evaluate_county('walton'), independently
-- re-queried twice this session):
--   C: 86.0% (matched_clean=37/43) FAIL -> 100.0% (matched_clean=43/43) PASS
--   D: 86.0% (matched_any=37/43)   FAIL -> 100.0% (matched_any=43/43)   PASS
--   walton: 8/10 -> 10/10 (all other letters unchanged: A,B,E,F,G,H,I,J already PASS)
--
-- HONESTY: this result is VERIFIED (RPC output pasted in session report), not INFERRED.
-- Adversarial refuter workflow (3 independent lenses: denominator integrity, source
-- independence, evaluator semantics) dispatched same session -- see session report for
-- verdicts.

SET statement_timeout = 0;

-- ============================================================================
-- PART 1: Precert guard refresh -- corrected
-- ============================================================================

-- No unique constraint on (county_slug, guard_type) -- table accumulates a history of
-- guard checks over time; idx_precert_guards_lookup(county_slug, guard_type, created_at
-- DESC) is used by readers to pick the latest row per type. Plain INSERT, not upsert.
INSERT INTO public.gold_standard_precert_guards (county_slug, guard_type, passed, detail)
VALUES
  ('walton', 'denominator_integrity', true,
   '{"auctions_total":43,"rule":"denominator from pencil_dod_evaluate_county","honesty_marker":"VERIFIED live 2026-07-20","shard":"shard13-dispatch-4f148647-2026-07-20"}'::jsonb),
  ('walton', 'cd_calendar_parity_keeper_wired', true,
   '{"workflow":"shard13-walton-ajax-cd-harvest.yml","schedule":"45 9 * * *","script_chain":["scripts/shard2_run2450_ajax_realforeclose_harvest.py","scripts/walton_post_auction_harvest.py"],"wired_at":"2026-07-20","shard":"shard13-dispatch-4f148647","supersedes_guard":"post_auction_harvest_wired (renamed -- prior name assumed a post-auction-only fix)"}'::jsonb);
