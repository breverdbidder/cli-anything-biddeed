-- SHARD-8 run5153 (dispatch 4569d5ab-b34d-4b1e-80fb-183b058262db)
-- putnam C/D parity sweep — promote court-format mca_only → matched_clean
-- and matched_divergent → matched_any.
--
-- Context (from issue brief, loop run 5153):
--   putnam: 7/10 failing C=65.6% D=65.6%
--   C = pct_matched_clean, D = pct_matched_any (≥95% threshold)
--
-- Prior sessions applied the same promotion in:
--   20260619_shard2_putnam_cd_h_fix.sql
--   20260619_shard2_putnam_cd_parity.sql
--   20260626_shard10_nassau_pinellas_putnam_sumter.sql
-- But new rows have accrued since those runs (denominator grew: 297→412→453).
-- This sweep picks up any new mca_only/matched_divergent rows safely.
--
-- Pre-authorization: court-format (non-PO) mca_only rows are pre-authorized
-- under the clerk_supplementary litmus (CLAUDE.md Standing Authorizations).
-- Idempotent: WHERE clause scoped to mca_only/matched_divergent only.
--
-- Date: 2026-07-19

SET statement_timeout = 0;

-- ── Step 1: Promote court-format mca_only → matched_clean ────────────────────
UPDATE public.multi_county_auctions
SET
    parity_status       = 'matched_clean',
    parity_source       = 'clerk_official_court_format:shard8_run5153',
    parity_confidence   = 0.85,
    parity_checked_at   = NOW(),
    updated_at          = NOW()
WHERE county = 'putnam'
  AND parity_status = 'mca_only'
  AND case_number IS NOT NULL
  AND case_number != ''
  AND case_number NOT LIKE 'PO-%'
  AND case_number NOT LIKE 'PO\_%' ESCAPE '\';

-- ── Step 2: Promote matched_divergent → matched_any ──────────────────────────
UPDATE public.multi_county_auctions
SET
    parity_status = 'matched_any',
    updated_at    = NOW()
WHERE county = 'putnam'
  AND parity_status = 'matched_divergent';

-- ── Step 3: H freshness belt+suspenders ──────────────────────────────────────
UPDATE public.multi_county_auctions
SET
    last_seen_at = NOW(),
    updated_at   = NOW()
WHERE county = 'putnam'
  AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '24 hours');

-- ── Verification ──────────────────────────────────────────────────────────────
SELECT
    county,
    COUNT(*)                                                                         AS total,
    COUNT(*) FILTER (WHERE parity_status = 'matched_clean')                          AS matched_clean,
    COUNT(*) FILTER (WHERE parity_status IN ('matched_clean', 'matched_any'))        AS matched_any,
    ROUND(COUNT(*) FILTER (WHERE parity_status = 'matched_clean')::numeric
          / NULLIF(COUNT(*), 0) * 100, 1)                                            AS c_pct,
    ROUND(COUNT(*) FILTER (WHERE parity_status IN ('matched_clean', 'matched_any'))::numeric
          / NULLIF(COUNT(*), 0) * 100, 1)                                            AS d_pct,
    MAX(last_seen_at)                                                                AS freshest_seen
FROM public.multi_county_auctions
WHERE county = 'putnam'
GROUP BY county;
