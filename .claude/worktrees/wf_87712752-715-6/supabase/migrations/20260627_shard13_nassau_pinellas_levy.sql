-- SHARD-13 Run 1113 Supplementary Migration
-- Dispatch ID: c67ed2ca-7139-40b5-a2a1-98c98fe2fe6e
-- Counties: nassau, pinellas, levy
-- Date: 2026-06-27
--
-- Idempotent: uses ON CONFLICT DO NOTHING and IF NOT EXISTS patterns.
-- Companion to 20260627_shard13_run1113_nassau_pinellas_levy.sql
-- (which covers levy TaxSmart data, zoning, and FC bootstrap).
-- This file covers: pipeline_counties config, ultraloop audit rows.

-- ============================================================
-- 1. LEVY: pipeline_counties configuration
-- ============================================================
-- Ensure levy is configured for evaluator/Sentinel/Gold Standard.
-- FC is dead (clerk_inperson — courthouse sales, no digital feed).
-- TaxSmart is the only viable TD source.

INSERT INTO pipeline_counties
    (county_slug, td_platform, fc_platform, active, wiring_complete, notes, updated_at)
VALUES (
    'levy',
    'taxsmart_levyclerk_com',
    'levyclerk_com_fc',
    true,
    true,
    'TD: TaxSmart (online.levyclerk.com/TaxSmartWeb). FC: levyclerk.com foreclosure page (currently no active sales — courthouse only). Scraper: scripts/levy_taxsmart_scraper.py wired 2026-06-27 shard13-run1113.',
    NOW()
)
ON CONFLICT (county_slug) DO UPDATE SET
    td_platform     = EXCLUDED.td_platform,
    fc_platform     = EXCLUDED.fc_platform,
    active          = true,
    wiring_complete = true,
    notes           = EXCLUDED.notes,
    updated_at      = NOW();

-- ============================================================
-- 2. ULTRALOOP AUDIT: gold_standard_ultraloop_audit rows
-- ============================================================
-- Inserted live during session via REST API (IDs 1826, 1827, 1828).
-- This SQL is idempotent via ON CONFLICT DO NOTHING in case
-- the dispatch_id + county_slug + letter combination has a unique index.

INSERT INTO gold_standard_ultraloop_audit
    (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived, created_at)
VALUES
    (
        'c67ed2ca-7139-40b5-a2a1-98c98fe2fe6e',
        'native',
        'nassau',
        'J',
        'nassau 10/10 verified — C/D fixed in this session, all 27 auctions passing all 10 criteria (A through J)',
        '{"score": 10, "auctions_total": 27, "previously_failing": ["C","D"]}',
        true,
        NOW()
    ),
    (
        'c67ed2ca-7139-40b5-a2a1-98c98fe2fe6e',
        'native',
        'pinellas',
        'B',
        'B=1666.7% anomaly - evaluator passes but outside 95-105% band. verified=50 vs closed_sold=3. GHOST-PASS: enforcement_status=UNTESTED.',
        '{"anomaly": "B>105%", "ratio": 1666.7, "verified_outcomes": 50, "closed_sold": 3, "enforcement_status": "UNTESTED"}',
        false,
        NOW()
    ),
    (
        'c67ed2ca-7139-40b5-a2a1-98c98fe2fe6e',
        'native',
        'levy',
        'A',
        'levy A metric after FC/TD insert: fc=3 td=29, auctions_total=32',
        '{"fc": 3, "td": 29, "auctions_total": 32}',
        true,
        NOW()
    )
ON CONFLICT DO NOTHING;

-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================
-- SELECT county_slug, letter, survived FROM gold_standard_ultraloop_audit
--   WHERE dispatch_id = 'c67ed2ca-7139-40b5-a2a1-98c98fe2fe6e'
--   ORDER BY county_slug, letter;
-- Expected: 3 rows (nassau/J, pinellas/B, levy/A)
--
-- SELECT county, COUNT(*) FROM multi_county_auctions
--   WHERE county IN ('nassau','pinellas','levy') GROUP BY county;
-- Expected: nassau=27, pinellas=364, levy=32
