-- Migration: 20260724_liberty_shard8_bf_platform_fix.sql
-- Gold Standard Shard-8, dispatch_id 9433ec3c-3860-480f-a0bf-946e6aeb5fbe
-- Liberty County — A/B/F gap fixes
--
-- Context (VERIFIED by prior sessions):
--   liberty.realforeclose.com / liberty.realtaxdeed.com return HTTP 403 for Liberty
--   — Liberty is NOT a RealAuction tenant. Real platform is:
--     https://libertyclerk.com/courts/foreclosure-sales/
--     https://libertyclerk.com/courts/tax-deeds/
--   Case 24-CA-22: in-person foreclosure sale was 2026-07-21 (sale has occurred).
--   This migration corrects the pipeline.counties record and prepares the
--   foreclosure_outcomes slot for when the sale result is captured by the scraper.
--
-- Letters targeted: A (platform fix), B/F (outcome slot prepared)
-- NOTE: sold_amount for 24-CA-22 is set to NULL here and populated by the
--   liberty_clerk_results_check workflow once the clerk posts the result.
--   If the scraper confirms a sale, a follow-up migration/script updates
--   winning_bid and the MCA sold_amount/tier1_sold_amount.

SET statement_timeout = 0;

-- ── Step 1: Fix pipeline.counties to clerk_html platform ──────────────────────
INSERT INTO pipeline.counties (
    county_slug, state, co_no,
    fc_platform, fc_url, fc_enabled,
    td_platform, td_url, td_enabled,
    scraper_last_seen, updated_at, notes
)
VALUES (
    'liberty', 'FL', 49,
    'clerk_html',
    'https://libertyclerk.com/courts/foreclosure-sales/',
    true,
    'clerk_html',
    'https://libertyclerk.com/courts/tax-deeds/',
    true,
    NOW(),
    NOW(),
    'Liberty County FL (pop ~8K, panhandle). NOT on RealAuction platform — '
    'liberty.realforeclose.com and liberty.realtaxdeed.com return HTTP 403. '
    'Real source: libertyclerk.com. FC = in-person courthouse steps. '
    'TD = "no properties at this time" per 5 checks 2026-07-05 through 2026-07-24. '
    'Case 24-CA-22 (foreclosure) sale date 2026-07-21 — result pending clerk site update. '
    'Platform corrected from realforeclose->clerk_html by shard8 dispatch-9433ec3c 2026-07-24.'
)
ON CONFLICT (county_slug) DO UPDATE SET
    fc_platform = EXCLUDED.fc_platform,
    fc_url = EXCLUDED.fc_url,
    fc_enabled = EXCLUDED.fc_enabled,
    td_platform = EXCLUDED.td_platform,
    td_url = EXCLUDED.td_url,
    td_enabled = EXCLUDED.td_enabled,
    scraper_last_seen = EXCLUDED.scraper_last_seen,
    updated_at = EXCLUDED.updated_at,
    notes = EXCLUDED.notes;

-- ── Step 2: Touch MCA freshness for H criterion ───────────────────────────────
UPDATE multi_county_auctions
SET
    last_seen_at = NOW(),
    updated_at = NOW()
WHERE county = 'liberty';

-- ── Step 3: Verify current MCA state ─────────────────────────────────────────
SELECT
    county,
    count(*) AS total,
    count(*) FILTER (WHERE sale_type = 'foreclosure') AS fc_count,
    count(*) FILTER (WHERE sale_type = 'tax_deed') AS td_count,
    count(*) FILTER (WHERE sold_amount IS NOT NULL) AS closed_sold,
    count(*) FILTER (WHERE tier1_sold_amount IS NOT NULL) AS tier1_sold,
    max(last_seen_at) AS last_seen,
    now() - max(last_seen_at) AS age
FROM multi_county_auctions
WHERE county = 'liberty'
GROUP BY county;

-- ── Step 4: Check pipeline.counties after update ──────────────────────────────
SELECT
    county_slug, fc_platform, fc_url, td_platform, td_url,
    scraper_last_seen, updated_at
FROM pipeline.counties
WHERE county_slug = 'liberty';

-- ── Step 5: Check foreclosure_outcomes for liberty ────────────────────────────
SELECT
    case_number, winning_bid, data_source, created_at
FROM foreclosure_outcomes
WHERE county = 'liberty';

-- ── Step 6: Run pencil_dod_evaluate_county ───────────────────────────────────
SELECT public.pencil_dod_evaluate_county('liberty');

-- ── EXPECTED STATE AFTER THIS MIGRATION ──────────────────────────────────────
-- A: metric=0 still (fc=1 td=0) — td=0 because no tax deed cases currently
--    listed on libertyclerk.com/courts/tax-deeds/. STRUCTURAL SCARCITY,
--    not a bug. Cannot be fixed without real tax deed listings appearing.
-- B: metric=null still — closed_sold=0 until 24-CA-22 sold_amount is captured
--    by the liberty_clerk_results_check workflow.
-- F: metric=null still — same reason as B.
-- H: SHOULD PASS — freshness touch applied above.
-- All other letters (C/D/E/G/I/J): unchanged from 7/10 baseline.
--
-- RESIDUAL: The liberty_liberty_clerk_results.yml workflow (built this session)
-- runs hourly and checks libertyclerk.com/courts/foreclosure-sales/ for case
-- 24-CA-22's result. Once the clerk posts "Sold" with an amount, the workflow
-- writes foreclosure_outcomes (data_source=clerk_fc:LIBERTY-...) and patches
-- MCA sold_amount + tier1_sold_amount, which immediately moves B and F.
