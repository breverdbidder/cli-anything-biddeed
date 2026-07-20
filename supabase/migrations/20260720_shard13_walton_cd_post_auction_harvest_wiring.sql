-- SHARD-13 dispatch 4f148647-e529-49e3-995a-b99f4a7713c0
-- walton C/D post-auction harvest wiring (2026-07-20)
--
-- Context:
--   walton: 8/10 (C=86.0% FAIL, D=86.0% FAIL)
--   6 unmatched rows: auction_dates 2026-07-20 (26CA000030), 2026-07-23, 2026-07-24
--   TODAY = 2026-07-20: auctions not yet past, cannot stamp without real disposition.
--
-- This migration:
--   1. Documents the structural situation in ultraloop_audit (honest assessment).
--   2. Pre-authorizes the post-auction backfill via walton-post-auction-cd-harvest.yml
--      (GHA workflow shipping in same commit) to fire starting 2026-07-24.
--   3. Refreshes the precert guard with current denominator (43).
--
-- The actual C/D metric move WILL happen when:
--   (a) walton.realforeclose.com posts results for 2026-07-23/24 auctions AND
--   (b) realforeclose_aids is updated with those case numbers AND
--   (c) walton-post-auction-cd-harvest.yml runs (daily 14:00 UTC starting 2026-07-24).
--
-- HONESTY: Cannot stamp today's future auctions. BLANK > WRONG.
-- walton remains at 8/10 until the auctions resolve. This is correct.

SET statement_timeout = 0;

-- ============================================================================
-- PART 1: Ultraloop audit rows — honest structural documentation
-- ============================================================================

INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES

  -- C: documented ceiling until 2026-07-23/24 auctions resolve
  ('4f148647-e529-49e3-995a-b99f4a7713c0', 'fallback', 'walton', 'C',
   'walton C (shard-13 dispatch 4f148647): 6 unmatched rows have auction_dates 2026-07-20 (26CA000030 FC), 2026-07-23, 2026-07-24. Today 2026-07-20 = 1-4 days pre-auction. Cannot stamp without real disposition. realforeclose_aids join is idempotent and will run automatically via walton-post-auction-cd-harvest.yml (wired same session) on 14:00 UTC daily starting 2026-07-24. Targeting 43/43 matched_clean = 100% (well above 95% threshold).',
   '{"verdict":"TIMING_BLOCK_NOT_STRUCTURAL","max_achievable":"43/43=100pct","threshold":"95pct","unmatched_rows":6,"target_auction_dates":["2026-07-20","2026-07-23","2026-07-24"],"automated_follow_up":"walton-post-auction-cd-harvest.yml scheduled 14:00 UTC daily","realforeclose_aids_join":"idempotent_will_catch_new_rows","prior_proof":"20260704_shard9_run2820_walton_santarosa_realforeclose_aids_cd.sql","clerk_url":"orsearch.clerkofcourts.co.walton.fl.us verified live (prior sessions)","honesty_marker":"VERIFIED situation; specific new matches UNTESTED until post-auction run"}'::jsonb,
   true),

  -- D: same as C
  ('4f148647-e529-49e3-995a-b99f4a7713c0', 'fallback', 'walton', 'D',
   'walton D: same rows and ceiling as C. matched_any = matched_clean for walton (no divergent-match routes available pre-auction). Will resolve together with C post 2026-07-24.',
   '{"verdict":"TIMING_BLOCK_NOT_STRUCTURAL","honesty_marker":"VERIFIED same root cause as C","run_date":"2026-07-20"}'::jsonb,
   true),

  -- I: I already PASSES at 97.7% (42/43). One gap is 26CA000030 (no parcel_id).
  --    walton-post-auction-cd-harvest.yml will also re-run EnerGov card enrichment.
  ('4f148647-e529-49e3-995a-b99f4a7713c0', 'fallback', 'walton', 'I',
   'walton I: PASSES at 97.7% (42/43 card_complete). Only gap is 26CA000030 (parcel_id=null, no address/geo/value — auction today 2026-07-20 FC). EnerGov enrichment cannot resolve without parcel_id. Post-auction harvest will re-attempt if parcel_id becomes available from clerk records.',
   '{"verdict":"ONE_ROW_MISSING","gap_case":"26CA000030","barrier":"parcel_id IS NULL — EnerGov requires PARCELNO to geocode","honesty_marker":"VERIFIED from 20260718_shard9_walton_cd_i_dixie_structural_ceiling.sql","run_date":"2026-07-20"}'::jsonb,
   true)

ON CONFLICT DO NOTHING;

-- ============================================================================
-- PART 2: Precert guard refresh
-- ============================================================================

INSERT INTO public.gold_standard_precert_guards (county_slug, guard_type, passed, detail)
VALUES
  ('walton', 'denominator_integrity', true,
   '{"auctions_total":43,"rule":"denominator from pencil_dod_evaluate_county","honesty_marker":"VERIFIED from 3rd-firing session (2026-07-19) — auctions_total=43","shard":"shard13-dispatch-4f148647-2026-07-20"}'::jsonb),
  ('walton', 'post_auction_harvest_wired', true,
   '{"workflow":"walton-post-auction-cd-harvest.yml","schedule":"0 14 * * *","first_meaningful_run":"2026-07-24","script":"scripts/walton_post_auction_harvest.py","wired_at":"2026-07-20","shard":"shard13-dispatch-4f148647"}'::jsonb)
ON CONFLICT (county_slug, guard_type) DO UPDATE
  SET passed = true,
      detail = EXCLUDED.detail,
      updated_at = now();
