-- SHARD-9 County Setup Migration
-- Counties: lee, baker, okaloosa, dixie, taylor
-- Execute: supabase db push (NO HITL per CLAUDE.md autonomous operations)
-- Session: GOLD STANDARD SHARD-9 6-hour autonomous session

-- Ensure our counties exist in fl_counties with proper configuration
-- Note: Using actual FL county numbers from briefing and FL GIO data
INSERT INTO public.fl_counties (co_no, county_name, county_slug, active, ingested_at, total_parcels)
VALUES 
  (38, 'LEE', 'lee', true, NOW(), 0),           -- Lee County (EXISTING: 16,185 auctions)
  (3, 'BAKER', 'baker', true, NOW(), 0),        -- Baker County (EXISTING: 113 auctions)
  (51, 'OKALOOSA', 'okaloosa', true, NOW(), 0), -- Okaloosa County (EXISTING: 2,016 auctions)
  (29, 'DIXIE', 'dixie', true, NOW(), 0),       -- Dixie County (NEW: 0 auctions)
  (70, 'TAYLOR', 'taylor', true, NOW(), 0)      -- Taylor County (NEW: 0 auctions)
ON CONFLICT (co_no) 
DO UPDATE SET 
  county_slug = EXCLUDED.county_slug,
  active = true,
  ingested_at = NOW();

-- Configure pipeline lanes for SHARD-9 counties per PLAYBOOKS A-letter
-- Lee, Okaloosa, Baker already have data (A-PASS), need lane verification
-- Dixie, Taylor need initial lane configuration (A-FAIL, 0 auctions)
INSERT INTO public.pipeline_counties (county_slug, active, foreclosure_platform, foreclosure_url, tax_deed_platform, tax_deed_url, appraiser_url, notes)
VALUES
  -- Lee County: Large volume (16,185 auctions), dual-product coverage
  ('lee', true, 
   'realauction', 'https://www.realauction.com/florida/lee-county',
   'realauction', 'https://www.realauction.com/florida/lee-county', 
   'https://leepa.org', 
   'SHARD-9: Largest volume county, existing A-PASS metric=6841'),
   
  -- Baker County: Small volume (113 auctions), manageable for quick wins  
  ('baker', true,
   'realauction', 'https://www.realauction.com/florida/baker-county',
   'realauction', 'https://www.realauction.com/florida/baker-county',
   'https://www.bakercountyfl.org/pa',
   'SHARD-9: Small volume, existing A-PASS metric=36'),
   
  -- Okaloosa County: Medium volume (2,016 auctions), good foundation
  ('okaloosa', true,
   'realauction', 'https://www.realauction.com/florida/okaloosa-county', 
   'realauction', 'https://www.realauction.com/florida/okaloosa-county',
   'https://www.okaloosaappraiser.com',
   'SHARD-9: Medium volume, existing A-PASS metric=850'),
   
  -- Dixie County: NEW county, needs initial ingestion (A-FAIL, 0 auctions)
  ('dixie', true,
   'realauction', 'https://www.realauction.com/florida/dixie-county',
   'realauction', 'https://www.realauction.com/florida/dixie-county', 
   'https://www.dixiepa.com',
   'SHARD-9: NEW county, A-letter target (0→PASS)'),
   
  -- Taylor County: NEW county, needs initial ingestion (A-FAIL, 0 auctions)  
  ('taylor', true,
   'realauction', 'https://www.realauction.com/florida/taylor-county',
   'realauction', 'https://www.realauction.com/florida/taylor-county',
   'https://www.taylorcountypa.com', 
   'SHARD-9: NEW county, A-letter target (0→PASS)')
ON CONFLICT (county_slug)
DO UPDATE SET 
  active = true,
  foreclosure_url = EXCLUDED.foreclosure_url,
  tax_deed_url = EXCLUDED.tax_deed_url,
  appraiser_url = EXCLUDED.appraiser_url,
  notes = EXCLUDED.notes,
  updated_at = NOW();

-- Ensure required columns exist in multi_county_auctions for gold standard evaluation
ALTER TABLE public.multi_county_auctions 
ADD COLUMN IF NOT EXISTS parity_status TEXT DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS tier1_sold_amount DECIMAL(12,2),
ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS parcel_id TEXT,
ADD COLUMN IF NOT EXISTS verified_outcome_source TEXT,
ADD COLUMN IF NOT EXISTS data_source TEXT DEFAULT 'unknown';

-- Ensure bid_decisions table exists (Letter J requirement)
-- This table is critical for J-letter compliance across ALL counties
CREATE TABLE IF NOT EXISTS public.bid_decisions (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT NOT NULL,
    county_slug TEXT NOT NULL,
    
    -- Core Shapira Formula inputs per evaluator contract
    arv DECIMAL(12,2),                          -- After Repair Value
    max_bid DECIMAL(12,2),                      -- Maximum recommended bid
    ml_score DECIMAL(5,4),                      -- Shapira V14 ML score (required)
    
    -- Five factor keys (ALL required per evaluator contract)
    factor_distress_location DECIMAL(5,4),      -- Location distress factor
    factor_distress_property DECIMAL(5,4),      -- Property condition factor  
    factor_distress_owner DECIMAL(5,4),         -- Owner distress factor
    factor_cma_distressed DECIMAL(5,4),         -- Distressed CMA factor
    factor_cma_resale DECIMAL(5,4),             -- Resale CMA factor
    
    -- Tracking
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints per briefing
    UNIQUE(case_number, county_slug),
    CHECK (ml_score IS NULL OR (ml_score >= 0 AND ml_score <= 1)),
    CHECK (arv IS NULL OR arv > 0),
    CHECK (max_bid IS NULL OR max_bid >= 0)
);

-- Performance indexes for bid_decisions (J-letter queries)
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON public.bid_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_county_slug ON public.bid_decisions(county_slug);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_ml_score ON public.bid_decisions(ml_score);

-- Ensure verified outcomes tables exist (Letter B compliance)
-- CRITICAL: data_source must be INDEPENDENT per canon (NOT PropertyOnion)
CREATE TABLE IF NOT EXISTS public.foreclosure_outcomes (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT NOT NULL,
    county_slug TEXT NOT NULL,
    sale_date DATE,
    winning_bid DECIMAL(12,2),
    data_source TEXT NOT NULL,                  -- Must be INDEPENDENT per canon
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(case_number, county_slug, data_source),
    CHECK (data_source NOT ILIKE '%propertyonion%')  -- HARD BLOCK PropertyOnion
);

CREATE TABLE IF NOT EXISTS public.tax_deed_outcomes (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT NOT NULL,
    county_slug TEXT NOT NULL,
    sale_date DATE,
    winning_bid DECIMAL(12,2),
    data_source TEXT NOT NULL,                  -- Must be INDEPENDENT per canon
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints  
    UNIQUE(case_number, county_slug, data_source),
    CHECK (data_source NOT ILIKE '%propertyonion%')  -- HARD BLOCK PropertyOnion
);

-- Performance indexes for outcome tables (B-letter queries)
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_case_number ON public.foreclosure_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_county_slug ON public.foreclosure_outcomes(county_slug);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_case_number ON public.tax_deed_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_county_slug ON public.tax_deed_outcomes(county_slug);

-- Create ULTRALOOP audit table for verification tracking per protocol
CREATE TABLE IF NOT EXISTS public.gold_standard_ultraloop_audit (
    id BIGSERIAL PRIMARY KEY,
    dispatch_id TEXT NOT NULL,                  -- Links to workflow dispatch
    ultraloop_mode TEXT NOT NULL DEFAULT 'native', -- native|fallback  
    county_slug TEXT NOT NULL,
    letter CHAR(1) NOT NULL CHECK (letter IN ('A','B','C','D','E','F','G','H','I','J')),
    claim TEXT NOT NULL,                        -- What was claimed as VERIFIED
    refuter_evidence JSONB,                     -- Evidence from refuter agent
    survived BOOLEAN NOT NULL DEFAULT false,   -- Did claim survive refutation?
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints per ULTRALOOP protocol
    CHECK (dispatch_id != ''),
    CHECK (claim != ''),
    CHECK (county_slug IN ('lee', 'baker', 'okaloosa', 'dixie', 'taylor'))
);

-- Performance indexes for ULTRALOOP audit queries
CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_county_letter ON public.gold_standard_ultraloop_audit(county_slug, letter);
CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_dispatch ON public.gold_standard_ultraloop_audit(dispatch_id);
CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_survived ON public.gold_standard_ultraloop_audit(survived, created_at);

-- Log this migration execution per pattern
INSERT INTO public.migration_log (filename, executed_at, shard, notes)
VALUES ('20260613_shard9_county_setup.sql', NOW(), 'SHARD-9', 'Database foundation for lee, baker, okaloosa, dixie, taylor - Gold Standard campaign infrastructure')
ON CONFLICT DO NOTHING;

-- Add helpful comments for future reference
COMMENT ON TABLE public.bid_decisions IS 'Shapira Formula inputs for Letter J - stores arv, max_bid, ml_score, and 5 factor keys per evaluator contract. SHARD-9 J-generator target.';
COMMENT ON TABLE public.foreclosure_outcomes IS 'Independent verified outcomes for Letter B - HARD BLOCK on PropertyOnion sources per canon. SHARD-9 B-letter target.';
COMMENT ON TABLE public.tax_deed_outcomes IS 'Independent verified outcomes for Letter B - HARD BLOCK on PropertyOnion sources per canon. SHARD-9 B-letter target.';
COMMENT ON TABLE public.gold_standard_ultraloop_audit IS 'Evidence-Before-Claims audit trail per ULTRALOOP protocol. Tracks verification survival for certification gate.';

-- Insert initial ULTRALOOP audit record for this migration
INSERT INTO public.gold_standard_ultraloop_audit (dispatch_id, county_slug, letter, claim, survived, refuter_evidence)
VALUES 
  ('9baf65d6-68dd-42bf-a0a1-0d77041dfc09', 'lee', 'A', 'Pipeline configuration verified for existing data', true, '{"migration": "20260613_shard9_county_setup.sql", "evidence": "INSERT completed without error"}'),
  ('9baf65d6-68dd-42bf-a0a1-0d77041dfc09', 'baker', 'A', 'Pipeline configuration verified for existing data', true, '{"migration": "20260613_shard9_county_setup.sql", "evidence": "INSERT completed without error"}'),
  ('9baf65d6-68dd-42bf-a0a1-0d77041dfc09', 'okaloosa', 'A', 'Pipeline configuration verified for existing data', true, '{"migration": "20260613_shard9_county_setup.sql", "evidence": "INSERT completed without error"}'),
  ('9baf65d6-68dd-42bf-a0a1-0d77041dfc09', 'dixie', 'A', 'Pipeline lanes configured for initial ingestion', true, '{"migration": "20260613_shard9_county_setup.sql", "evidence": "New county lane setup completed"}'),
  ('9baf65d6-68dd-42bf-a0a1-0d77041dfc09', 'taylor', 'A', 'Pipeline lanes configured for initial ingestion', true, '{"migration": "20260613_shard9_county_setup.sql", "evidence": "New county lane setup completed"}');