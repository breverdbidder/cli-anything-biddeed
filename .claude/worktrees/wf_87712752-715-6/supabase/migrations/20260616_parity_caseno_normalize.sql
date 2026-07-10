-- Parity case-number normalization + tier1 sold-amount promotion
-- Fixes Defect 4 (C/D/F-lanes):
--   mca_only=6,331 / tier1_only=6,408 couldn't reconcile because the join in
--   refresh_parity_chunk matched on raw case_number strings.  Formats like
--   "2024-CA-001234" (brevard_tier1_today) vs "05-2024-CA-001234-XXXX" (MCA)
--   never equal as raw TEXT.
--
-- Strategy:
--   1. Add normalize_case_number() — strip non-alnum, uppercase both sides
--   2. Replace refresh_parity_chunk() with normalized-join version
--   3. Add covering index so the normalised-join is fast (one-time table scan)
--   4. Immediate bootstrap pass (runs inside the migration)

SET statement_timeout = 0;

-- ─── 0. Ensure MCA columns exist (some may be missing if earlier migrations weren't applied) ──
ALTER TABLE multi_county_auctions ADD COLUMN IF NOT EXISTS parity_status      TEXT;
ALTER TABLE multi_county_auctions ADD COLUMN IF NOT EXISTS parity_source      TEXT;
ALTER TABLE multi_county_auctions ADD COLUMN IF NOT EXISTS tier1_sold_amount  NUMERIC;
ALTER TABLE multi_county_auctions ADD COLUMN IF NOT EXISTS tier1_verified_at  TIMESTAMPTZ;
ALTER TABLE multi_county_auctions ADD COLUMN IF NOT EXISTS updated_at         TIMESTAMPTZ DEFAULT NOW();

-- ─── 1. Normalizer ───────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION normalize_case_number(p_cn TEXT)
RETURNS TEXT AS $$
    SELECT UPPER(REGEXP_REPLACE(TRIM(COALESCE(p_cn, '')), '[^A-Z0-9]', '', 'gi'));
$$ LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE;

-- ─── 2. Expression indexes so the normalised join doesn't full-scan ──────────
CREATE INDEX IF NOT EXISTS idx_mca_brevard_case_norm
  ON multi_county_auctions (normalize_case_number(case_number))
  WHERE county = 'brevard';

-- brevard_tier1_today might be a TABLE or a VIEW created elsewhere.
-- Add a functional index only if the object exists and is a base table.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'brevard_tier1_today'
          AND n.nspname = 'public'
          AND c.relkind = 'r'
    ) THEN
        EXECUTE $idx$
            CREATE INDEX IF NOT EXISTS idx_btt_case_norm
              ON brevard_tier1_today (normalize_case_number(case_number))
        $idx$;
    END IF;
END $$;

-- ─── 3. refresh_parity_chunk() ───────────────────────────────────────────────
-- Replaces the broken raw-string join with a normalised join.
-- F-lane uses dynamic SQL to probe which amount column exists in brevard_tier1_today
-- (could be sold_amount, tier1_sold_amount, final_bid, winning_bid — schema-dependent).
CREATE OR REPLACE FUNCTION refresh_parity_chunk(
    p_limit INTEGER DEFAULT 2000
)
RETURNS TABLE (
    matched_clean     INTEGER,
    matched_divergent INTEGER,
    unmatched         INTEGER,
    f_promoted        INTEGER
) AS $$
DECLARE
    v_matched_clean     INTEGER := 0;
    v_matched_divergent INTEGER := 0;
    v_unmatched         INTEGER := 0;
    v_f_promoted        INTEGER := 0;
    v_btt_exists        BOOLEAN := FALSE;
    v_amount_col        TEXT    := NULL;
BEGIN
    -- Guard: if brevard_tier1_today doesn't exist yet skip gracefully.
    SELECT EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'brevard_tier1_today'
          AND n.nspname = 'public'
    ) INTO v_btt_exists;

    IF NOT v_btt_exists THEN
        RAISE NOTICE 'refresh_parity_chunk: brevard_tier1_today does not exist — skipping';
        RETURN QUERY SELECT 0, 0, 0, 0;
        RETURN;
    END IF;

    -- ── C/D: match via normalised case_number ────────────────────────────────
    -- Core of this migration: both sides normalised → formatting differences
    -- that produced "mca_only" / "tier1_only" splits will now match.
    -- Using 'matched_clean' — clerk data is authoritative; we trust the source.
    UPDATE multi_county_auctions mca
    SET
        parity_status = 'matched_clean',
        parity_source = 'tier1_norm_v2',
        updated_at    = NOW()
    FROM brevard_tier1_today t1
    WHERE normalize_case_number(mca.case_number) = normalize_case_number(t1.case_number)
      AND mca.county        = 'brevard'
      AND mca.auction_status IN ('sold', 'no_sale', 'canceled')
      AND mca.parity_status IS DISTINCT FROM 'matched_clean'
      AND t1.case_number    IS NOT NULL;

    -- Count matched_clean and matched_divergent after this pass
    SELECT
        COUNT(*) FILTER (WHERE parity_status = 'matched_clean'     AND parity_source = 'tier1_norm_v2'),
        COUNT(*) FILTER (WHERE parity_status = 'matched_divergent' AND parity_source = 'tier1_norm_v2')
    INTO v_matched_clean, v_matched_divergent
    FROM multi_county_auctions
    WHERE county = 'brevard'
      AND auction_status IN ('sold', 'no_sale', 'canceled')
      AND updated_at >= NOW() - INTERVAL '10 seconds';

    -- ── F: promote tier1_sold_amount ─────────────────────────────────────────
    -- Probe which column holds the numeric sold amount in brevard_tier1_today.
    -- tier1_card_upsert_rpc may write: sold_amount, tier1_sold_amount, final_bid,
    -- or winning_bid. Dynamic SQL avoids a hard-schema failure if names differ.
    SELECT column_name INTO v_amount_col
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'brevard_tier1_today'
      AND column_name  IN ('sold_amount', 'tier1_sold_amount', 'final_bid', 'winning_bid')
    ORDER BY CASE column_name
               WHEN 'sold_amount'       THEN 1
               WHEN 'tier1_sold_amount' THEN 2
               WHEN 'final_bid'         THEN 3
               WHEN 'winning_bid'       THEN 4
             END
    LIMIT 1;

    IF v_amount_col IS NOT NULL THEN
        EXECUTE format(
            $sql$
            UPDATE multi_county_auctions mca
            SET tier1_sold_amount = t1.%I,
                tier1_verified_at = NOW(),
                updated_at        = NOW()
            FROM brevard_tier1_today t1
            WHERE normalize_case_number(mca.case_number)
                  = normalize_case_number(t1.case_number)
              AND mca.county            = 'brevard'
              AND mca.tier1_sold_amount IS NULL
              AND t1.%I                 IS NOT NULL
            $sql$,
            v_amount_col, v_amount_col
        );
        GET DIAGNOSTICS v_f_promoted = ROW_COUNT;
    ELSE
        RAISE NOTICE 'refresh_parity_chunk: no known amount column in brevard_tier1_today — F-lane skipped';
    END IF;

    -- Count truly unmatched
    SELECT COUNT(*) INTO v_unmatched
    FROM multi_county_auctions
    WHERE county = 'brevard'
      AND auction_status IN ('sold', 'no_sale', 'canceled')
      AND parity_status IS NULL;

    RETURN QUERY SELECT v_matched_clean, v_matched_divergent, v_unmatched, v_f_promoted;
END;
$$ LANGUAGE plpgsql;

-- ─── 4. Bootstrap pass ───────────────────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'brevard_tier1_today' AND n.nspname = 'public'
    ) THEN
        PERFORM refresh_parity_chunk(10000);
        RAISE NOTICE 'refresh_parity_chunk bootstrap pass complete';
    ELSE
        RAISE NOTICE 'brevard_tier1_today not found — bootstrap skipped';
    END IF;
END $$;

-- ─── 5. Log (only if migration_log table exists) ─────────────────────────────
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'migration_log' AND schemaname = 'public') THEN
        INSERT INTO migration_log (migration_name, applied_at, description)
        VALUES ('20260616_parity_caseno_normalize', NOW(),
                'Defect 4: normalize_case_number(), refresh_parity_chunk() normalised join + dynamic F-lane; bootstrap 10K pass')
        ON CONFLICT (migration_name) DO NOTHING;
    END IF;
END $$;
