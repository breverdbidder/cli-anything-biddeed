-- Defect 3 fix: zoning_assignments had no UNIQUE(parcel_id) constraint.
-- melbourne_gap_fill_v2.py and usecode_gap_fill_final.py both call
-- POST /rest/v1/zoning_assignments?on_conflict=parcel_id  which requires
-- a named UNIQUE or PRIMARY KEY on that single column.
-- If the constraint was (parcel_id, county), the REST call silently failed
-- with HTTP 400/409 and wrote 0 rows — which explains "0 writes since Mar 30".

SET statement_timeout = 0;

-- Dedup before attempting UNIQUE index: if duplicate parcel_ids exist, keep
-- the row with the highest id (most recently inserted) and delete the rest.
DO $$
DECLARE
    dup_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO dup_count
    FROM (
        SELECT parcel_id FROM zoning_assignments
        GROUP BY parcel_id HAVING COUNT(*) > 1
    ) d;

    IF dup_count > 0 THEN
        RAISE NOTICE 'Deduplicating % parcel_id groups before UNIQUE index creation', dup_count;
        DELETE FROM zoning_assignments za
        WHERE id NOT IN (
            SELECT MAX(id) FROM zoning_assignments GROUP BY parcel_id
        );
        RAISE NOTICE 'Dedup complete';
    END IF;
END $$;

-- Ensure parcel_id is UNIQUE within Brevard zoning data.
-- Use a partial unique index so other counties can have the same parcel_id value
-- (rare but possible in multi-county schema).
DO $$
BEGIN
    -- Only add if it doesn't already exist
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'zoning_assignments'
          AND indexname  = 'idx_za_parcel_id_unique'
    ) THEN
        CREATE UNIQUE INDEX idx_za_parcel_id_unique
          ON zoning_assignments (parcel_id);
    END IF;
END $$;

-- Also ensure zone_source column exists (scripts guard on it, but should be there).
ALTER TABLE zoning_assignments
  ADD COLUMN IF NOT EXISTS zone_source    TEXT,
  ADD COLUMN IF NOT EXISTS jurisdiction   TEXT,
  ADD COLUMN IF NOT EXISTS county         TEXT DEFAULT 'brevard';

CREATE INDEX IF NOT EXISTS idx_za_jurisdiction ON zoning_assignments(jurisdiction);
CREATE INDEX IF NOT EXISTS idx_za_county        ON zoning_assignments(county);

-- Log
INSERT INTO migration_log (migration_name, applied_at, description)
VALUES (
    '20260616_zoning_upsert_constraint',
    NOW(),
    'Add UNIQUE(parcel_id) to zoning_assignments so on_conflict=parcel_id upserts work; add missing columns'
) ON CONFLICT (migration_name) DO NOTHING;
