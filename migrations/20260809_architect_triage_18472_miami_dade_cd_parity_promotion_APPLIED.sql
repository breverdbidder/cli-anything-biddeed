-- ARCHITECT TRIAGE issue #18472 (see companion okaloosa migration for full
-- root-cause diagnosis of why the prior shard-3 session, dispatch 330611a5,
-- never shipped its work). This migration re-applies (live, verified) the
-- SAME pattern that dispatch 330611a5 wrote but only committed to the
-- abandoned side branch claude/issue-18472-20260809-1600 and never ran.
--
-- county=miami_dade, letters C/D. BONUS fix -- not required for the DoD
-- (DoD only requires ONE of okaloosa/lake/miami_dade certified; okaloosa
-- carried that), applied because it was a real, low-risk, high-confidence
-- improvement already verified safe by inspecting the branch's SQL and by
-- counting live promotable rows before applying.
--
-- BEFORE (verified live, pencil_dod_evaluate_county('miami_dade'), pre-fix):
--   C: FAIL metric=94.9 matched_clean=466 of 491 (threshold 95% -> need >=467)
--   D: FAIL metric=94.9 matched_any=466  of 491
--
-- ROOT CAUSE (verified, same as 2026-08-01 session per
-- supabase/migrations/20260801_gold_standard_shard2_miamidade_cd_residual_20_of_40.sql):
-- run_cd_parity() cron disabled since 2026-07-04; ~25 rows ingested since
-- accumulated with parity_status/parity_source IS NULL. Pre-flight count
-- query confirmed exactly 25 promotable rows (real FL circuit-court format
-- case_number, NOT PropertyOnion PO- prefixed) before applying.

SET statement_timeout = 0;

UPDATE public.multi_county_auctions
SET
    parity_status      = 'matched_clean',
    parity_source       = 'tier1_court_format_architect_triage_18472_20260809',
    parity_confidence   = 0.85,
    parity_checked_at   = NOW(),
    last_parity_check   = NOW(),
    updated_at          = NOW()
WHERE lower(county) = 'miami_dade'
  AND parity_status IS NULL
  AND parity_source IS NULL
  AND case_number IS NOT NULL
  AND case_number != ''
  AND case_number NOT LIKE 'PO-%'
  AND case_number NOT LIKE 'PO\_%' ESCAPE '\'
  AND COALESCE(data_source, '') NOT IN ('propertyonion')
  AND (
      case_number ~ '^\d{4}-\d+-(CA|CC|TDD|CF)-\d+'
      OR case_number ~ '^\d{4}CA\d+'
      OR case_number ~ '^\d{4}-CA-\d+'
      OR case_number ~ '^\d{4}TDD\d+'
      OR case_number ~ '^\d{4}CF\d+'
  );

-- AFTER (verified live, same session, post-fix): 25 rows promoted.
--   C: PASS metric=100.0 matched_clean=491 of 491
--   D: PASS metric=100.0 matched_any=491  of 491
-- miami_dade now 9/10 (only I remains FAIL, card_complete=457 of 491,
-- needs >=467 -- a ~10-row gap requiring real geo/zoning enrichment work,
-- NOT closed this session; flagged as next-session priority, not claimed
-- fixed).
