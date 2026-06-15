-- SHARD-8 A-LANE CONFIGURATION - Generated at 2026-06-15T16:12:00Z
-- Purpose: Configure pipeline.counties for desoto and monroe
-- Target: Enable dual-product coverage (A-lane)

-- SHARD-8 A-LANE SETUP: Configure desoto and monroe counties
-- Target: Enable A-lane (dual-product coverage) for both counties
-- Current: desoto A=null, monroe A=null (0 auctions)

SET statement_timeout = 0;

-- Insert or update DeSoto County configuration
INSERT INTO pipeline.counties (
    county_slug,
    county_name,
    state,
    co_no,
    foreclosure_platform,
    foreclosure_url,
    tax_deed_platform,
    tax_deed_url,
    appraiser_url,
    clerk_url,
    foreclosure_frequency,
    tax_deed_frequency,
    timezone,
    status,
    notes,
    priority,
    created_at,
    updated_at
) VALUES (
    'desoto',
    'DeSoto County',
    'FL',
    22,
    'realauction',
    'https://desoto.realforeclose.com',
    'realauction', 
    'https://desoto.realforeclose.com',
    'https://www.desotocountyfl.gov/departments/property-appraiser',
    'https://www.desotoclerk.com',
    'weekly',
    'monthly',
    'America/New_York',
    'configured',
    'SHARD-8: Rural agricultural county, configured for dual-product coverage',
    'medium',
    NOW(),
    NOW()
)
ON CONFLICT (county_slug) DO UPDATE SET
    county_name = EXCLUDED.county_name,
    co_no = EXCLUDED.co_no,
    foreclosure_platform = EXCLUDED.foreclosure_platform,
    foreclosure_url = EXCLUDED.foreclosure_url,
    tax_deed_platform = EXCLUDED.tax_deed_platform,
    tax_deed_url = EXCLUDED.tax_deed_url,
    appraiser_url = EXCLUDED.appraiser_url,
    clerk_url = EXCLUDED.clerk_url,
    foreclosure_frequency = EXCLUDED.foreclosure_frequency,
    tax_deed_frequency = EXCLUDED.tax_deed_frequency,
    status = 'configured',
    notes = EXCLUDED.notes,
    priority = EXCLUDED.priority,
    updated_at = NOW();

-- Insert or update Monroe County configuration  
INSERT INTO pipeline.counties (
    county_slug,
    county_name,
    state,
    co_no,
    foreclosure_platform,
    foreclosure_url,
    tax_deed_platform,
    tax_deed_url,
    appraiser_url,
    clerk_url,
    foreclosure_frequency,
    tax_deed_frequency,
    timezone,
    status,
    notes,
    priority,
    created_at,
    updated_at
) VALUES (
    'monroe',
    'Monroe County',
    'FL',
    52,
    'realauction',
    'https://monroe.realforeclose.com',
    'realauction',
    'https://monroe.realforeclose.com', 
    'https://www.monroecounty-fl.gov/departments/property_appraiser',
    'https://www.clerk-of-the-court.com',
    'weekly',
    'monthly',
    'America/New_York',
    'configured',
    'SHARD-8: Florida Keys high-value market, configured for dual-product coverage',
    'high',
    NOW(),
    NOW()
)
ON CONFLICT (county_slug) DO UPDATE SET
    county_name = EXCLUDED.county_name,
    co_no = EXCLUDED.co_no,
    foreclosure_platform = EXCLUDED.foreclosure_platform,
    foreclosure_url = EXCLUDED.foreclosure_url,
    tax_deed_platform = EXCLUDED.tax_deed_platform,
    tax_deed_url = EXCLUDED.tax_deed_url,
    appraiser_url = EXCLUDED.appraiser_url,
    clerk_url = EXCLUDED.clerk_url,
    foreclosure_frequency = EXCLUDED.foreclosure_frequency,
    tax_deed_frequency = EXCLUDED.tax_deed_frequency,
    status = 'configured',
    notes = EXCLUDED.notes,
    priority = EXCLUDED.priority,
    updated_at = NOW();

-- Verify the configurations
SELECT 
    'SHARD-8 A-LANE VERIFICATION' as check_type,
    county_slug,
    county_name,
    foreclosure_platform,
    tax_deed_platform,
    status,
    priority,
    updated_at
FROM pipeline.counties
WHERE county_slug IN ('desoto', 'monroe')
ORDER BY county_slug;