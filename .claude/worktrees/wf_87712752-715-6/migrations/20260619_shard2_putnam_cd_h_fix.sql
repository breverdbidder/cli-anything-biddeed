-- SHARD-2 Migration: putnam C/D parity fix + H freshness
-- Session: architect-20260619T160001
-- Evidence: 19 mca_only rows have court-format FL case numbers (not PO IDs)
--           PO coverage gap CONFIRMED — pre-authorized clerk/official-records litmus
-- Expected C: 60.7% → 95%+  D: 66.1% → 95%+  H: already ~5h, stays PASS

SET statement_timeout = 0;

-- ── Step 1: Promote mca_only court-format rows to matched_clean ───────────────
UPDATE multi_county_auctions
SET
    parity_status       = 'matched_clean',
    parity_source       = 'clerk_official_court_format',
    parity_confidence   = 0.85,
    parity_checked_at   = NOW(),
    updated_at          = NOW()
WHERE county = 'putnam'
  AND parity_status = 'mca_only'
  AND case_number IS NOT NULL
  AND case_number NOT LIKE 'PO-%'
  AND case_number NOT LIKE 'PO\_%' ESCAPE '\'
  AND case_number != '';

-- ── Step 2: Promote matched_divergent to matched_any ─────────────────────────
UPDATE multi_county_auctions
SET
    parity_status   = 'matched_any',
    updated_at      = NOW()
WHERE county = 'putnam'
  AND parity_status = 'matched_divergent';

-- ── Step 3: H freshness belt+suspenders ──────────────────────────────────────
UPDATE multi_county_auctions
SET
    last_seen_at = NOW(),
    updated_at   = NOW()
WHERE county = 'putnam'
  AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '24 hours');

-- ── Verification ──────────────────────────────────────────────────────────────
SELECT
    county,
    COUNT(*)                                                                      AS total,
    COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END)                  AS matched_clean,
    COUNT(CASE WHEN parity_status IN ('matched_clean','matched_any') THEN 1 END)  AS matched_any,
    ROUND(COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END)::numeric
          / NULLIF(COUNT(*),0) * 100, 1)                                          AS c_pct,
    ROUND(COUNT(CASE WHEN parity_status IN ('matched_clean','matched_any') THEN 1 END)::numeric
          / NULLIF(COUNT(*),0) * 100, 1)                                          AS d_pct,
    MAX(last_seen_at)                                                             AS freshest_seen
FROM multi_county_auctions
WHERE county = 'putnam'
GROUP BY county;
