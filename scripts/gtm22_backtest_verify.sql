-- GTM-22 Phase 1.4 post-fix backtest
-- Run AFTER applying 20260718_gtm22_snapshot_param_loop_rewrite.sql
-- Purpose: verify the new loop output matches pencil_dod_evaluate_county live
-- Success criteria: 0 rows in disagreement_summary (unexplained divergences)
--
-- Step 1: Run gold_standard_loop() once to populate gold_standard_county_status
--   SELECT public.gold_standard_loop();
--
-- Step 2: Run this backtest query

WITH latest_run AS (
  SELECT max(loop_run_id) AS run_id
  FROM gold_standard_county_status
),
loop_verdicts AS (
  SELECT county_slug,
         count(*) FILTER (WHERE status = 'PASS') AS loop_pass_count,
         bool_and(status = 'PASS') FILTER (WHERE letter IN ('A','B','C','D','E','F','G','H','I','J')) AS loop_ten_pass
  FROM gold_standard_county_status
  WHERE loop_run_id = (SELECT run_id FROM latest_run)
  GROUP BY county_slug
),
rpc_verdicts AS (
  SELECT pc.county_slug,
         (SELECT count(*) FROM jsonb_object_keys(public.pencil_dod_evaluate_county(pc.county_slug)) ltr
           WHERE ltr IN ('A','B','C','D','E','F','G','H','I','J')
             AND (public.pencil_dod_evaluate_county(pc.county_slug)->ltr->>'pass')::boolean = true
         ) AS rpc_pass_count
  FROM pipeline.counties pc
),
disagreements AS (
  SELECT lv.county_slug,
         lv.loop_pass_count,
         rv.rpc_pass_count,
         lv.loop_pass_count - rv.rpc_pass_count AS delta
  FROM loop_verdicts lv
  JOIN rpc_verdicts rv USING (county_slug)
  WHERE lv.loop_pass_count != rv.rpc_pass_count
)
SELECT
  county_slug,
  loop_pass_count AS loop_pass,
  rpc_pass_count  AS rpc_pass,
  delta
FROM disagreements
ORDER BY abs(delta) DESC, county_slug;

-- Expected result after fix: 0 rows (all 67 counties agree)
-- If any rows appear, investigate before re-enabling crons.
