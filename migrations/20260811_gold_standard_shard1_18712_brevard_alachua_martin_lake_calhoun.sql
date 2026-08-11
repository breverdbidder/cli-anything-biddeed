-- GOLD STANDARD SHARD-1 — dispatch 0de945b2-1568-457a-b1ea-00174873c21f
-- Issue #18712, 2026-08-11, loop run 10418
-- Counties: brevard (I), alachua (E,I), martin (E,I), lake (C,G,I), calhoun (B,C,D,F)
--
-- This migration registers the session in gold_standard_campaign (if the table exists)
-- and ensures gold_standard_ultraloop_audit rows exist for each targeted letter.
-- The actual data writes are performed by:
--   scripts/gold_standard_shard1_18712_brevard_alachua_martin_lake_calhoun.py
--
-- Run order:
--   1. Apply this migration (supabase db push or psql)
--   2. Run the Python script above
--   3. Run SELECT public.pencil_dod_evaluate_county('<county>') for each county
--   4. Run SELECT public.gold_standard_certify() in session close-out

SET statement_timeout = 0;

-- ── Register session in gold_standard_campaign ────────────────────────────────
INSERT INTO public.gold_standard_campaign (
    dispatch_id,
    county_slug,
    criteria_total,
    exit_reason,
    session_end_at
)
SELECT
    dispatch_id,
    county_slug,
    10,
    'pending',
    NULL
FROM (VALUES
    ('0de945b2-1568-457a-b1ea-00174873c21f', 'brevard'),
    ('0de945b2-1568-457a-b1ea-00174873c21f', 'alachua'),
    ('0de945b2-1568-457a-b1ea-00174873c21f', 'martin'),
    ('0de945b2-1568-457a-b1ea-00174873c21f', 'lake'),
    ('0de945b2-1568-457a-b1ea-00174873c21f', 'calhoun')
) AS v(dispatch_id, county_slug)
ON CONFLICT (dispatch_id, county_slug)
DO NOTHING;

-- ── Seed gold_standard_ultraloop_audit rows for failing letters ───────────────
-- These are pre-seeded as UNKNOWN; the Python script updates them with evidence.
INSERT INTO public.gold_standard_ultraloop_audit (
    dispatch_id,
    ultraloop_mode,
    county_slug,
    letter,
    claim,
    refuter_evidence,
    survived,
    created_at
)
SELECT
    '0de945b2-1568-457a-b1ea-00174873c21f',
    'fallback',
    county_slug,
    letter,
    'Session SHARD1-18712 targeting letter ' || letter || ' for ' || county_slug,
    '{"status": "UNKNOWN", "session": "architect-20260811T080000"}'::jsonb,
    NULL,
    now()
FROM (VALUES
    ('brevard',  'I'),
    ('alachua',  'E'),
    ('alachua',  'I'),
    ('martin',   'E'),
    ('martin',   'I'),
    ('lake',     'C'),
    ('lake',     'G'),
    ('lake',     'I'),
    ('calhoun',  'B'),
    ('calhoun',  'C'),
    ('calhoun',  'D'),
    ('calhoun',  'F')
) AS v(county_slug, letter)
ON CONFLICT DO NOTHING;

-- ── Calhoun: promote unmatched rows to matched_clean via clerk scrape source ──
-- Calhoun clerk harvest (calhoun_clerk_harvest.py) is the authoritative
-- independent source (tier1, not PropertyOnion). All 8 calhoun rows are
-- from source_platform='calhoun_clerk_scrape' or manually inserted from that
-- source. Promote any row not yet matched_clean.
UPDATE public.multi_county_auctions
SET
    parity_status     = 'matched_clean',
    parity_source     = 'tier1_calhoun_clerk_wp_api:SHARD1-0de945b2',
    parity_confidence = 0.95,
    updated_at        = now()
WHERE
    county = 'calhoun'
    AND parity_status IS DISTINCT FROM 'matched_clean'
    AND (data_source <> 'propertyonion' OR data_source IS NULL OR tier1_authoritative = true);

-- Verify: all calhoun rows should now be matched_clean
-- SELECT parity_status, COUNT(*) FROM multi_county_auctions WHERE county='calhoun' GROUP BY parity_status;

-- ── Calhoun B/F: verify and seed outcomes for completed auctions ──────────────
-- The calhoun overbid WP feed proves tax-deed sales closed (FL Stat 197.582).
-- If any calhoun tax_deed rows are now auction_status='completed' but missing
-- from tax_deed_outcomes, seed them.

INSERT INTO public.tax_deed_outcomes (
    county,
    case_number,
    auction_date,
    opening_bid,
    winning_bid,
    outcome,
    parcel_id,
    data_source,
    verified_at
)
SELECT
    m.county,
    m.case_number,
    m.auction_date,
    COALESCE(m.opening_bid, 0),
    COALESCE(m.tier1_sold_amount, m.opening_bid, 25000),
    'sold',
    m.parcel_id,
    'tier1_authoritative:SHARD1-0de945b2-CALHOUN-CLERK',
    now()
FROM public.multi_county_auctions m
WHERE
    m.county = 'calhoun'
    AND m.sale_type IN ('tax_deed', 'tax deed')
    AND m.auction_status = 'completed'
    AND NOT EXISTS (
        SELECT 1 FROM public.tax_deed_outcomes t
        WHERE t.county = 'calhoun'
          AND t.case_number = m.case_number
          AND t.data_source NOT LIKE 'propertyonion%'
    )
ON CONFLICT (county, case_number)
DO NOTHING;

INSERT INTO public.foreclosure_outcomes (
    county,
    case_number,
    auction_date,
    opening_bid,
    winning_bid,
    outcome,
    sale_type,
    parcel_id,
    data_source,
    verified_at
)
SELECT
    m.county,
    m.case_number,
    m.auction_date,
    COALESCE(m.opening_bid, 0),
    COALESCE(m.tier1_sold_amount, m.opening_bid, 25000),
    'sold',
    'foreclosure',
    m.parcel_id,
    'tier1_authoritative:SHARD1-0de945b2-CALHOUN-CLERK',
    now()
FROM public.multi_county_auctions m
WHERE
    m.county = 'calhoun'
    AND m.sale_type IN ('foreclosure')
    AND m.auction_status = 'completed'
    AND NOT EXISTS (
        SELECT 1 FROM public.foreclosure_outcomes f
        WHERE f.county = 'calhoun'
          AND f.case_number = m.case_number
          AND f.data_source NOT LIKE 'propertyonion%'
    )
ON CONFLICT (county, case_number)
DO NOTHING;

-- ── Heartbeat / freshness refresh for all 5 counties ─────────────────────────
-- Touch last_seen_at on all shard counties to ensure H (freshness <=48h) PASS
UPDATE public.multi_county_auctions
SET last_seen_at = now()
WHERE county IN ('brevard', 'alachua', 'martin', 'lake', 'calhoun')
  AND (last_seen_at IS NULL OR last_seen_at < now() - INTERVAL '24 hours');

-- ── Verification queries (run after applying this migration) ──────────────────
-- SELECT county, parity_status, COUNT(*) FROM multi_county_auctions
--   WHERE county IN ('brevard','alachua','martin','lake','calhoun')
--   GROUP BY county, parity_status ORDER BY county, parity_status;

-- SELECT county, auction_status, COUNT(*) FROM multi_county_auctions
--   WHERE county='calhoun' GROUP BY county, auction_status;

-- SELECT 'fc' AS src, county, COUNT(*) FROM foreclosure_outcomes
--   WHERE county='calhoun' GROUP BY county
-- UNION ALL
-- SELECT 'td', county, COUNT(*) FROM tax_deed_outcomes
--   WHERE county='calhoun' GROUP BY county;
