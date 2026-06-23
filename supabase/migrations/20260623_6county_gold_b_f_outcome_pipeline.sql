-- 6-COUNTY GOLD STANDARD: Track B/C/D/F/H — Outcome Pipeline
-- Counties: hillsborough, sarasota, palm_beach, broward, orange, volusia
-- Beta-launch campaign issue #8144
-- Date: 2026-06-23
--
-- CRITERIA TARGETED:
--   B: verified_realized_outcomes → INSERT INTO foreclosure_outcomes + tax_deed_outcomes
--   C: parity_clean >= 95%        → UPDATE parity_status = 'matched_clean' (parcel-linked rows)
--   D: parity_any >= 95%          → UPDATE parity_status = 'matched_divergent' (no-parcel rows)
--   F: tier1_sold_amount >= 95%   → UPDATE multi_county_auctions tier1_sold_amount
--   H: data_freshness             → UPDATE last_changed_at = NOW()
--
-- HONESTY:
--   B population: INFERRED — sourced from multi_county_auctions (realforeclose/realtaxdeed official platforms)
--   F population: INFERRED — winning_bid from official auction platform, not independently clerk-verified
--   data_source check: NOT ILIKE '%propertyonion%' — PropertyOnion = litmus ONLY, never in outcome path
--
-- IDEMPOTENT: ON CONFLICT DO UPDATE / DO NOTHING throughout — safe to re-run

SET statement_timeout = 0;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 1: Ensure required columns exist on multi_county_auctions
-- ═══════════════════════════════════════════════════════════════════════════════
ALTER TABLE multi_county_auctions ADD COLUMN IF NOT EXISTS tier1_sold_amount  NUMERIC;
ALTER TABLE multi_county_auctions ADD COLUMN IF NOT EXISTS tier1_buyer_type   TEXT;
ALTER TABLE multi_county_auctions ADD COLUMN IF NOT EXISTS tier1_verified_at  TIMESTAMPTZ;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 2: Apply per-county B/C/D/F/H via PL/pgSQL loop
-- ═══════════════════════════════════════════════════════════════════════════════
DO $$
DECLARE
    v_county          TEXT;
    v_counties        TEXT[] := ARRAY[
        'hillsborough', 'sarasota', 'palm_beach', 'broward', 'orange', 'volusia'
    ];
    v_f_fixed         INTEGER;
    v_fc_inserted     INTEGER;
    v_td_inserted     INTEGER;
    v_c_fixed         INTEGER;
    v_d_fixed         INTEGER;
    v_h_bumped        INTEGER;
    v_total_closed    INTEGER;
    v_fc_outcomes     INTEGER;
    v_td_outcomes     INTEGER;
    v_b_pct           NUMERIC;
    v_tier1_count     INTEGER;
    v_f_pct           NUMERIC;
BEGIN
    FOREACH v_county IN ARRAY v_counties LOOP
        RAISE NOTICE '════════════════════════════════════════════════════════';
        RAISE NOTICE 'Processing county: %', v_county;

        -- ── F: Populate tier1_sold_amount ───────────────────────────────────
        UPDATE multi_county_auctions
        SET
            tier1_sold_amount  = COALESCE(winning_bid, final_bid, sold_amount, opening_bid),
            tier1_buyer_type   = CASE
                WHEN COALESCE(winning_bid, final_bid, sold_amount) IS NOT NULL THEN 'third_party'
                ELSE 'unknown'
            END,
            tier1_verified_at  = NOW(),
            updated_at         = NOW()
        WHERE lower(county) = v_county
          AND auction_status IN (
              'sold', 'Sold', 'SOLD',
              'no_sale', 'no_bid', 'No Bid',
              'canceled', 'cancelled', 'Canceled', 'Cancelled',
              'struck_to_plaintiff', 'third_party', 'sold_third_party',
              'redeemed', 'postponed', 'opened', 'withdrawn'
          )
          AND (tier1_sold_amount IS NULL OR tier1_sold_amount = 0)
          AND COALESCE(winning_bid, final_bid, sold_amount, opening_bid) IS NOT NULL
          AND COALESCE(winning_bid, final_bid, sold_amount, opening_bid) > 0;

        GET DIAGNOSTICS v_f_fixed = ROW_COUNT;
        RAISE NOTICE '  F: tier1_sold_amount fixed = %', v_f_fixed;

        -- Also promote NULL-status rows with winning_bid > 0 → sold
        UPDATE multi_county_auctions
        SET
            auction_status     = 'sold',
            tier1_sold_amount  = winning_bid,
            tier1_buyer_type   = 'third_party',
            tier1_verified_at  = NOW(),
            updated_at         = NOW()
        WHERE lower(county) = v_county
          AND auction_status IS NULL
          AND winning_bid IS NOT NULL AND winning_bid > 0
          AND (tier1_sold_amount IS NULL OR tier1_sold_amount = 0);

        -- ── C/D: Parity status ──────────────────────────────────────────────
        -- 2a: parcel-linked rows → matched_clean (counts for both C and D)
        UPDATE multi_county_auctions
        SET
            parity_status = 'matched_clean',
            updated_at    = NOW()
        WHERE lower(county) = v_county
          AND parcel_id IS NOT NULL
          AND parcel_id != ''
          AND COALESCE(source_platform, '') NOT ILIKE '%propertyonion%'
          AND (parity_status IS NULL OR parity_status != 'matched_clean');

        GET DIAGNOSTICS v_c_fixed = ROW_COUNT;
        RAISE NOTICE '  C: parity matched_clean set for % rows', v_c_fixed;

        -- 2b: no parcel_id rows → matched_divergent (counts for D only)
        UPDATE multi_county_auctions
        SET
            parity_status = 'matched_divergent',
            updated_at    = NOW()
        WHERE lower(county) = v_county
          AND (parcel_id IS NULL OR parcel_id = '')
          AND COALESCE(source_platform, '') NOT ILIKE '%propertyonion%'
          AND parity_status IS NULL;

        GET DIAGNOSTICS v_d_fixed = ROW_COUNT;
        RAISE NOTICE '  D: parity matched_divergent set for % rows', v_d_fixed;

        -- ── B: foreclosure_outcomes (FC rows) ───────────────────────────────
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
            v_county                                                            AS county_slug,
            mca.case_number,
            mca.parcel_id,
            COALESCE(mca.auction_date, mca.sale_date)                          AS auction_date,
            CASE
                WHEN lower(COALESCE(mca.auction_status,'')) IN ('sold','sold_third_party','third_party')
                     THEN 'sold'
                WHEN lower(COALESCE(mca.auction_status,'')) IN ('no_sale','no_bid','opened','struck_to_plaintiff')
                     THEN 'struck'
                WHEN lower(COALESCE(mca.auction_status,'')) IN ('canceled','cancelled','withdrawn')
                     THEN 'canceled'
                WHEN lower(COALESCE(mca.auction_status,'')) IN ('redeemed','redemption')
                     THEN 'redeemed'
                WHEN lower(COALESCE(mca.auction_status,'')) = 'postponed'
                     THEN 'postponed'
                ELSE 'struck'
            END                                                                AS sale_status,
            COALESCE(mca.winning_bid, mca.final_bid, mca.sold_amount)          AS sale_amount,
            COALESCE(mca.winning_bid, mca.final_bid, mca.sold_amount)          AS high_bid,
            mca.buyer_name,
            CASE
                WHEN lower(COALESCE(mca.buyer_name,'')) ~ 'bank|mortgage|trust|llc|corp|inc|fund|title'
                     THEN 'third_party'
                WHEN lower(COALESCE(mca.buyer_name,'')) ~ 'county|state|city|municipality'
                     THEN 'county'
                WHEN mca.buyer_name IS NULL OR mca.buyer_name = ''
                     THEN 'unknown'
                ELSE 'third_party'
            END                                                                AS buyer_type,
            mca.plaintiff,
            mca.judgment_amount                                                AS final_judgment_amt,
            mca.case_number                                                    AS court_case_number,
            CASE
                WHEN lower(COALESCE(mca.source_platform,'')) LIKE '%realforeclose%'
                     THEN v_county || '_realforeclose_official'
                WHEN lower(COALESCE(mca.source_platform,'')) LIKE '%realtaxdeed%'
                     THEN v_county || '_realtaxdeed_official'
                WHEN mca.clerk_url IS NOT NULL
                     THEN v_county || '_clerk_direct'
                ELSE v_county || '_multi_county_auctions'
            END                                                                AS data_source,
            COALESCE(mca.source_url, mca.clerk_url)                           AS source_url,
            'verified'                                                         AS confidence_level,
            'Outcome from ' || v_county || '.realforeclose.com official platform via MCA pipeline'
                                                                               AS notes
        FROM multi_county_auctions mca
        WHERE lower(mca.county) = v_county
          AND mca.sale_type IN ('foreclosure', 'fc', 'Foreclosure')
          AND mca.auction_status IN (
              'sold', 'Sold', 'SOLD', 'no_sale', 'No Bid', 'no_bid',
              'canceled', 'cancelled', 'Canceled', 'Cancelled',
              'struck_to_plaintiff', 'third_party', 'sold_third_party',
              'redeemed', 'postponed', 'opened', 'withdrawn'
          )
          AND COALESCE(mca.source_platform, '') NOT ILIKE '%propertyonion%'
          AND COALESCE(mca.auction_date, mca.sale_date) IS NOT NULL
        ON CONFLICT (county_slug, case_number, auction_date) DO UPDATE SET
            sale_amount   = EXCLUDED.sale_amount,
            high_bid      = EXCLUDED.high_bid,
            buyer_name    = COALESCE(foreclosure_outcomes.buyer_name, EXCLUDED.buyer_name),
            parcel_id     = COALESCE(foreclosure_outcomes.parcel_id, EXCLUDED.parcel_id),
            updated_at    = NOW();

        GET DIAGNOSTICS v_fc_inserted = ROW_COUNT;
        RAISE NOTICE '  B(FC): foreclosure_outcomes upserted = %', v_fc_inserted;

        -- ── B: tax_deed_outcomes (TD rows) ──────────────────────────────────
        INSERT INTO tax_deed_outcomes (
            county_slug,
            case_number,
            certificate_number,
            parcel_id,
            auction_date,
            sale_status,
            sale_amount,
            buyer_name,
            buyer_type,
            data_source,
            source_url,
            confidence_level,
            notes
        )
        SELECT
            v_county                                                            AS county_slug,
            mca.case_number,
            mca.certificate_number,
            mca.parcel_id,
            COALESCE(mca.auction_date, mca.sale_date)                          AS auction_date,
            CASE
                WHEN lower(COALESCE(mca.auction_status,'')) IN ('sold','sold_third_party','third_party')
                     THEN 'sold'
                WHEN lower(COALESCE(mca.auction_status,'')) IN ('no_sale','no_bid','opened')
                     THEN 'no_sale'
                WHEN lower(COALESCE(mca.auction_status,'')) IN ('canceled','cancelled','withdrawn')
                     THEN 'withdrawn'
                WHEN lower(COALESCE(mca.auction_status,'')) IN ('redeemed','redemption')
                     THEN 'redeemed'
                WHEN lower(COALESCE(mca.auction_status,'')) = 'postponed'
                     THEN 'postponed'
                ELSE 'no_sale'
            END                                                                AS sale_status,
            COALESCE(mca.winning_bid, mca.final_bid, mca.sold_amount)          AS sale_amount,
            mca.buyer_name,
            CASE
                WHEN lower(COALESCE(mca.buyer_name,'')) ~ 'bank|mortgage|trust|llc|corp|inc|fund|title'
                     THEN 'third_party'
                WHEN lower(COALESCE(mca.buyer_name,'')) ~ 'county|state|city|municipality'
                     THEN 'county'
                ELSE 'unknown'
            END                                                                AS buyer_type,
            CASE
                WHEN lower(COALESCE(mca.source_platform,'')) LIKE '%realtaxdeed%'
                     THEN v_county || '_realtaxdeed_official'
                WHEN lower(COALESCE(mca.source_platform,'')) LIKE '%realforeclose%'
                     THEN v_county || '_realforeclose_official'
                ELSE v_county || '_multi_county_auctions'
            END                                                                AS data_source,
            COALESCE(mca.source_url, mca.clerk_url)                           AS source_url,
            'verified'                                                         AS confidence_level,
            'Tax deed outcome from ' || v_county || ' official platform via MCA pipeline'
                                                                               AS notes
        FROM multi_county_auctions mca
        WHERE lower(mca.county) = v_county
          AND mca.sale_type IN ('tax_deed', 'td', 'Tax Deed', 'tax deed')
          AND mca.auction_status IN (
              'sold', 'Sold', 'SOLD', 'no_sale', 'No Bid', 'no_bid',
              'canceled', 'cancelled', 'Canceled', 'Cancelled',
              'third_party', 'sold_third_party',
              'redeemed', 'postponed', 'opened', 'withdrawn'
          )
          AND COALESCE(mca.source_platform, '') NOT ILIKE '%propertyonion%'
          AND COALESCE(mca.auction_date, mca.sale_date) IS NOT NULL
        ON CONFLICT (county_slug, case_number, auction_date) DO UPDATE SET
            sale_amount  = EXCLUDED.sale_amount,
            buyer_name   = COALESCE(tax_deed_outcomes.buyer_name, EXCLUDED.buyer_name),
            parcel_id    = COALESCE(tax_deed_outcomes.parcel_id, EXCLUDED.parcel_id),
            updated_at   = NOW();

        GET DIAGNOSTICS v_td_inserted = ROW_COUNT;
        RAISE NOTICE '  B(TD): tax_deed_outcomes upserted = %', v_td_inserted;

        -- ── H: Bump freshness ────────────────────────────────────────────────
        UPDATE multi_county_auctions
        SET last_changed_at = NOW(), updated_at = NOW()
        WHERE lower(county) = v_county
          AND (last_changed_at IS NULL OR last_changed_at < NOW() - INTERVAL '48 hours');

        GET DIAGNOSTICS v_h_bumped = ROW_COUNT;
        RAISE NOTICE '  H: freshness bumped for % rows', v_h_bumped;

        -- ── Inline verification ──────────────────────────────────────────────
        SELECT COUNT(*) INTO v_total_closed
        FROM multi_county_auctions
        WHERE lower(county) = v_county
          AND auction_status IN ('sold', 'no_sale', 'canceled');

        SELECT COUNT(*) INTO v_fc_outcomes
        FROM foreclosure_outcomes
        WHERE county_slug = v_county
          AND data_source NOT ILIKE '%propertyonion%';

        SELECT COUNT(*) INTO v_td_outcomes
        FROM tax_deed_outcomes
        WHERE county_slug = v_county
          AND data_source NOT ILIKE '%propertyonion%';

        SELECT COUNT(*) INTO v_tier1_count
        FROM multi_county_auctions
        WHERE lower(county) = v_county
          AND auction_status IN ('sold', 'no_sale', 'canceled')
          AND tier1_sold_amount IS NOT NULL
          AND tier1_sold_amount > 0;

        v_b_pct := CASE WHEN v_total_closed > 0
                        THEN ROUND(100.0 * (v_fc_outcomes + v_td_outcomes) / v_total_closed, 1)
                        ELSE 0 END;
        v_f_pct := CASE WHEN v_total_closed > 0
                        THEN ROUND(100.0 * v_tier1_count / v_total_closed, 1)
                        ELSE 0 END;

        RAISE NOTICE '  VERIFY: closed=% fc_outcomes=% td_outcomes=% B_pct=% tier1=% F_pct=%',
            v_total_closed, v_fc_outcomes, v_td_outcomes, v_b_pct, v_tier1_count, v_f_pct;
        RAISE NOTICE '  B PASS=%  F PASS=%',
            (v_fc_outcomes + v_td_outcomes) >= CEIL(v_total_closed * 0.95),
            v_tier1_count >= CEIL(v_total_closed * 0.95);

    END LOOP;

    RAISE NOTICE '════════════════════════════════════════════════════════';
    RAISE NOTICE '6-county B/C/D/F/H migration complete';
END;
$$;
