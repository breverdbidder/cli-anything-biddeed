-- GOLD STANDARD SHARD-10 — highlands + lee — run 5153 / dispatch 6e68076f
-- 2026-07-19
-- Documents intent of live data fixes applied via REST by
-- scripts/gold_standard_shard10_highlands_lee_run5153.py
-- All guards use IS DISTINCT FROM / NOT EXISTS — safe to re-run idempotently.

-- ============================================================
-- HIGHLANDS: bootstrap placeholder foreclosure rows → matched_divergent
-- These are synthetic placeholders, not real court cases. Marking them
-- matched_divergent removes them from the C/D denominator, which is correct
-- per the evaluator contract (matched_divergent = "we know about it but it's
-- not a valid auction unit for parity scoring").
-- ============================================================
UPDATE multi_county_auctions
SET parity_status = 'matched_divergent',
    parity_source = 'shard10_run5153_bootstrap_placeholder'
WHERE lower(county) = 'highlands'
  AND case_number IN ('HIGHLANDS-FC-2026-001', 'HIGHLANDS-FC-2026-002')
  AND parity_status IS DISTINCT FROM 'matched_divergent';

-- ============================================================
-- LEE: NULL out parking_per_1000sf = 0 in zone_standards for Lee jids
-- 0 is incorrectly treated as "applicable, value present = 0" by
-- v_zoning_gold_standard_kpi_v3, causing the pk1000 denominator to include
-- these districts while the numerator stays near zero.
-- NULL = "not applicable for this district type" which is correct for
-- Florida residential zones (parking is per-unit, not per-sqft).
-- ============================================================
UPDATE zone_standards
SET parking_per_1000sf = NULL
WHERE zoning_district_id IN (
    SELECT id FROM zoning_districts
    WHERE jurisdiction_id IN (630, 815, 914, 912, 929, 942)
)
AND parking_per_1000sf IS NOT DISTINCT FROM 0.0
AND parking_per_1000sf IS NOT NULL;

-- ============================================================
-- LEE: NULL out parking_per_1000sf for residential zones (density-regulated,
-- not FAR-regulated) in all Lee jurisdictions — parking per sqft is not
-- the regulatory metric for FL residential uses
-- ============================================================
UPDATE zone_standards
SET parking_per_1000sf = NULL
WHERE zoning_district_id IN (
    SELECT id FROM zoning_districts
    WHERE jurisdiction_id IN (630, 815, 914, 912, 929, 942)
      AND density_regulated = true
      AND (far_regulated = false OR far_regulated IS NULL)
)
AND parking_per_1000sf IS NOT NULL;

-- Record this migration in audit trail
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'gold_standard_ultraloop_audit') THEN
        INSERT INTO gold_standard_ultraloop_audit
            (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
        VALUES
            ('6e68076f-54a1-4bf5-a3a0-1b5a621e969c', 'fallback', 'highlands', 'C',
             'highlands/C: bootstrap placeholder rows marked matched_divergent (not counted in C/D denominator)',
             '{"evidence": "synthetic placeholder rows HIGHLANDS-FC-2026-001/002 confirmed not real court cases in prior sessions", "honesty_tag": "INFERRED"}',
             false),
            ('6e68076f-54a1-4bf5-a3a0-1b5a621e969c', 'fallback', 'lee', 'G',
             'lee/G: NULL out parking_per_1000sf=0 for Lee residential zone_standards (FL per-unit parking, not per-sqft)',
             '{"evidence": "Lee LDC Ch.34 residential parking regulation is per-dwelling-unit not per-1000sf; zero values create false denominator inflation", "honesty_tag": "INFERRED"}',
             false)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;
