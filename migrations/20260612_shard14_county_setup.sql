-- ============================================================
-- SHARD-14 COUNTY SETUP MIGRATION
-- Migration: 20260612_shard14_county_setup.sql  
-- Adds missing counties for SHARD-14: okeechobee, hamilton
-- Osceola and Bay already exist from SHARD-12
-- ============================================================

-- Add SHARD-14 county slug mappings to fl_counties
-- Using correct co_no from fl_counties_manifest.yml:
-- Hamilton = 34, Okeechobee = 57, Osceola = 59 (exists), Bay = 13 (exists)
INSERT INTO fl_counties (co_no, name, fips_code, slug, region) VALUES 
  (34, 'Hamilton', '12047', 'hamilton', 'north'),
  (57, 'Okeechobee', '12093', 'okeechobee', 'central')
ON CONFLICT (co_no) DO UPDATE SET 
  slug = EXCLUDED.slug,
  fips_code = EXCLUDED.fips_code,
  region = EXCLUDED.region
WHERE fl_counties.slug IS NULL OR fl_counties.slug != EXCLUDED.slug;

-- Update existing SHARD-12 counties with proper slugs if missing
UPDATE fl_counties SET 
  slug = 'osceola',
  fips_code = '12097',
  region = 'central'
WHERE co_no = 59 AND (slug IS NULL OR slug != 'osceola');

UPDATE fl_counties SET 
  slug = 'bay', 
  fips_code = '12005',
  region = 'panhandle'
WHERE co_no = 13 AND (slug IS NULL OR slug != 'bay');

-- Ensure multi_county_auctions table has all needed columns for Gold Standard
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

  -- Add property enrichment columns if missing (needed for Letter I)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'property_address') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN property_address TEXT;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'property_lat') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN property_lat NUMERIC(10,7);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'property_lon') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN property_lon NUMERIC(10,7);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'appraised_value') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN appraised_value NUMERIC(12,2);
  END IF;
END $$;

-- Ensure bid_decisions table exists for Letter J (may already exist from SHARD-12)
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
  
  -- ML Score
  ml_score              NUMERIC(5,3),       -- 0.000 to 1.000
  ml_model_version      TEXT,
  ml_features_used      TEXT[],
  
  -- Triangle factors (comparable analysis)
  triangle_score        NUMERIC(5,3),       -- 0.000 to 1.000  
  comparable_count      INTEGER,
  avg_price_per_sqft    NUMERIC(8,2),
  market_velocity       TEXT,               -- 'hot', 'normal', 'slow'
  
  -- Two-arm CMA
  cma_low               NUMERIC(12,2),      -- Conservative estimate
  cma_high              NUMERIC(12,2),      -- Optimistic estimate
  cma_confidence        NUMERIC(3,2),       -- 0.0 to 1.0
  
  -- Final recommendation
  recommendation        TEXT,               -- 'BID', 'SKIP', 'RESEARCH'
  recommendation_reason TEXT,
  max_bid_ratio         NUMERIC(5,2),       -- max_bid / opening_bid * 100
  
  -- Audit trail
  calculated_at         TIMESTAMPTZ DEFAULT now(),
  calculated_by         TEXT DEFAULT 'shapira_formula_v1',
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

-- Ensure verified outcome tables exist for Letter B (may already exist from previous migrations)
CREATE TABLE IF NOT EXISTS tax_deed_outcomes (
  id                  SERIAL PRIMARY KEY,
  county_slug         TEXT NOT NULL,
  case_number         TEXT NOT NULL,
  certificate_number  TEXT,
  parcel_id           TEXT,
  auction_date        DATE NOT NULL,
  sale_status         TEXT NOT NULL,
  sale_amount         NUMERIC(12,2),
  buyer_name          TEXT,
  buyer_type          TEXT,
  redemption_amount   NUMERIC(12,2),
  
  data_source         TEXT NOT NULL,
  source_url          TEXT,
  scraped_at          TIMESTAMPTZ DEFAULT now(),
  verified_at         TIMESTAMPTZ DEFAULT now(),
  
  confidence_level    TEXT DEFAULT 'verified',
  notes               TEXT,
  created_at          TIMESTAMPTZ DEFAULT now(),
  updated_at          TIMESTAMPTZ DEFAULT now(),
  
  UNIQUE(county_slug, case_number, auction_date),
  CHECK (sale_status IN ('sold', 'no_sale', 'withdrawn', 'redeemed', 'postponed')),
  CHECK (data_source NOT ILIKE '%propertyonion%'),
  CHECK (buyer_type IN ('third_party', 'county', 'state', 'city', 'unknown') OR buyer_type IS NULL)
);

CREATE TABLE IF NOT EXISTS foreclosure_outcomes (
  id                  SERIAL PRIMARY KEY,
  county_slug         TEXT NOT NULL,
  case_number         TEXT NOT NULL,
  parcel_id           TEXT,
  auction_date        DATE NOT NULL,
  sale_status         TEXT NOT NULL,
  sale_amount         NUMERIC(12,2),
  high_bid            NUMERIC(12,2),
  buyer_name          TEXT,
  buyer_type          TEXT,
  
  plaintiff           TEXT,
  final_judgment_date DATE,
  final_judgment_amt  NUMERIC(12,2),
  court_case_number   TEXT,
  
  data_source         TEXT NOT NULL,
  source_url          TEXT,
  scraped_at          TIMESTAMPTZ DEFAULT now(),
  verified_at         TIMESTAMPTZ DEFAULT now(),
  
  confidence_level    TEXT DEFAULT 'verified',
  notes               TEXT,
  created_at          TIMESTAMPTZ DEFAULT now(),
  updated_at          TIMESTAMPTZ DEFAULT now(),
  
  UNIQUE(county_slug, case_number, auction_date),
  CHECK (sale_status IN ('sold', 'canceled', 'redeemed', 'struck', 'postponed')),
  CHECK (data_source NOT ILIKE '%propertyonion%'),
  CHECK (buyer_type IN ('third_party', 'plaintiff', 'bank', 'county', 'unknown') OR buyer_type IS NULL)
);

-- Add indexes for the new counties
CREATE INDEX IF NOT EXISTS idx_tdo_county_date ON tax_deed_outcomes(county_slug, auction_date);
CREATE INDEX IF NOT EXISTS idx_tdo_case_number ON tax_deed_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_tdo_parcel_id ON tax_deed_outcomes(parcel_id);
CREATE INDEX IF NOT EXISTS idx_tdo_data_source ON tax_deed_outcomes(data_source);

CREATE INDEX IF NOT EXISTS idx_fco_county_date ON foreclosure_outcomes(county_slug, auction_date);
CREATE INDEX IF NOT EXISTS idx_fco_case_number ON foreclosure_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_fco_parcel_id ON foreclosure_outcomes(parcel_id);
CREATE INDEX IF NOT EXISTS idx_fco_data_source ON foreclosure_outcomes(data_source);

-- Grant permissions
GRANT SELECT ON tax_deed_outcomes TO anon, authenticated;
GRANT SELECT ON foreclosure_outcomes TO anon, authenticated;
GRANT SELECT ON bid_decisions TO anon, authenticated;

COMMENT ON TABLE tax_deed_outcomes IS 'Independent verified tax deed outcomes for SHARD-14 counties';
COMMENT ON TABLE foreclosure_outcomes IS 'Independent verified foreclosure outcomes for SHARD-14 counties'; 
COMMENT ON TABLE bid_decisions IS 'Shapira Formula deal decisions for SHARD-14 counties';

-- Log completion
INSERT INTO public.migration_log (migration_name, executed_at, notes) 
VALUES ('20260612_shard14_county_setup', now(), 'SHARD-14 county setup: hamilton, okeechobee added, osceola/bay slugs verified')
ON CONFLICT DO NOTHING;