-- SHARD-2, issue 17097, dispatch 83c11ccb-424b-4b3b-822b-909c6e8fccaa
-- Session: architect-20260731T160000
-- Counties: calhoun (8/10) + miami_dade (C/D/I fix)
--
-- ============================================================================
-- CALHOUN (8/10 — B/F structurally blocked, no action taken)
-- ============================================================================
-- BEFORE (brief baseline):
--   A PASS fc=2 td=6 | B FAIL null (verified=0 closed_sold=0)
--   C PASS 100.0 | D PASS 100.0 | E PASS 100.0 | F FAIL null (tier1_sold=0 closed_sold=0)
--   G PASS 100.0 | H PASS | I PASS 100.0 (card_complete=8 of 8)
--   J PASS 100.0 (deal_complete=8)
--
-- DIAGNOSIS: B/F remain genuinely blocked. All prior sessions (d0d45cbc 1st and
-- 2nd firings) confirmed exhaustively:
--   - calhounclerk.com WP REST API (/wp-json/wp/v2/{foreclosures,taxdeeds,taxdeedoverbids})
--     shows 0 rows with auction_status='sold' or equivalent
--   - tax_deed_overbid surplus list: 39 records, none matching calhoun's 8 cert numbers
--   - foreclosure_outcomes: 1 row, status='scheduled', winning_bid=null
--   - tax_deed_outcomes: 0 rows for calhoun
--
-- The brief shows td=6 vs the 2nd-firing report's td=5 — one new tax deed ingested
-- by the daily cron (calhoun-clerk-harvest.yml, 05:45 UTC). The harvester is healthy.
-- A/C/D/E/G/I/J all continue to PASS. B/F blocked until county posts a sale outcome.
--
-- ACTION: None. Confirmed via calhoun_clerk_harvest.py's mark_closed_from_overbids()
-- cross-reference — the existing daily cron auto-resolves B/F the moment a sale
-- closes (overbid entry proves closure under FL Stat 197.582). No manual session
-- time spent on a genuinely data-blocked criterion.
--
-- ULTRALOOP ENTRY (calhoun B/F blocked claim):
INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim,
   refuter_evidence, survived, created_at)
VALUES
  ('83c11ccb-424b-4b3b-822b-909c6e8fccaa', 'fallback', 'calhoun', 'B',
   'B/F remain null-metric because no calhoun auction has closed as of 2026-07-31; '
   'the 06-taxdeedoverbids API cross-reference in the daily cron will auto-resolve '
   'when the first sale posts',
   '{"evidence": "calhounclerk.com WP REST: foreclosures=2 rows status=scheduled/cancelled, taxdeeds=6 rows status=scheduled/cancelled; taxdeedoverbids: 39 records, 0 matching calhoun cert numbers. foreclosure_outcomes: 1 row status=scheduled winning_bid=null. tax_deed_outcomes: 0 rows for calhoun.", "prior_sessions": "d0d45cbc 1st and 2nd firings both confirmed same finding", "resolution": "SURVIVED -- B/F blocked by real-world data, not pipeline bug"}'::jsonb,
   true,
   now()
),
  ('83c11ccb-424b-4b3b-822b-909c6e8fccaa', 'fallback', 'calhoun', 'F',
   'F null-metric is same root cause as B -- no tier1 sold-amount exists because no sale has closed',
   '{"evidence": "Same as B: all 8 calhoun rows have tier1_sold_amount=null, tier1_sale_status not sold", "resolution": "SURVIVED"}'::jsonb,
   true,
   now()
)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- MIAMI-DADE (C/D/I AJAX harvest for new 66-row population)
-- ============================================================================
-- BEFORE (brief baseline, run 7726):
--   A PASS fc=311 td=111 | B PASS 100.0 (verified=5 closed_sold=5)
--   C FAIL 94.3% (matched_clean=398) | D FAIL 94.3% (matched_any=398)
--   E PASS 96.9% (parcel_linked=409) | F PASS 100.0 (tier1_sold=5 closed_sold=5)
--   G PASS 99.3% (density=99.3 far=100.0) | H PASS 0.1h
--   I FAIL 80.1% (card_complete=338 of 422) | J PASS 100.0 (deal_complete=422)
--
-- NOTE: Denominator grew from 356 (run3786, 2026-07-11) to 422 (current) —
-- 66 new auctions ingested by the pipeline since last session. These 66 new rows
-- are the primary source of the C/D drop from 94.9% to 94.3%, and the I drop
-- from 96.1% to 80.1%. They need parity matching and card backfill.
--
-- ACTION: scripts/shard2_17097_miami_dade_cd_i_harvest.py sweeps the AJAX calendar
-- for all unmatched (sale_type, auction_date) pairs via harvest_date() from
-- scripts/shard2_run2450_ajax_realforeclose_harvest.py. On case_number match:
--   - parity_status='matched_clean', parity_source='tier1:shard2_17097_83c11ccb_ajax_harvest:...'
--   - backfill parcel_id/property_address/assessed_value where null
--
-- The 12 residual cases from run3786 (exhaustively checked, genuinely UNKNOWN) are
-- left untouched — they were already swept across 60+ weeks × 2 platforms with zero
-- hits. Targeting new rows only; no re-sweep of known-UNKNOWN cases.
--
-- This migration is a record of the session; actual DB writes are applied live via
-- scripts/shard2_17097_miami_dade_cd_i_harvest.py + PostgREST.
-- Actual before/after pencil_dod_evaluate_county output is in the GitHub issue comment.

SELECT 1; -- no-op placeholder: live writes applied by the harvest script above

-- ============================================================================
-- SESSION CLOSE-OUT: gold_standard_campaign checkpoint
-- ============================================================================
-- Per mandatory close-out protocol: update the campaign row with A-J status
-- based on the brief's baseline (will be refreshed by gold_standard_loop after session).
UPDATE public.gold_standard_campaign
SET
  criteria_passed = jsonb_build_object(
    'A', true, 'B', false, 'C', false, 'D', false,
    'E', true, 'F', false, 'G', true, 'H', true,
    'I', false, 'J', true
  ),
  criteria_total = 10,
  exit_reason = 'timeout',
  session_end_at = now()
WHERE county_slug = 'calhoun'
  AND dispatch_id = '83c11ccb-424b-4b3b-822b-909c6e8fccaa';

UPDATE public.gold_standard_campaign
SET
  criteria_passed = jsonb_build_object(
    'A', true, 'B', true, 'C', false, 'D', false,
    'E', true, 'F', true, 'G', true, 'H', true,
    'I', false, 'J', true
  ),
  criteria_total = 10,
  exit_reason = 'timeout',
  session_end_at = now()
WHERE county_slug = 'miami_dade'
  AND dispatch_id = '83c11ccb-424b-4b3b-822b-909c6e8fccaa';
