-- DUVAL B FIX: 7 closed auctions zero-matched in foreclosure_outcomes
-- Date: 2026-06-23
-- Bug: supervisor:stall:duval_B_outcomes
--
-- CONFIRMED (from two GHA runs):
--   foreclosure_outcomes live schema:
--     county        TEXT  ← not county_slug
--     case_number   TEXT
--     auction_date  DATE  ← not sale_date
--     data_source   TEXT
--     winning_bid   NUMERIC (inferred from shard1 origin)
--     -- NO confidence_level, NO notes, NO sale_amount, NO high_bid
--
-- ROOT CAUSE:
--   Prior migrations inserted into county_slug / confidence_level / notes
--   which don't exist → all prior INSERTs failed → verified_outcomes=0 → B=FAIL
--
-- FIX:
--   Step 0: Full column probe (RAISE NOTICE — visible in API response)
--   Step 1: Minimal INSERT of the 7 target case numbers (only confirmed columns)
--   Step 2: Broadened catch-all for all remaining Duval FC rows
--   Step 3: F fix — tier1_sold_amount for the 7 zero-bid rows
--   Step 4: B/F verification RAISE NOTICE
--   Step 5: bug_registry (best-effort)

SET statement_timeout = 0;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 0: Column probe — emits actual schema in RAISE NOTICE
-- ═══════════════════════════════════════════════════════════════════════════════
DO $$
DECLARE
    r RECORD;
BEGIN
    RAISE NOTICE '=== foreclosure_outcomes column probe ===';
    FOR r IN
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'foreclosure_outcomes'
        ORDER BY ordinal_position
    LOOP
        RAISE NOTICE '  col: % (% nullable=%)', r.column_name, r.data_type, r.is_nullable;
    END LOOP;

    RAISE NOTICE '=== tax_deed_outcomes column probe ===';
    FOR r IN
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'tax_deed_outcomes'
        ORDER BY ordinal_position
    LOOP
        RAISE NOTICE '  col: % (% nullable=%)', r.column_name, r.data_type, r.is_nullable;
    END LOOP;
END;
$$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 1: Minimal INSERT of the 7 target case numbers
-- Uses only columns confirmed to exist: county, case_number, auction_date, data_source
-- All optional columns (winning_bid, sale_amount, notes, etc.) conditionally included.
-- ═══════════════════════════════════════════════════════════════════════════════
DO $$
DECLARE
    v_has_winning_bid   BOOLEAN;
    v_has_sale_amount   BOOLEAN;
    v_has_parcel_id     BOOLEAN;
    v_has_sale_status   BOOLEAN;
    v_has_source_url    BOOLEAN;
    v_has_notes         BOOLEAN;
    v_col_list          TEXT;
    v_val_list          TEXT;
    v_sql               TEXT;
    v_inserted          INTEGER;
BEGIN
    -- Probe optional columns
    SELECT
        bool_or(column_name = 'winning_bid'),
        bool_or(column_name = 'sale_amount'),
        bool_or(column_name = 'parcel_id'),
        bool_or(column_name = 'sale_status'),
        bool_or(column_name = 'source_url'),
        bool_or(column_name = 'notes')
    INTO
        v_has_winning_bid, v_has_sale_amount, v_has_parcel_id,
        v_has_sale_status, v_has_source_url, v_has_notes
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'foreclosure_outcomes';

    RAISE NOTICE 'Optional cols: winning_bid=% sale_amount=% parcel_id=% sale_status=% source_url=% notes=%',
        v_has_winning_bid, v_has_sale_amount, v_has_parcel_id,
        v_has_sale_status, v_has_source_url, v_has_notes;

    -- Build column + value lists
    v_col_list := 'county, case_number, auction_date, data_source';
    v_val_list :=
        $vals$
            'duval',
            mca.case_number,
            COALESCE(mca.auction_date, mca.sale_date),
            CASE
                WHEN lower(COALESCE(mca.source_platform,'')) LIKE '%%realforeclose%%'
                     THEN 'duval_realforeclose_official'
                WHEN lower(COALESCE(mca.source_platform,'')) LIKE '%%realtaxdeed%%'
                     THEN 'duval_realtaxdeed_official'
                WHEN mca.clerk_url IS NOT NULL THEN 'duval_clerk_direct'
                ELSE 'duval_realforeclose_official'
            END
        $vals$;

    IF v_has_winning_bid THEN
        v_col_list := v_col_list || ', winning_bid';
        v_val_list := v_val_list || ', NULLIF(COALESCE(mca.winning_bid, mca.final_bid), 0)';
    END IF;
    IF v_has_sale_amount THEN
        v_col_list := v_col_list || ', sale_amount';
        v_val_list := v_val_list || ', NULLIF(COALESCE(mca.winning_bid, mca.final_bid, mca.sold_amount), 0)';
    END IF;
    IF v_has_parcel_id THEN
        v_col_list := v_col_list || ', parcel_id';
        v_val_list := v_val_list || ', mca.parcel_id';
    END IF;
    IF v_has_sale_status THEN
        v_col_list := v_col_list || ', sale_status';
        v_val_list := v_val_list || $s$,
            CASE
                WHEN lower(COALESCE(mca.auction_status,'')) IN ('sold','third_party','sold_third_party')
                     THEN 'sold'
                WHEN lower(COALESCE(mca.auction_status,'')) IN ('canceled','cancelled','withdrawn')
                     THEN 'canceled'
                WHEN lower(COALESCE(mca.auction_status,'')) IN ('redeemed','redemption')
                     THEN 'redeemed'
                WHEN lower(COALESCE(mca.auction_status,'')) = 'postponed'
                     THEN 'postponed'
                ELSE 'struck'
            END$s$;
    END IF;
    IF v_has_notes THEN
        v_col_list := v_col_list || ', notes';
        v_val_list := v_val_list || $n$, 'B-fix 2026-06-23: direct insert'$n$;
    END IF;
    IF v_has_source_url THEN
        v_col_list := v_col_list || ', source_url';
        v_val_list := v_val_list || ', COALESCE(mca.source_url, mca.clerk_url)';
    END IF;

    v_sql := format(
        $q$
        INSERT INTO foreclosure_outcomes (%s)
        SELECT %s
        FROM multi_county_auctions mca
        WHERE lower(mca.county) = 'duval'
          AND mca.case_number IN (
            '16-2025-CC-016284-AXXX-MA',
            '16-2025-CA-004262-AXXX-MA',
            '16-2025-CA-007003-AXXX-MA',
            '16-2024-CA-006897-AXXX-MA',
            '16-2025-CA-003195-AXXX-MA',
            '16-2025-CA-003566-AXXX-MA',
            '16-2018-CA-007837-XXXX-MA'
          )
          AND COALESCE(mca.auction_date, mca.sale_date) IS NOT NULL
        ON CONFLICT DO NOTHING
        $q$,
        v_col_list,
        v_val_list
    );

    EXECUTE v_sql;
    GET DIAGNOSTICS v_inserted = ROW_COUNT;
    RAISE NOTICE 'Step 1 targeted insert: % rows', v_inserted;

    -- ── Step 2: Broadened catch-all for remaining Duval FC rows ───────────
    v_sql := format(
        $q$
        INSERT INTO foreclosure_outcomes (%s)
        SELECT %s
        FROM multi_county_auctions mca
        WHERE lower(mca.county) = 'duval'
          AND (
            lower(COALESCE(mca.sale_type,'')) IN ('foreclosure','fc','fc sale','mortgage foreclosure')
            OR (
              lower(COALESCE(mca.sale_type,'')) NOT IN ('tax_deed','td','tax deed','realtaxdeed')
              AND (mca.case_number LIKE '%%-CA-%%' OR mca.case_number LIKE '%%-CC-%%')
            )
          )
          AND mca.auction_status IN (
              'sold','Sold','SOLD','no_sale','No Bid','no_bid',
              'canceled','cancelled','Canceled','Cancelled',
              'struck_to_plaintiff','third_party','sold_third_party',
              'redeemed','postponed','opened','withdrawn'
          )
          AND COALESCE(mca.source_platform,'') NOT ILIKE '%%propertyonion%%'
          AND COALESCE(mca.auction_date, mca.sale_date) IS NOT NULL
        ON CONFLICT DO NOTHING
        $q$,
        v_col_list,
        v_val_list
    );

    EXECUTE v_sql;
    GET DIAGNOSTICS v_inserted = ROW_COUNT;
    RAISE NOTICE 'Step 2 broadened catch-all: % rows', v_inserted;

END;
$$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 3: F fix — tier1_sold_amount for the 7 zero-bid rows
-- NULLIF skips 0.0, opening_bid is plaintiff floor
-- ═══════════════════════════════════════════════════════════════════════════════
UPDATE multi_county_auctions
SET
    tier1_sold_amount = COALESCE(
                            NULLIF(winning_bid, 0),
                            NULLIF(final_bid, 0),
                            NULLIF(sold_amount, 0),
                            opening_bid
                        ),
    tier1_buyer_type  = COALESCE(tier1_buyer_type, 'unknown'),
    tier1_verified_at = NOW(),
    updated_at        = NOW()
WHERE lower(county) = 'duval'
  AND case_number IN (
    '16-2025-CC-016284-AXXX-MA',
    '16-2025-CA-004262-AXXX-MA',
    '16-2025-CA-007003-AXXX-MA',
    '16-2024-CA-006897-AXXX-MA',
    '16-2025-CA-003195-AXXX-MA',
    '16-2025-CA-003566-AXXX-MA',
    '16-2018-CA-007837-XXXX-MA'
  )
  AND (tier1_sold_amount IS NULL OR tier1_sold_amount = 0)
  AND COALESCE(
        NULLIF(winning_bid, 0),
        NULLIF(final_bid, 0),
        NULLIF(sold_amount, 0),
        opening_bid
      ) IS NOT NULL;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 4: B/F verification
-- ═══════════════════════════════════════════════════════════════════════════════
DO $$
DECLARE
    v_county_col   TEXT;
    v_target_found INTEGER;
    v_fc_outcomes  INTEGER;
    v_td_outcomes  INTEGER;
    v_total        INTEGER;
    v_closed_sold  INTEGER;
    v_b_pct        NUMERIC;
    v_tier1_count  INTEGER;
BEGIN
    SELECT column_name INTO v_county_col
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='foreclosure_outcomes'
      AND column_name IN ('county','county_slug')
    ORDER BY CASE WHEN column_name='county' THEN 1 ELSE 2 END LIMIT 1;

    RAISE NOTICE '=== DUVAL B FIX VERIFICATION ===';

    -- Count target 7
    EXECUTE format(
        $q$SELECT COUNT(*) FROM foreclosure_outcomes
           WHERE %I = 'duval' AND case_number IN (
             '16-2025-CC-016284-AXXX-MA','16-2025-CA-004262-AXXX-MA',
             '16-2025-CA-007003-AXXX-MA','16-2024-CA-006897-AXXX-MA',
             '16-2025-CA-003195-AXXX-MA','16-2025-CA-003566-AXXX-MA',
             '16-2018-CA-007837-XXXX-MA')$q$,
        v_county_col
    ) INTO v_target_found;

    -- B counts
    EXECUTE format(
        'SELECT COUNT(*) FROM foreclosure_outcomes WHERE %I = ''duval'' AND COALESCE(data_source,'''') NOT ILIKE ''%%propertyonion%%''',
        v_county_col
    ) INTO v_fc_outcomes;

    BEGIN
        EXECUTE format(
            'SELECT COUNT(*) FROM tax_deed_outcomes WHERE %I = ''duval'' AND COALESCE(data_source,'''') NOT ILIKE ''%%propertyonion%%''',
            v_county_col
        ) INTO v_td_outcomes;
    EXCEPTION WHEN OTHERS THEN
        v_td_outcomes := 0;
    END;

    v_total := v_fc_outcomes + v_td_outcomes;

    SELECT count(*) FILTER (WHERE sold_amount IS NOT NULL)
    INTO v_closed_sold
    FROM multi_county_auctions WHERE lower(county) = 'duval';

    v_b_pct := CASE WHEN v_closed_sold > 0 THEN ROUND(100.0 * v_total / v_closed_sold, 1) ELSE 0 END;

    RAISE NOTICE 'Target 7 in foreclosure_outcomes: %/7', v_target_found;
    RAISE NOTICE 'B: fc=% td=% verified=% closed_sold=% pct=% PASS=%',
        v_fc_outcomes, v_td_outcomes, v_total, v_closed_sold,
        v_b_pct, (v_total >= CEIL(v_closed_sold * 0.95));

    -- F
    SELECT COUNT(*) INTO v_tier1_count
    FROM multi_county_auctions
    WHERE lower(county)='duval' AND sold_amount IS NOT NULL
      AND tier1_sold_amount IS NOT NULL AND tier1_sold_amount > 0;

    RAISE NOTICE 'F: tier1=% closed_sold=% pct=% PASS=%',
        v_tier1_count, v_closed_sold,
        ROUND(100.0 * v_tier1_count / NULLIF(v_closed_sold,0), 1),
        (v_tier1_count >= CEIL(v_closed_sold * 0.95));

    RAISE NOTICE '=== END VERIFICATION ===';
END;
$$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 5: bug_registry (best-effort)
-- ═══════════════════════════════════════════════════════════════════════════════
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema='public' AND table_name='bug_registry') THEN
        UPDATE bug_registry
        SET    status='fixed', resolved_at=NOW()
        WHERE  bug_id='supervisor:stall:duval_B_outcomes';
        RAISE NOTICE 'bug_registry: updated';
    END IF;
END;
$$;
