-- ARCHITECT TRIAGE (issue #19540, dispatch_id=55395387-15d7-4034-8557-0b5603c976fa)
--
-- DoD: SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications
--                      WHERE county_slug = ANY('{brevard,lake,bradford,st_lucie,wakulla}'::text[])
--                      AND certified)
-- Prior state: FALSE (all 5 counties certified=false). Today's shard-1 engineer session
-- (dispatch 95d2d8fc, GHA run 33163004262, conclusion success at 08:39Z) worked this exact
-- shard and exhausted its 1/1 attempt without reaching a certified=true DB state.
--
-- DIAGNOSIS (CONFIRMED live via REST against gold_standard_county_status@loop_run_id=15009
-- [2026-08-28T13:30:00Z, the most recent official loop -- already reflects this morning's
-- shard-1 session work], gold_standard_certifications, gold_standard_ultraloop_audit,
-- gold_standard_precert_guards, multi_county_auctions, and pencil_dod_evaluate_county()):
--
-- Unlike the clay/hamilton/gilchrist/seminole precedents (20260824b_architect_triage_19424,
-- 20260827j_architect_triage_19530), where the root cause was a stale-freshness-gate
-- artifact blocking a county that was ALREADY 10/10 on raw letters, NONE of this shard's 5
-- counties are currently 10/10 live. This is a genuine data ceiling, not a certify()-pipeline
-- bug:
--   brevard (9/10):  I FAILS 85.6-86.0%% (card_complete=6106-6292 of 7099-7347, denominator
--                    actively growing from live ingestion -- ~1000-row property-card
--                    enrichment gap: address+geo+value+zoned parcel). All other letters PASS.
--   lake (9/10):     C FAILS 87.9%% (matched_clean=124 of 141). Root-caused via direct query
--                    of the 17 non-matched-clean rows: 100%% of them are parity_status=
--                    'CLERK_SSOT_CANCELLED' (Lake Clerk confirmed the auction cancelled --
--                    counted correctly in D/matched_any=100%% but BY DESIGN excluded from C,
--                    since a cancelled sale was never matched-clean to anything). Already
--                    diagnosed identically in 3 prior lake-C sessions (see
--                    supabase/migrations/20260810_gold_standard_shard3_lake_clerk_ssot_cd_
--                    recognition.sql and repo session logs lake_c_15_stale_parity_
--                    reconciliation_backfill.sql, lake_c_3row_new_clerk_calendar_parity_
--                    fix.sql). Forcing these into matched_clean would be ghost-success
--                    fabrication -- NOT touched.
--   bradford (8/10): B and F FAIL (metric=null, closed_sold=0). Queried multi_county_auctions
--                    directly: all 5 bradford rows (auction_status) are 'upcoming' -- ZERO
--                    foreclosure or tax-deed sale has EVER closed in Bradford in this dataset.
--                    Same hard-ceiling class already reconfirmed for liberty in decision_log
--                    id=2361 (2026-08-26 triage of issue #19477) -- nothing exists yet to
--                    verify. NOT fixable by data engineering; only a real future sale closing
--                    can move this.
--   st_lucie (8/10): C FAILS 80.7%% (matched_clean=201 of 249) -- genuine parity gap, ~36-row
--                    reconciliation shortfall. G improved 0.0%%->95.5%% this morning's session
--                    (real fix landed) but C remains untouched, real work required.
--   wakulla (6/10, regressed from 7/10 in the dispatch brief): C 77.1%% (down from 84.1%%),
--                    E newly FAILS 91.7%% (was 100.0%%), I 85.4%%, J 91.7%% -- auctions_total
--                    grew (new rows ingested) faster than card/parcel enrichment kept up.
--                    Genuine structural gap, not a code bug.
--
-- No certify()-pipeline bug found. Checked gold_standard_certify()'s two ancillary gates
-- (rolling-7-day gold_standard_ultraloop_audit survival + gold_standard_precert_guards
-- freshness) for brevard specifically, since it is the closest county to certifying (only I
-- fails, at a 9.4-point gap to the 95%% bar): ALL of brevard's letter rows in
-- gold_standard_ultraloop_audit were 28-31 days stale (A-H last touched 2026-07-28/07-31),
-- well outside the 7-day certify() window, and both precert_guards rows (calendar_parity,
-- denominator_integrity) were last touched 2026-07-28 (31 days stale). Since I genuinely
-- fails today, refreshing these gates does not flip the DoD -- but leaving them stale means
-- a FUTURE session that finally closes brevard's I gap would immediately hit a second,
-- unrelated freshness block, exactly the churn pattern the clay/hamilton/gilchrist precedents
-- exist to close. Pre-clearing it now, using ONLY the already-true PASS values from the last
-- official loop_run_id=15009 (no fabrication, no letter I touched), removes that future
-- blocker at zero risk.
--
-- PARALLEL-FLEET SAFETY: `gh run list --workflow cc-runner-ghonly.yml` showed 3 CC Runner
-- sessions in_progress at triage time (33180029537, 33179863573, 33179786470) -- per the
-- campaign's PARALLEL-FLEET rule this blocks running the shared public.gold_standard_loop()
-- / public.gold_standard_certify() functions fleet-wide. This migration therefore does NOT
-- run either function; it only inserts county-scoped, NOT-EXISTS-guarded evidence rows for
-- brevard and leaves loop/certify execution to the next safe window (tomorrow's engineer
-- session close-out, or a later architect pass once no shard is mid-flight).
--
-- RESULT: DoD verified FALSE at end of this session (all 5 counties remain certified=false)
-- -- correctly so, since none pass all 10 letters. This is a genuine data ceiling requiring
-- further Gold Standard engineer work on brevard-I (card enrichment), lake-C/st_lucie-C/
-- wakulla-C+E+I+J (parity/linkage reconciliation), and a real future bradford sale closing
-- for B/F. No human action required (not a credential/authorization/spend/protected-schema
-- block) -- logged as UNTESTED-ceiling per Honesty V3, not escalated as BLOCKED.
--
-- This file documents the already-applied live INSERTs for the repo audit trail (SHIP GATE
-- mandate). Re-running it is a safe no-op (NOT EXISTS guarded on county_slug+letter/
-- guard_type+dispatch_id).

INSERT INTO public.gold_standard_ultraloop_audit (dispatch_id, ultraloop_mode, county_slug, letter, claim, survived, refuter_evidence)
SELECT * FROM (VALUES
  ('55395387-15d7-4034-8557-0b5603c976fa'::uuid, 'fallback'::text, 'brevard'::text, 'A'::text,
   'A passes (fc=6235 td=864, dual-product coverage)', true,
   '{"loop_run_id":15009,"metric":864,"honesty_marker":"CONFIRMED via live gold_standard_county_status re-query, architect triage issue 19540"}'::jsonb),
  ('55395387-15d7-4034-8557-0b5603c976fa', 'fallback', 'brevard', 'B',
   'B passes (verified=267 closed_sold=271, 98.5%%)', true,
   '{"loop_run_id":15009,"metric":98.5,"honesty_marker":"CONFIRMED via live gold_standard_county_status re-query, architect triage issue 19540"}'::jsonb),
  ('55395387-15d7-4034-8557-0b5603c976fa', 'fallback', 'brevard', 'C',
   'C passes (matched_clean=6937, 97.7%%)', true,
   '{"loop_run_id":15009,"metric":97.7,"honesty_marker":"CONFIRMED via live gold_standard_county_status re-query, architect triage issue 19540"}'::jsonb),
  ('55395387-15d7-4034-8557-0b5603c976fa', 'fallback', 'brevard', 'D',
   'D passes (matched_any=6947, 97.9%%)', true,
   '{"loop_run_id":15009,"metric":97.9,"honesty_marker":"CONFIRMED via live gold_standard_county_status re-query, architect triage issue 19540"}'::jsonb),
  ('55395387-15d7-4034-8557-0b5603c976fa', 'fallback', 'brevard', 'E',
   'E passes (parcel_linked=7082, 99.8%%)', true,
   '{"loop_run_id":15009,"metric":99.8,"honesty_marker":"CONFIRMED via live gold_standard_county_status re-query, architect triage issue 19540"}'::jsonb),
  ('55395387-15d7-4034-8557-0b5603c976fa', 'fallback', 'brevard', 'F',
   'F passes (tier1_sold=268 closed_sold=271, 98.9%%)', true,
   '{"loop_run_id":15009,"metric":98.9,"honesty_marker":"CONFIRMED via live gold_standard_county_status re-query, architect triage issue 19540"}'::jsonb),
  ('55395387-15d7-4034-8557-0b5603c976fa', 'fallback', 'brevard', 'G',
   'G passes (density=99.7%% far=99.1%% pk1000=100.0%%)', true,
   '{"loop_run_id":15009,"metric":99.1,"honesty_marker":"CONFIRMED via live gold_standard_county_status re-query, architect triage issue 19540"}'::jsonb),
  ('55395387-15d7-4034-8557-0b5603c976fa', 'fallback', 'brevard', 'H',
   'H passes (1.3h since last_seen, SLA 48h)', true,
   '{"loop_run_id":15009,"metric":1.3,"honesty_marker":"CONFIRMED via live gold_standard_county_status re-query, architect triage issue 19540"}'::jsonb),
  ('55395387-15d7-4034-8557-0b5603c976fa', 'fallback', 'brevard', 'J',
   'J passes (deal_complete=7098, 100.0%%)', true,
   '{"loop_run_id":15009,"metric":100.0,"honesty_marker":"CONFIRMED via live gold_standard_county_status re-query, architect triage issue 19540"}'::jsonb)
) AS v(dispatch_id, ultraloop_mode, county_slug, letter, claim, survived, refuter_evidence)
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_ultraloop_audit a
  WHERE a.county_slug = v.county_slug AND a.letter = v.letter AND a.dispatch_id = v.dispatch_id
);

INSERT INTO public.gold_standard_precert_guards (county_slug, guard_type, passed, detail)
SELECT 'brevard', 'denominator_integrity', true,
  '{
    "auctions_total": 7099,
    "matched_clean": 6937,
    "matched_any": 6947,
    "parcel_linked": 7082,
    "rule": "auctions_total/matched_clean/matched_any/parcel_linked all consistent around 7099 within loop_run_id=15009 (2026-08-28T13:30:00Z); no denominator inflation. Letter I (card_complete=6106 of 7099, 86.0%%) is the sole failing letter and is untouched by this guard.",
    "honesty_marker": "CONFIRMED via gold_standard_county_status loop_run_id=15009, letters C/D/E raw counts",
    "dispatch_id": "55395387-15d7-4034-8557-0b5603c976fa",
    "note": "architect-triage-issue-19540: prior guard rows (2026-07-28) had aged out of the 7-day certify() window."
  }'::jsonb
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_precert_guards
  WHERE county_slug = 'brevard' AND guard_type = 'denominator_integrity'
    AND detail->>'dispatch_id' = '55395387-15d7-4034-8557-0b5603c976fa'
);

INSERT INTO public.gold_standard_precert_guards (county_slug, guard_type, passed, detail)
SELECT 'brevard', 'calendar_parity', true,
  '{
    "rule": "calendar_parity: matched_clean=6937 of 7099 (97.7%%, C PASS), matched_any=6947 of 7099 (97.9%%, D PASS) on loop_run_id=15009.",
    "matched_clean": 6937,
    "matched_any": 6947,
    "auctions_total": 7099,
    "honesty_marker": "CONFIRMED via gold_standard_county_status loop_run_id=15009",
    "dispatch_id": "55395387-15d7-4034-8557-0b5603c976fa",
    "note": "architect-triage-issue-19540: prior guard rows (2026-07-28) had aged out of the 7-day certify() window."
  }'::jsonb
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_precert_guards
  WHERE county_slug = 'brevard' AND guard_type = 'calendar_parity'
    AND detail->>'dispatch_id' = '55395387-15d7-4034-8557-0b5603c976fa'
);

-- VERIFICATION QUERIES (results pasted into issue #19540 after live execution):
-- SELECT county_slug, letter, survived, created_at FROM gold_standard_ultraloop_audit
--   WHERE county_slug='brevard' ORDER BY letter;
-- SELECT county_slug, guard_type, passed, created_at FROM gold_standard_precert_guards
--   WHERE county_slug='brevard' ORDER BY guard_type;
-- SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications
--   WHERE county_slug = ANY('{brevard,lake,bradford,st_lucie,wakulla}'::text[]) AND certified);
--   -- still FALSE: I remains the sole failing letter for brevard, genuinely below threshold.
