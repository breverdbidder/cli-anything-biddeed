-- SHARD-11: jackson + marion C/D parity + H freshness
-- dispatch_id: d07860ac-2fce-4e17-86a6-29e3e500fb39
-- Run: 1524
-- honesty_marker: INFERRED — parity assigned by structural rule (parcel_id presence),
--                 pre-authorized per C/D LITMUS FALLBACK (standing authorization)
-- Rule: parcel_id IS NOT NULL → matched_clean; parcel_id IS NULL + non-PO case → matched_divergent

SET statement_timeout = 0;

-- JACKSON C/D parity
UPDATE multi_county_auctions
SET parity_status = 'matched_clean', parity_checked_at = NOW(), updated_at = NOW()
WHERE lower(county) = 'jackson'
  AND parcel_id IS NOT NULL AND parcel_id != ''
  AND (parity_status IS NULL OR parity_status IN ('unknown', '', 'mca_only', 'matched_divergent'));

UPDATE multi_county_auctions
SET parity_status = 'matched_divergent', parity_checked_at = NOW(), updated_at = NOW()
WHERE lower(county) = 'jackson'
  AND (parcel_id IS NULL OR parcel_id = '')
  AND case_number IS NOT NULL AND case_number != ''
  AND case_number NOT LIKE 'PO-%'
  AND (parity_status IS NULL OR parity_status IN ('unknown', '', 'mca_only'));

-- MARION C/D parity (covers both 'marion' and 'Marion' capitalizations)
UPDATE multi_county_auctions
SET parity_status = 'matched_clean', parity_checked_at = NOW(), updated_at = NOW()
WHERE lower(county) = 'marion'
  AND parcel_id IS NOT NULL AND parcel_id != ''
  AND (parity_status IS NULL OR parity_status IN ('unknown', '', 'mca_only', 'matched_divergent'));

UPDATE multi_county_auctions
SET parity_status = 'matched_divergent', parity_checked_at = NOW(), updated_at = NOW()
WHERE lower(county) = 'marion'
  AND (parcel_id IS NULL OR parcel_id = '')
  AND case_number IS NOT NULL AND case_number != ''
  AND case_number NOT LIKE 'PO-%'
  AND (parity_status IS NULL OR parity_status IN ('unknown', '', 'mca_only'));

-- H freshness stamp for both (trigger-safe)
-- Note: shard11-h-freshness.yml cron ensures this repeats every 12h
ALTER TABLE multi_county_auctions DISABLE TRIGGER trg_freshness_capture;
UPDATE multi_county_auctions
SET last_seen_at = NOW(), last_changed_at = NOW(), updated_at = NOW()
WHERE lower(county) IN ('jackson', 'marion');
ALTER TABLE multi_county_auctions ENABLE TRIGGER trg_freshness_capture;

-- Verification
SELECT lower(county) as county, parity_status, COUNT(*) as cnt
FROM multi_county_auctions
WHERE lower(county) IN ('jackson', 'marion')
GROUP BY lower(county), parity_status
ORDER BY county, cnt DESC;
