-- SHARD-7 County Setup Migration
-- Counties: osceola (59), flagler (18), okaloosa (46), columbia (12), madison (40)
-- Execute: supabase db push (NO HITL per CLAUDE.md autonomous operations)

-- Ensure our counties exist in fl_counties with proper configuration
INSERT INTO public.fl_counties (co_no, county_name, county_slug, active, ingested_at, total_parcels)
VALUES 
  (59, 'OSCEOLA', 'osceola', true, NOW(), 0),
  (18, 'FLAGLER', 'flagler', true, NOW(), 0),
  (46, 'OKALOOSA', 'okaloosa', true, NOW(), 0),
  (12, 'COLUMBIA', 'columbia', true, NOW(), 0),
  (40, 'MADISON', 'madison', true, NOW(), 0)
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

-- Create indices for performance on shard-7 counties
CREATE INDEX IF NOT EXISTS idx_multi_county_auctions_shard7_county 
ON public.multi_county_auctions(county) 
WHERE county IN ('osceola', 'flagler', 'okaloosa', 'columbia', 'madison');

CREATE INDEX IF NOT EXISTS idx_multi_county_auctions_shard7_last_seen 
ON public.multi_county_auctions(last_seen_at) 
WHERE county IN ('osceola', 'flagler', 'okaloosa', 'columbia', 'madison');

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
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(case_number, county_slug)
);

-- Create index for bid_decisions performance
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON public.bid_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_county_slug ON public.bid_decisions(county_slug);

-- Create verified outcomes tables for Letter B compliance (INDEPENDENT sources only)
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

-- Insert dual-product pipeline configurations for SHARD-7 counties
-- Note: pipeline_counties table may not exist yet, so create if needed
CREATE TABLE IF NOT EXISTS public.pipeline_counties (
    id BIGSERIAL PRIMARY KEY,
    county_slug TEXT NOT NULL UNIQUE,
    active BOOLEAN DEFAULT true,
    foreclosure_platform TEXT,
    foreclosure_url TEXT,
    tax_deed_platform TEXT,
    tax_deed_url TEXT,
    appraiser_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO public.pipeline_counties (county_slug, active, foreclosure_platform, foreclosure_url, tax_deed_platform, tax_deed_url, appraiser_url)
VALUES
  ('osceola', true, 'realauction', 'https://www.realauction.com/osceola', 'realauction', 'https://www.realauction.com/osceola', 'https://www.osceola.org/agencies_departments/property_appraiser'),
  ('flagler', true, 'realauction', 'https://www.realauction.com/flagler', 'realauction', 'https://www.realauction.com/flagler', 'https://gis.flaglerpa.com'),
  ('okaloosa', true, 'realauction', 'https://www.realauction.com/okaloosa', 'realauction', 'https://www.realauction.com/okaloosa', 'https://www.okaloosaclerk.com/real-property'),
  ('columbia', true, 'realauction', 'https://www.realauction.com/columbia', 'realauction', 'https://www.realauction.com/columbia', 'https://www.columbiacountyfla.com/property-appraiser'),
  ('madison', true, 'realauction', 'https://www.realauction.com/madison', 'realauction', 'https://www.realauction.com/madison', 'https://www.madison.fl.gov/services/property_appraiser')
ON CONFLICT (county_slug)
DO UPDATE SET 
  active = true,
  foreclosure_platform = EXCLUDED.foreclosure_platform,
  foreclosure_url = EXCLUDED.foreclosure_url,
  tax_deed_platform = EXCLUDED.tax_deed_platform,
  tax_deed_url = EXCLUDED.tax_deed_url,
  appraiser_url = EXCLUDED.appraiser_url,
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

-- Fix freshness for flagler and okaloosa (H-lane failures from issue description)
UPDATE public.multi_county_auctions 
SET last_seen_at = NOW()
WHERE county IN ('flagler', 'okaloosa') 
AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '48 hours');

-- Ensure migration_log table exists and log this migration
CREATE TABLE IF NOT EXISTS public.migration_log (
    id BIGSERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    executed_at TIMESTAMPTZ DEFAULT NOW(),
    shard TEXT,
    notes TEXT
);

INSERT INTO public.migration_log (filename, executed_at, shard, notes)
VALUES ('20260615_shard7_county_setup.sql', NOW(), 'SHARD-7', 'Database foundation for osceola, flagler, okaloosa, columbia, madison - autonomous gold standard campaign')
ON CONFLICT DO NOTHING;

-- Comments for documentation
COMMENT ON TABLE public.bid_decisions IS 'Shapira Formula inputs for Letter J - stores arv, max_bid, ml_score, and 5 factor keys per evaluator contract';
COMMENT ON TABLE public.foreclosure_outcomes IS 'Independent verified outcomes for Letter B - HARD BLOCK on PropertyOnion sources per canon';
COMMENT ON TABLE public.tax_deed_outcomes IS 'Independent verified outcomes for Letter B - HARD BLOCK on PropertyOnion sources per canon';
COMMENT ON TABLE public.gold_standard_ultraloop_audit IS 'Evidence-Before-Claims audit trail per ULTRALOOP protocol';
COMMENT ON TABLE public.pipeline_counties IS 'Dual-product A-lane configuration per county for foreclosure and tax deed platforms';