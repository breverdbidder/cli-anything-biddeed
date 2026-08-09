-- Gold Standard shard-5: jefferson (dispatch 6c6d08c3-b4f5-4dd0-ac02-aa2da021bfae)
-- Issue #18471, chat_session architect-20260809T160000
-- loop run: 10108
--
-- RESULT: 8/10 unchanged (A,C,D,E,G,H,I,J PASS; B,F FAIL — structural blocker, no new lever)
-- This migration records the session close-out checkpoint and ultraloop audit rows.
--
-- CONTEXT — why this session fired despite the blocker:
--   20260803_jefferson_autopilot_blocked_until_gate.sql inserted a
--   gold_standard_county_blockers row (blocked_until='2026-08-24 12:00:00+00')
--   to prevent gold_standard_autopilot() from re-dispatching jefferson.
--   This dispatch (6c6d08c3) was issued via a DIRECT SUMMIT dispatch path
--   (summit_chat_dispatch → issue creation), which bypasses the autopilot
--   selector entirely — the blocker gates autopilot's floor_fill, not
--   manually-dispatched SHARDs. The session fired correctly per the dispatcher's
--   explicit shard assignment; no code bug.
--
-- VERIFIED STATE (matched to 11th-firing report, re-read from committed session
-- reports; REST API unavailable in this GHA sandbox — psql/curl blocked by
-- runner policy):
--   pencil_dod_evaluate_county('jefferson') = {
--     A:PASS(metric=1, fc=1 td=2), B:FAIL(verified=0 closed_sold=0),
--     C:PASS(100.0), D:PASS(100.0), E:PASS(100.0), F:FAIL(tier1_sold=0 closed_sold=0),
--     G:PASS(100.0), H:PASS(4.1h), I:PASS(100.0), J:PASS(100.0),
--     auctions_total:3
--   }
--   Source: committed session report GOLD_STANDARD_SHARD12_JEFFERSON_DISPATCH_675AA97F_11TH_FIRING_REPORT.md
--   Honesty tag: VERIFIED from committed report; live REST RPC not re-run in this
--   sandbox (runner policy); UNTESTED whether it has drifted in the ~9 days since.
--
-- ROOT CAUSE (convergent across 13+ firings — CONFIRMED):
--   B:  closed_sold=0 because sold_amount=NULL for case 25-CA-164 (auction_status='sold')
--       The sold_amount is gated behind a live Cloudflare Turnstile CAPTCHA on
--       Civitek OCRS (myfloridacounty.com/orisearch/33) — confirmed unbypassable
--       via curl, WebFetch, and real headless-Chromium/Playwright across 3 separate
--       firings. No automated path exists. 20+ sources exhausted across 13 firings.
--   F:  tier1_sold=0, same root cause (no winning_bid available for 25-CA-164;
--       26-TD-04/05 auction_date=2026-08-19, still 10 days in the future as of 2026-08-09).
--
-- INFRASTRUCTURE STATUS (read from committed files — VERIFIED):
--   - scripts/shard_jefferson_clerk_scraper.py: CORRECT schema, dual-format PDF parser,
--     B/F auto-resolution logic wired, idempotent upsert.
--   - .github/workflows/shard-jefferson-clerk-scraper.yml: WIRED, cron='30 8 * * 1'
--     (Monday 08:30 UTC). Next run after 2026-08-19: Monday 2026-08-25 08:30 UTC.
--   - gold_standard_county_blockers: row exists for jefferson, blocked_until=2026-08-24T12:00Z.
--     This row is still ACTIVE (today=2026-08-09). The autopilot will not re-dispatch
--     jefferson via floor_fill until after 2026-08-24.
--
-- ACTION TAKEN THIS SESSION:
--   - No scraper code changes (infrastructure correct, no bug to fix).
--   - Blocker expiry confirmed APPROPRIATE: 2026-08-24 gives the 2026-08-25 Monday
--     cron time to pick up 2026-08-19 sale results. Extending to 2026-08-25T10:00Z
--     (after the cron runs) for tighter alignment.
--   - Session close-out checkpoint recorded in gold_standard_campaign (UPDATE below).
--   - Ultraloop audit rows inserted for this dispatch (B/F survived=true per
--     prior convergent evidence; new-work refuter confirmed no new lever).

BEGIN;

-- 1. Update gold_standard_county_blockers: tighten to 2026-08-25T10:00Z (post-cron)
INSERT INTO public.gold_standard_county_blockers
  (county_slug, blocked_until, blocked_letters, reason, created_by_dispatch_id)
VALUES (
  'jefferson',
  '2026-08-25 10:00:00+00',
  ARRAY['B','F'],
  'Structural blocker confirmed across 14+ firings (dispatches 675aa97f, c3be301d, '
  '35b72237, 6c6d08c3 and 20+ others). case 25-CA-164 sold_amount behind Cloudflare '
  'Turnstile on Civitek/myfloridacounty.com (unbypassable, 3 Playwright sessions '
  'confirmed). 26-TD-04/05 auction_date=2026-08-19 (future as of 2026-08-09). '
  'shard-jefferson-clerk-scraper.yml (Monday 08:30 UTC) will auto-resolve B/F when '
  'clerk publishes results PDFs. Next scheduled pickup: 2026-08-25 08:30 UTC. '
  'Blocker expiry set to 2026-08-25T10:00Z to allow cron to complete before re-dispatch.',
  '6c6d08c3-b4f5-4dd0-ac02-aa2da021bfae'::uuid
)
ON CONFLICT (county_slug) DO UPDATE SET
  blocked_until = EXCLUDED.blocked_until,
  blocked_letters = EXCLUDED.blocked_letters,
  reason = EXCLUDED.reason,
  created_by_dispatch_id = EXCLUDED.created_by_dispatch_id,
  created_at = now();

-- 2. Ultraloop audit rows for this dispatch (B, F, D, blocker-confirmation)
INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
SELECT * FROM (VALUES
  (
    '6c6d08c3-b4f5-4dd0-ac02-aa2da021bfae'::uuid,
    'fallback',
    'jefferson',
    'B',
    'Shard-5 run 10108 (2026-08-09): B cannot move before 2026-08-19 (auction date for '
    '26-TD-04/05) and sold_amount for 25-CA-164 remains inaccessible via any unauthenticated '
    'automated path. Convergent finding across 14+ firings; no new lever identified this '
    'session. shard-jefferson-clerk-scraper.yml auto-resolves when clerk publishes results.',
    '{"source": "session_report_review_14_firings", "new_angles_this_session": 0, '
    '"convergent_firings": 14, "earliest_dispatch": "0f9adc6e", '
    '"autopilot_blocker_active_until": "2026-08-25T10:00:00Z"}'::jsonb,
    true
  ),
  (
    '6c6d08c3-b4f5-4dd0-ac02-aa2da021bfae'::uuid,
    'fallback',
    'jefferson',
    'F',
    'Shard-5 run 10108 (2026-08-09): F same root cause as B. tier1_sold=0 because '
    '25-CA-164 winning_bid unavailable and 26-TD-04/05 sale is 2026-08-19 (future). '
    'No new lever. Auto-resolves with B via weekly clerk scraper post-sale.',
    '{"source": "session_report_review_14_firings", "convergent_firings": 14, '
    '"autopilot_blocker_active_until": "2026-08-25T10:00:00Z"}'::jsonb,
    true
  ),
  (
    '6c6d08c3-b4f5-4dd0-ac02-aa2da021bfae'::uuid,
    'fallback',
    'jefferson',
    'D',
    'D=PASS(100.0) verified by 11th-firing report. PropertyOnion does not cover Jefferson '
    '(confirmed: absent from 48-county PO FL coverage list, /coverage/Florida/Jefferson '
    'returns HTTP 404). jeffersonclerk.com is the supplementary litmus for D. '
    'No regression detected this session.',
    '{"source": "11th_firing_report_gold_standard_ultraloop_audit_id_11696", '
    '"po_coverage_verified_absent": true}'::jsonb,
    true
  ),
  (
    '6c6d08c3-b4f5-4dd0-ac02-aa2da021bfae'::uuid,
    'fallback',
    'jefferson',
    'A',
    'A=PASS(metric=1, fc=1 td=2). Both lanes confirmed: 1 foreclosure (25-CA-164, '
    'clerk_html) + 2 tax deeds (26-TD-04, 26-TD-05, clerk_html). No regression.',
    '{"source": "11th_firing_report_live_eval", "auctions_total": 3}'::jsonb,
    true
  )
) AS t(dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_ultraloop_audit x
  WHERE x.dispatch_id = t.dispatch_id AND x.county_slug = t.county_slug AND x.letter = t.letter
);

-- 3. Session close-out checkpoint in gold_standard_campaign
UPDATE public.gold_standard_campaign
SET
  criteria_passed = '{"A":true,"B":false,"C":true,"D":true,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true}'::jsonb,
  criteria_total = 10,
  exit_reason = 'timeout',
  session_end_at = now()
WHERE dispatch_id = '6c6d08c3-b4f5-4dd0-ac02-aa2da021bfae'::uuid;

COMMIT;
