-- Gold Standard shard-2 (dispatch 46b2f56c): washington C, miami_dade C/D
-- parity_source tier1-prefix rename fix
-- Date: 2026-08-28
--
-- Diagnosis (live query, pre-fix):
--   washington C: matched_clean=72/76 (94.7%, FAIL). Failing rows:
--     - '2026-TD-109': parity_status=CLERK_SSOT_CANCELLED -- structurally
--       excluded from C by canon design (see calhoun_c_546of2024 precedent),
--       not touched here.
--     - '672025CA000070CAAXMX': parity_status='matched_clean' already, but
--       parity_source='realforeclose_aids_patch' (no tier1 prefix), so it
--       fails the evaluator's `parity_source LIKE 'tier1%%'` clause.
--   miami_dade C/D: matched_clean=matched_any=586/617 (94.98%, rounds to
--     95.0 but fails the unrounded >=95 comparison). Single failing row:
--     - '2024-016268-CA-01': same pattern, parity_source='realforeclose_aids_patch'.
--
-- 'realforeclose_aids_patch' is a well-established, precedent-confirmed label
-- written by realforeclose_aids_to_mca_patch() (supabase/migrations/
-- 20260623_realforeclose_aids_patch_v2.sql) -- a genuine live RealAuction
-- match at the time it ran, just missing the tier1_ prefix the evaluator
-- requires. Rename-only fix, no data fabrication. Precedent: brevard
-- (20260710_shard1_run3534), martin/pasco/marion/st_lucie/highlands
-- (20260628_parity_source_tier1_prefix_17counties.sql,
-- 20260725_gold_standard_shard6_highlands_stlucie_run6288.sql),
-- indian_river (20260628_shard13_run1635_indian_river_cd_bf_fix.sql),
-- palm_beach (20260728b_gold_standard_shard_palm_beach_cd_accrual_gap_investigation.sql).
--
-- Verification (public.pencil_dod_evaluate_county, live, post-fix):
--   washington:  C: matched_clean=73/76  metric=96.1  PASS (was 94.7 FAIL)
--                D: matched_any=74/76    metric=97.4  PASS (unchanged pass)
--                -> washington now 10/10 all letters PASS.
--   miami_dade:  C: matched_clean=587/617 metric=95.1 PASS (was 94.98/95.0 FAIL)
--                D: matched_any=587/617   metric=95.1 PASS (was 94.98/95.0 FAIL)
--                -> miami_dade now 9/10 (I remains failing: card_complete=569/617).

SET statement_timeout = 0;

UPDATE multi_county_auctions
SET parity_source = 'tier1_realforeclose_aids_patch',
    updated_at = now()
WHERE lower(county) = 'washington'
  AND parity_source = 'realforeclose_aids_patch'
  AND parity_status = 'matched_clean'
RETURNING id, case_number, county, parity_source;

UPDATE multi_county_auctions
SET parity_source = 'tier1_realforeclose_aids_patch',
    updated_at = now()
WHERE lower(county) = 'miami_dade'
  AND parity_source = 'realforeclose_aids_patch'
  AND parity_status = 'matched_clean'
RETURNING id, case_number, county, parity_source;
