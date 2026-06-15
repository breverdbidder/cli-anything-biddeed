-- ============================================================
-- SHARD-12 CORRECT COUNTY SETUP MIGRATION
-- Migration: 20260615_shard12_correct_county_setup.sql  
-- Sets up sarasota, hendry, pasco, glades counties for Gold Standard pipeline
-- ISSUE #7797 - Corrected county assignments 
-- ============================================================

-- Add SHARD-12 county slug mappings to fl_counties
-- Using correct co_no from fl_counties_manifest.yml:
-- Glades = 32, Hendry = 36, Pasco = 61, Sarasota = 68
INSERT INTO fl_counties (co_no, name, fips_code, slug, region) VALUES 
  (32, 'Glades', '12043', 'glades', 'central'),
  (36, 'Hendry', '12051', 'hendry', 'southwest'),
  (61, 'Pasco', '12101', 'pasco', 'west_central'),
  (68, 'Sarasota', '12115', 'sarasota', 'west_central')
ON CONFLICT (co_no) DO UPDATE SET 
  slug = EXCLUDED.slug,
  fips_code = EXCLUDED.fips_code,
  region = EXCLUDED.region
WHERE fl_counties.slug IS NULL OR fl_counties.slug != EXCLUDED.slug;

-- Ensure multi_county_auctions table is ready for SHARD-12 data
-- Add any missing columns that might be needed for Letter improvements
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

  -- Add matched_clean_po_id column if it doesn't exist (needed for C/D parity tracking)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'matched_clean_po_id') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN matched_clean_po_id TEXT;
    CREATE INDEX IF NOT EXISTS idx_mca_matched_clean_po_id ON multi_county_auctions(matched_clean_po_id);
  END IF;

  -- Add property_address_normalized column if it doesn't exist (needed for E linkage)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'property_address_normalized') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN property_address_normalized TEXT;
    CREATE INDEX IF NOT EXISTS idx_mca_property_address_normalized ON multi_county_auctions(property_address_normalized);
  END IF;
END $$;

-- Create bid_decisions table if it doesn't exist (needed for Letter J)
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
  max_bid               NUMERIC(12,2),      -- Maximum recommended bid
  repair_estimate       NUMERIC(12,2),      -- Estimated repair costs
  holding_costs         NUMERIC(12,2),      -- 6-month holding estimate
  profit_target         NUMERIC(12,2),      -- Target profit amount
  
  -- ML Score from Shapira V14 model
  ml_score              NUMERIC(5,3),       -- 0.000 to 1.000
  ml_model_version      TEXT,
  ml_features_used      TEXT[],
  
  -- Triangle factors (comparable analysis) - REQUIRED for Letter J
  triangle_score        NUMERIC(5,3),       -- 0.000 to 1.000  
  comparable_count      INTEGER,
  avg_price_per_sqft    NUMERIC(8,2),
  market_velocity       TEXT,               -- 'hot', 'normal', 'slow'
  
  -- Two-arm CMA - REQUIRED for Letter J 
  cma_distressed        NUMERIC(12,2),      -- Distressed comps average
  cma_resale            NUMERIC(12,2),      -- Retail resale comps average
  cma_confidence        NUMERIC(3,2),       -- 0.0 to 1.0
  
  -- Distress factors - REQUIRED for Letter J
  distress_location     NUMERIC(3,2),       -- Location adjustment factor
  distress_property     NUMERIC(3,2),       -- Property condition factor  
  distress_owner        NUMERIC(3,2),       -- Owner situation factor
  
  -- Final recommendation
  recommendation        TEXT,               -- 'BID', 'SKIP', 'RESEARCH'
  recommendation_reason TEXT,
  max_bid_ratio         NUMERIC(5,2),       -- max_bid / opening_bid * 100
  
  -- Audit trail
  calculated_at         TIMESTAMPTZ DEFAULT now(),
  calculated_by         TEXT DEFAULT 'shapira_formula_v14',
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

-- Create foreclosure_outcomes table if it doesn't exist (needed for Letter B)
CREATE TABLE IF NOT EXISTS foreclosure_outcomes (
  id                    SERIAL PRIMARY KEY,
  case_number           TEXT NOT NULL,
  county_slug           TEXT NOT NULL,
  auction_date          DATE,
  
  -- Outcome details
  outcome_type          TEXT NOT NULL,      -- 'sold', 'no_sale', 'canceled', 'postponed'
  winning_bid           NUMERIC(12,2),
  final_judgment_amount NUMERIC(12,2),
  
  -- Independent verification
  data_source           TEXT NOT NULL,      -- MUST be independent (not PropertyOnion)
  source_url            TEXT,
  scraped_at            TIMESTAMPTZ DEFAULT now(),
  verified_at           TIMESTAMPTZ,
  
  -- Cross-references
  parcel_id             TEXT,
  property_address      TEXT,
  
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now(),
  
  UNIQUE(case_number, county_slug, auction_date)
);

CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_county ON foreclosure_outcomes(county_slug);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_case_number ON foreclosure_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_outcome_type ON foreclosure_outcomes(outcome_type);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_data_source ON foreclosure_outcomes(data_source);

-- Create tax_deed_outcomes table if it doesn't exist (needed for Letter B)
CREATE TABLE IF NOT EXISTS tax_deed_outcomes (
  id                    SERIAL PRIMARY KEY,
  case_number           TEXT NOT NULL,
  county_slug           TEXT NOT NULL,
  auction_date          DATE,
  
  -- Outcome details  
  outcome_type          TEXT NOT NULL,      -- 'sold', 'no_sale', 'canceled', 'postponed'
  winning_bid           NUMERIC(12,2),
  assessed_value        NUMERIC(12,2),
  
  -- Independent verification
  data_source           TEXT NOT NULL,      -- MUST be independent (not PropertyOnion) 
  source_url            TEXT,
  scraped_at            TIMESTAMPTZ DEFAULT now(),
  verified_at           TIMESTAMPTZ,
  
  -- Cross-references
  parcel_id             TEXT,
  property_address      TEXT,
  
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now(),
  
  UNIQUE(case_number, county_slug, auction_date)
);

CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_county ON tax_deed_outcomes(county_slug);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_case_number ON tax_deed_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_outcome_type ON tax_deed_outcomes(outcome_type);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_data_source ON tax_deed_outcomes(data_source);

-- Grant permissions for public access
GRANT SELECT ON bid_decisions TO anon, authenticated;
GRANT SELECT ON foreclosure_outcomes TO anon, authenticated;  
GRANT SELECT ON tax_deed_outcomes TO anon, authenticated;

-- Comments for documentation
COMMENT ON TABLE bid_decisions IS 'Shapira Formula deal thesis decisions for Gold Standard Letter J compliance';
COMMENT ON TABLE foreclosure_outcomes IS 'Independent verified foreclosure auction outcomes for Letter B compliance';
COMMENT ON TABLE tax_deed_outcomes IS 'Independent verified tax deed auction outcomes for Letter B compliance';

-- Insert sample test data to validate table structure
INSERT INTO bid_decisions (case_number, county_slug, arv, max_bid, ml_score, triangle_score, cma_distressed, cma_resale, distress_location, distress_property, distress_owner, recommendation)
VALUES ('SHARD12-TEST-001', 'sarasota', 150000.00, 75000.00, 0.750, 0.850, 85000.00, 140000.00, 0.95, 0.80, 0.70, 'BID')
ON CONFLICT (case_number) DO NOTHING;

COMMENT ON MIGRATION IS 'SHARD-12 county setup for Issue #7797: sarasota, hendry, pasco, glades - corrected assignments with full Letter A-J infrastructure';