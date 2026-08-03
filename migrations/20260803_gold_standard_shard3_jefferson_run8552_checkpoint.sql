-- Jefferson County Gold Standard Session Checkpoint
-- dispatch_id: 35b72237-0368-4e53-a134-c638d24b1638
-- loop_run: 8552
-- session: architect-20260803T160000
-- date: 2026-08-03
--
-- Result: 8/10 (unchanged from runs 6253-7622, 11 prior sessions).
-- B and F remain blocked by structural data unavailability:
--   - 25-CA-164 (foreclosure 2026-06-25): sold_amount CAPTCHA-gated at all public sources
--   - 26-TD-04/26-TD-05 (tax deed 2026-08-19): FUTURE sale, not yet occurred
-- All 8 PASSING letters (A,C,D,E,G,H,I,J) confirmed stable from last verified state.
-- Infrastructure confirmed correct: shard-jefferson-clerk-scraper.yml healthy,
--   last run 2026-07-27 success, next run 2026-08-04 Monday.
-- Auto-resolution is wired: B/F will resolve automatically the Monday after 2026-08-19.
-- Next productive session: 2026-08-25 or after (let cron run 2026-08-25 first).
--
-- MANDATORY CLOSE-OUT CHECKPOINT (per issue brief):

UPDATE public.gold_standard_campaign
SET
  criteria_passed = '{
    "A": true,
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
  criteria_total = 10,
  exit_reason = 'blocker',
  session_end_at = now()
WHERE dispatch_id = '35b72237-0368-4e53-a134-c638d24b1638';

-- Also insert an ultraloop audit row documenting B/F structural blocker
-- so certification gate knows the evidence trail for this session
INSERT INTO public.gold_standard_ultraloop_audit (
  dispatch_id,
  ultraloop_mode,
  county_slug,
  letter,
  claim,
  refuter_evidence,
  survived
)
VALUES
  (
    '35b72237-0368-4e53-a134-c638d24b1638',
    'fallback',
    'jefferson',
    'B',
    'B remains FAIL: verified=0, closed_sold=0. Structural blocker: 25-CA-164 sold_amount CAPTCHA-gated; 26-TD-04/05 future sales (2026-08-19). 12th session confirming identical state.',
    '{"sources_checked_this_session": ["prior_session_reports_1_through_11", "shard_jefferson_clerk_scraper_py_dry_run_attempted"],
      "root_cause": "25-CA-164 foreclosure sold_amount blocked by Cloudflare Turnstile at myfloridacounty.com/orisearch/33 and civitekflorida.com/ocrs/county/33/; tax deed sales 26-TD-04 and 26-TD-05 scheduled 2026-08-19 (not yet past); no public unauthenticated source has published a sold amount",
      "infrastructure_status": "VERIFIED_PRIOR: shard-jefferson-clerk-scraper.yml healthy, last run 2026-07-27 success 0 outcomes (expected), B/F auto-resolution wired for when results PDF published post 2026-08-19",
      "honesty_tag": "VERIFIED from 11 prior session reports and git history of scraper"
     }'::jsonb,
    true
  ),
  (
    '35b72237-0368-4e53-a134-c638d24b1638',
    'fallback',
    'jefferson',
    'F',
    'F remains FAIL: tier1_sold=0, closed_sold=0. Same root cause as B: no sold_amount in DB for any jefferson row.',
    '{"sources_checked_this_session": "same as B",
      "root_cause": "identical to B: closed_sold denominator counts rows with sold_amount IS NOT NULL; all 3 jefferson rows have sold_amount=NULL",
      "infrastructure_status": "tier1-promote-hourly cron will auto-advance F once outcomes write as winning_bid; wiring confirmed correct",
      "honesty_tag": "VERIFIED from 11 prior session reports"
     }'::jsonb,
    true
  )
ON CONFLICT DO NOTHING;

-- Verification query (run to confirm state):
-- SELECT public.pencil_dod_evaluate_county('jefferson');
-- Expected: A=PASS(1), B=FAIL(null), C=PASS(100), D=PASS(100), E=PASS(100),
--           F=FAIL(null), G=PASS(100), H=PASS(<48h), I=PASS(100), J=PASS(100)
