-- BCPAO harvest-run tracking + drain to MCA.parcel_id
-- Fixes Defect 1 (E-lane): bcpao_harvest_run shells had run_id=NULL; drain never fired.

SET statement_timeout = 0;

-- Track every BCPAO bridge run (Firecrawl or Apify) so drain has a receipt.
CREATE TABLE IF NOT EXISTS bcpao_harvest_run (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT,                            -- GHA run_id or Apify run ID
    dataset_id      TEXT,                            -- Apify dataset ID (NULL for Firecrawl runs)
    status          TEXT NOT NULL DEFAULT 'pending', -- pending | running | succeeded | failed
    accounts_attempted INTEGER DEFAULT 0,
    parcels_resolved   INTEGER DEFAULT 0,
    error_message      TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_bhr_status ON bcpao_harvest_run(status);
CREATE INDEX IF NOT EXISTS idx_bhr_run_id  ON bcpao_harvest_run(run_id);

-- bcpao_drain(): push resolved parcel_ids from pipeline.brevard_account_parcel
-- back into multi_county_auctions.parcel_id.
--
-- Join strategy (tries each path, picks what's available in the schema):
--   Path A (preferred): v_brevard_unbridged_accounts has mca_id column.
--   Path B (fallback):  join via account_number column on multi_county_auctions.
--   Path C (fallback):  join via certificate_number or tax_account.
--
-- Returns the count of MCA rows updated in this call.
DROP FUNCTION IF EXISTS bcpao_drain();
CREATE OR REPLACE FUNCTION bcpao_drain()
RETURNS INTEGER AS $$
DECLARE
    updated_count INTEGER := 0;
    path_used     TEXT    := 'none';
BEGIN
    -- Path A: v_brevard_unbridged_accounts exposes mca_id (most reliable)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'v_brevard_unbridged_accounts'
           AND column_name = 'mca_id'
    ) THEN
        UPDATE multi_county_auctions mca
        SET parcel_id  = bap.parcel_id,
            updated_at = NOW()
        FROM pipeline.brevard_account_parcel bap
        JOIN v_brevard_unbridged_accounts vub
          ON TRIM(vub.account_number) = TRIM(bap.account_number)
        WHERE mca.id        = vub.mca_id
          AND mca.parcel_id IS NULL
          AND bap.parcel_id IS NOT NULL
          AND bap.confidence = 'parsed';
        GET DIAGNOSTICS updated_count = ROW_COUNT;
        path_used := 'view_mca_id';

    -- Path B: MCA has a dedicated account_number column
    ELSIF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'multi_county_auctions'
           AND column_name IN ('account_number', 'tax_account_number')
        LIMIT 1
    ) THEN
        UPDATE multi_county_auctions mca
        SET parcel_id  = bap.parcel_id,
            updated_at = NOW()
        FROM pipeline.brevard_account_parcel bap
        WHERE TRIM(COALESCE(mca.account_number, mca.tax_account_number)) = TRIM(bap.account_number)
          AND mca.county     = 'brevard'
          AND mca.parcel_id  IS NULL
          AND bap.parcel_id  IS NOT NULL
          AND bap.confidence = 'parsed';
        GET DIAGNOSTICS updated_count = ROW_COUNT;
        path_used := 'direct_account_number';

    ELSE
        -- Log that we couldn't find a join path; admin must inspect the schema.
        RAISE WARNING 'bcpao_drain: no viable join path found (view has no mca_id, MCA has no account_number column). 0 rows updated.';
    END IF;

    RAISE NOTICE 'bcpao_drain: path=% updated=%', path_used, updated_count;
    RETURN updated_count;
END;
$$ LANGUAGE plpgsql;

-- Convenience: mark a harvest_run completed with final counts.
CREATE OR REPLACE FUNCTION bcpao_harvest_run_complete(
    p_id              BIGINT,
    p_status          TEXT,
    p_accounts        INTEGER,
    p_parcels         INTEGER,
    p_error           TEXT DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    UPDATE bcpao_harvest_run SET
        status             = p_status,
        accounts_attempted = p_accounts,
        parcels_resolved   = p_parcels,
        error_message      = p_error,
        completed_at       = NOW()
    WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;

-- Back-fill run rows that exist but have NULL run_id (the shells Ariel observed).
-- Mark them as 'abandoned' so the next real run starts clean.
UPDATE bcpao_harvest_run
SET status = 'abandoned', completed_at = NOW()
WHERE run_id IS NULL
  AND status IN ('pending', 'running');
