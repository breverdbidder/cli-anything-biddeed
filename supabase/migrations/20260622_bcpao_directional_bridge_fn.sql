-- bcpao_directional_bridge() — S6/S7 folio→PIN via directional suffix matching
-- Called via PostgREST RPC after addr matching strategies exhaust exact/clean matches.
--
-- Strategy: for each queued folio, try 8 directional variants of street_normalized
-- (e.g. '792GEARYST' → try '792GEARYSTN', '792GEARYSTNE', …, '792GEARYSTSW').
-- Uses exact addr_key equality so the (co_no, addr_key) index is used.
-- Only inserts when exactly ONE fl_parcels row matches per folio (no ambiguity).
--
-- Returns: count of new bridges inserted.

CREATE OR REPLACE FUNCTION bcpao_directional_bridge()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    inserted_s6 INTEGER := 0;
    inserted_s7 INTEGER := 0;
BEGIN
    -- ── S6: directional suffix ──────────────────────────────────────────────────
    -- mca.street_normalized + USPS directional appended → exact addr_key match
    INSERT INTO brevard_folio_pin_bridge (folio, resolved_pin, match_method)
    WITH addr_variants AS (
        SELECT
            j.account                              AS folio,
            mca.street_normalized || d.dir         AS addr_variant
        FROM bcpao_fetch_jobs j
        JOIN multi_county_auctions mca
            ON  mca.county          = 'brevard'
            AND mca.parcel_id       = j.account
            AND mca.street_normalized IS NOT NULL
            AND length(mca.street_normalized) > 3
            AND mca.street_normalized NOT ILIKE '%unknown%'
        CROSS JOIN (
            VALUES ('N'),('NE'),('NW'),('E'),('SE'),('SW'),('S'),('W')
        ) AS d(dir)
        WHERE j.status IN ('queued', 'failed')
    ),
    matches AS (
        SELECT
            av.folio,
            fp.parcel_id,
            COUNT(*) OVER (PARTITION BY av.folio) AS match_cnt
        FROM addr_variants av
        JOIN fl_parcels fp
            ON  fp.co_no    = 15
            AND fp.addr_key = av.addr_variant
    )
    SELECT DISTINCT folio, parcel_id, 'directional_suffix'
    FROM matches
    WHERE match_cnt = 1
    ON CONFLICT (folio) DO NOTHING;

    GET DIAGNOSTICS inserted_s6 = ROW_COUNT;

    -- Mark newly bridged jobs done
    UPDATE bcpao_fetch_jobs j
    SET status    = 'done',
        parcel_id = b.resolved_pin,
        done_at   = now()
    FROM brevard_folio_pin_bridge b
    WHERE b.folio  = j.account
      AND j.status IN ('queued', 'failed')
      AND b.match_method = 'directional_suffix';

    -- ── S7: USPS suffix_norm + directional suffix ───────────────────────────────
    -- Applies WAY→WY / AVENUE→AVE / BOULEVARD→BLVD etc. first, then directional.
    INSERT INTO brevard_folio_pin_bridge (folio, resolved_pin, match_method)
    WITH normed AS (
        SELECT
            j.account AS folio,
            -- USPS suffix abbreviation chain
            REGEXP_REPLACE(
            REGEXP_REPLACE(
            REGEXP_REPLACE(
            REGEXP_REPLACE(
            REGEXP_REPLACE(
            REGEXP_REPLACE(
            REGEXP_REPLACE(
                mca.street_normalized,
                'WAY$',       'WY'),
                'AVENUE$',    'AVE'),
                'BOULEVARD$', 'BLVD'),
                'CIRCLE$',    'CIR'),
                'COURT$',     'CT'),
                'STREET$',    'ST'),
                'TERRACE$',   'TER')   AS normed_addr
        FROM bcpao_fetch_jobs j
        JOIN multi_county_auctions mca
            ON  mca.county          = 'brevard'
            AND mca.parcel_id       = j.account
            AND mca.street_normalized IS NOT NULL
            AND length(mca.street_normalized) > 3
            AND mca.street_normalized NOT ILIKE '%unknown%'
        WHERE j.status IN ('queued', 'failed')
          AND mca.street_normalized IS DISTINCT FROM
              REGEXP_REPLACE(
              REGEXP_REPLACE(
              REGEXP_REPLACE(
              REGEXP_REPLACE(
              REGEXP_REPLACE(
              REGEXP_REPLACE(
              REGEXP_REPLACE(
                  mca.street_normalized,
                  'WAY$','WY'),'AVENUE$','AVE'),'BOULEVARD$','BLVD'),
                  'CIRCLE$','CIR'),'COURT$','CT'),'STREET$','ST'),'TERRACE$','TER')
    ),
    addr_variants AS (
        SELECT folio, normed_addr || d.dir AS addr_variant
        FROM normed
        CROSS JOIN (
            VALUES ('N'),('NE'),('NW'),('E'),('SE'),('SW'),('S'),('W')
        ) AS d(dir)
    ),
    matches AS (
        SELECT
            av.folio,
            fp.parcel_id,
            COUNT(*) OVER (PARTITION BY av.folio) AS match_cnt
        FROM addr_variants av
        JOIN fl_parcels fp
            ON  fp.co_no    = 15
            AND fp.addr_key = av.addr_variant
    )
    SELECT DISTINCT folio, parcel_id, 'suffix_directional'
    FROM matches
    WHERE match_cnt = 1
    ON CONFLICT (folio) DO NOTHING;

    GET DIAGNOSTICS inserted_s7 = ROW_COUNT;

    UPDATE bcpao_fetch_jobs j
    SET status    = 'done',
        parcel_id = b.resolved_pin,
        done_at   = now()
    FROM brevard_folio_pin_bridge b
    WHERE b.folio  = j.account
      AND j.status IN ('queued', 'failed')
      AND b.match_method = 'suffix_directional';

    RAISE NOTICE 'bcpao_directional_bridge: S6=% S7=%', inserted_s6, inserted_s7;
    RETURN inserted_s6 + inserted_s7;
END;
$$;
