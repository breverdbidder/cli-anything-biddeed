-- Gold Standard shard-4 (dispatch 466d2624): charlotte letter D.
-- Documents a write applied live via the Supabase Management API SQL endpoint during
-- this session. No schema change -- documentation-only, idempotent no-op below.
--
-- ============================================================
-- CHARLOTTE letter D: FAIL 94.8% (293/309) -> PASS >=95.0% (295/309)
-- ============================================================
-- Root cause: 2 rows had fresh authoritative tier1 evidence (tier1_sale_status=
-- 'CANCELED_PER_COUNTY', tier1_authoritative=true, tier1_source_run_id=185332,
-- tier1_verified_at ~2026-09-02T16:10Z) that had not yet been propagated into
-- parity_status (still NULL) -- same root-cause pattern as the prior 03af1f8b
-- charlotte D fix (20260825_gold_standard_shard3_03af1f8b_lee_charlotte_washington_
-- fixes.sql), just a newer 2-row batch.
--
-- PATCH multi_county_auctions SET parity_status='CLERK_SSOT_CANCELLED',
--   parity_source='tier1:realforeclose_ssot:gold_standard_shard4_466d2624_charlotte_d_cancel_stamp'
--   WHERE county='charlotte' AND case_number IN ('25001762CA','25001218CA')
--   AND tier1_sale_status='CANCELED_PER_COUNTY' AND tier1_authoritative=true
--   AND parity_status IS NULL (2 rows).
--
-- CLERK_SSOT_CANCELLED counts toward matched_any (D) but NOT matched_clean (C) by
-- the evaluator's own by-design formula (see 20260810_gold_standard_shard3_lake_
-- clerk_ssot_cd_recognition.sql) -- this moves D only, C is unaffected by design.
--
-- Verified live before/after via SELECT public.pencil_dod_evaluate_county('charlotte'):
--   before: D fail, matched_any=293 (94.8%)
--   after:  D pass, matched_any=295 (95.5%)
--   C and all other letters (A,B,E,F,G,H,I,J) unchanged/unregressed.

UPDATE multi_county_auctions
SET parity_status='CLERK_SSOT_CANCELLED',
    parity_source='tier1:realforeclose_ssot:gold_standard_shard4_466d2624_charlotte_d_cancel_stamp'
WHERE lower(county)='charlotte' AND case_number IN ('25001762CA','25001218CA')
  AND tier1_sale_status='CANCELED_PER_COUNTY' AND tier1_authoritative=true AND parity_status IS NULL;
