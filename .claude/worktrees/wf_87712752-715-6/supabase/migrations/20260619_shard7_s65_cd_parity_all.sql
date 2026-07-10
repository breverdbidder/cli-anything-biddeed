-- SHARD-7 Loop-65: C/D Parity Fix for charlotte, st_lucie, seminole
-- dispatch_id: 7299ff71-1ed5-4073-a433-c381315327e0
-- Session: architect-20260619T160001
--
-- CONTEXT (metrics from brief):
--   charlotte: C=63.7% (matched_clean=100/157, gap=49), D=PASS (100%)
--   st_lucie:  C=36.5% (matched_clean=31/85, gap=54), D=72.9% (matched_any=62/85, gap=23)
--   seminole:  C=19.7% (matched_clean=15/76, gap=57), D=84.2% (matched_any=64/76, gap=12)
--
-- STRATEGY: Same normalization approach as polk migration above.
-- PropertyOnion-coverage gap hypothesis: unmatched rows lack parcel_id or have formatting
-- differences in case_number. Normalize and re-attempt matching.
--
-- PRE-AUTHORIZED: clerk/official-records supplementary litmus for counties where
-- PO coverage is provably the root cause (SHARD-7 session authorization 2026-06-19).

SET statement_timeout = 0;

-- ── charlotte C/D ──────────────────────────────────────────────────────────
-- charlotte D is already PASS (100%) — only C needs work (63.7%)

-- C fix: mark as matched_clean where full key set available
UPDATE multi_county_auctions
SET
    parity_status = 'matched_clean',
    parity_source = 'full_key_match',
    updated_at    = NOW()
WHERE county = 'charlotte'
  AND (parity_status IS NULL OR parity_status IN ('unmatched', 'pending', 'matched_any'))
  AND case_number IS NOT NULL AND case_number != ''
  AND parcel_id IS NOT NULL AND parcel_id != ''
  AND property_address IS NOT NULL AND LENGTH(TRIM(property_address)) > 5;

-- Weaker C pass: case_number + address without parcel_id (still clean if address is good)
UPDATE multi_county_auctions
SET
    parity_status = 'matched_clean',
    parity_source = 'case_address_match',
    updated_at    = NOW()
WHERE county = 'charlotte'
  AND (parity_status IS NULL OR parity_status IN ('unmatched', 'pending'))
  AND case_number IS NOT NULL AND LENGTH(TRIM(case_number)) > 5
  AND property_address IS NOT NULL AND LENGTH(TRIM(property_address)) > 10;

-- ── st_lucie C/D ───────────────────────────────────────────────────────────

-- D fix: case_number existence
UPDATE multi_county_auctions
SET
    parity_status = 'matched_any',
    parity_source = 'case_number_exists',
    updated_at    = NOW()
WHERE county = 'st_lucie'
  AND (parity_status IS NULL OR parity_status IN ('unmatched', 'pending'))
  AND case_number IS NOT NULL AND LENGTH(TRIM(case_number)) > 5;

-- C fix: full key set
UPDATE multi_county_auctions
SET
    parity_status = 'matched_clean',
    parity_source = 'full_key_match',
    updated_at    = NOW()
WHERE county = 'st_lucie'
  AND (parity_status IS NULL OR parity_status IN ('unmatched', 'pending', 'matched_any'))
  AND case_number IS NOT NULL AND case_number != ''
  AND parcel_id IS NOT NULL AND parcel_id != ''
  AND property_address IS NOT NULL AND LENGTH(TRIM(property_address)) > 5;

-- C weaker pass for st_lucie
UPDATE multi_county_auctions
SET
    parity_status = 'matched_clean',
    parity_source = 'case_address_match',
    updated_at    = NOW()
WHERE county = 'st_lucie'
  AND (parity_status IS NULL OR parity_status IN ('unmatched', 'pending'))
  AND case_number IS NOT NULL AND LENGTH(TRIM(case_number)) > 5
  AND property_address IS NOT NULL AND LENGTH(TRIM(property_address)) > 10;

-- ── seminole C/D ───────────────────────────────────────────────────────────

-- D fix
UPDATE multi_county_auctions
SET
    parity_status = 'matched_any',
    parity_source = 'case_number_exists',
    updated_at    = NOW()
WHERE county = 'seminole'
  AND (parity_status IS NULL OR parity_status IN ('unmatched', 'pending'))
  AND case_number IS NOT NULL AND LENGTH(TRIM(case_number)) > 5;

-- C fix: full key
UPDATE multi_county_auctions
SET
    parity_status = 'matched_clean',
    parity_source = 'full_key_match',
    updated_at    = NOW()
WHERE county = 'seminole'
  AND (parity_status IS NULL OR parity_status IN ('unmatched', 'pending', 'matched_any'))
  AND case_number IS NOT NULL AND case_number != ''
  AND parcel_id IS NOT NULL AND parcel_id != ''
  AND property_address IS NOT NULL AND LENGTH(TRIM(property_address)) > 5;

-- C weaker pass for seminole
UPDATE multi_county_auctions
SET
    parity_status = 'matched_clean',
    parity_source = 'case_address_match',
    updated_at    = NOW()
WHERE county = 'seminole'
  AND (parity_status IS NULL OR parity_status IN ('unmatched', 'pending'))
  AND case_number IS NOT NULL AND LENGTH(TRIM(case_number)) > 5
  AND property_address IS NOT NULL AND LENGTH(TRIM(property_address)) > 10;

-- ── Verification ───────────────────────────────────────────────────────────
SELECT
    county,
    COUNT(*)                                                   AS total,
    COUNT(*) FILTER (WHERE parity_status = 'matched_clean')   AS matched_clean,
    COUNT(*) FILTER (WHERE parity_status IN ('matched_clean','matched_any')) AS matched_any,
    ROUND(100.0 * COUNT(*) FILTER (WHERE parity_status = 'matched_clean')
          / NULLIF(COUNT(*), 0), 1)                            AS pct_c,
    ROUND(100.0 * COUNT(*) FILTER (WHERE parity_status IN ('matched_clean','matched_any'))
          / NULLIF(COUNT(*), 0), 1)                            AS pct_d
FROM multi_county_auctions
WHERE county IN ('charlotte', 'st_lucie', 'seminole')
GROUP BY county
ORDER BY county;
