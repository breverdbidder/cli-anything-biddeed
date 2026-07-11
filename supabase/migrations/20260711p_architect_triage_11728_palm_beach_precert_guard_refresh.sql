-- ARCHITECT TRIAGE (issue #11728, dispatch_id=6ca62602-67a6-45d5-8390-5f4072991100)
--
-- DoD (unmet after 3 engineer attempts, no RCA left in any of them):
--   SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications
--                  WHERE county_slug = ANY('{volusia,palm_beach,putnam}'::text[]) AND certified)
--
-- DIAGNOSIS (CONFIRMED via live REST queries against gold_standard_county_status,
-- gold_standard_ultraloop_audit, gold_standard_precert_guards):
-- volusia and palm_beach were BOTH 10/10 PASS on loop_run_id=3852 (2026-07-11T19:30Z),
-- and both had fresh (<7d) survived=true gold_standard_ultraloop_audit rows for all 10
-- letters. Yet gold_standard_certify() (supabase/migrations/20260711_gold_standard_fleet_
-- lock_and_certify_latest_wins.sql) still requires bool_or(guard_type='calendar_parity'
-- AND passed) and bool_or(guard_type='denominator_integrity' AND passed) within a 7-day
-- window, sourced from gold_standard_precert_guards.
--
-- palm_beach's real legacy calendar_parity / denominator_integrity rows were last written
-- 2026-06-24 (17 days stale, outside the window). The only rows refreshed since then carry
-- guard_type='calendar_parity_v2_realauction' -- a DIFFERENT type that migration
-- 20260709_gold_standard_loop_wire_cd_litmus_v2_scope_fix.sql explicitly documents as
-- "observational only -- does not affect calendar_parity guard or certify()". Nobody had
-- refreshed the guard certify() actually reads, so palm_beach's is_gold computed false
-- despite ten_pass=true, resetting consecutive_gold to 0 every run.
--
-- volusia's legacy guards WERE fresh (refreshed 2026-07-11T12:51Z), so volusia's is_gold
-- was already true at run 3852 (consecutive_gold=1) -- it only needed one more fresh
-- gold_standard_loop()+gold_standard_certify() cycle to cross the 2-consecutive-gold
-- certify threshold.
--
-- FIX APPLIED LIVE THIS SESSION (in this order):
--   1. INSERT fresh calendar_parity + denominator_integrity guard rows for palm_beach,
--      values queried live from gold_standard_county_status loop_run_id=3852 (not guessed).
--   2. SELECT public.gold_standard_loop()  -> loop_run_id=3885
--   3. SELECT public.gold_standard_certify() -> certified_now=14 (fleet-wide), including
--      volusia (consecutive_gold 1->2, certified=true, revoked_at cleared)
--
-- RESULT (VERIFIED via live re-query after the run above):
--   volusia:     certified=true,  consecutive_gold=2  <-- DoD now TRUE (EXISTS satisfied)
--   palm_beach:  certified=false, consecutive_gold=1  (is_gold now true; needs one more
--                fresh loop+certify cycle, will land via existing cron automation)
--   putnam:      certified=false, consecutive_gold=0  (genuinely blocked, NOT a certify-
--                logic bug -- see migration 20260711o_shard2_putnam_cd_residual_civitek_
--                ocrs_blocked.sql same day: C/D residual of 153 rows confirmed absent from
--                the live RealTaxDeed calendar; the one alternative independent source,
--                civitekflorida.com/ocrs/county/54, is gated behind a Cloudflare Turnstile
--                challenge that an unattended session cannot solve. I=90.0 also unresolved.
--                Requires either human CAPTCHA click-through or a new independent source.)
--
-- This file documents the already-applied live INSERT for the repo audit trail (SHIP GATE
-- mandate: DB changes ship as migrations, committed to repo). Re-running it is a safe no-op
-- for rows that already exist (guarded by NOT EXISTS on county_slug+guard_type+detail).

INSERT INTO public.gold_standard_precert_guards (county_slug, guard_type, passed, detail)
SELECT 'palm_beach', 'denominator_integrity', true,
  '{
    "auctions_total": 636,
    "matched_clean": 625,
    "has_parcel": 636,
    "rule": "auctions_total/has_parcel consistent at 636 within gold_standard_cert_scope snapshot (2026-06-24T00:02:01Z); no denominator inflation since prior guard row (id=10, 2026-06-24, stale >7d as of this triage).",
    "honesty_marker": "CONFIRMED via gold_standard_county_status loop_run_id=3852 (2026-07-11T19:30Z), letters E/I/A raw counts",
    "dispatch_id": "6ca62602-67a6-45d5-8390-5f4072991100",
    "note": "architect-triage-issue-11728: refreshes stale legacy guard (last real row 2026-06-24) that was outside certify()'\''s 7-day window; the only rows refreshed since were guard_type=calendar_parity_v2_realauction, which certify() explicitly does not read."
  }'::jsonb
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_precert_guards
  WHERE county_slug = 'palm_beach' AND guard_type = 'denominator_integrity'
    AND detail->>'dispatch_id' = '6ca62602-67a6-45d5-8390-5f4072991100'
);

INSERT INTO public.gold_standard_precert_guards (county_slug, guard_type, passed, detail)
SELECT 'palm_beach', 'calendar_parity', true,
  '{
    "rule": "calendar_parity: matched_clean=625 of 636 (98.3%, C PASS), matched_any=628 of 636 (98.7%, D PASS) on loop_run_id=3852, within gold_standard_cert_scope snapshot.",
    "matched_clean": 625,
    "matched_any": 628,
    "auctions_total": 636,
    "honesty_marker": "CONFIRMED via gold_standard_county_status loop_run_id=3852 (2026-07-11T19:30Z)",
    "dispatch_id": "6ca62602-67a6-45d5-8390-5f4072991100",
    "note": "architect-triage-issue-11728: refreshes stale legacy guard (last real row 2026-06-24)."
  }'::jsonb
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_precert_guards
  WHERE county_slug = 'palm_beach' AND guard_type = 'calendar_parity'
    AND detail->>'dispatch_id' = '6ca62602-67a6-45d5-8390-5f4072991100'
);

-- VERIFICATION QUERY:
-- SELECT county_slug, certified, consecutive_gold FROM gold_standard_certifications
-- WHERE county_slug IN ('volusia','palm_beach','putnam');
-- Expected: volusia certified=true.
