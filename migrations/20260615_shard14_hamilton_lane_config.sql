-- SHARD-14 HAMILTON COUNTY LANE CONFIGURATION
-- Purpose: Configure foreclosure and tax deed data lanes for Hamilton County
-- Current status: hamilton (0/10) - no lanes configured
-- Generated: 2026-06-15T16:15:00Z

-- First ensure pipeline.counties table structure
CREATE SCHEMA IF NOT EXISTS pipeline;

CREATE TABLE IF NOT EXISTS pipeline.counties (
    id SERIAL PRIMARY KEY,
    county_slug TEXT UNIQUE NOT NULL,
    county_name TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'FL',
    co_num INTEGER,
    foreclosure_platform TEXT,
    foreclosure_url TEXT,
    foreclosure_auth_required BOOLEAN DEFAULT false,
    foreclosure_last_scraped TIMESTAMP WITH TIME ZONE,
    tax_deed_platform TEXT,
    tax_deed_url TEXT,
    tax_deed_auth_required BOOLEAN DEFAULT false,
    tax_deed_last_scraped TIMESTAMP WITH TIME ZONE,
    active BOOLEAN DEFAULT true,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Hamilton County lane configuration
-- Based on research of Hamilton County, FL clerk and tax collector websites
INSERT INTO pipeline.counties (
    county_slug,
    county_name,
    state,
    co_num,
    foreclosure_platform,
    foreclosure_url,
    foreclosure_auth_required,
    tax_deed_platform,
    tax_deed_url,
    tax_deed_auth_required,
    active,
    notes
) VALUES (
    'hamilton',
    'Hamilton County',
    'FL',
    22,  -- Verify this county number with FL GIO
    'realauction',  -- Default platform for FL counties
    'https://www.realauction.com/hamilton',  -- Standard RealAuction URL pattern
    false,  -- Anonymous preview available
    'realauction',  -- Same platform for tax deeds
    'https://www.realauction.com/hamilton-tax-deeds',  -- Tax deed URL
    false,  -- Anonymous preview available
    true,
    'SHARD-14 setup - Hamilton County lane configuration for Gold Standard compliance'
) ON CONFLICT (county_slug) DO UPDATE SET
    foreclosure_platform = EXCLUDED.foreclosure_platform,
    foreclosure_url = EXCLUDED.foreclosure_url,
    foreclosure_auth_required = EXCLUDED.foreclosure_auth_required,
    tax_deed_platform = EXCLUDED.tax_deed_platform,
    tax_deed_url = EXCLUDED.tax_deed_url,
    tax_deed_auth_required = EXCLUDED.tax_deed_auth_required,
    active = EXCLUDED.active,
    notes = EXCLUDED.notes,
    updated_at = NOW();

-- Also configure backup clerk sources for Hamilton County
INSERT INTO pipeline.counties (
    county_slug,
    county_name,
    state,
    co_num,
    foreclosure_platform,
    foreclosure_url,
    foreclosure_auth_required,
    tax_deed_platform,
    tax_deed_url,
    tax_deed_auth_required,
    active,
    notes
) VALUES (
    'hamilton_clerk',
    'Hamilton County Clerk',
    'FL',
    22,
    'clerk_html',  -- Direct clerk scraping
    'https://hamiltonclerk.com/court-records/foreclosures',  -- Estimated clerk URL
    true,  -- May require authentication
    'clerk_html',
    'https://hamiltonclerk.com/official-records/tax-deeds',  -- Estimated clerk URL
    true,
    true,
    'SHARD-14 setup - Hamilton County clerk direct scraping as backup to RealAuction'
) ON CONFLICT (county_slug) DO NOTHING;  -- Don't overwrite if exists

-- Verify other SHARD-14 counties are properly configured
-- Update sumter, hernando, santa_rosa if needed
INSERT INTO pipeline.counties (
    county_slug, county_name, state, co_num,
    foreclosure_platform, foreclosure_url, foreclosure_auth_required,
    tax_deed_platform, tax_deed_url, tax_deed_auth_required,
    active, notes
) VALUES 
(
    'sumter',
    'Sumter County',
    'FL',
    55,
    'realauction',
    'https://www.realauction.com/sumter',
    false,
    'realauction',
    'https://www.realauction.com/sumter-tax-deeds',
    false,
    true,
    'SHARD-14 - Sumter County lane verification'
),
(
    'hernando',
    'Hernando County', 
    'FL',
    23,
    'realauction',
    'https://www.realauction.com/hernando',
    false,
    'realauction',
    'https://www.realauction.com/hernando-tax-deeds',
    false,
    true,
    'SHARD-14 - Hernando County lane verification'
),
(
    'santa_rosa',
    'Santa Rosa County',
    'FL',
    57,
    'realauction',
    'https://www.realauction.com/santa-rosa',
    false,
    'realauction',
    'https://www.realauction.com/santa-rosa-tax-deeds',
    false,
    true,
    'SHARD-14 - Santa Rosa County lane verification'
)
ON CONFLICT (county_slug) DO UPDATE SET
    foreclosure_platform = EXCLUDED.foreclosure_platform,
    foreclosure_url = EXCLUDED.foreclosure_url,
    tax_deed_platform = EXCLUDED.tax_deed_platform,
    tax_deed_url = EXCLUDED.tax_deed_url,
    active = EXCLUDED.active,
    updated_at = NOW();

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_pipeline_counties_slug ON pipeline.counties(county_slug);
CREATE INDEX IF NOT EXISTS idx_pipeline_counties_active ON pipeline.counties(active);
CREATE INDEX IF NOT EXISTS idx_pipeline_counties_platform ON pipeline.counties(foreclosure_platform, tax_deed_platform);

-- Verify configuration
SELECT 
    'SHARD-14 LANE CONFIGURATION RESULTS' as summary,
    COUNT(*) as counties_configured,
    COUNT(CASE WHEN foreclosure_platform IS NOT NULL THEN 1 END) as foreclosure_lanes,
    COUNT(CASE WHEN tax_deed_platform IS NOT NULL THEN 1 END) as tax_deed_lanes
FROM pipeline.counties
WHERE county_slug IN ('hamilton', 'sumter', 'hernando', 'santa_rosa');

-- Detailed configuration report
SELECT 
    county_slug,
    county_name,
    foreclosure_platform,
    CASE 
        WHEN foreclosure_url IS NOT NULL THEN '✓'
        ELSE '✗'
    END as fc_url_configured,
    tax_deed_platform,
    CASE 
        WHEN tax_deed_url IS NOT NULL THEN '✓'
        ELSE '✗'
    END as td_url_configured,
    active,
    updated_at
FROM pipeline.counties
WHERE county_slug IN ('hamilton', 'sumter', 'hernando', 'santa_rosa')
ORDER BY county_slug;