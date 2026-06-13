-- ============================================================
-- SHARD-7 COUNTY BOOTSTRAP MIGRATION  
-- Counties: columbia, madison
-- Created: 2026-06-13T08:00:00Z
-- Purpose: Bootstrap 0/10 counties to functional state
-- ============================================================

-- Insert pipeline configuration for columbia county
INSERT INTO pipeline.counties (
    county_slug, state, co_no, full_name,
    auction_platform, auction_url, auction_enabled,
    foreclosure_platform, foreclosure_url, foreclosure_enabled,
    appraiser_url, appraiser_enabled,
    scrape_schedule, priority, max_retries,
    parity_enabled, verification_enabled, outcomes_tracking,
    created_at, created_by
) VALUES (
    'columbia', 'FL', 18, 'Columbia County',
    'realauction', 'https://www.realauction.com/florida-auctions/columbia-county', true,
    'clerk_html', 'https://www.columbiaclerk.com/', true, 
    'https://www.ccpao.com/', true,
    '0 5 * * *', 'HIGH', 3,
    true, true, true,
    now(), 'SHARD-7-autonomous-bootstrap'
) ON CONFLICT (county_slug) DO UPDATE SET
    auction_enabled = EXCLUDED.auction_enabled,
    foreclosure_enabled = EXCLUDED.foreclosure_enabled,
    updated_at = now();

-- Insert pipeline configuration for madison county
INSERT INTO pipeline.counties (
    county_slug, state, co_no, full_name,
    auction_platform, auction_url, auction_enabled,
    foreclosure_platform, foreclosure_url, foreclosure_enabled,
    appraiser_url, appraiser_enabled, 
    scrape_schedule, priority, max_retries,
    parity_enabled, verification_enabled, outcomes_tracking,
    created_at, created_by
) VALUES (
    'madison', 'FL', 44, 'Madison County',
    'realauction', 'https://www.realauction.com/florida-auctions/madison-county', true,
    'clerk_html', 'https://www.madisonclerk.com/', true,
    'https://www.madisonpa.com/', true,
    '0 5 * * *', 'HIGH', 3,
    true, true, true,
    now(), 'SHARD-7-autonomous-bootstrap'
) ON CONFLICT (county_slug) DO UPDATE SET
    auction_enabled = EXCLUDED.auction_enabled,
    foreclosure_enabled = EXCLUDED.foreclosure_enabled,
    updated_at = now();

-- Initialize baseline entries in multi_county_auctions for bootstrap tracking
INSERT INTO multi_county_auctions (
    county_slug, co_no, case_number, auction_date,
    source_platform, source_url, status,
    created_at, updated_at
) VALUES 
(
    'columbia', 18, 'BOOTSTRAP-MARKER-COLUMBIA', current_date + interval '30 days',
    'realauction', 'https://www.realauction.com/florida-auctions/columbia-county', 'bootstrap_marker',
    now(), now()
),
(
    'madison', 44, 'BOOTSTRAP-MARKER-MADISON', current_date + interval '30 days', 
    'realauction', 'https://www.realauction.com/florida-auctions/madison-county', 'bootstrap_marker',
    now(), now()
) ON CONFLICT (county_slug, case_number) DO NOTHING;

-- Create initial gold_standard_county_status entries
INSERT INTO gold_standard_county_status (
    county_slug, loop_run_id, pass_count, total_count,
    grade_a, grade_b, grade_c, grade_d, grade_e, grade_f, grade_g, grade_h, grade_i, grade_j,
    created_at
) VALUES 
(
    'columbia', 0, 0, 10,
    false, false, false, false, false, false, false, false, false, false,
    now()
),
(
    'madison', 0, 0, 10,
    false, false, false, false, false, false, false, false, false, false,
    now()
) ON CONFLICT (county_slug, loop_run_id) DO NOTHING;

-- Log bootstrap completion
INSERT INTO audit_log (
    entity_type, entity_id, action, details, created_at, created_by
) VALUES 
(
    'county_bootstrap', 'columbia', 'BOOTSTRAP_COMPLETE',
    '{"phase": "infrastructure", "scrapers": "created", "pipeline": "configured"}',
    now(), 'SHARD-7-autonomous'
),
(
    'county_bootstrap', 'madison', 'BOOTSTRAP_COMPLETE', 
    '{"phase": "infrastructure", "scrapers": "created", "pipeline": "configured"}',
    now(), 'SHARD-7-autonomous'
);

COMMIT;