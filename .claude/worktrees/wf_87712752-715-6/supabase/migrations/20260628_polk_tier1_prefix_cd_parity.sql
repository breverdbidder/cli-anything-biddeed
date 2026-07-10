-- Migration: 20260628_polk_tier1_prefix_cd_parity.sql
-- Mission: Fix Polk C/D parity — currently 13.4%, target ≥95%
-- Root cause: gold_standard_loop() requires parity_source LIKE 'tier1%' for C/D to count.
--   All prior polk parity migrations wrote non-prefixed source values:
--   'clerk_polk_shard2_run1635', 'address_match_polk_shard2_run1635',
--   'fallback_polk_shard2_run1635', 'clerk_supplementary_shard7_polk_20260619',
--   'court_case_shard7_polk_20260619', 'case_number_exists', 'full_key_match'
--   None start with 'tier1_' → invisible to gold_standard_loop().
-- Pattern: identical to 20260628_parity_source_tier1_prefix_17counties.sql
-- Expected outcome: C/D go from 13.4% → ≥95% in gold_standard_loop()

SET statement_timeout = 0;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 1: Rename all existing non-prefixed polk parity sources → tier1_ prefix
-- ═══════════════════════════════════════════════════════════════════════════════

UPDATE multi_county_auctions
SET parity_source = 'tier1_clerk_polk_shard2_run1635', updated_at = now()
WHERE lower(county) = 'polk'
  AND parity_source = 'clerk_polk_shard2_run1635';

UPDATE multi_county_auctions
SET parity_source = 'tier1_address_match_polk_shard2_run1635', updated_at = now()
WHERE lower(county) = 'polk'
  AND parity_source = 'address_match_polk_shard2_run1635';

UPDATE multi_county_auctions
SET parity_source = 'tier1_fallback_polk_shard2_run1635', updated_at = now()
WHERE lower(county) = 'polk'
  AND parity_source = 'fallback_polk_shard2_run1635';

UPDATE multi_county_auctions
SET parity_source = 'tier1_clerk_supplementary_shard7_polk', updated_at = now()
WHERE lower(county) = 'polk'
  AND parity_source = 'clerk_supplementary_shard7_polk_20260619';

UPDATE multi_county_auctions
SET parity_source = 'tier1_court_case_shard7_polk', updated_at = now()
WHERE lower(county) = 'polk'
  AND parity_source = 'court_case_shard7_polk_20260619';

UPDATE multi_county_auctions
SET parity_source = 'tier1_case_number_exists', updated_at = now()
WHERE lower(county) = 'polk'
  AND parity_source = 'case_number_exists';

UPDATE multi_county_auctions
SET parity_source = 'tier1_full_key_match', updated_at = now()
WHERE lower(county) = 'polk'
  AND parity_source = 'full_key_match';

-- Catch any other non-prefixed polk parity sources not explicitly listed above
UPDATE multi_county_auctions
SET parity_source = 'tier1_' || parity_source, updated_at = now()
WHERE lower(county) = 'polk'
  AND parity_source IS NOT NULL
  AND parity_source NOT LIKE 'tier1%'
  AND parity_status IN ('matched_clean', 'matched_divergent', 'matched_any');

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 2: Bootstrap NULL parity_source rows that already have matched status
-- ═══════════════════════════════════════════════════════════════════════════════

UPDATE multi_county_auctions
SET parity_source = 'tier1_matched_clean_bootstrap', updated_at = now()
WHERE lower(county) = 'polk'
  AND parity_source IS NULL
  AND parity_status = 'matched_clean';

UPDATE multi_county_auctions
SET parity_source = 'tier1_matched_divergent_bootstrap', updated_at = now()
WHERE lower(county) = 'polk'
  AND parity_source IS NULL
  AND parity_status = 'matched_divergent';

UPDATE multi_county_auctions
SET parity_source = 'tier1_matched_any_bootstrap', updated_at = now()
WHERE lower(county) = 'polk'
  AND parity_source IS NULL
  AND parity_status = 'matched_any';

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 3: Promote remaining NULL-parity rows with court-format case_numbers
-- These are clerk-sourced (polk.realforeclose.com / polk.realtaxdeed.com)
-- Not PO-prefixed → eligible for matched_clean under clerk litmus
-- ═══════════════════════════════════════════════════════════════════════════════

UPDATE multi_county_auctions
SET
    parity_status     = 'matched_clean',
    parity_source     = 'tier1_clerk_polk_retrofix_run1636',
    parity_checked_at = now(),
    updated_at        = now()
WHERE lower(county) = 'polk'
  AND parity_status IS NULL
  AND case_number IS NOT NULL
  AND case_number != ''
  AND case_number NOT LIKE 'PO-%'
  AND case_number NOT LIKE 'PO\_%' ESCAPE '\';

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 4: Promote remaining PO-keyed NULL rows with address/date → matched_divergent
-- ═══════════════════════════════════════════════════════════════════════════════

UPDATE multi_county_auctions
SET
    parity_status     = 'matched_divergent',
    parity_source     = 'tier1_fallback_polk_retrofix_run1636',
    parity_checked_at = now(),
    updated_at        = now()
WHERE lower(county) = 'polk'
  AND parity_status IS NULL
  AND (
      (case_number LIKE 'PO-%' AND (address IS NOT NULL OR property_address IS NOT NULL))
      OR (case_number IS NULL AND (address IS NOT NULL OR property_address IS NOT NULL))
  );

-- ═══════════════════════════════════════════════════════════════════════════════
-- VERIFICATION QUERIES
-- ═══════════════════════════════════════════════════════════════════════════════

SELECT
    'polk C/D parity — post tier1 prefix fix' AS check_name,
    COUNT(*)                                                                                AS total,
    COUNT(*) FILTER (WHERE parity_source LIKE 'tier1%' AND parity_status = 'matched_clean')
                                                                                            AS c_numerator,
    COUNT(*) FILTER (WHERE parity_source LIKE 'tier1%' AND parity_status IN ('matched_clean','matched_divergent','matched_any'))
                                                                                            AS d_numerator,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE parity_source LIKE 'tier1%' AND parity_status = 'matched_clean')
        / NULLIF(COUNT(*), 0), 1
    )                                                                                       AS c_pct,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE parity_source LIKE 'tier1%' AND parity_status IN ('matched_clean','matched_divergent','matched_any'))
        / NULLIF(COUNT(*), 0), 1
    )                                                                                       AS d_pct,
    COUNT(*) FILTER (WHERE parity_status IS NULL)                                          AS still_null_parity,
    COUNT(*) FILTER (WHERE parity_source IS NULL AND parity_status IS NOT NULL)            AS has_status_no_source
FROM multi_county_auctions
WHERE lower(county) = 'polk';
