-- SHARD-5 run2753 (osceola/levy/volusia/putnam/sumter): putnam C/D ghost-success revert
-- dispatch_id: e815c313-9d14-4a45-b961-f4979680beea
-- Session: architect-20260703T160000
--
-- ROOT CAUSE (VERIFIED live 2026-07-05 via Supabase Management API SQL, then independently
-- re-verified by an adversarial ULTRALOOP refuter subagent running its own live queries):
-- migrations/20260619_shard2_putnam_cd_parity.sql mass-stamped 217 putnam multi_county_auctions
-- rows from parity_status='mca_only' to 'matched_clean' with parity_source='clerk_official_court_format'
-- and parity_confidence=0.85 (214 rows) / 0.80 (3 rows, stamped in a separate later event on
-- 2026-07-02, same signature). The stamping rule was purely "case_number does NOT start with
-- 'PO-' or 'PO_'" -- there is no JOIN and no cross-check against tax_deed_outcomes or
-- foreclosure_outcomes anywhere in that migration or anywhere else for these rows.
--
-- Refuter-verified facts (independent live queries, 2026-07-05):
--   1. All 217 rows carrying parity_source='clerk_official_court_format' AND
--      parity_status='matched_clean' have sold_amount IS NULL (0 of 217 have any sale result).
--   2. 0 of 217 have a matching case_number in tax_deed_outcomes OR foreclosure_outcomes for
--      lower(county)='putnam' -- zero independent backing of any kind.
--   3. The evaluator (pencil_dod_evaluate_county) already excludes these from C/D because its
--      filter requires parity_source LIKE 'tier1%%' -- so this ghost-success was NOT inflating
--      the current live scoreboard (putnam C/D already correctly read 2.5%%, backed only by the
--      6 genuinely tier1-sourced rows). This migration is a data-integrity cleanup, not a metric
--      fix: it removes a false "verified" stamp sitting in the base table before it can
--      accidentally get picked up by any future join, dashboard, or certification path that
--      doesn't share the evaluator's tier1%% filter.
--
-- ACTION: null the fabricated parity stamp on exactly these 217 rows. The WHERE clause matches
-- on (county, parity_source, parity_status) with no confidence filter, so it captures both the
-- 214 rows at confidence 0.85 and the 3 at confidence 0.80 in one statement, and cannot touch
-- the 6 genuinely tier1_tax_deed_outcome / tier1_foreclosure_outcome-backed putnam rows (they
-- carry a different parity_source value entirely).

BEGIN;

UPDATE multi_county_auctions
   SET parity_status     = NULL,
       parity_source     = NULL,
       parity_confidence = NULL,
       parity_checked_at = NULL,
       updated_at        = now()
 WHERE lower(county) = 'putnam'
   AND parity_source = 'clerk_official_court_format'
   AND parity_status = 'matched_clean';

INSERT INTO honesty_violations
  (id, domain, claim, tag_used, actual_truth, severity, session_source, corrective_action, resolved)
VALUES
  (gen_random_uuid(), 'GOLD_STANDARD_CAMPAIGN',
   'putnam multi_county_auctions carried 217 rows stamped parity_status=matched_clean / parity_source=clerk_official_court_format / parity_confidence=0.85(214)+0.80(3)',
   'VERIFIED',
   'All 217 rows had sold_amount IS NULL and zero backing in tax_deed_outcomes or foreclosure_outcomes by case_number. The stamp came from migrations/20260619_shard2_putnam_cd_parity.sql, which flips mca_only to matched_clean purely because a case_number does not start with PO-/PO_, with no cross-check against any outcome table. The evaluator already excludes these from C/D (requires parity_source LIKE tier1%%), so live C/D metrics were unaffected, but the false stamp remained live in the base table as a data-integrity risk.',
   'CRITICAL',
   'architect-20260703T160000 (dispatch e815c313-9d14-4a45-b961-f4979680beea), independently re-verified by ULTRALOOP refuter subagent (run wf_67ae8f8a-f30) before execution',
   'Nulled parity_status/parity_source/parity_confidence/parity_checked_at on the 217 fabricated rows. See supabase/migrations/20260705_shard5_run2753_putnam_cd_ghost_success_revert.sql.',
   true);

INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  ('e815c313-9d14-4a45-b961-f4979680beea', 'native', 'putnam', 'C',
   'putnam has 217 rows genuinely matched_clean via clerk_official_court_format that could be restamped tier1 to raise C from 2.5%% to ~93%%',
   '{"verdict":"CONFIRMED_GHOST_SUCCESS","evidence":"0 of 217 rows have any backing in tax_deed_outcomes/foreclosure_outcomes by case_number; all 217 have sold_amount IS NULL; source migration 20260619_shard2_putnam_cd_parity.sql stamps matched_clean purely by excluding PO-prefixed case numbers with zero cross-check","independent_refuter_run":"wf_67ae8f8a-f30"}'::jsonb,
   false),
  ('e815c313-9d14-4a45-b961-f4979680beea', 'native', 'putnam', 'D',
   'same claim as C, for matched_any',
   '{"verdict":"CONFIRMED_GHOST_SUCCESS","evidence":"same root cause as C"}'::jsonb,
   false);

COMMIT;
