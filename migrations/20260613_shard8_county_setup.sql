-- ============================================================
-- SHARD-8 COUNTY SETUP MIGRATION
-- Migration: 20260613_shard8_county_setup.sql  
-- Sets up hillsborough, alachua, nassau, desoto, monroe counties for Gold Standard pipeline
-- ============================================================

-- Add SHARD-8 county slug mappings to fl_counties
-- Using correct co_no from fl_counties_manifest.yml:
-- Hillsborough = 39 (already has slug), Alachua = 11, Nassau = 55, DeSoto = 24, Monroe = 54
INSERT INTO fl_counties (co_no, name, fips_code, slug, region) VALUES 
  (39, 'Hillsborough', '12057', 'hillsborough', 'central'),
  (11, 'Alachua', '12001', 'alachua', 'north'),
  (55, 'Nassau', '12089', 'nassau', 'northeast'), 
  (24, 'DeSoto', '12027', 'desoto', 'central'),
  (54, 'Monroe', '12087', 'monroe', 'keys')
ON CONFLICT (co_no) DO UPDATE SET 
  slug = EXCLUDED.slug,
  fips_code = EXCLUDED.fips_code,
  region = EXCLUDED.region
WHERE fl_counties.slug IS NULL OR fl_counties.slug != EXCLUDED.slug;

-- Ensure multi_county_auctions table is ready for SHARD-8 data
-- Add any missing columns that might be needed for Letter improvements
DO $$ 
BEGIN
  -- Add parity_status column if it doesn't exist (needed for Letters C/D)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'parity_status') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN parity_status TEXT;
    CREATE INDEX IF NOT EXISTS idx_mca_parity_status ON multi_county_auctions(parity_status);
    COMMENT ON COLUMN multi_county_auctions.parity_status IS 'PropertyOnion parity status: matched_clean, matched_divergent, no_match';
  END IF;

  -- Add tier1_sold_amount column if it doesn't exist (needed for Letter F)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'tier1_sold_amount') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN tier1_sold_amount NUMERIC(12,2);
    CREATE INDEX IF NOT EXISTS idx_mca_tier1_sold ON multi_county_auctions(tier1_sold_amount);
    COMMENT ON COLUMN multi_county_auctions.tier1_sold_amount IS 'Verified sold amount from independent sources (Letter F compliance)';
  END IF;

  -- Add tier1_verified_at column if it doesn't exist (needed for Letter F timing)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'tier1_verified_at') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN tier1_verified_at TIMESTAMPTZ;
    CREATE INDEX IF NOT EXISTS idx_mca_tier1_verified_at ON multi_county_auctions(tier1_verified_at);
    COMMENT ON COLUMN multi_county_auctions.tier1_verified_at IS 'Timestamp when tier1_sold_amount was last verified';
  END IF;

  -- Add last_seen_at column if it doesn't exist (needed for Letter H freshness)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'last_seen_at') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN last_seen_at TIMESTAMPTZ;
    CREATE INDEX IF NOT EXISTS idx_mca_last_seen_at ON multi_county_auctions(last_seen_at);
    COMMENT ON COLUMN multi_county_auctions.last_seen_at IS 'Last time this auction was seen in scrape (Letter H freshness)';
  END IF;

  -- Add source_platform column if it doesn't exist (needed for tracking data sources)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'source_platform') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN source_platform TEXT;
    CREATE INDEX IF NOT EXISTS idx_mca_source_platform ON multi_county_auctions(source_platform);
    COMMENT ON COLUMN multi_county_auctions.source_platform IS 'Data source platform: realauction, clerk_direct, etc';
  END IF;

  -- Add property_address column if it doesn't exist (needed for Letter I property cards)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'property_address') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN property_address TEXT;
    CREATE INDEX IF NOT EXISTS idx_mca_property_address ON multi_county_auctions(property_address);
    COMMENT ON COLUMN multi_county_auctions.property_address IS 'Normalized property address for Letter I property card completion';
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
  
  -- ML Score (Shapira V14 model)
  ml_score              NUMERIC(5,3),       -- 0.000 to 1.000
  ml_model_version      TEXT,
  ml_features_used      TEXT[],
  
  -- Distress factors (required by evaluator)
  distress_location     NUMERIC(3,2),       -- Location distress factor
  distress_property     NUMERIC(3,2),       -- Property condition factor  
  distress_owner        NUMERIC(3,2),       -- Owner distress factor
  
  -- Two-arm CMA (required by evaluator)
  cma_distressed        NUMERIC(12,2),      -- Distressed comparable sales
  cma_resale            NUMERIC(12,2),      -- Regular market comparable sales
  cma_confidence        NUMERIC(3,2),       -- 0.0 to 1.0
  
  -- Triangle factors (comparable analysis)
  triangle_score        NUMERIC(5,3),       -- 0.000 to 1.000  
  comparable_count      INTEGER,
  avg_price_per_sqft    NUMERIC(8,2),
  market_velocity       TEXT,               -- 'hot', 'normal', 'slow'
  
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
  CONSTRAINT chk_cma_confidence_valid CHECK (cma_confidence BETWEEN 0 AND 1 OR cma_confidence IS NULL),
  CONSTRAINT chk_distress_factors_valid CHECK (
    (distress_location BETWEEN 0 AND 1 OR distress_location IS NULL) AND
    (distress_property BETWEEN 0 AND 1 OR distress_property IS NULL) AND 
    (distress_owner BETWEEN 0 AND 1 OR distress_owner IS NULL)
  )
);

CREATE INDEX IF NOT EXISTS idx_bid_decisions_county ON bid_decisions(county_slug);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON bid_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_parcel_id ON bid_decisions(parcel_id);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_recommendation ON bid_decisions(recommendation);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_ml_score ON bid_decisions(ml_score);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_calculated_at ON bid_decisions(calculated_at);

-- SHARD-8 counties pipeline.counties configuration
-- Enable both RealAuction and clerk direct lanes per Gold Standard requirements
INSERT INTO pipeline.counties (
  slug, 
  name,
  state,
  status,
  foreclosure_url,
  tax_deed_url,
  foreclosure_platform,
  tax_deed_platform,
  priority_tier,
  region
) VALUES 
  ('hillsborough', 'Hillsborough', 'FL', 'active', 'https://www.realauction.com/florida/hillsborough-county', 'https://www.realauction.com/florida/hillsborough-county', 'realauction', 'realauction', 1, 'central'),
  ('alachua', 'Alachua', 'FL', 'active', 'https://www.realauction.com/florida/alachua-county', 'https://www.realauction.com/florida/alachua-county', 'realauction', 'realauction', 2, 'north'),
  ('nassau', 'Nassau', 'FL', 'active', 'https://www.realauction.com/florida/nassau-county', 'https://www.realauction.com/florida/nassau-county', 'realauction', 'realauction', 2, 'northeast'),
  ('desoto', 'DeSoto', 'FL', 'active', 'https://www.realauction.com/florida/desoto-county', 'https://www.realauction.com/florida/desoto-county', 'realauction', 'realauction', 3, 'central'),
  ('monroe', 'Monroe', 'FL', 'active', 'https://www.realauction.com/florida/monroe-county', 'https://www.realauction.com/florida/monroe-county', 'realauction', 'realauction', 3, 'keys')
ON CONFLICT (slug) DO UPDATE SET
  foreclosure_url = EXCLUDED.foreclosure_url,
  tax_deed_url = EXCLUDED.tax_deed_url,
  foreclosure_platform = EXCLUDED.foreclosure_platform,
  tax_deed_platform = EXCLUDED.tax_deed_platform,
  status = EXCLUDED.status,
  region = EXCLUDED.region;

-- Initialize gold_standard_ultraloop_audit table for ULTRALOOP protocol compliance  
CREATE TABLE IF NOT EXISTS gold_standard_ultraloop_audit (
  id                    SERIAL PRIMARY KEY,
  dispatch_id           UUID,                -- From GitHub Actions dispatch
  ultraloop_mode        TEXT NOT NULL,       -- 'native' or 'fallback'
  county_slug           TEXT NOT NULL,
  letter                CHAR(1) NOT NULL,    -- A-J
  claim                 TEXT NOT NULL,       -- The improvement claim being tested
  refuter_evidence      JSONB,               -- Evidence from refuter subagent
  survived              BOOLEAN NOT NULL,    -- TRUE if claim survived refutation
  
  created_at            TIMESTAMPTZ DEFAULT now(),
  session_id            TEXT,                -- For tracking multiple claims in one session
  
  CONSTRAINT chk_letter_valid CHECK (letter IN ('A','B','C','D','E','F','G','H','I','J')),
  CONSTRAINT chk_ultraloop_mode_valid CHECK (ultraloop_mode IN ('native', 'fallback'))
);

CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_county_letter ON gold_standard_ultraloop_audit(county_slug, letter);
CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_dispatch_id ON gold_standard_ultraloop_audit(dispatch_id);
CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_survived ON gold_standard_ultraloop_audit(survived);
CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_created_at ON gold_standard_ultraloop_audit(created_at);

-- Grant permissions
GRANT SELECT ON bid_decisions TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON gold_standard_ultraloop_audit TO anon, authenticated;

COMMENT ON TABLE bid_decisions IS 'Shapira Formula deal thesis decisions for Gold Standard Letter J compliance (SHARD-8)';
COMMENT ON TABLE gold_standard_ultraloop_audit IS 'ULTRALOOP protocol audit trail for verification claims (prevents ghost-success)';
COMMENT ON TABLE pipeline.counties IS 'Counties configuration for scraper dispatch and platform routing';