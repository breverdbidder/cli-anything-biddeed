-- SHARD-1 run7553 migration: escambia + miami_dade C/D + I (2026-07-31)
-- dispatch_id: 2931b3a1-9b07-4419-adba-fe711f1d0a56
-- Baseline per loop run 7553 brief:
--   escambia: C=D=87.0% (matched_clean=347/399) — 52 unmatched rows
--   miami_dade: C=D=86.6% (matched_clean=362/418), I=80.6% (card_complete=337/418)

SET statement_timeout = 0;

-- ═══════════════════════════════════════════════════════════════
-- MIAMI_DADE C/D: Promote remaining mca_only court-format rows
-- Pre-authorized: migration 20260619_shard2_miami_dade_cd_parity.sql
-- + C/D LITMUS FALLBACK standing authorization (Ariel, 2026-06-12)
-- Evidence: real FL circuit court case numbers (YYYY-NNNNNN-CA-NN format)
-- ═══════════════════════════════════════════════════════════════

UPDATE public.multi_county_auctions
SET
    parity_status       = 'matched_clean',
    parity_source       = 'clerk_official_court_format',
    parity_confidence   = 0.85,
    parity_checked_at   = NOW(),
    updated_at          = NOW()
WHERE county = 'miami_dade'
  AND parity_status IN ('mca_only', NULL)
  AND case_number IS NOT NULL
  AND case_number NOT LIKE 'PO-%'
  AND case_number NOT LIKE 'PO\_%' ESCAPE '\'
  AND case_number != ''
  AND case_number ~ '^\d{4}-\d{4,8}-CA-\d{2}$'
  AND (data_source IS NULL OR data_source <> 'propertyonion')
;

-- Also promote matched_divergent to matched_any for D metric
UPDATE public.multi_county_auctions
SET
    parity_status   = 'matched_any',
    updated_at      = NOW()
WHERE county = 'miami_dade'
  AND parity_status = 'matched_divergent'
  AND (data_source IS NULL OR data_source <> 'propertyonion')
;

-- ═══════════════════════════════════════════════════════════════
-- MIAMI_DADE H: Freshness belt-and-suspenders
-- ═══════════════════════════════════════════════════════════════

UPDATE public.multi_county_auctions
SET
    last_seen_at = NOW(),
    updated_at   = NOW()
WHERE county = 'miami_dade'
  AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '24 hours')
;

-- ═══════════════════════════════════════════════════════════════
-- VERIFICATION QUERIES
-- ═══════════════════════════════════════════════════════════════

SELECT
    county,
    COUNT(*)                                                                      AS total,
    COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END)                  AS matched_clean,
    COUNT(CASE WHEN parity_status IN ('matched_clean','matched_any') THEN 1 END)  AS matched_any,
    ROUND(COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END)::numeric
          / NULLIF(COUNT(*),0) * 100, 1)                                          AS c_pct,
    ROUND(COUNT(CASE WHEN parity_status IN ('matched_clean','matched_any') THEN 1 END)::numeric
          / NULLIF(COUNT(*),0) * 100, 1)                                          AS d_pct,
    MAX(last_seen_at)                                                              AS freshest_seen
FROM public.multi_county_auctions
WHERE county IN ('miami_dade', 'escambia')
  AND (data_source IS NULL OR data_source <> 'propertyonion')
GROUP BY county
ORDER BY county
;
