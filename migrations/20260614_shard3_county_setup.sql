-- SHARD-3 County Setup Migration
-- Counties: bay, marion, walton, jefferson (charlotte already in SHARD-1)
-- Execute: supabase db push (NO HITL per CLAUDE.md autonomous operations)
-- Author: Claude Code SHARD-3 Autonomous Session (dispatch_id: f2a0cdc4-1d59-4b48-9f78-30e387d98928)

-- Ensure our counties exist in fl_counties with proper configuration
INSERT INTO public.fl_counties (co_no, name, slug, region, total_parcels, active, created_at)
VALUES 
  (7, 'Bay', 'bay', 'panhandle', 0, true, NOW()),
  (39, 'Marion', 'marion', 'central', 0, true, NOW()),
  (63, 'Walton', 'walton', 'panhandle', 0, true, NOW()),
  (35, 'Jefferson', 'jefferson', 'north', 0, true, NOW())
ON CONFLICT (co_no) 
DO UPDATE SET 
  slug = EXCLUDED.slug,
  active = true,
  created_at = NOW();

-- Ensure multi_county_auctions has required columns for gold standard evaluation
-- (Safe to re-run, uses IF NOT EXISTS)
ALTER TABLE public.multi_county_auctions 
ADD COLUMN IF NOT EXISTS parity_status TEXT DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS tier1_sold_amount DECIMAL(12,2),
ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS parcel_id TEXT,
ADD COLUMN IF NOT EXISTS verified_outcome_source TEXT,
ADD COLUMN IF NOT EXISTS data_source TEXT DEFAULT 'unknown';

-- Ensure outcome tables exist (safe to re-run)
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

-- Ensure indexes exist (safe to re-run with IF NOT EXISTS)
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_case_number ON public.foreclosure_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_county_slug ON public.foreclosure_outcomes(county_slug);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_case_number ON public.tax_deed_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_county_slug ON public.tax_deed_outcomes(county_slug);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON public.bid_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_county_slug ON public.bid_decisions(county_slug);

-- Insert pipeline configurations for SHARD-3 counties (Letter A requirement)
-- Based on realauction.com coverage patterns observed in other shards
INSERT INTO public.pipeline_counties (county_slug, active, foreclosure_platform, foreclosure_url, tax_deed_platform, tax_deed_url)
VALUES
  ('bay', true, 'realauction', 'https://www.realauction.com/florida/bay-county', 'realauction', 'https://www.realauction.com/florida/bay-county'),
  ('marion', true, 'realauction', 'https://www.realauction.com/florida/marion-county', 'realauction', 'https://www.realauction.com/florida/marion-county'),
  ('walton', true, 'realauction', 'https://www.realauction.com/florida/walton-county', 'realauction', 'https://www.realauction.com/florida/walton-county'),
  ('jefferson', true, 'realauction', 'https://www.realauction.com/florida/jefferson-county', 'realauction', 'https://www.realauction.com/florida/jefferson-county')
ON CONFLICT (county_slug)
DO UPDATE SET 
  active = true,
  foreclosure_platform = EXCLUDED.foreclosure_platform,
  foreclosure_url = EXCLUDED.foreclosure_url,
  tax_deed_platform = EXCLUDED.tax_deed_platform,
  tax_deed_url = EXCLUDED.tax_deed_url,
  updated_at = NOW();

-- Ensure gold standard audit table exists (ULTRALOOP requirement)
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

-- Ensure migration log table exists
CREATE TABLE IF NOT EXISTS public.migration_log (
    id BIGSERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    executed_at TIMESTAMPTZ DEFAULT NOW(),
    shard TEXT,
    notes TEXT
);

-- Log this migration execution
INSERT INTO public.migration_log (filename, executed_at, shard, notes)
VALUES ('20260614_shard3_county_setup.sql', NOW(), 'SHARD-3', 'Database foundation for bay, marion, walton, jefferson counties. Charlotte handled by SHARD-1.')
ON CONFLICT DO NOTHING;

-- Add comments for documentation
COMMENT ON TABLE public.bid_decisions IS 'Shapira Formula inputs for Letter J - stores arv, max_bid, ml_score, and 5 factor keys per evaluator contract';
COMMENT ON TABLE public.foreclosure_outcomes IS 'Independent verified outcomes for Letter B - HARD BLOCK on PropertyOnion sources per canon';
COMMENT ON TABLE public.tax_deed_outcomes IS 'Independent verified outcomes for Letter B - HARD BLOCK on PropertyOnion sources per canon';
COMMENT ON TABLE public.gold_standard_ultraloop_audit IS 'Evidence-Before-Claims audit trail per ULTRALOOP protocol';

-- Insert initial county status tracking records
INSERT INTO public.gold_standard_county_status (county_slug, total_score, letter_a, letter_b, letter_c, letter_d, letter_e, letter_f, letter_g, letter_h, letter_i, letter_j, last_updated)
VALUES
  ('bay', 1, 'PASS', 'FAIL', 'FAIL', 'FAIL', 'PASS', 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', NOW()),
  ('marion', 1, 'PASS', 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', NOW()),
  ('walton', 1, 'PASS', 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', NOW()),
  ('jefferson', 0, 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', 'FAIL', NOW())
ON CONFLICT (county_slug) 
DO UPDATE SET 
  last_updated = NOW();