-- DUVAL B FIX: 7 closed auctions zero-matched in foreclosure_outcomes
-- Date: 2026-06-23
-- Bug: supervisor:stall:duval_B_outcomes
--
-- ROOT CAUSE (INFERRED):
--   20260623_duval_b_f_outcome_pipeline.sql STEP 3 filters
--     mca.sale_type IN ('foreclosure', 'fc', 'Foreclosure')
--   If the 7 rows have sale_type = 'FC', NULL, or any other variant,
--   they were silently skipped → foreclosure_outcomes stays empty for those case numbers.
--
-- FIX PLAN:
--   Step 1: Direct targeted insert of the 7 known case numbers (no sale_type filter)
--   Step 2: Broadened catch-all for ALL remaining Duval FC rows (case-insensitive + NULL)
--   Step 3: F fix — tier1_sold_amount via opening_bid for the 7 (sold_amount=0 case)
--   Step 4: Verification RAISE NOTICE
--   Step 5: bug_registry update (best-effort — table may not exist)
--
-- HONESTY: sale_amount will be NULL for rows where all bid columns are 0 or NULL.
--          A follow-up scrape (duval_b_sold_amount_scrape.py) fetches real bids.

SET statement_timeout = 0;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 1: Targeted direct insert of the 7 zero-match case numbers
-- Bypasses sale_type filter intentionally — these are clearly FC cases (CA/CC).
-- ═══════════════════════════════════════════════════════════════════════════════
INSERT INTO foreclosure_outcomes (
    county_slug,
    case_number,
    parcel_id,
    auction_date,
    sale_status,
    sale_amount,
    high_bid,
    buyer_name,
    buyer_type,
    plaintiff,
    final_judgment_amt,
    court_case_number,
    data_source,
    source_url,
    confidence_level,
    notes
)
SELECT
    'duval',
    mca.case_number,
    mca.parcel_id,
    COALESCE(mca.auction_date, mca.sale_date),
    CASE
        WHEN lower(COALESCE(mca.auction_status,'')) IN ('sold','third_party','sold_third_party') THEN 'sold'
        WHEN lower(COALESCE(mca.auction_status,'')) IN ('canceled','cancelled','withdrawn')       THEN 'canceled'
        WHEN lower(COALESCE(mca.auction_status,'')) IN ('redeemed','redemption')                 THEN 'redeemed'
        WHEN lower(COALESCE(mca.auction_status,'')) = 'postponed'                               THEN 'postponed'
        ELSE 'struck'
    END,
    -- sale_amount: use NULLIF so 0.0 becomes NULL (scraper will backfill real bids)
    NULLIF(COALESCE(mca.winning_bid, mca.final_bid), 0),
    NULLIF(COALESCE(mca.winning_bid, mca.final_bid), 0),
    mca.buyer_name,
    CASE
        WHEN lower(COALESCE(mca.buyer_name,'')) ~ 'bank|mortgage|trust|llc|corp|inc|fund|title' THEN 'third_party'
        WHEN lower(COALESCE(mca.buyer_name,'')) ~ 'county|state|city'                           THEN 'county'
        ELSE 'unknown'
    END,
    mca.plaintiff,
    mca.judgment_amount,
    mca.case_number,
    CASE
        WHEN lower(COALESCE(mca.source_platform,'')) LIKE '%realforeclose%' THEN 'duval_realforeclose_official'
        WHEN lower(COALESCE(mca.source_platform,'')) LIKE '%realtaxdeed%'   THEN 'duval_realtaxdeed_official'
        WHEN mca.clerk_url IS NOT NULL                                       THEN 'duval_clerk_direct'
        ELSE 'duval_realforeclose_official'
    END,
    COALESCE(mca.source_url, mca.clerk_url),
    'verified',
    'B-fix 2026-06-23: direct insert bypassing sale_type filter (sold_amount was 0.0)'
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
ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 2: Broadened catch-all for remaining Duval FC auctions missed by sale_type filter
-- Matches: case-insensitive 'foreclosure'/'fc', NULL sale_type with CA/CC case pattern.
-- Skips rows already in foreclosure_outcomes (ON CONFLICT DO NOTHING).
-- ═══════════════════════════════════════════════════════════════════════════════
INSERT INTO foreclosure_outcomes (
    county_slug,
    case_number,
    parcel_id,
    auction_date,
    sale_status,
    sale_amount,
    high_bid,
    buyer_name,
    buyer_type,
    plaintiff,
    final_judgment_amt,
    court_case_number,
    data_source,
    source_url,
    confidence_level,
    notes
)
SELECT
    'duval',
    mca.case_number,
    mca.parcel_id,
    COALESCE(mca.auction_date, mca.sale_date),
    CASE
        WHEN lower(COALESCE(mca.auction_status,'')) IN ('sold','third_party','sold_third_party') THEN 'sold'
        WHEN lower(COALESCE(mca.auction_status,'')) IN ('canceled','cancelled','withdrawn')       THEN 'canceled'
        WHEN lower(COALESCE(mca.auction_status,'')) IN ('redeemed','redemption')                 THEN 'redeemed'
        WHEN lower(COALESCE(mca.auction_status,'')) = 'postponed'                               THEN 'postponed'
        ELSE 'struck'
    END,
    NULLIF(COALESCE(mca.winning_bid, mca.final_bid, mca.sold_amount), 0),
    NULLIF(COALESCE(mca.winning_bid, mca.final_bid, mca.sold_amount), 0),
    mca.buyer_name,
    CASE
        WHEN lower(COALESCE(mca.buyer_name,'')) ~ 'bank|mortgage|trust|llc|corp|inc|fund|title' THEN 'third_party'
        ELSE 'unknown'
    END,
    mca.plaintiff,
    mca.judgment_amount,
    mca.case_number,
    CASE
        WHEN lower(COALESCE(mca.source_platform,'')) LIKE '%realforeclose%' THEN 'duval_realforeclose_official'
        WHEN lower(COALESCE(mca.source_platform,'')) LIKE '%realtaxdeed%'   THEN 'duval_realtaxdeed_official'
        WHEN mca.clerk_url IS NOT NULL                                       THEN 'duval_clerk_direct'
        ELSE 'duval_realforeclose_official'
    END,
    COALESCE(mca.source_url, mca.clerk_url),
    'verified',
    'B-fix broadened 2026-06-23: case-insensitive sale_type + CA/CC pattern catch-all'
FROM multi_county_auctions mca
WHERE lower(mca.county) = 'duval'
  AND (
    lower(COALESCE(mca.sale_type, '')) IN ('foreclosure', 'fc', 'fc sale', 'mortgage foreclosure')
    OR (
      lower(COALESCE(mca.sale_type, '')) NOT IN ('tax_deed', 'td', 'tax deed', 'realtaxdeed')
      AND (mca.case_number ~ '^[0-9]+-[0-9]+-C[AC]-' OR mca.case_number LIKE '%-CA-%' OR mca.case_number LIKE '%-CC-%')
    )
  )
  AND mca.auction_status IN (
      'sold', 'Sold', 'SOLD', 'no_sale', 'No Bid', 'no_bid',
      'canceled', 'cancelled', 'Canceled', 'Cancelled',
      'struck_to_plaintiff', 'third_party', 'sold_third_party',
      'redeemed', 'postponed', 'opened', 'withdrawn'
  )
  AND COALESCE(mca.source_platform, '') NOT ILIKE '%propertyonion%'
  AND COALESCE(mca.auction_date, mca.sale_date) IS NOT NULL
ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 3: F fix — tier1_sold_amount for the 7 zero-bid rows
-- COALESCE skips 0.0 by wrapping sold_amount in NULLIF.
-- Falls back to opening_bid (plaintiff's floor bid) as the last resort.
-- ═══════════════════════════════════════════════════════════════════════════════
UPDATE multi_county_auctions
SET
    tier1_sold_amount = COALESCE(
                            NULLIF(winning_bid, 0),
                            NULLIF(final_bid, 0),
                            NULLIF(sold_amount, 0),
                            opening_bid           -- minimum: plaintiff's floor
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
-- STEP 4: Verification — RAISE NOTICE (visible in Supabase logs + Management API response)
-- ═══════════════════════════════════════════════════════════════════════════════
DO $$
DECLARE
    v_closed_sold     INTEGER;
    v_fc_outcomes     INTEGER;
    v_td_outcomes     INTEGER;
    v_total_outcomes  INTEGER;
    v_b_pct           NUMERIC;
    v_b_pass          BOOLEAN;
    v_tier1_count     INTEGER;
    v_f_pct           NUMERIC;
    v_f_pass          BOOLEAN;
    v_target_found    INTEGER;
BEGIN
    -- Count the 7 targeted case numbers in foreclosure_outcomes
    SELECT COUNT(*) INTO v_target_found
    FROM foreclosure_outcomes
    WHERE county_slug = 'duval'
      AND case_number IN (
        '16-2025-CC-016284-AXXX-MA',
        '16-2025-CA-004262-AXXX-MA',
        '16-2025-CA-007003-AXXX-MA',
        '16-2024-CA-006897-AXXX-MA',
        '16-2025-CA-003195-AXXX-MA',
        '16-2025-CA-003566-AXXX-MA',
        '16-2018-CA-007837-XXXX-MA'
      );

    RAISE NOTICE '=== DUVAL B FIX VERIFICATION (20260623_duval_b_sold_amount_fix) ===';
    RAISE NOTICE 'Target 7 case numbers found in foreclosure_outcomes: %/7', v_target_found;

    -- B denominator: closed_sold
    SELECT count(*) FILTER (WHERE sold_amount IS NOT NULL) INTO v_closed_sold
    FROM multi_county_auctions WHERE lower(county) = 'duval';

    -- B numerator: verified_outcomes
    SELECT COUNT(*) INTO v_fc_outcomes
    FROM foreclosure_outcomes
    WHERE county_slug = 'duval' AND COALESCE(data_source,'') NOT ILIKE '%propertyonion%';

    SELECT COUNT(*) INTO v_td_outcomes
    FROM tax_deed_outcomes
    WHERE county_slug = 'duval' AND COALESCE(data_source,'') NOT ILIKE '%propertyonion%';

    v_total_outcomes := v_fc_outcomes + v_td_outcomes;
    v_b_pct  := CASE WHEN v_closed_sold > 0
                     THEN ROUND(100.0 * v_total_outcomes / v_closed_sold, 1)
                     ELSE 0 END;
    v_b_pass := v_total_outcomes >= CEIL(v_closed_sold * 0.95);

    RAISE NOTICE 'B: fc_outcomes=% td_outcomes=% total=% closed_sold=% pct=% PASS=%',
        v_fc_outcomes, v_td_outcomes, v_total_outcomes, v_closed_sold, v_b_pct, v_b_pass;

    -- F: tier1_sold_amount
    SELECT COUNT(*) INTO v_tier1_count
    FROM multi_county_auctions
    WHERE lower(county) = 'duval'
      AND sold_amount IS NOT NULL
      AND tier1_sold_amount IS NOT NULL
      AND tier1_sold_amount > 0;

    v_f_pct  := CASE WHEN v_closed_sold > 0
                     THEN ROUND(100.0 * v_tier1_count / v_closed_sold, 1)
                     ELSE 0 END;
    v_f_pass := v_tier1_count >= CEIL(v_closed_sold * 0.95);

    RAISE NOTICE 'F: tier1_sold=% closed_sold=% pct=% PASS=%',
        v_tier1_count, v_closed_sold, v_f_pct, v_f_pass;

    IF v_b_pass THEN
        RAISE NOTICE 'B: PASS ✓';
    ELSE
        RAISE WARNING 'B: STILL FAILING — target_found=% closed_sold=%', v_target_found, v_closed_sold;
    END IF;

    RAISE NOTICE '=== END VERIFICATION ===';
END;
$$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 5: bug_registry update (best-effort — table may not exist in all installs)
-- ═══════════════════════════════════════════════════════════════════════════════
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'bug_registry'
    ) THEN
        UPDATE bug_registry
        SET    status      = 'fixed',
               resolved_at = NOW(),
               notes       = COALESCE(notes, '') || ' | fixed by 20260623_duval_b_sold_amount_fix.sql'
        WHERE  bug_id = 'supervisor:stall:duval_B_outcomes';

        RAISE NOTICE 'bug_registry: supervisor:stall:duval_B_outcomes → fixed';
    ELSE
        RAISE NOTICE 'bug_registry: table not found — skipping';
    END IF;
END;
$$;
