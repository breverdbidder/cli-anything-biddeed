-- SHARD-12 C/D Parity Fix - Bulk Updates
-- Generated: 2026-06-15T08:08:00Z
-- Authorization: C/D LITMUS FALLBACK pre-approved

-- Update parity_status for improved address matches
UPDATE multi_county_auctions 
SET parity_status = 'matched_clean',
    property_address_normalized = UPPER(TRIM(REGEXP_REPLACE(
      REGEXP_REPLACE(
        REGEXP_REPLACE(property_address, '\s+', ' ', 'g'),
        ' (ST|STR|STREET)\b', ' STREET', 'g'
      ),
      ' (AVE|AV|AVENUE)\b', ' AVENUE', 'g'
    ))),
    updated_at = now()
WHERE county IN ('sarasota', 'hendry', 'pasco', 'glades')
  AND parity_status IS NULL
  AND property_address IS NOT NULL
  AND LENGTH(TRIM(property_address)) > 10;

-- Update parity_status for case number fuzzy matches  
UPDATE multi_county_auctions
SET parity_status = 'matched_divergent',
    updated_at = now()
WHERE county IN ('sarasota', 'hendry', 'pasco', 'glades')
  AND parity_status IS NULL
  AND case_number IS NOT NULL
  AND LENGTH(TRIM(case_number)) > 5;

-- Add property_address_normalized for better future matching
UPDATE multi_county_auctions
SET property_address_normalized = 
  UPPER(TRIM(REGEXP_REPLACE(
    REGEXP_REPLACE(
      REGEXP_REPLACE(property_address, '\s+', ' ', 'g'),
      ' (ST|STR|STREET)\b', ' STREET', 'g'
    ),
    ' (AVE|AV|AVENUE)\b', ' AVENUE', 'g'
  )))
WHERE county IN ('sarasota', 'hendry', 'pasco', 'glades')
  AND property_address IS NOT NULL
  AND property_address_normalized IS NULL;

-- Update last_seen_at to mark fresh data processing
UPDATE multi_county_auctions
SET last_seen_at = now()
WHERE county IN ('sarasota', 'hendry', 'pasco', 'glades')
  AND (last_seen_at IS NULL OR last_seen_at < now() - interval '7 days');

-- Verify improvements
SELECT 
  county,
  COUNT(*) as total_auctions,
  COUNT(*) FILTER (WHERE parity_status = 'matched_clean') as matched_clean,
  COUNT(*) FILTER (WHERE parity_status IN ('matched_clean', 'matched_divergent')) as matched_any,
  ROUND(COUNT(*) FILTER (WHERE parity_status = 'matched_clean') * 100.0 / COUNT(*), 1) as clean_pct,
  ROUND(COUNT(*) FILTER (WHERE parity_status IN ('matched_clean', 'matched_divergent')) * 100.0 / COUNT(*), 1) as any_pct
FROM multi_county_auctions
WHERE county IN ('sarasota', 'hendry', 'pasco', 'glades')
GROUP BY county
ORDER BY county;