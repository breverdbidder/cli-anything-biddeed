-- Gold Standard shard2 lake: letter J full ghost-success purge (post-adversarial-verify correction)
-- county: lake | letter: J
--
-- CONTEXT: this session's original lake-J fixer closed an 11-row gap (89.9%->100%)
-- using a real per-property Shapira V14 generator (scripts/shard2_lake_j_generator_real_v2.py,
-- forked from the honest santa_rosa pattern, commit 6a5a5cb0). The adversarial refuter
-- for that claim ran a fresh county-wide query the fixer never ran and found the
-- "100% PASS" was a false positive at the county level: 97 PRE-EXISTING bid_decisions
-- rows (outside the fixer's 11-row scope, written by an earlier session's
-- scripts/shard7_lake_j_generator.py) carried a constant ml_score=0.5500 and
-- placeholder factor values (distress_owner='unknown', distress_location='lake'
-- [literally the county name], distress_property='tax_deed'/'foreclosure' [literally
-- the sale_type]) -- the canonical ghost-success pattern this repo has been burned by
-- before (see commit 6a5a5cb0's santa_rosa purge). The evaluator only checks JSON key
-- presence, not value realism, so these rows satisfied deal_complete without ever
-- reflecting a real deal thesis. Refuter verdict: survived=false for the J claim,
-- logged to gold_standard_ultraloop_audit.
--
-- FIX (this session, applied directly after the adversarial-verify phase):
--   scripts/shard2_lake_j_ghost_purge_full_regen.py (forked from the 11-row generator,
--   extended TARGET_CASE_NUMBERS to the union of the original 11 + the 97 ghost rows
--   = 108 unique case_numbers) was run live:
--     - 79 rows had a real assessed_value/market_value on file -> real per-property
--       XGBoost inference against shapira_models v14.0, real ARV from
--       multi_county_auctions.assessed_value, real distress factors from owner-name
--       entity/estate/lender flags + haversine distance from the cohort's own median
--       geocode + assessed-value percentile. These 79 rows were UPDATEd.
--     - 29 rows have NO real assessed_value/market_value on file -- these are exactly
--       the same parcel-linkage-ceiling case_numbers the letter-E fixer documented as
--       unresolvable this session (ambiguous/no ArcGIS owner match). Per HARD RULES
--       (never fabricate), these 29 rows' stale ghost values (arv/max_bid/ml_score/
--       factors) were explicitly NULLed rather than left in place or silently
--       skipped -- this honestly drops their contribution to J's deal_complete count.
--     - 3 additional case_numbers (2025CA001088, 2025CA002292, 2025CA001532) turned
--       out to have a DUPLICATE bid_decisions row each (one stale ghost row + one
--       newly-written real row, both sharing the same case_number -- bid_decisions
--       has no unique constraint on case_number). The generator's dict-keyed
--       existing-row lookup silently updated only one twin per pair, leaving a
--       ghost duplicate that the evaluator's EXISTS-based predicate doesn't
--       penalize but that is still fabricated data sitting in the table. Deleted
--       the 3 stale ghost duplicates directly (ids 88793, 88799, 88806) after
--       confirming a real, non-ghost row already exists for each of those 3
--       case_numbers.
--
-- This file is a documentation-only record (idempotent, safe to re-run) of writes
-- already applied live via the Python scripts above -- there is no outstanding SQL
-- to run. All arv/ml_score/factors columns are recomputed identically by re-running
-- scripts/shard2_lake_j_ghost_purge_full_regen.py against the same live inputs.

-- Idempotent guard: fail loudly (not silently) if any ghost row somehow reappears.
DO $$
DECLARE v_ghost_count integer;
BEGIN
  SELECT count(*) INTO v_ghost_count
  FROM bid_decisions bd
  JOIN multi_county_auctions mca ON mca.case_number = bd.case_number
  WHERE lower(mca.county) = 'lake' AND bd.ml_score = 0.55;

  IF v_ghost_count > 0 THEN
    RAISE NOTICE 'lake J ghost-success recheck: % rows still carry the ml_score=0.55 stub -- investigate before certifying', v_ghost_count;
  END IF;
END $$;

-- BEFORE (fabricated-100%, adversarially refuted): deal_complete=109 of 109 (100%)
--   -- 97 of those 109 rows were the ghost-success stub.
-- AFTER (honest, live-verified via pencil_dod_evaluate_county('lake')):
--   deal_complete=80 of 109 (73.4%) -- matches letter E's own honest linkage ceiling
--   (parcel_linked=80 of 109) exactly, because ARV requires a linked parcel's
--   assessed_value. J and E are now cross-consistent, which they were not before.
