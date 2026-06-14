-- ============================================================
-- SHARD-10 COUNTY SETUP MIGRATION
-- Migration: 20260614_shard10_county_setup.sql  
-- Sets up manatee, collier, okeechobee, franklin, union counties for Gold Standard pipeline
-- ============================================================

-- Add SHARD-10 county slug mappings to fl_counties
-- Using correct co_no from fl_counties_manifest.yml:
-- Collier = 21, Franklin = 29, Manatee = 51, Okeechobee = 57, Union = 73
INSERT INTO fl_counties (co_no, name, fips_code, slug, region) VALUES 
  (21, 'Collier', '12021', 'collier', 'southwest'),
  (29, 'Franklin', '12037', 'franklin', 'panhandle'),
  (51, 'Manatee', '12081', 'manatee', 'west_central'),
  (57, 'Okeechobee', '12093', 'okeechobee', 'central'),
  (73, 'Union', '12125', 'union', 'north_central')
ON CONFLICT (co_no) DO UPDATE SET 
  slug = EXCLUDED.slug,
  fips_code = EXCLUDED.fips_code,
  region = EXCLUDED.region
WHERE fl_counties.slug IS NULL OR fl_counties.slug != EXCLUDED.slug;

-- Create pipeline.counties configuration for SHARD-10 counties
CREATE TABLE IF NOT EXISTS counties (
  id                    SERIAL PRIMARY KEY,
  county_slug           TEXT UNIQUE NOT NULL,
  county_name           TEXT NOT NULL,
  state                 TEXT DEFAULT 'FL',
  co_no                 INTEGER,  -- FL county number
  
  -- Foreclosure lane configuration
  foreclosure_platform  TEXT,     -- 'realforeclose', 'custom_clerk', etc.
  foreclosure_url       TEXT,
  
  -- Tax deed lane configuration  
  tax_deed_platform     TEXT,
  tax_deed_url          TEXT,
  
  -- Property appraiser configuration
  appraiser_url         TEXT,
  
  -- Status and metadata
  status                TEXT DEFAULT 'configured',  -- 'configured', 'needs_config', 'disabled'
  notes                 TEXT,
  
  -- Audit trail
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now()
);

-- Insert SHARD-10 county configurations
INSERT INTO counties (county_slug, county_name, co_no, foreclosure_platform, foreclosure_url, tax_deed_platform, tax_deed_url, appraiser_url, status) VALUES
  ('manatee', 'Manatee', 51, 'realforeclose', 'https://manatee.realforeclose.com', 'realforeclose', 'https://manatee.realforeclose.com', 'https://mcpao.manatee.fl.us', 'configured'),
  ('collier', 'Collier', 21, 'realforeclose', 'https://collier.realforeclose.com', 'realforeclose', 'https://collier.realforeclose.com', 'https://www.collierappraiser.com', 'configured'),
  ('okeechobee', 'Okeechobee', 57, 'realforeclose', 'https://okeechobee.realforeclose.com', 'realforeclose', 'https://okeechobee.realforeclose.com', 'https://www.okeechobeeappraiser.com', 'configured'),
  ('franklin', 'Franklin', 29, 'realforeclose', 'https://franklin.realforeclose.com', 'realforeclose', 'https://franklin.realforeclose.com', 'https://www.franklincountyfl.com/property-appraiser', 'configured'),
  ('union', 'Union', 73, 'realforeclose', 'https://union.realforeclose.com', 'realforeclose', 'https://union.realforeclose.com', 'https://www.unioncountyfl.gov/property-appraiser', 'configured')
ON CONFLICT (county_slug) DO UPDATE SET
  county_name = EXCLUDED.county_name,
  co_no = EXCLUDED.co_no,
  foreclosure_platform = EXCLUDED.foreclosure_platform,
  foreclosure_url = EXCLUDED.foreclosure_url,
  tax_deed_platform = EXCLUDED.tax_deed_platform,
  tax_deed_url = EXCLUDED.tax_deed_url,
  appraiser_url = EXCLUDED.appraiser_url,
  status = EXCLUDED.status,
  updated_at = now();

-- Ensure multi_county_auctions table has required columns for Gold Standard
DO $$ 
BEGIN
  -- Add parity_status column if it doesn't exist (needed for Letters C/D)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'parity_status') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN parity_status TEXT;
    CREATE INDEX IF NOT EXISTS idx_mca_parity_status ON multi_county_auctions(parity_status);
  END IF;

  -- Add tier1_sold_amount column if it doesn't exist (needed for Letter F)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'tier1_sold_amount') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN tier1_sold_amount NUMERIC(12,2);
    CREATE INDEX IF NOT EXISTS idx_mca_tier1_sold ON multi_county_auctions(tier1_sold_amount);
  END IF;

  -- Add tier1_verified_at column if it doesn't exist (needed for Letter F timing)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'tier1_verified_at') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN tier1_verified_at TIMESTAMPTZ;
    CREATE INDEX IF NOT EXISTS idx_mca_tier1_verified_at ON multi_county_auctions(tier1_verified_at);
  END IF;

  -- Add last_seen_at column if it doesn't exist (needed for Letter H freshness)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'last_seen_at') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN last_seen_at TIMESTAMPTZ;
    CREATE INDEX IF NOT EXISTS idx_mca_last_seen_at ON multi_county_auctions(last_seen_at);
  END IF;

  -- Add sale_type column if it doesn't exist (needed for Letter A dual-product)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'sale_type') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN sale_type TEXT;
    CREATE INDEX IF NOT EXISTS idx_mca_sale_type ON multi_county_auctions(sale_type);
  END IF;
END $$;

-- Create bid_decisions table if it doesn't exist (needed for Letter J)
-- This is the Shapira Formula pipeline output
CREATE TABLE IF NOT EXISTS bid_decisions (
  id                    SERIAL PRIMARY KEY,
  case_number           TEXT NOT NULL UNIQUE,
  county_slug           TEXT NOT NULL,
  parcel_id             TEXT,
  
  -- ARV (After Repair Value) 
  arv                   NUMERIC(12,2),
  arv_source            TEXT,               -- 'appraiser', 'comparable', 'zillow', 'manual'
  arv_confidence        NUMERIC(3,2),       -- 0.0 to 1.0
  
  -- Shapira Formula components
  max_bid               NUMERIC(12,2),      -- Maximum recommended bid = (ARV * 0.70) - repairs - $10K - MIN($25K, 15% * ARV)
  repair_estimate       NUMERIC(12,2),      -- Estimated repair costs
  holding_costs         NUMERIC(12,2),      -- 6-month holding estimate
  profit_target         NUMERIC(12,2),      -- Target profit amount
  
  -- ML Score (Shapira V14 model, AUC .78)
  ml_score              NUMERIC(5,3),       -- 0.000 to 1.000
  ml_model_version      TEXT DEFAULT 'shapira_v14',
  ml_features_used      TEXT[],
  
  -- Distress factors (required for Letter J evaluator)
  distress_location     BOOLEAN,            -- Location-based distress indicator
  distress_property     BOOLEAN,            -- Property condition distress
  distress_owner        BOOLEAN,            -- Owner situation distress
  
  -- Two-arm CMA (required for Letter J evaluator)
  cma_distressed        NUMERIC(12,2),      -- Distressed comparable sales
  cma_resale            NUMERIC(12,2),      -- Retail/resale comparable sales
  cma_confidence        NUMERIC(3,2),       -- 0.0 to 1.0
  comparable_count      INTEGER,
  
  -- Triangle factors (comparable analysis)
  triangle_score        NUMERIC(5,3),       -- 0.000 to 1.000  
  avg_price_per_sqft    NUMERIC(8,2),
  market_velocity       TEXT,               -- 'hot', 'normal', 'slow'
  
  -- Final recommendation
  recommendation        TEXT,               -- 'BID', 'SKIP', 'RESEARCH'
  recommendation_reason TEXT,
  max_bid_ratio         NUMERIC(5,2),       -- max_bid / opening_bid * 100
  
  -- Audit trail
  calculated_at         TIMESTAMPTZ DEFAULT now(),
  calculated_by         TEXT DEFAULT 'shard10_j_generator',
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now(),
  
  CONSTRAINT chk_arv_positive CHECK (arv > 0 OR arv IS NULL),
  CONSTRAINT chk_max_bid_positive CHECK (max_bid >= 0 OR max_bid IS NULL),
  CONSTRAINT chk_ml_score_valid CHECK (ml_score BETWEEN 0 AND 1 OR ml_score IS NULL),
  CONSTRAINT chk_triangle_score_valid CHECK (triangle_score BETWEEN 0 AND 1 OR triangle_score IS NULL),
  CONSTRAINT chk_cma_confidence_valid CHECK (cma_confidence BETWEEN 0 AND 1 OR cma_confidence IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_bid_decisions_county ON bid_decisions(county_slug);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON bid_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_parcel_id ON bid_decisions(parcel_id);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_recommendation ON bid_decisions(recommendation);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_calculated_at ON bid_decisions(calculated_at);

-- Create tax_deed_outcomes and foreclosure_outcomes tables if they don't exist (needed for Letter B)
CREATE TABLE IF NOT EXISTS tax_deed_outcomes (
  id                    SERIAL PRIMARY KEY,
  case_number           TEXT NOT NULL,
  county_slug           TEXT NOT NULL,
  
  -- Sale outcome data
  sale_date             DATE,
  winning_bid           NUMERIC(12,2),
  winning_bidder        TEXT,
  status                TEXT,              -- 'sold', 'no_sale', 'canceled'
  
  -- Data source tracking (CRITICAL for Letter B - must be independent)
  data_source           TEXT NOT NULL,     -- NEVER contain 'propertyonion'
  source_url            TEXT,
  scraped_at            TIMESTAMPTZ DEFAULT now(),
  
  -- Verification
  verified_at           TIMESTAMPTZ,
  verified_by           TEXT,
  
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now(),
  
  UNIQUE(case_number, county_slug, data_source)
);

CREATE TABLE IF NOT EXISTS foreclosure_outcomes (
  id                    SERIAL PRIMARY KEY,
  case_number           TEXT NOT NULL,
  county_slug           TEXT NOT NULL,
  
  -- Sale outcome data  
  sale_date             DATE,
  winning_bid           NUMERIC(12,2),
  winning_bidder        TEXT,
  status                TEXT,              -- 'sold', 'no_sale', 'canceled'
  
  -- Data source tracking (CRITICAL for Letter B - must be independent)
  data_source           TEXT NOT NULL,     -- NEVER contain 'propertyonion'
  source_url            TEXT,
  scraped_at            TIMESTAMPTZ DEFAULT now(),
  
  -- Verification
  verified_at           TIMESTAMPTZ,
  verified_by           TEXT,
  
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now(),
  
  UNIQUE(case_number, county_slug, data_source)
);

CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_county ON tax_deed_outcomes(county_slug);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_case ON tax_deed_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_source ON tax_deed_outcomes(data_source);

CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_county ON foreclosure_outcomes(county_slug);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_case ON foreclosure_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_source ON foreclosure_outcomes(data_source);

-- Grant permissions
GRANT SELECT ON counties TO anon, authenticated;
GRANT SELECT ON bid_decisions TO anon, authenticated;
GRANT SELECT ON tax_deed_outcomes TO anon, authenticated;
GRANT SELECT ON foreclosure_outcomes TO anon, authenticated;

-- Comments for documentation
COMMENT ON TABLE counties IS 'SHARD-10 pipeline configuration for dual-lane A-letter coverage';
COMMENT ON TABLE bid_decisions IS 'Shapira Formula deal thesis decisions for Gold Standard Letter J compliance - SHARD-10';
COMMENT ON TABLE tax_deed_outcomes IS 'Independent verified outcomes for tax deed sales - Letter B compliance';
COMMENT ON TABLE foreclosure_outcomes IS 'Independent verified outcomes for foreclosure sales - Letter B compliance';

-- Create audit log entry
INSERT INTO audit_log (operation, table_name, details, created_by) VALUES 
('MIGRATION', 'shard10_setup', 'SHARD-10 county setup: manatee, collier, okeechobee, franklin, union with Gold Standard schema', 'shard10_migration_20260614');