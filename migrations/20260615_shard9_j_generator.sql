-- SHARD-9 J Generator Migration
-- Session: 50ad6e05-015c-4b1d-be49-420103896d2e
-- Created: 2026-06-15 00:06 UTC
-- Purpose: Support bid_decisions pipeline per gold standard J criteria

-- Ensure bid_decisions table exists with proper structure
CREATE TABLE IF NOT EXISTS public.bid_decisions (
    id bigserial PRIMARY KEY,
    case_number text NOT NULL,
    county text NOT NULL,
    
    -- Core Shapira Formula components
    arv decimal,              -- After Repair Value
    max_bid decimal,          -- Recommended maximum bid
    ml_score decimal,         -- Machine learning score from Shapira V14
    
    -- Triangle + two-arm CMA factors (per evaluator contract)
    factors jsonb,            -- Must contain: distress_location, distress_property, distress_owner, cma_distressed, cma_resale
    
    -- Metadata
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    data_source text,         -- Source of the calculation
    
    -- Constraints
    UNIQUE(case_number, county)
);

-- Index for fast lookups by case_number (evaluation key)
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON public.bid_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_county ON public.bid_decisions(county);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_created_at ON public.bid_decisions(created_at);

-- Ensure factors JSONB contains required keys for J evaluation
CREATE OR REPLACE FUNCTION validate_j_factors(factors_json jsonb)
RETURNS boolean AS $$
BEGIN
    -- Check that all required factor keys exist per evaluator contract
    RETURN (
        factors_json ? 'distress_location' AND
        factors_json ? 'distress_property' AND  
        factors_json ? 'distress_owner' AND
        factors_json ? 'cma_distressed' AND
        factors_json ? 'cma_resale'
    );
END;
$$ LANGUAGE plpgsql;

-- Add constraint to ensure factor completeness
ALTER TABLE public.bid_decisions 
ADD CONSTRAINT check_j_factors 
CHECK (factors IS NULL OR validate_j_factors(factors));

-- Enable RLS (if not already enabled)
ALTER TABLE public.bid_decisions ENABLE ROW LEVEL SECURITY;

-- RLS policy for service role access
DROP POLICY IF EXISTS "Service role access" ON public.bid_decisions;
CREATE POLICY "Service role access" ON public.bid_decisions
    FOR ALL USING (auth.role() = 'service_role');

-- Comments for documentation
COMMENT ON TABLE public.bid_decisions IS 'Shapira formula bid decisions for gold standard J criteria compliance';
COMMENT ON COLUMN public.bid_decisions.factors IS 'Required keys: distress_location, distress_property, distress_owner, cma_distressed, cma_resale';
COMMENT ON COLUMN public.bid_decisions.ml_score IS 'Shapira V14 machine learning score (AUC 0.78)';
COMMENT ON COLUMN public.bid_decisions.case_number IS 'Match key to multi_county_auctions.case_number';

-- Ensure audit log table exists for SHIP GATE compliance
CREATE TABLE IF NOT EXISTS public.audit_log (
    id bigserial PRIMARY KEY,
    county text,
    fix_type text,
    timestamp timestamptz DEFAULT now(),
    status text,
    evidence text,
    metadata jsonb
);

CREATE INDEX IF NOT EXISTS idx_audit_log_county_type ON public.audit_log(county, fix_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON public.audit_log(timestamp);

-- Enable RLS on audit_log
ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role access audit" ON public.audit_log;
CREATE POLICY "Service role access audit" ON public.audit_log
    FOR ALL USING (auth.role() = 'service_role');

COMMENT ON TABLE public.audit_log IS 'SHIP GATE compliance: SQL evidence logging for gold standard sessions';

-- Ensure pipeline_counties table exists for A-lane setup
CREATE TABLE IF NOT EXISTS public.pipeline_counties (
    id bigserial PRIMARY KEY,
    county text UNIQUE NOT NULL,
    dor_number integer,
    full_name text,
    foreclosure_platform text DEFAULT 'realauction',
    tax_deed_platform text DEFAULT 'realauction',
    status text DEFAULT 'configured',
    configured_at timestamptz DEFAULT now(),
    configured_by text
);

CREATE INDEX IF NOT EXISTS idx_pipeline_counties_county ON public.pipeline_counties(county);
CREATE INDEX IF NOT EXISTS idx_pipeline_counties_dor ON public.pipeline_counties(dor_number);

-- Enable RLS on pipeline_counties
ALTER TABLE public.pipeline_counties ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role access pipeline" ON public.pipeline_counties;
CREATE POLICY "Service role access pipeline" ON public.pipeline_counties
    FOR ALL USING (auth.role() = 'service_role');

COMMENT ON TABLE public.pipeline_counties IS 'County configuration for A-lane auction ingestion setup';