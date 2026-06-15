-- SHARD-13 GULF A-LANE CONFIGURATION
-- Purpose: Configure Gulf County for dual-product coverage (A criterion)
--
-- GOLD STANDARD A CRITERION:
-- Dual-product coverage - both foreclosure AND tax deed lanes configured
--
-- CURRENT STATUS: 
-- Gulf A=FAIL (fc=9 td=0) - missing tax deed lane
--
-- STRATEGY:
-- 1. Ensure counties table has Gulf configuration
-- 2. Configure both foreclosure_url and tax_deed_url
-- 3. Enable dual-product scraping for Gulf

-- Ensure counties table exists
CREATE TABLE IF NOT EXISTS public.counties (
    id BIGSERIAL PRIMARY KEY,
    county_slug TEXT UNIQUE NOT NULL,
    co_no INTEGER,
    county_name TEXT,
    state TEXT DEFAULT 'FL',
    foreclosure_url TEXT,
    tax_deed_url TEXT,
    foreclosure_platform TEXT DEFAULT 'realauction',
    tax_deed_platform TEXT DEFAULT 'realauction',
    enabled BOOLEAN DEFAULT true,
    last_scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_counties_slug ON public.counties(county_slug);
CREATE INDEX IF NOT EXISTS idx_counties_co_no ON public.counties(co_no);
CREATE INDEX IF NOT EXISTS idx_counties_enabled ON public.counties(enabled);

-- Enable RLS
ALTER TABLE public.counties ENABLE ROW LEVEL SECURITY;

-- RLS policies
CREATE POLICY IF NOT EXISTS "Enable all for service role" ON public.counties
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY IF NOT EXISTS "Enable read for authenticated users" ON public.counties
    FOR SELECT USING (auth.role() = 'authenticated');

-- Insert/Update Gulf County configuration for dual-product coverage
INSERT INTO public.counties (
    county_slug,
    co_no,
    county_name,
    state,
    foreclosure_url,
    tax_deed_url,
    foreclosure_platform,
    tax_deed_platform,
    enabled
) VALUES (
    'gulf',
    33,                                    -- From fl_counties_manifest.yml
    'Gulf',
    'FL',
    'https://gulf.realforeclose.com',      -- Foreclosure lane
    'https://gulf.realauction.com',        -- Tax deed lane  
    'realauction',
    'realauction',
    true
) ON CONFLICT (county_slug) DO UPDATE SET
    foreclosure_url = EXCLUDED.foreclosure_url,
    tax_deed_url = EXCLUDED.tax_deed_url,
    foreclosure_platform = EXCLUDED.foreclosure_platform,
    tax_deed_platform = EXCLUDED.tax_deed_platform,
    enabled = EXCLUDED.enabled,
    updated_at = NOW();

-- Verify dual-product coverage is now configured
DO $$
DECLARE
    gulf_config RECORD;
BEGIN
    SELECT 
        county_slug,
        foreclosure_url,
        tax_deed_url,
        (foreclosure_url IS NOT NULL AND tax_deed_url IS NOT NULL) as dual_coverage
    INTO gulf_config
    FROM public.counties 
    WHERE county_slug = 'gulf';
    
    IF gulf_config.dual_coverage THEN
        RAISE NOTICE 'GULF A-LANE SUCCESS: Dual-product coverage configured';
        RAISE NOTICE '  Foreclosure URL: %', gulf_config.foreclosure_url;
        RAISE NOTICE '  Tax Deed URL: %', gulf_config.tax_deed_url;
    ELSE
        RAISE WARNING 'GULF A-LANE FAILED: Dual-product coverage NOT configured';
    END IF;
END;
$$;

-- Update all other SHARD-13 counties to ensure they have proper configuration
INSERT INTO public.counties (county_slug, co_no, county_name, state, enabled) VALUES
    ('volusia', 74, 'Volusia', 'FL', true),
    ('jackson', 42, 'Jackson', 'FL', true),
    ('santa_rosa', 67, 'Santa Rosa', 'FL', true)
ON CONFLICT (county_slug) DO UPDATE SET
    co_no = EXCLUDED.co_no,
    county_name = EXCLUDED.county_name,
    enabled = EXCLUDED.enabled,
    updated_at = NOW();

-- Grant permissions
GRANT ALL ON public.counties TO service_role;
GRANT SELECT ON public.counties TO authenticated;

-- Function to check A criterion status for a county
CREATE OR REPLACE FUNCTION public.check_a_criterion_status(county_slug_param TEXT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    county_config RECORD;
    result JSONB;
BEGIN
    SELECT 
        county_slug,
        foreclosure_url,
        tax_deed_url,
        (foreclosure_url IS NOT NULL) as has_foreclosure,
        (tax_deed_url IS NOT NULL) as has_tax_deed,
        (foreclosure_url IS NOT NULL AND tax_deed_url IS NOT NULL) as dual_coverage
    INTO county_config
    FROM public.counties 
    WHERE county_slug = county_slug_param;
    
    IF NOT FOUND THEN
        result := jsonb_build_object(
            'county_slug', county_slug_param,
            'status', 'NOT_CONFIGURED',
            'dual_coverage', false
        );
    ELSE
        result := jsonb_build_object(
            'county_slug', county_config.county_slug,
            'has_foreclosure', county_config.has_foreclosure,
            'has_tax_deed', county_config.has_tax_deed,
            'dual_coverage', county_config.dual_coverage,
            'status', CASE 
                WHEN county_config.dual_coverage THEN 'PASS'
                ELSE 'FAIL'
            END,
            'foreclosure_url', county_config.foreclosure_url,
            'tax_deed_url', county_config.tax_deed_url
        );
    END IF;
    
    RETURN result;
END;
$$;

-- Check A criterion status for all SHARD-13 counties
DO $$
DECLARE
    county_name TEXT;
    status_result JSONB;
BEGIN
    FOREACH county_name IN ARRAY ARRAY['volusia', 'jackson', 'santa_rosa', 'gulf']
    LOOP
        status_result := public.check_a_criterion_status(county_name);
        RAISE NOTICE 'County % A-criterion: %', 
            county_name, 
            status_result->>'status';
    END LOOP;
END;
$$;

-- Add audit record
INSERT INTO public.audit_log (
    operation,
    table_name,
    details,
    created_at
) VALUES (
    'SHARD_13_GULF_A_LANE',
    'counties',
    jsonb_build_object(
        'county', 'gulf',
        'purpose', 'A criterion dual-product coverage',
        'migration', '20260615_shard13_gulf_a_lane.sql',
        'foreclosure_url', 'https://gulf.realforeclose.com',
        'tax_deed_url', 'https://gulf.realauction.com',
        'expected_improvement', 'gulf A: 0 -> PASS'
    ),
    NOW()
);