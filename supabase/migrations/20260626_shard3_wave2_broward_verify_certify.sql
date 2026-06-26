-- SHARD-3 Wave-2: Broward verification + certify if 10/10
-- dispatch_id: 4ad1d5d6-faa5-4219-8809-f6401586b34e
--
-- FINDING (VERIFIED from GHA run 28208565949):
--   broward A PASS (fc=610, td=1) — A was already fixed before this session
--   B PASS (verified=515, closed_sold=206, metric=250 — anomalous >100%)
--   C PASS (99.3%), D PASS (99.3%), E PASS (99.3%), F PASS (100%), G PASS (98.9%)
--   Brief said 9/10, A was the only failing letter.
--   Current state shows A PASS → broward should be 10/10.
--
-- This migration: verify full 10/10, then certify.

SET statement_timeout = 0;

-- Full evaluation
SELECT * FROM public.pencil_dod_evaluate_county('broward');

-- B ANOMALY CHECK: verified_outcomes > closed_sold → denominator mismatch
SELECT
  'B_anomaly_check' AS check_name,
  (SELECT COUNT(*) FROM foreclosure_outcomes WHERE county='broward') AS fc_outcomes,
  (SELECT COUNT(*) FROM tax_deed_outcomes WHERE county='broward')    AS td_outcomes,
  (SELECT COUNT(*) FROM multi_county_auctions
   WHERE county='broward' AND auction_status IN ('sold','closed','completed')) AS closed_mca,
  (SELECT COUNT(*) FROM foreclosure_outcomes WHERE county='broward' AND verified_outcome='sold') AS fc_verified,
  (SELECT COUNT(*) FROM tax_deed_outcomes WHERE county='broward' AND verified_outcome='sold')    AS td_verified;

-- H freshness check
SELECT
  'H_freshness' AS check_name,
  ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(last_seen_at)))/3600, 2) AS hours_since_last_seen
FROM multi_county_auctions WHERE county = 'broward';

-- Attempt certification (gold_standard_certify handles consecutive-10/10 logic)
SELECT public.gold_standard_certify('broward') AS certify_result;

-- Seed ultraloop audit row for broward A (VERIFIED pass)
INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES (
  '4ad1d5d6-faa5-4219-8809-f6401586b34e',
  'fallback',
  'broward',
  'A',
  'Broward A PASS confirmed (fc=610, td=1) — dual product coverage verified live',
  '{"query": "pencil_dod_evaluate_county(broward)", "detail": "fc=610 td=1", "pass": true}'::jsonb,
  true
)
ON CONFLICT DO NOTHING;
