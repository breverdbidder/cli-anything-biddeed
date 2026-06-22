-- BCPAO folio->PIN bridge infrastructure
-- Criterion I unblock: drain 2713 unbridged 7-digit folios from multi_county_auctions
-- into brevard_folio_pin_bridge so fl_parcels joins resolve.

SET statement_timeout = 0;

-- Job queue: one row per BCPAO account number to resolve
CREATE TABLE IF NOT EXISTS bcpao_fetch_jobs (
    account     TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'queued',  -- queued | done | empty | failed
    parcel_id   TEXT,           -- resolved PIN (e.g. "23-3627-00-56-00000.0")
    done_at     TIMESTAMPTZ,
    last_error  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bcpao_fetch_jobs_status ON bcpao_fetch_jobs(status);

-- Bridge table: folio (BCPAO account#) -> resolved PIN
CREATE TABLE IF NOT EXISTS brevard_folio_pin_bridge (
    folio           TEXT PRIMARY KEY,
    resolved_pin    TEXT NOT NULL,
    match_method    TEXT NOT NULL DEFAULT 'bcpao_playwright',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bfpb_pin ON brevard_folio_pin_bridge(resolved_pin);

-- Seed the job queue from multi_county_auctions:
-- 7-digit numeric parcel_ids in Brevard are BCPAO account numbers, not real PINs.
-- Skip any folio already bridged.
INSERT INTO bcpao_fetch_jobs (account, status)
SELECT DISTINCT mca.parcel_id, 'queued'
FROM multi_county_auctions mca
WHERE mca.county    = 'brevard'
  AND mca.parcel_id ~ '^\d{7}$'
  AND NOT EXISTS (
        SELECT 1 FROM brevard_folio_pin_bridge bfpb
        WHERE bfpb.folio = mca.parcel_id
  )
ON CONFLICT (account) DO NOTHING;

-- After PIN harvest, this function updates multi_county_auctions.parcel_id
-- by joining through the bridge. Call via RPC after the harvest run completes.
CREATE OR REPLACE FUNCTION bcpao_folio_drain()
RETURNS INTEGER AS $$
DECLARE
    updated_count INTEGER := 0;
BEGIN
    UPDATE multi_county_auctions mca
    SET parcel_id  = bfpb.resolved_pin,
        updated_at = NOW()
    FROM brevard_folio_pin_bridge bfpb
    WHERE mca.county    = 'brevard'
      AND mca.parcel_id = bfpb.folio        -- current value is the 7-digit account#
      AND mca.parcel_id ~ '^\d{7}$';        -- guard: only replace placeholder folios
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RAISE NOTICE 'bcpao_folio_drain: % MCA rows updated', updated_count;
    RETURN updated_count;
END;
$$ LANGUAGE plpgsql;
