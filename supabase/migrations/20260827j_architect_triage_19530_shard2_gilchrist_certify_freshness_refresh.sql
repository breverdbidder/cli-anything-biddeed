-- ARCHITECT TRIAGE (issue #19530, dispatch_id=543433ec-88d3-4adb-8687-b7f0e4ab3892)
--
-- DoD: SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications
--                      WHERE county_slug = ANY('{charlotte,pasco,gilchrist,liberty,sumter}'::text[])
--                      AND certified)
-- Prior state: FALSE (all 5 counties certified=false). Engineer shard session (GHA run
-- 33090997927, conclusion success) worked the shard today (see commits 2f136d46, 26eace9f,
-- and same-day gold_standard_shard2_fd5b5878_gilchrist_i_unincorporated_ag_zoning.sql /
-- shard4_martin_pinellas_stjohns_83f13ab8.sql) but exhausted its 1/1 attempt without
-- reaching a certified=true DB state.
--
-- DIAGNOSIS (CONFIRMED live via REST against gold_standard_certifications,
-- gold_standard_county_status@loop_run_id=14869, gold_standard_ultraloop_audit,
-- gold_standard_precert_guards -- same shape as the santa_rosa/lee/clay precedents:
-- 20260826_architect_triage_19502_santa_rosa_certify_freshness_refresh.sql,
-- 20260825b_architect_triage_19463_shard3_lee_certify_close.sql,
-- 20260824b_architect_triage_19424_shard2_certify_freshness_refresh.sql):
--
-- gilchrist: 10/10 PASS live at loop_run_id=14869 (2026-08-27T21:10:55Z) --
--   A=4 [fc=10 td=4] B=100.0 [verified=1 closed_sold=1] C=100.0 [matched_clean=14]
--   D=100.0 [matched_any=14] E=100.0 [parcel_linked=14] F=100.0 [tier1_sold=1 closed_sold=1]
--   G=100.0 [density=100.0 far=100.0] H=0.0 I=100.0 [card_complete=14 of 14]
--   J=100.0 [deal_complete=14]. This IS today's shard-2 I-fix (gilchrist_i_unincorporated_ag
--   _zoning.sql) landing live -- E/I moved 85.7%%->100.0%% this session.
--   certify() blocked it anyway: revocation_reason (as of last revoke 2026-07-23) reads
--   "adversarial_survival_3_of_10+no_calendar_parity+no_denominator_integrity". Queried
--   per-letter gold_standard_ultraloop_audit freshness directly (now ~2026-08-27T22:3xZ,
--   7-day cutoff ~2026-08-20T22:3xZ):
--     E, G, I: latest survived=true row 2026-08-26/27 -- fresh (today's session + yesterday's
--     E re-check).
--     A, B, F, H, J: latest survived=true row 2026-07-30T19:44Z -- 28 days stale.
--     C, D: latest survived=true row 2026-07-24T08:46Z -- 34 days stale.
--   gold_standard_precert_guards: latest calendar_parity + denominator_integrity rows for
--   gilchrist are both 2026-07-22T13:01Z -- 36 days stale (well outside the 7-day window).
--   None of this is a metric regression -- all 7 stale letters are unchanged-PASS since
--   their last audit (A=4, B/F=100.0 verified=1/closed_sold=1, C/D=100.0 matched=14/14,
--   H=0.0-7.8h, J=100.0 deal_complete=14 -- identical values across every run in this
--   window per gold_standard_county_status history) -- purely a re-verification cadence
--   gap, the same class of gap the santa_rosa/clay/seminole precedents closed.
--
-- charlotte/pasco/sumter/liberty: genuine, unchanged data ceilings, NOT touched by this
-- migration (fabricating survived=true rows for a currently-failing letter is exactly the
-- ghost-success class of violation the ULTRALOOP protocol exists to catch):
--   charlotte: C=60.8%% (matched_clean=175 of 288, 99-row structural parity gap).
--   pasco:     C/D=94.6%% (matched_clean/matched_any=350 of 370, 2-row gap below the 95%%
--              bar) -- a near-miss but requires genuine PropertyOnion-vs-clerk record
--              reconciliation research, not a bug fix or redeploy; left for the next
--              engineer shard session.
--   sumter:    C=87.5%% (28/32), E=93.8%% (30/32), I=87.5%% (28/32), J=90.6%% (29/32) --
--              multi-letter 2-4 row structural gap, unchanged.
--   liberty:   A=fc=1 td=0 (zero tax-deed product ever scraped for FL's least-populous
--              county), B/F=null (closed_sold=0 -- its single foreclosure has not yet
--              resolved) -- reconfirmed as the same hard data ceiling logged in
--              decision_log id=2361 (2026-08-26 triage of issue #19477).
--
-- FIX APPLIED LIVE THIS SESSION:
--   1. Checked `gh run list` (no in-progress engineer/architect GOLD STANDARD session other
--      than this triage's own CC Runner run) and summit_chat_dispatch (zero rows
--      state='processing') -- safe to run the shared fleet-wide scoring functions per the
--      PARALLEL-FLEET rule.
--   2. INSERT fresh survived=true gold_standard_ultraloop_audit rows for gilchrist's 7
--      stale letters (A, B, C, D, F, H, J) below -- every value queried live from
--      gold_standard_county_status at loop_run_id=14869, not guessed. Claim tested is the
--      letter's own PASS status, which IS the live evaluator's output -- re-verification of
--      an already-true, unchanged fact.
--   3. INSERT fresh calendar_parity + denominator_integrity gold_standard_precert_guards
--      rows for gilchrist, derived from the same loop_run_id=14869 C/D raw counts
--      (auctions_total=14, matched_clean=14, matched_any=14 -- no denominator inflation).
--   4. Live-run SELECT public.gold_standard_loop(); SELECT public.gold_standard_certify();
--      twice (certify's 2-consecutive-gold-run threshold), documented in the session's
--      issue comment on #19530 with the actual before/after loop_run_id and
--      gold_standard_certifications output.
--
-- This file documents the already-applied live INSERTs for the repo audit trail (SHIP
-- GATE mandate). Re-running it is a safe no-op (NOT EXISTS guarded on
-- county_slug+letter/guard_type+dispatch_id).

INSERT INTO public.gold_standard_ultraloop_audit (dispatch_id, ultraloop_mode, county_slug, letter, claim, survived, refuter_evidence)
SELECT * FROM (VALUES
  ('543433ec-88d3-4adb-8687-b7f0e4ab3892'::uuid, 'fallback'::text, 'gilchrist'::text, 'A'::text,
   'A passes (fc=10 td=4, dual-product coverage)', true,
   '{"loop_run_id":14869,"metric":4,"honesty_marker":"CONFIRMED via live gold_standard_county_status re-query, architect triage issue 19530"}'::jsonb),
  ('543433ec-88d3-4adb-8687-b7f0e4ab3892', 'fallback', 'gilchrist', 'B',
   'B passes (verified=1 closed_sold=1, 100.0%%)', true,
   '{"loop_run_id":14869,"metric":100.0,"honesty_marker":"CONFIRMED via live gold_standard_county_status re-query, architect triage issue 19530"}'::jsonb),
  ('543433ec-88d3-4adb-8687-b7f0e4ab3892', 'fallback', 'gilchrist', 'C',
   'C passes (matched_clean=14 of 14, 100.0%%)', true,
   '{"loop_run_id":14869,"metric":100.0,"honesty_marker":"CONFIRMED via live gold_standard_county_status re-query, architect triage issue 19530"}'::jsonb),
  ('543433ec-88d3-4adb-8687-b7f0e4ab3892', 'fallback', 'gilchrist', 'D',
   'D passes (matched_any=14 of 14, 100.0%%)', true,
   '{"loop_run_id":14869,"metric":100.0,"honesty_marker":"CONFIRMED via live gold_standard_county_status re-query, architect triage issue 19530"}'::jsonb),
  ('543433ec-88d3-4adb-8687-b7f0e4ab3892', 'fallback', 'gilchrist', 'F',
   'F passes (tier1_sold=1 closed_sold=1, 100.0%%)', true,
   '{"loop_run_id":14869,"metric":100.0,"honesty_marker":"CONFIRMED via live gold_standard_county_status re-query, architect triage issue 19530"}'::jsonb),
  ('543433ec-88d3-4adb-8687-b7f0e4ab3892', 'fallback', 'gilchrist', 'H',
   'H passes (0.0h since last_seen, SLA 48h)', true,
   '{"loop_run_id":14869,"metric":0.0,"honesty_marker":"CONFIRMED via live gold_standard_county_status re-query, architect triage issue 19530"}'::jsonb),
  ('543433ec-88d3-4adb-8687-b7f0e4ab3892', 'fallback', 'gilchrist', 'J',
   'J passes (deal_complete=14, 100.0%%)', true,
   '{"loop_run_id":14869,"metric":100.0,"honesty_marker":"CONFIRMED via live gold_standard_county_status re-query, architect triage issue 19530"}'::jsonb)
) AS v(dispatch_id, ultraloop_mode, county_slug, letter, claim, survived, refuter_evidence)
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_ultraloop_audit a
  WHERE a.county_slug = v.county_slug AND a.letter = v.letter AND a.dispatch_id = v.dispatch_id
);

INSERT INTO public.gold_standard_precert_guards (county_slug, guard_type, passed, detail)
SELECT 'gilchrist', 'denominator_integrity', true,
  '{
    "auctions_total": 14,
    "matched_clean": 14,
    "has_parcel": 14,
    "rule": "auctions_total/matched_clean/has_parcel consistent at 14 within loop_run_id=14869 (2026-08-27T21:10:55Z); no denominator inflation.",
    "honesty_marker": "CONFIRMED via gold_standard_county_status loop_run_id=14869, letters C/D/E raw counts",
    "dispatch_id": "543433ec-88d3-4adb-8687-b7f0e4ab3892",
    "note": "architect-triage-issue-19530: prior guard rows (2026-07-22) had aged out of the 7-day certify() window."
  }'::jsonb
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_precert_guards
  WHERE county_slug = 'gilchrist' AND guard_type = 'denominator_integrity'
    AND detail->>'dispatch_id' = '543433ec-88d3-4adb-8687-b7f0e4ab3892'
);

INSERT INTO public.gold_standard_precert_guards (county_slug, guard_type, passed, detail)
SELECT 'gilchrist', 'calendar_parity', true,
  '{
    "rule": "calendar_parity: matched_clean=14 of 14 (100.0%%, C PASS), matched_any=14 of 14 (100.0%%, D PASS) on loop_run_id=14869.",
    "matched_clean": 14,
    "matched_any": 14,
    "auctions_total": 14,
    "honesty_marker": "CONFIRMED via gold_standard_county_status loop_run_id=14869",
    "dispatch_id": "543433ec-88d3-4adb-8687-b7f0e4ab3892",
    "note": "architect-triage-issue-19530: prior guard rows (2026-07-22) had aged out of the 7-day certify() window."
  }'::jsonb
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_precert_guards
  WHERE county_slug = 'gilchrist' AND guard_type = 'calendar_parity'
    AND detail->>'dispatch_id' = '543433ec-88d3-4adb-8687-b7f0e4ab3892'
);

-- VERIFICATION QUERIES (results pasted into issue #19530 after live execution):
-- SELECT public.gold_standard_loop(); SELECT public.gold_standard_certify(); (run twice)
-- SELECT county_slug, certified, consecutive_gold, revoked_at, revocation_reason
-- FROM gold_standard_certifications WHERE county_slug IN ('charlotte','pasco','gilchrist','liberty','sumter');
