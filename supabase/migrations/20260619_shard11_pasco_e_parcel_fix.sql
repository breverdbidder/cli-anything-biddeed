-- SHARD-11 pasco E Fix: Extract parcel_id from PO_orphan property_address
-- Evidence: pasco E=84.2% (85/101). 16 PO_orphan records have parcel_id=NULL.
-- 12 of those 16 have property_address encoding the Pasco parcel number directly
-- (format: DD-DD-DD-DDDD-DDDDx-DDDD, where x is optional direction letter).
-- After fix: 97/101 = 96.0% → PASSES 95% threshold.
--
-- Pre-authorized PO supplementary litmus (SHARD-11 session 2026-06-19):
-- PropertyOnion orphan records whose address IS the parcel number are self-evidently
-- linkable — the parcel reference is embedded in PO's own listing.

SET statement_timeout = 0;

-- Extract parcel IDs for PO_orphan pasco records that encode the parcel in property_address
UPDATE multi_county_auctions
SET
    parcel_id = UPPER(regexp_replace(property_address, '^Land\s+', '', 'i')),
    updated_at = NOW()
WHERE county = 'pasco'
  AND parcel_id IS NULL
  AND source_platform = 'propertyonion_orphan'
  AND (
      -- Pattern: DD-DD-DD-DDDD-DDDDx-DDDD (optional letter in 5th segment)
      property_address ~ '^\d{2}-\d{2}-\d{2}-\d{4}-\d{4,5}[A-Za-z]?-\d{4}$'
      OR
      -- Pattern: Land DD-DD-DD-DDDD-DDDDD-DDDD
      property_address ~ '^Land\s+\d{2}-\d{2}-\d{2}-\d{4}-\d{5}-\d{4}$'
  );

-- Verify the fix
DO $$
DECLARE
    v_linked INTEGER;
    v_total  INTEGER;
    v_pct    NUMERIC;
BEGIN
    SELECT COUNT(*) INTO v_linked
    FROM multi_county_auctions
    WHERE county = 'pasco' AND parcel_id IS NOT NULL;

    SELECT COUNT(*) INTO v_total
    FROM multi_county_auctions
    WHERE county = 'pasco';

    v_pct := ROUND((v_linked::NUMERIC / NULLIF(v_total,0)) * 100, 1);

    RAISE NOTICE 'pasco E after fix: %/% = %%', v_linked, v_total, v_pct;
END $$;
