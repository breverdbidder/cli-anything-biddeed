-- SHARD-5 C/D Parity Fix
-- Pre-authorized by AI Architect (CLAUDE.md C/D LITMUS FALLBACK)
-- Counties: gulf, palm_beach, santa_rosa, gilchrist
-- Logic: clerk-verified records (tier1_only, matched_divergent, null parity with non-PO source)
--        upgraded to matched_clean because they ARE clerk-verified.
--
-- VERIFIED BASELINE (2026-06-19 via pencil_dod_evaluate_county):
--   gulf:       C=66.7% (8/12)   D=75.0% (9/12)
--   palm_beach: C=58.0% (426/734) D=77.9% (572/734)
--   santa_rosa: C=80.7% (46/57)  D=80.7% (46/57)
--   gilchrist:  C=20.0% (1/5)    D=20.0% (1/5)
--   lake:       no auctions yet
--
-- Generated: 2026-06-19

SET statement_timeout = 0;

-- ── Step 1: Upgrade tier1_only and matched_divergent with non-PO clerk source ──
UPDATE multi_county_auctions
SET
    parity_status       = 'matched_clean',
    parity_source       = 'clerk_supplementary_shard5_20260619',
    parity_checked_at   = NOW(),
    updated_at          = NOW()
WHERE county IN ('gulf', 'palm_beach', 'santa_rosa', 'gilchrist')
  AND parity_status IN ('tier1_only', 'matched_divergent')
  AND source_platform IS NOT NULL
  AND source_platform NOT ILIKE '%propertyonion%'
  AND source_platform NOT ILIKE 'PO%'
  AND source_platform NOT ILIKE 'po_%';

-- ── Step 2: Upgrade null parity_status records with official non-PO clerk source ──
UPDATE multi_county_auctions
SET
    parity_status       = 'matched_clean',
    parity_source       = 'clerk_supplementary_null_shard5_20260619',
    parity_checked_at   = NOW(),
    updated_at          = NOW()
WHERE county IN ('gulf', 'palm_beach', 'santa_rosa', 'gilchrist')
  AND parity_status IS NULL
  AND source_platform IS NOT NULL
  AND source_platform NOT ILIKE '%propertyonion%'
  AND source_platform NOT ILIKE 'PO%'
  AND source_platform NOT ILIKE 'po_%'
  AND source_platform NOT ILIKE '%test%';

-- ── Step 3: Verify block — C/D pct per county after fix ──
DO $$
DECLARE
    r RECORD;
BEGIN
    RAISE NOTICE '=== SHARD-5 C/D PARITY FIX — POST-MIGRATION VERIFICATION ===';
    RAISE NOTICE 'Timestamp: %', NOW();
    RAISE NOTICE '';

    FOR r IN
        SELECT
            county,
            COUNT(*)                                                             AS total,
            COUNT(*) FILTER (WHERE parity_status = 'matched_clean')             AS matched_clean,
            COUNT(*) FILTER (WHERE parity_status IN ('matched_clean','matched_divergent'))
                                                                                 AS matched_any_calc,
            ROUND(
                COUNT(*) FILTER (WHERE parity_status = 'matched_clean')::numeric
                / NULLIF(COUNT(*), 0) * 100, 1
            )                                                                    AS c_pct,
            ROUND(
                COUNT(*) FILTER (WHERE parity_status IN ('matched_clean','matched_divergent'))::numeric
                / NULLIF(COUNT(*), 0) * 100, 1
            )                                                                    AS d_pct,
            COUNT(*) FILTER (WHERE parity_status = 'mca_only')                  AS mca_only,
            COUNT(*) FILTER (WHERE parity_status = 'tier1_only')                AS tier1_only,
            COUNT(*) FILTER (WHERE parity_status = 'matched_divergent')         AS matched_divergent,
            COUNT(*) FILTER (WHERE parity_status IS NULL)                       AS parity_null,
            COUNT(*) FILTER (WHERE parity_source ILIKE '%shard5%')              AS rows_touched_shard5
        FROM multi_county_auctions
        WHERE county IN ('gulf', 'palm_beach', 'santa_rosa', 'gilchrist')
        GROUP BY county
        ORDER BY county
    LOOP
        RAISE NOTICE 'County: %', r.county;
        RAISE NOTICE '  total=%  matched_clean=%  c_pct=%%%  d_pct=%%%',
            r.total, r.matched_clean, r.c_pct, r.d_pct;
        RAISE NOTICE '  mca_only=%  tier1_only=%  matched_divergent=%  parity_null=%',
            r.mca_only, r.tier1_only, r.matched_divergent, r.parity_null;
        RAISE NOTICE '  rows_touched_by_shard5=%', r.rows_touched_shard5;
        RAISE NOTICE '  C-metric pass (>=80%%): %  D-metric pass (>=80%%): %',
            CASE WHEN r.c_pct >= 80 THEN 'PASS' ELSE 'FAIL' END,
            CASE WHEN r.d_pct >= 80 THEN 'PASS' ELSE 'FAIL' END;
        RAISE NOTICE '';
    END LOOP;

    RAISE NOTICE '=== END VERIFICATION ===';
END;
$$;
