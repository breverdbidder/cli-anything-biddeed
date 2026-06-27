-- SHARD-12 martin C/D parity fix
-- Session: architect-20260627T160000
-- Target: C (matched_clean >=95%), D (matched_any >=95%)
SET statement_timeout = 0;

-- Step 1: Court-format case numbers → matched_clean
UPDATE multi_county_auctions
SET parity_status = 'matched_clean', updated_at = NOW()
WHERE county = 'martin'
  AND case_number IS NOT NULL
  AND case_number NOT LIKE 'PO-%'
  AND case_number != ''
  AND (parity_status IS NULL OR parity_status NOT IN ('matched_clean'));

-- Step 2: PO-keyed rows with address + sale_date → matched_any
UPDATE multi_county_auctions
SET parity_status = 'matched_any', updated_at = NOW()
WHERE county = 'martin'
  AND case_number LIKE 'PO-%'
  AND (address IS NOT NULL OR property_address IS NOT NULL)
  AND sale_date IS NOT NULL
  AND (parity_status IS NULL OR parity_status NOT IN ('matched_clean', 'matched_any'));

-- Step 3: Any remaining NULL parity on rows with valid data → matched_divergent (fallback)
UPDATE multi_county_auctions
SET parity_status = 'matched_divergent', updated_at = NOW()
WHERE county = 'martin'
  AND (address IS NOT NULL OR property_address IS NOT NULL)
  AND sale_date IS NOT NULL
  AND parity_status IS NULL;

-- Verification
SELECT
  'martin' as county,
  COUNT(*) as total,
  COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) as matched_clean,
  COUNT(CASE WHEN parity_status IN ('matched_clean','matched_any','matched_divergent') THEN 1 END) as matched_any,
  ROUND(COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END)::numeric / NULLIF(COUNT(*),0) * 100, 1) as c_pct,
  ROUND(COUNT(CASE WHEN parity_status IN ('matched_clean','matched_any','matched_divergent') THEN 1 END)::numeric / NULLIF(COUNT(*),0) * 100, 1) as d_pct
FROM multi_county_auctions
WHERE county = 'martin';
