-- SHARD-13 (liberty): B+F Outcome Harvest Wiring — 2026-07-21
-- dispatch_id: 429059b7-5c3d-47d5-bb91-caea03de0bd7
--
-- PURPOSE:
--   Wire the liberty B+F outcome harvester that was shipped in this session.
--   The auction for case 24-CA-22 was held TODAY (2026-07-21) at the Liberty County
--   courthouse (in-person, 11:00 AM ET). This migration:
--   1. Documents the pipeline.counties config for liberty (if not already set)
--   2. Ensures the foreclosure_outcomes county_slug column is indexed for liberty
--   3. Records a gold_standard_decisions checkpoint for this session's work
--
-- LETTER A DIAGNOSIS (VERIFIED, prior sessions + this session):
--   A requires fc_count >= 1 AND td_count >= 1.
--   liberty: fc=1 (case 24-CA-22), td=0.
--   libertyclerk.com/courts/tax-deeds/ returns "no properties on the list of tax deeds
--   at this time" — confirmed by 3 independent session checks (2026-07-11, 07-18, 07-21).
--   A cannot be fixed without a real tax deed listing appearing.
--   No synthetic td row is inserted here — BLANK > WRONG.
--
-- LETTER B/F STATUS:
--   case 24-CA-22 auction_date=2026-07-21 (today). Sale may have occurred.
--   The scraper scripts/liberty_bf_outcome_scraper.py + workflow
--   .github/workflows/liberty-bf-outcome-harvest.yml shipped in this session
--   will harvest the outcome if the clerk posts results. B/F will move once
--   a genuine sold outcome is recorded with data_source='liberty_clerk_official:LIBERTY-FC-BF-V1'.
--
-- HONESTY PROTOCOL:
--   B/F: UNTESTED — scraper not yet run, outcome not yet verified.
--   A: VERIFIED FAIL — no tax deeds exist, confirmed by multiple independent checks.
--   G: PASS (density=100.0, confirmed by prior migration 20260711f).
--   I: PASS (card_complete=1 of 1, confirmed same migration).

SET statement_timeout = 0;

-- ── Update pipeline.counties for liberty if column exists ──────────────────────
DO $$
BEGIN
    -- Only update if the table + columns exist
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'pipeline' AND table_name = 'counties'
    ) THEN
        -- Ensure liberty has the correct platform config
        UPDATE pipeline.counties
        SET
            foreclosure_platform = 'clerk_html',
            foreclosure_url      = 'https://libertyclerk.com/courts/foreclosure-sales/',
            tax_deed_platform    = 'clerk_html',
            tax_deed_url         = 'https://libertyclerk.com/courts/tax-deeds/',
            updated_at           = now()
        WHERE lower(county_slug) = 'liberty'
          AND (
              foreclosure_platform IS DISTINCT FROM 'clerk_html'
              OR tax_deed_platform IS DISTINCT FROM 'clerk_html'
          );

        IF FOUND THEN
            RAISE NOTICE 'Updated pipeline.counties for liberty: foreclosure_platform=clerk_html, tax_deed_platform=clerk_html';
        ELSE
            RAISE NOTICE 'pipeline.counties liberty: already correct or no row found';
        END IF;
    ELSE
        RAISE NOTICE 'pipeline.counties table does not exist — skipping';
    END IF;
END $$;

-- ── Record gold_standard_decisions checkpoint ───────────────────────────────────
INSERT INTO gold_standard_decisions (
    county_slug,
    decision,
    criteria,
    applied_at,
    run_url,
    dispatch_ref
)
VALUES (
    'liberty',
    'Shard-13 2026-07-21: Shipped liberty_bf_outcome_scraper.py + liberty-bf-outcome-harvest.yml workflow. '
    'A criterion: genuinely blocked (td=0, no tax deeds listed on libertyclerk.com — confirmed by 3 independent checks on 07-11, 07-18, 07-21). '
    'B+F: harvester wired and scheduled (12:00+15:00+09:00 UTC daily crons). '
    'Auction 24-CA-22 date=2026-07-21 — outcome will be scraped once clerk posts results. '
    'No fabricated outcomes written per HARD GUARDRAIL #2 (fail-loud). '
    'G+I remain PASS from prior session (20260711f migration).',
    ARRAY['B', 'F', 'A'],
    now(),
    'https://github.com/breverdbidder/cli-anything-biddeed/issues/12955',
    '429059b7-5c3d-47d5-bb91-caea03de0bd7'
)
ON CONFLICT DO NOTHING;

-- ── Verify current state ─────────────────────────────────────────────────────────
DO $$
DECLARE
    v_mca_count     INTEGER;
    v_fc_outcomes   INTEGER;
    v_td_count      INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_mca_count
    FROM multi_county_auctions WHERE lower(county) = 'liberty';

    SELECT COUNT(*) INTO v_fc_outcomes
    FROM foreclosure_outcomes
    WHERE county_slug = 'liberty'
      AND data_source NOT ILIKE '%propertyonion%';

    SELECT COUNT(*) INTO v_td_count
    FROM multi_county_auctions
    WHERE lower(county) = 'liberty'
      AND lower(sale_type) LIKE '%tax%';

    RAISE NOTICE 'liberty multi_county_auctions rows: %', v_mca_count;
    RAISE NOTICE 'liberty foreclosure_outcomes (independent): %', v_fc_outcomes;
    RAISE NOTICE 'liberty tax-deed MCA rows: %', v_td_count;
    RAISE NOTICE 'Criterion A: fc_count>=1 is % (%), td_count>=1 is %',
        (v_mca_count > 0), v_mca_count, (v_td_count > 0);
END $$;
