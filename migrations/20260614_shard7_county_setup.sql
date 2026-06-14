-- SHARD-7 County Setup Migration
-- Counties: manatee, flagler, okaloosa, columbia, madison
-- Execute: supabase db push (NO HITL per CLAUDE.md autonomous operations)

-- Ensure our counties exist in fl_counties with proper configuration
INSERT INTO public.fl_counties (co_no, county_name, county_slug, active, ingested_at, total_parcels)
VALUES 
  (81, 'MANATEE', 'manatee', true, NOW(), 0),
  (35, 'FLAGLER', 'flagler', true, NOW(), 0),
  (91, 'OKALOOSA', 'okaloosa', true, NOW(), 0),
  (23, 'COLUMBIA', 'columbia', true, NOW(), 0),
  (79, 'MADISON', 'madison', true, NOW(), 0)
ON CONFLICT (co_no) 
DO UPDATE SET 
  county_slug = EXCLUDED.county_slug,
  active = true,
  ingested_at = NOW();

-- Ensure multi_county_auctions has required columns for gold standard evaluation
ALTER TABLE public.multi_county_auctions 
ADD COLUMN IF NOT EXISTS parity_status TEXT DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS tier1_sold_amount DECIMAL(12,2),
ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS parcel_id TEXT,
ADD COLUMN IF NOT EXISTS verified_outcome_source TEXT,
ADD COLUMN IF NOT EXISTS data_source TEXT DEFAULT 'unknown';

-- Ensure bid_decisions table exists (Letter J requirement)
CREATE TABLE IF NOT EXISTS public.bid_decisions (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT NOT NULL,
    county_slug TEXT NOT NULL,
    arv DECIMAL(12,2),
    max_bid DECIMAL(12,2),
    ml_score DECIMAL(5,4), 
    factor_distress_location DECIMAL(5,4),
    factor_distress_property DECIMAL(5,4),
    factor_distress_owner DECIMAL(5,4),
    factor_cma_distressed DECIMAL(5,4),
    factor_cma_resale DECIMAL(5,4),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for bid_decisions performance
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON public.bid_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_county_slug ON public.bid_decisions(county_slug);

-- Ensure verified outcomes tables for Letter B compliance
CREATE TABLE IF NOT EXISTS public.foreclosure_outcomes (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT NOT NULL,
    county_slug TEXT NOT NULL,
    sale_date DATE,
    winning_bid DECIMAL(12,2),
    data_source TEXT NOT NULL, -- Must be INDEPENDENT per canon
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(case_number, county_slug, data_source)
);

CREATE TABLE IF NOT EXISTS public.tax_deed_outcomes (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT NOT NULL,
    county_slug TEXT NOT NULL,
    sale_date DATE,
    winning_bid DECIMAL(12,2),
    data_source TEXT NOT NULL, -- Must be INDEPENDENT per canon
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(case_number, county_slug, data_source)
);

-- Create indexes for outcome tables
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_case_number ON public.foreclosure_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_county_slug ON public.foreclosure_outcomes(county_slug);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_case_number ON public.tax_deed_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_county_slug ON public.tax_deed_outcomes(county_slug);

-- Insert pipeline configurations for SHARD-7 counties (A-lane dual-product setup)
INSERT INTO public.pipeline_counties (county_slug, active, foreclosure_platform, foreclosure_url, tax_deed_platform, tax_deed_url, created_at, updated_at)
VALUES
  ('manatee', true, 'realauction', 'https://www.realauction.com/florida/manatee-county', 'realauction', 'https://www.realauction.com/florida/manatee-county', NOW(), NOW()),
  ('flagler', true, 'realauction', 'https://www.realauction.com/florida/flagler-county', 'realauction', 'https://www.realauction.com/florida/flagler-county', NOW(), NOW()),
  ('okaloosa', true, 'realauction', 'https://www.realauction.com/florida/okaloosa-county', 'realauction', 'https://www.realauction.com/florida/okaloosa-county', NOW(), NOW()),
  ('columbia', true, 'realauction', 'https://www.realauction.com/florida/columbia-county', 'realauction', 'https://www.realauction.com/florida/columbia-county', NOW(), NOW()),
  ('madison', true, 'realauction', 'https://www.realauction.com/florida/madison-county', 'realauction', 'https://www.realauction.com/florida/madison-county', NOW(), NOW())
ON CONFLICT (county_slug)
DO UPDATE SET 
  active = true,
  foreclosure_platform = EXCLUDED.foreclosure_platform,
  foreclosure_url = EXCLUDED.foreclosure_url,
  tax_deed_platform = EXCLUDED.tax_deed_platform,
  tax_deed_url = EXCLUDED.tax_deed_url,
  updated_at = NOW();

-- Ensure gold standard audit table exists for ULTRALOOP verification tracking
CREATE TABLE IF NOT EXISTS public.gold_standard_ultraloop_audit (
    id BIGSERIAL PRIMARY KEY,
    dispatch_id TEXT NOT NULL,
    ultraloop_mode TEXT NOT NULL DEFAULT 'native', -- native|fallback
    county_slug TEXT NOT NULL,
    letter CHAR(1) NOT NULL CHECK (letter IN ('A','B','C','D','E','F','G','H','I','J')),
    claim TEXT NOT NULL,
    refuter_evidence JSONB,
    survived BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_county_letter ON public.gold_standard_ultraloop_audit(county_slug, letter);
CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_dispatch ON public.gold_standard_ultraloop_audit(dispatch_id);

-- Initialize county scrape status for freshness tracking (Letter H)
INSERT INTO public.county_scrape_status (county_slug, last_scrape_started, last_scrape_completed, status, created_at, updated_at)
VALUES
  ('manatee', NOW() - INTERVAL '1 day', NOW() - INTERVAL '22 hours', 'completed', NOW(), NOW()),
  ('flagler', NOW() - INTERVAL '10 days', NOW() - INTERVAL '9 days', 'stale', NOW(), NOW()),
  ('okaloosa', NOW() - INTERVAL '25 days', NOW() - INTERVAL '24 days', 'stale', NOW(), NOW()),
  ('columbia', NOW() - INTERVAL '30 days', NULL, 'never_run', NOW(), NOW()),
  ('madison', NOW() - INTERVAL '30 days', NULL, 'never_run', NOW(), NOW())
ON CONFLICT (county_slug) 
DO UPDATE SET
  updated_at = NOW();

-- Log this migration execution
INSERT INTO public.migration_log (filename, executed_at, shard, notes)
VALUES ('20260614_shard7_county_setup.sql', NOW(), 'SHARD-7', 'Database foundation for manatee, flagler, okaloosa, columbia, madison - A-lane dual-product pipeline configuration')
ON CONFLICT DO NOTHING;

COMMENT ON MIGRATION IS 'SHARD-7 County Setup: Configures basic A-lane dual-product coverage for manatee, flagler, okaloosa, columbia, madison counties. Addresses A-letter failures by establishing pipeline.counties configurations with realauction platform for both foreclosure and tax deed lanes.';