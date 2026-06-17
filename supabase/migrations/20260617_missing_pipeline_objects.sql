-- PIPELINE SCHEMA OBJECTS — Defect 1 & 2 infrastructure
-- Creates all DB objects that worker scripts depend on but were never migrated:
--   pipeline.brevard_realtdm_cases      (feeder for BCPAO bridge)
--   upsert_brevard_realtdm_cases        (RPC called by realtdm_cases_sweep.py)
--   pipeline.brevard_account_parcel     (account→parcel mapping store)
--   upsert_brevard_account_parcel       (RPC called by bcpao_bridge.py)
--   v_brevard_unbridged_accounts        (worklist view for bcpao_bridge.py)
--   bcpao_drain()                       (corrected version — replaces infra migration)
--   realforeclose_aids                  (AITEM harvest store, if not already created)
--   realforeclose_aids_to_mca_patch     (RPC called after every aids batch insert)

SET statement_timeout = 0;

-- ─── 0. normalize_case_number safety ─────────────────────────────────────────
-- CREATE OR REPLACE is a no-op if already defined by 20260616_parity_caseno_normalize.sql.
-- Ensures this migration is safe to run standalone or before migration 3.
CREATE OR REPLACE FUNCTION normalize_case_number(p_cn TEXT)
RETURNS TEXT AS $$
    SELECT UPPER(REGEXP_REPLACE(TRIM(COALESCE(p_cn, '')), '[^A-Z0-9]', '', 'gi'));
$$ LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE;

-- ─── 0a. Pipeline schema ─────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS pipeline;

-- ─── 1. RealTDM case list (feeder for BCPAO bridge) ─────────────────────────
-- Populated by realtdm_cases_sweep.py via upsert_brevard_realtdm_cases RPC.
-- "Parcel Number" on RealTDM cards = BCPAO tax-account number → stored as account_number.
CREATE TABLE IF NOT EXISTS pipeline.brevard_realtdm_cases (
    id              BIGSERIAL PRIMARY KEY,
    case_number     TEXT NOT NULL,
    tdm_case_id     TEXT,
    account_number  TEXT,           -- BCPAO tax-account number ("Parcel Number" on card)
    app_number      TEXT,
    case_status     TEXT,
    sale_date       DATE,
    surplus_balance TEXT,
    date_created    DATE,
    mca_id          UUID,           -- FK to multi_county_auctions.id; NULL until back-filled
    scraped_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(case_number)
);

CREATE INDEX IF NOT EXISTS idx_brtc_account ON pipeline.brevard_realtdm_cases(account_number) WHERE account_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_brtc_mca_id  ON pipeline.brevard_realtdm_cases(mca_id)         WHERE mca_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_brtc_sale_date ON pipeline.brevard_realtdm_cases(sale_date)    WHERE sale_date IS NOT NULL;

-- ─── 2. upsert_brevard_realtdm_cases ─────────────────────────────────────────
-- Called by realtdm_cases_sweep.py: rpc("upsert_brevard_realtdm_cases", new)
-- where new is a list of {case_number, tdm_case_id, account_number, app_number,
--   case_status, sale_date, surplus_balance, date_created}.
DROP FUNCTION IF EXISTS upsert_brevard_realtdm_cases(JSONB);
CREATE OR REPLACE FUNCTION upsert_brevard_realtdm_cases(p JSONB)
RETURNS VOID AS $$
DECLARE
    rec JSONB;
BEGIN
    FOR rec IN SELECT value FROM jsonb_array_elements(p)
    LOOP
        INSERT INTO pipeline.brevard_realtdm_cases (
            case_number,
            tdm_case_id,
            account_number,
            app_number,
            case_status,
            sale_date,
            surplus_balance,
            date_created
        )
        SELECT
            TRIM(rec->>'case_number'),
            NULLIF(TRIM(rec->>'tdm_case_id'),   ''),
            NULLIF(TRIM(rec->>'account_number'), ''),
            NULLIF(TRIM(rec->>'app_number'),     ''),
            NULLIF(TRIM(rec->>'case_status'),    ''),
            NULLIF(rec->>'sale_date',   '')::DATE,
            NULLIF(TRIM(rec->>'surplus_balance'),''),
            NULLIF(rec->>'date_created','')::DATE
        WHERE TRIM(rec->>'case_number') <> ''
        ON CONFLICT (case_number) DO UPDATE SET
            tdm_case_id    = COALESCE(EXCLUDED.tdm_case_id,    tdm_case_id),
            account_number = COALESCE(EXCLUDED.account_number, account_number),
            app_number     = COALESCE(EXCLUDED.app_number,     app_number),
            case_status    = COALESCE(EXCLUDED.case_status,    case_status),
            sale_date      = COALESCE(EXCLUDED.sale_date,      sale_date),
            surplus_balance= COALESCE(EXCLUDED.surplus_balance,surplus_balance),
            scraped_at     = now();
    END LOOP;

    -- Best-effort back-fill mca_id for newly inserted/updated cases.
    -- normalize_case_number() exists after 20260616_parity_caseno_normalize.sql is applied.
    UPDATE pipeline.brevard_realtdm_cases rtc
    SET mca_id = mca.id
    FROM multi_county_auctions mca
    WHERE normalize_case_number(mca.case_number) = normalize_case_number(rtc.case_number)
      AND mca.county   = 'brevard'
      AND rtc.mca_id   IS NULL
      AND rtc.case_number IS NOT NULL
      AND rtc.scraped_at >= now() - INTERVAL '5 minutes';   -- only rows just touched
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ─── 3. BCPAO account → parcel mapping ───────────────────────────────────────
-- Populated by bcpao_bridge.py via upsert_brevard_account_parcel RPC.
CREATE TABLE IF NOT EXISTS pipeline.brevard_account_parcel (
    id              BIGSERIAL PRIMARY KEY,
    account_number  TEXT NOT NULL UNIQUE,
    parcel_id       TEXT,
    site_address    TEXT,
    market_value    NUMERIC,
    raw             JSONB,
    confidence      TEXT NOT NULL DEFAULT 'raw_only',   -- 'parsed' | 'raw_only'
    fetched_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bap_parcel     ON pipeline.brevard_account_parcel(parcel_id)   WHERE parcel_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bap_confidence ON pipeline.brevard_account_parcel(confidence);

-- ─── 4. upsert_brevard_account_parcel ────────────────────────────────────────
-- Called by bcpao_bridge.py: rpc("upsert_brevard_account_parcel", batch)
-- where batch is a list of {account_number, parcel_id, site_address, market_value, raw, confidence}.
DROP FUNCTION IF EXISTS upsert_brevard_account_parcel(JSONB);
CREATE OR REPLACE FUNCTION upsert_brevard_account_parcel(p JSONB)
RETURNS VOID AS $$
DECLARE
    rec JSONB;
BEGIN
    FOR rec IN SELECT value FROM jsonb_array_elements(p)
    LOOP
        INSERT INTO pipeline.brevard_account_parcel (
            account_number,
            parcel_id,
            site_address,
            market_value,
            raw,
            confidence
        )
        SELECT
            TRIM(rec->>'account_number'),
            NULLIF(TRIM(rec->>'parcel_id'),    ''),
            NULLIF(TRIM(rec->>'site_address'), ''),
            NULLIF(rec->>'market_value', '')::NUMERIC,
            rec->'raw',
            COALESCE(NULLIF(rec->>'confidence',''), 'raw_only')
        WHERE TRIM(rec->>'account_number') <> ''
        ON CONFLICT (account_number) DO UPDATE SET
            -- Only overwrite parcel_id when new data is better (parsed > raw_only)
            parcel_id    = CASE
                             WHEN EXCLUDED.confidence = 'parsed' AND EXCLUDED.parcel_id IS NOT NULL
                               THEN EXCLUDED.parcel_id
                             ELSE COALESCE(parcel_id, EXCLUDED.parcel_id)
                           END,
            site_address = COALESCE(EXCLUDED.site_address, site_address),
            market_value = COALESCE(EXCLUDED.market_value, market_value),
            raw          = COALESCE(EXCLUDED.raw,          raw),
            confidence   = CASE
                             WHEN EXCLUDED.confidence = 'parsed' THEN 'parsed'
                             ELSE confidence
                           END,
            fetched_at   = now();
    END LOOP;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ─── 5. v_brevard_unbridged_accounts ─────────────────────────────────────────
-- Worklist for bcpao_bridge.py: RealTDM cases with an account_number that
-- haven't yet been resolved to a parsed parcel_id.
-- Exposed via Supabase REST API (public schema view).
CREATE OR REPLACE VIEW v_brevard_unbridged_accounts AS
SELECT
    rtc.account_number,
    mca.id           AS mca_id,       -- UUID for bcpao_drain() Path A
    rtc.case_number,
    rtc.sale_date
FROM pipeline.brevard_realtdm_cases rtc
LEFT JOIN multi_county_auctions mca
       ON normalize_case_number(mca.case_number) = normalize_case_number(rtc.case_number)
      AND mca.county = 'brevard'
WHERE rtc.account_number IS NOT NULL
  AND rtc.account_number <> ''
  AND NOT EXISTS (
      SELECT 1 FROM pipeline.brevard_account_parcel bap
       WHERE bap.account_number = rtc.account_number
         AND bap.confidence     = 'parsed'
  );

-- ─── 6. bcpao_drain() — corrected version ────────────────────────────────────
-- Replaces the version in 20260616_bcpao_drain_infra.sql.
-- Fix: join directly through pipeline.brevard_realtdm_cases (not the worklist view)
-- so accounts freshly marked 'parsed' are still found by the drain in the same session.
CREATE OR REPLACE FUNCTION bcpao_drain()
RETURNS INTEGER AS $$
DECLARE
    updated_count INTEGER := 0;
    v_rows        INTEGER := 0;
BEGIN
    -- Path A: account_number → realtdm_cases → mca_id → MCA (UUID join — most reliable)
    UPDATE multi_county_auctions mca
    SET parcel_id  = bap.parcel_id,
        updated_at = NOW()
    FROM pipeline.brevard_account_parcel bap
    JOIN pipeline.brevard_realtdm_cases rtc
      ON TRIM(rtc.account_number) = TRIM(bap.account_number)
    WHERE mca.id        = rtc.mca_id
      AND mca.parcel_id IS NULL
      AND bap.parcel_id IS NOT NULL
      AND bap.confidence = 'parsed'
      AND rtc.mca_id    IS NOT NULL;
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    updated_count := updated_count + v_rows;
    RAISE NOTICE 'bcpao_drain Path A (mca_id join): %', v_rows;

    -- Path B: account_number → realtdm_cases → case_number norm join → MCA
    -- Covers cases where mca_id back-fill hasn't run yet.
    UPDATE multi_county_auctions mca
    SET parcel_id  = bap.parcel_id,
        updated_at = NOW()
    FROM pipeline.brevard_account_parcel bap
    JOIN pipeline.brevard_realtdm_cases rtc
      ON TRIM(rtc.account_number) = TRIM(bap.account_number)
    WHERE normalize_case_number(mca.case_number) = normalize_case_number(rtc.case_number)
      AND mca.county     = 'brevard'
      AND mca.parcel_id  IS NULL
      AND bap.parcel_id  IS NOT NULL
      AND bap.confidence = 'parsed'
      AND rtc.mca_id     IS NULL;   -- only rows Path A didn't already cover
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    updated_count := updated_count + v_rows;
    RAISE NOTICE 'bcpao_drain Path B (case_norm join): %', v_rows;

    RAISE NOTICE 'bcpao_drain total MCA rows updated: %', updated_count;
    RETURN updated_count;
END;
$$ LANGUAGE plpgsql;

-- ─── 7. realforeclose_aids table ─────────────────────────────────────────────
-- AITEM blocks scraped from RealForeclose PREVIEW pages.
-- Unique on `aid` (RealForeclose's own auction identifier).
-- Accessed via Supabase REST: POST /rest/v1/realforeclose_aids?on_conflict=aid
CREATE TABLE IF NOT EXISTS realforeclose_aids (
    id                  BIGSERIAL PRIMARY KEY,
    aid                 TEXT NOT NULL,             -- e.g. "12345678" — RealForeclose AID
    county_slug         TEXT NOT NULL DEFAULT 'brevard',
    county_subdomain    TEXT,
    auction_type        TEXT,                      -- e.g. "FORECLOSURE", "TAX DEED"
    case_number         TEXT,                      -- court case #
    case_clerk_url      TEXT,
    judgment_amount     NUMERIC,
    parcel_id           TEXT,                      -- from BCPAO parcel lookup on the card
    parcel_assessor_url TEXT,
    property_address    TEXT,
    assessed_value      NUMERIC,
    plaintiff_max_bid   NUMERIC,
    auction_starts_at   TIMESTAMPTZ,
    auction_starts_raw  TEXT,
    source_response_id  BIGINT,                    -- FK to court_responses_raw.id
    source_dispatch_id  BIGINT,
    source_run_id       BIGINT,
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE(aid)
);

CREATE INDEX IF NOT EXISTS idx_ra_county_slug ON realforeclose_aids(county_slug);
CREATE INDEX IF NOT EXISTS idx_ra_case_number ON realforeclose_aids(case_number) WHERE case_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ra_parcel_id   ON realforeclose_aids(parcel_id)   WHERE parcel_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ra_starts_at   ON realforeclose_aids(auction_starts_at) WHERE auction_starts_at IS NOT NULL;

-- ─── 8. realforeclose_aids_to_mca_patch ──────────────────────────────────────
-- Called immediately after each batch of aids is inserted.
-- Pass 1: fill MCA.parcel_id from aids.parcel_id (case_number join).
-- Pass 2: mark MCA.parity_status='matched_clean' where aids exist.
-- Returns total rows updated (parcel fills + parity marks).
DROP FUNCTION IF EXISTS realforeclose_aids_to_mca_patch(BIGINT);
CREATE OR REPLACE FUNCTION realforeclose_aids_to_mca_patch(
    p_dispatch_id BIGINT DEFAULT NULL
)
RETURNS INTEGER AS $$
DECLARE
    v_updated INTEGER := 0;
    v_rows    INTEGER := 0;
BEGIN
    -- ── Pass 1: fill parcel_id on MCA from aids.parcel_id ────────────────────
    UPDATE multi_county_auctions mca
    SET parcel_id  = ra.parcel_id,
        updated_at = NOW()
    FROM realforeclose_aids ra
    WHERE mca.county     = 'brevard'
      AND mca.parcel_id  IS NULL
      AND ra.county_slug = 'brevard'
      AND ra.parcel_id   IS NOT NULL
      AND (
          -- exact normalised match (most cases)
          normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
          OR
          -- substring match: Brevard MCA has "05-2011-CA-012345-XXXX-XX",
          -- aids may store "2011-CA-012345-XXXX-XX" (county prefix stripped)
          (
              LENGTH(normalize_case_number(mca.case_number)) >= 10
              AND LENGTH(normalize_case_number(ra.case_number)) >= 8
              AND normalize_case_number(mca.case_number)
                  LIKE '%' || normalize_case_number(ra.case_number) || '%'
          )
      );
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    v_updated := v_updated + v_rows;
    RAISE NOTICE 'realforeclose_aids_to_mca_patch: parcel_id fill=%', v_rows;

    -- ── Pass 2: mark parity_status for all matched auctions ──────────────────
    -- Covers all terminal + upcoming statuses so aids from the drain workflow
    -- (which scrapes future dates) immediately register in parity.
    UPDATE multi_county_auctions mca
    SET parity_status = 'matched_clean',
        parity_source = 'realforeclose_aids_patch',
        updated_at    = NOW()
    FROM realforeclose_aids ra
    WHERE mca.county     = 'brevard'
      AND mca.auction_status IN (
          'completed','sold','redeemed','cancelled','canceled',
          'no_sale','scheduled','upcoming'
      )
      AND mca.parity_status IS DISTINCT FROM 'matched_clean'
      AND ra.county_slug = 'brevard'
      AND (
          normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
          OR (
              LENGTH(normalize_case_number(mca.case_number)) >= 10
              AND LENGTH(normalize_case_number(ra.case_number)) >= 8
              AND normalize_case_number(mca.case_number)
                  LIKE '%' || normalize_case_number(ra.case_number) || '%'
          )
          OR (mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL
              AND mca.parcel_id = ra.parcel_id)
      );
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    v_updated := v_updated + v_rows;
    RAISE NOTICE 'realforeclose_aids_to_mca_patch: parity mark=%', v_rows;

    RETURN v_updated;
END;
$$ LANGUAGE plpgsql;

-- ─── 9. Log ──────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'migration_log' AND schemaname = 'public') THEN
        INSERT INTO migration_log (migration_name, applied_at, description)
        VALUES ('20260617_missing_pipeline_objects', NOW(),
                'Defect 1+2: pipeline schema, realtdm_cases, account_parcel, v_brevard_unbridged_accounts, bcpao_drain v2, realforeclose_aids, realforeclose_aids_to_mca_patch')
        ON CONFLICT (migration_name) DO NOTHING;
    END IF;
END $$;
