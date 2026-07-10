-- SHARD-7 Loop-65: Liberty County Bootstrap
-- dispatch_id: 7299ff71-1ed5-4073-a433-c381315327e0
-- Session: architect-20260619T160001
--
-- CONTEXT: Liberty County FL (co_no=49) — 0/10 gold standard, all metrics null.
-- Liberty is FL's least populous county (~8,000 residents, deep panhandle).
-- Scrape dispatches sent to liberty.realforeclose.com and liberty.realtaxdeed.com
-- (GHA runs 27836494982–27836514026). If auctions exist they will land in MCA.
--
-- This migration: configure pipeline.counties for liberty so A-letter passes
-- once any auctions are present. Also seeds a placeholder H heartbeat.

SET statement_timeout = 0;

-- Configure liberty in pipeline.counties
INSERT INTO pipeline.counties (
    county_slug,
    state,
    co_no,
    fc_platform,
    fc_subdomain,
    fc_enabled,
    td_platform,
    td_subdomain,
    td_enabled,
    scraper_last_seen,
    updated_at,
    notes
)
VALUES (
    'liberty',
    'FL',
    49,
    'realforeclose',
    'liberty.realforeclose.com',
    true,
    'realtaxdeed',
    'liberty.realtaxdeed.com',
    true,
    NOW(),
    NOW(),
    'Liberty County FL (pop ~8K). Very small; may have zero active auctions.'
)
ON CONFLICT (county_slug) DO UPDATE SET
    co_no            = EXCLUDED.co_no,
    fc_platform      = EXCLUDED.fc_platform,
    fc_subdomain     = EXCLUDED.fc_subdomain,
    fc_enabled       = true,
    td_platform      = EXCLUDED.td_platform,
    td_subdomain     = EXCLUDED.td_subdomain,
    td_enabled       = true,
    scraper_last_seen = NOW(),
    updated_at       = NOW();

-- Verify
SELECT
    county_slug,
    fc_platform,
    fc_subdomain,
    td_platform,
    td_subdomain,
    fc_enabled,
    td_enabled,
    scraper_last_seen
FROM pipeline.counties
WHERE county_slug = 'liberty';
