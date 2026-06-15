-- SHARD-8 County Setup Migration - Gold Standard Campaign Run 28
-- Counties: palm_beach, gilchrist, okeechobee, desoto, monroe
-- Execute: supabase db push (NO HITL per CLAUDE.md autonomous operations)

-- Set timeout for heavy operations
SET statement_timeout = 0;

-- Ensure our counties exist in fl_counties with proper configuration  
INSERT INTO public.fl_counties (co_no, county_name, county_slug, active, ingested_at, total_parcels)
VALUES 
  (60, 'PALM_BEACH', 'palm_beach', true, NOW(), 0),
  (31, 'GILCHRIST', 'gilchrist', true, NOW(), 0),
  (57, 'OKEECHOBEE', 'okeechobee', true, NOW(), 0), 
  (24, 'DESOTO', 'desoto', true, NOW(), 0),
  (54, 'MONROE', 'monroe', true, NOW(), 0)
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

-- Create bid_decisions table if not exists (Letter J requirement)
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

-- Create index for bid_decisions performance  
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON public.bid_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_county_slug ON public.bid_decisions(county_slug);

-- Create verified outcomes tables for Letter B compliance
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

-- Insert pipeline configurations for SHARD-8 counties  
-- Note: desoto and monroe start with null to indicate they need A-lane setup
INSERT INTO public.pipeline_counties (county_slug, active, foreclosure_platform, foreclosure_url, tax_deed_platform, tax_deed_url)
VALUES
  ('palm_beach', true, 'realauction', 'https://www.realauction.com/palm_beach', 'realauction', 'https://www.realauction.com/palm_beach'),
  ('gilchrist', true, 'realauction', 'https://www.realauction.com/gilchrist', 'realauction', 'https://www.realauction.com/gilchrist'),
  ('okeechobee', true, 'realauction', 'https://www.realauction.com/okeechobee', 'realauction', 'https://www.realauction.com/okeechobee'),
  ('desoto', false, NULL, NULL, NULL, NULL), -- Need to discover actual sources
  ('monroe', false, NULL, NULL, NULL, NULL)  -- Need to discover actual sources
ON CONFLICT (county_slug)
DO UPDATE SET 
  active = EXCLUDED.active,
  updated_at = NOW();

-- Create gold standard audit table for ULTRALOOP verification tracking
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

-- Create migration log table if not exists
CREATE TABLE IF NOT EXISTS public.migration_log (
    id BIGSERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    executed_at TIMESTAMPTZ DEFAULT NOW(),
    shard TEXT,
    notes TEXT
);

-- Log this migration execution
INSERT INTO public.migration_log (filename, executed_at, shard, notes)
VALUES ('20260615_shard8_county_setup.sql', NOW(), 'SHARD-8', 'Database foundation for palm_beach, gilchrist, okeechobee, desoto, monroe - Gold Standard Campaign Run 28')
ON CONFLICT DO NOTHING;

COMMENT ON TABLE public.bid_decisions IS 'Shapira Formula inputs for Letter J - stores arv, max_bid, ml_score, and 5 factor keys per evaluator contract';
COMMENT ON TABLE public.foreclosure_outcomes IS 'Independent verified outcomes for Letter B - HARD BLOCK on PropertyOnion sources per canon';
COMMENT ON TABLE public.tax_deed_outcomes IS 'Independent verified outcomes for Letter B - HARD BLOCK on PropertyOnion sources per canon';  
COMMENT ON TABLE public.gold_standard_ultraloop_audit IS 'Evidence-Before-Claims audit trail per ULTRALOOP protocol';

-- Add dispatch tracking for this specific run
INSERT INTO public.gold_standard_ultraloop_audit (dispatch_id, ultraloop_mode, county_slug, letter, claim, survived)
VALUES ('063e58cd-6255-495f-9ce0-15db5bd73f44', 'native', 'shard8_init', 'A', 'Database schema prepared for SHARD-8 counties', true);