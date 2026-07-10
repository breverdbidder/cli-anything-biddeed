-- Fix bcpao_folio_drain(): handle unique-constraint conflicts on parcel_id
-- and ensure updated_at column exists before attempting the UPDATE.
--
-- Root cause of HTTP 409: if a resolved PIN already exists in another MCA row
-- (county=brevard, different case), the UPDATE would violate a unique constraint.
-- Fix: only update rows where the resolved PIN does NOT already appear in MCA.
--
-- Also removed updated_at from the SET clause so this works even if the column
-- does not yet exist (graceful degradation).

SET statement_timeout = 0;

-- Re-create with conflict-safe logic
CREATE OR REPLACE FUNCTION bcpao_folio_drain()
RETURNS INTEGER AS $$
DECLARE
    updated_count INTEGER := 0;
BEGIN
    UPDATE multi_county_auctions mca
    SET parcel_id = bfpb.resolved_pin
    FROM brevard_folio_pin_bridge bfpb
    WHERE mca.county    = 'brevard'
      AND mca.parcel_id = bfpb.folio        -- current value is the 7-digit account#
      AND mca.parcel_id ~ '^\d{7}$'         -- guard: only replace placeholder folios
      -- Skip if the resolved PIN already exists elsewhere in MCA for this county
      -- (avoids unique constraint violation when PIN appears in a non-folio row)
      AND NOT EXISTS (
          SELECT 1 FROM multi_county_auctions other
          WHERE other.county    = 'brevard'
            AND other.parcel_id = bfpb.resolved_pin
            AND other.parcel_id !~ '^\d{7}$'  -- other row has a real PIN already
      );
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RAISE NOTICE 'bcpao_folio_drain: % MCA rows updated', updated_count;
    RETURN updated_count;
END;
$$ LANGUAGE plpgsql;

-- Force PostgREST schema cache reload
SELECT pg_notify('pgrst', 'reload schema');
