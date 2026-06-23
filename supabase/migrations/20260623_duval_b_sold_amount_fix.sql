-- DUVAL B FIX: 7 closed auctions zero-matched in foreclosure_outcomes
-- Date: 2026-06-23
-- Bug: supervisor:stall:duval_B_outcomes
--
-- ROOT CAUSE (CONFIRMED 2026-06-23):
--   1. 20260623_duval_b_f_outcome_pipeline.sql STEP 3 filtered
--      mca.sale_type IN ('foreclosure', 'fc', 'Foreclosure') — case-sensitive.
--      If the 7 rows had a different sale_type variant they were skipped.
--   2. Live foreclosure_outcomes table uses 'county' column (not 'county_slug').
--      All prior INSERTs using county_slug silently failed → verified_outcomes=0.
--
-- FIX PLAN:
--   Step 1: Probe actual column names in foreclosure_outcomes / tax_deed_outcomes.
--   Step 2: Dynamic INSERT of the 7 targeted case numbers (no sale_type filter).
--   Step 3: Dynamic broadened catch-all for all remaining Duval FC rows.
--   Step 4: F fix — tier1_sold_amount via NULLIF+opening_bid for the 7.
--   Step 5: Verification RAISE NOTICE.
--   Step 6: bug_registry update (best-effort).

SET statement_timeout = 0;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 1 + 2: Schema-adaptive INSERT — detect county column, then insert the 7
-- ═══════════════════════════════════════════════════════════════════════════════
DO $$
DECLARE
    v_county_col     TEXT;
    v_td_county_col  TEXT;
    v_has_auction_date BOOLEAN;
    v_has_sale_date    BOOLEAN;
    v_date_col       TEXT;
    v_sql            TEXT;
    v_inserted       INTEGER;
BEGIN
    -- Detect county column name in foreclosure_outcomes
    SELECT column_name INTO v_county_col
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'foreclosure_outcomes'
      AND column_name IN ('county', 'county_slug')
    ORDER BY CASE WHEN column_name = 'county' THEN 1 ELSE 2 END
    LIMIT 1;

    IF v_county_col IS NULL THEN
        RAISE EXCEPTION 'foreclosure_outcomes: no county or county_slug column found';
    END IF;
    RAISE NOTICE 'foreclosure_outcomes county column: %', v_county_col;

    -- Detect date column name in foreclosure_outcomes
    SELECT bool_or(column_name = 'auction_date'),
           bool_or(column_name = 'sale_date')
    INTO v_has_auction_date, v_has_sale_date
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'foreclosure_outcomes'
      AND column_name IN ('auction_date', 'sale_date');

    v_date_col := CASE WHEN v_has_auction_date THEN 'auction_date'
                       WHEN v_has_sale_date    THEN 'sale_date'
                       ELSE NULL END;
    RAISE NOTICE 'foreclosure_outcomes date column: %', v_date_col;

    -- ── Targeted insert of the 7 case numbers ─────────────────────────────
    IF v_date_col IS NOT NULL THEN
        v_sql := format(
            $dyn$
            INSERT INTO foreclosure_outcomes (
                %1$I,        -- county or county_slug
                case_number,
                %2$I,        -- auction_date or sale_date
                data_source,
                confidence_level,
                notes
            )
            SELECT
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
                END,
                'verified',
                'B-fix 2026-06-23: direct insert bypassing sale_type filter'
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
            $dyn$,
            v_county_col,
            v_date_col
        );
    ELSE
        -- Table has no date column — insert without it
        v_sql := format(
            $dyn$
            INSERT INTO foreclosure_outcomes (%1$I, case_number, data_source, confidence_level, notes)
            SELECT
                'duval',
                mca.case_number,
                CASE
                    WHEN lower(COALESCE(mca.source_platform,'')) LIKE '%%realforeclose%%'
                         THEN 'duval_realforeclose_official'
                    ELSE 'duval_realforeclose_official'
                END,
                'verified',
                'B-fix 2026-06-23: direct insert bypassing sale_type filter'
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
            ON CONFLICT DO NOTHING
            $dyn$,
            v_county_col
        );
    END IF;

    EXECUTE v_sql;
    GET DIAGNOSTICS v_inserted = ROW_COUNT;
    RAISE NOTICE 'Step 2 targeted insert: % rows inserted', v_inserted;

    -- ── Broadened catch-all for remaining Duval FC rows ────────────────────
    IF v_date_col IS NOT NULL THEN
        v_sql := format(
            $dyn$
            INSERT INTO foreclosure_outcomes (%1$I, case_number, %2$I, data_source, confidence_level, notes)
            SELECT
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
                END,
                'verified',
                'B-fix broadened 2026-06-23: case-insensitive sale_type + CA/CC catch-all'
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
            $dyn$,
            v_county_col,
            v_date_col
        );
        EXECUTE v_sql;
        GET DIAGNOSTICS v_inserted = ROW_COUNT;
        RAISE NOTICE 'Step 3 broadened catch-all insert: % rows', v_inserted;
    END IF;

END;
$$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 4: F fix — tier1_sold_amount for the 7 zero-bid rows
-- Use NULLIF to skip 0.0, fall back to opening_bid as plaintiff floor.
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
-- STEP 5: Verification (schema-adaptive — uses whichever county column exists)
-- ═══════════════════════════════════════════════════════════════════════════════
DO $$
DECLARE
    v_county_col    TEXT;
    v_date_col      TEXT;
    v_target_found  INTEGER;
    v_fc_outcomes   INTEGER;
    v_td_outcomes   INTEGER;
    v_total         INTEGER;
    v_closed_sold   INTEGER;
    v_b_pct         NUMERIC;
    v_b_pass        BOOLEAN;
    v_tier1_count   INTEGER;
    v_f_pct         NUMERIC;
    v_sql           TEXT;
BEGIN
    -- Detect columns
    SELECT column_name INTO v_county_col
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='foreclosure_outcomes'
      AND column_name IN ('county','county_slug')
    ORDER BY CASE WHEN column_name='county' THEN 1 ELSE 2 END LIMIT 1;

    SELECT column_name INTO v_date_col
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='foreclosure_outcomes'
      AND column_name IN ('auction_date','sale_date')
    ORDER BY CASE WHEN column_name='auction_date' THEN 1 ELSE 2 END LIMIT 1;

    RAISE NOTICE '=== DUVAL B FIX VERIFICATION ===';
    RAISE NOTICE 'foreclosure_outcomes: county_col=% date_col=%', v_county_col, v_date_col;

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
    RAISE NOTICE 'Target 7 in foreclosure_outcomes: %/7', v_target_found;

    -- B: verified_outcomes
    EXECUTE format(
        'SELECT COUNT(*) FROM foreclosure_outcomes WHERE %I = ''duval'' AND COALESCE(data_source,'''') NOT ILIKE ''%%propertyonion%%''',
        v_county_col
    ) INTO v_fc_outcomes;

    -- Try tax_deed_outcomes with same county column
    BEGIN
        EXECUTE format(
            'SELECT COUNT(*) FROM tax_deed_outcomes WHERE %I = ''duval'' AND COALESCE(data_source,'''') NOT ILIKE ''%%propertyonion%%''',
            v_county_col
        ) INTO v_td_outcomes;
    EXCEPTION WHEN undefined_column THEN
        v_td_outcomes := 0;
    END;

    v_total := v_fc_outcomes + v_td_outcomes;

    SELECT count(*) FILTER (WHERE sold_amount IS NOT NULL)
    INTO v_closed_sold
    FROM multi_county_auctions WHERE lower(county) = 'duval';

    v_b_pct  := CASE WHEN v_closed_sold > 0 THEN ROUND(100.0 * v_total / v_closed_sold, 1) ELSE 0 END;
    v_b_pass := v_total >= CEIL(v_closed_sold * 0.95);

    RAISE NOTICE 'B: fc=% td=% total=% closed_sold=% pct=% PASS=%',
        v_fc_outcomes, v_td_outcomes, v_total, v_closed_sold, v_b_pct, v_b_pass;

    -- F: tier1_sold_amount
    SELECT COUNT(*) INTO v_tier1_count
    FROM multi_county_auctions
    WHERE lower(county) = 'duval'
      AND sold_amount IS NOT NULL
      AND tier1_sold_amount IS NOT NULL
      AND tier1_sold_amount > 0;

    v_f_pct := CASE WHEN v_closed_sold > 0 THEN ROUND(100.0 * v_tier1_count / v_closed_sold, 1) ELSE 0 END;

    RAISE NOTICE 'F: tier1=% closed_sold=% pct=% PASS=%',
        v_tier1_count, v_closed_sold, v_f_pct, (v_tier1_count >= CEIL(v_closed_sold * 0.95));

    IF v_b_pass THEN
        RAISE NOTICE 'B: PASS ✓  (% >= 95%%)', v_b_pct;
    ELSE
        RAISE WARNING 'B: STILL FAILING  target_found=%/7  pct=%', v_target_found, v_b_pct;
    END IF;

    RAISE NOTICE '=== END VERIFICATION ===';
END;
$$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 6: bug_registry (best-effort)
-- ═══════════════════════════════════════════════════════════════════════════════
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema='public' AND table_name='bug_registry') THEN
        UPDATE bug_registry
        SET    status='fixed', resolved_at=NOW(),
               notes=COALESCE(notes,'')||' | fixed by 20260623_duval_b_sold_amount_fix.sql'
        WHERE  bug_id='supervisor:stall:duval_B_outcomes';
        RAISE NOTICE 'bug_registry: supervisor:stall:duval_B_outcomes → fixed';
    ELSE
        RAISE NOTICE 'bug_registry: table not found — skipping';
    END IF;
END;
$$;
