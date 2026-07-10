-- SHARD-2 Gold Standard Letter J: Bid Decisions Table
-- Required for deal thesis pipeline (Shapira Formula)

CREATE TABLE IF NOT EXISTS bid_decisions (
  id                    SERIAL PRIMARY KEY,
  case_number           TEXT NOT NULL UNIQUE,
  county_slug           TEXT NOT NULL,
  parcel_id             TEXT,
  
  -- ARV (After Repair Value) 
  arv                   NUMERIC(12,2),
  arv_source            TEXT,              -- 'cma', 'zestimate', 'manual', 'model'
  arv_confidence        TEXT,              -- 'high', 'medium', 'low'
  
  -- Triangle factors (location, condition, market)
  location_score        NUMERIC(4,2),     -- 0-10 location desirability
  condition_score       NUMERIC(4,2),     -- 0-10 property condition
  market_score          NUMERIC(4,2),     -- 0-10 market strength
  triangle_composite    NUMERIC(4,2),     -- Weighted average
  
  -- Two-arm CMA components
  cma_high              NUMERIC(12,2),    -- High comp estimate
  cma_low               NUMERIC(12,2),    -- Low comp estimate  
  cma_median            NUMERIC(12,2),    -- Median comp estimate
  comp_count            INTEGER,          -- Number of comparables
  comp_distance_avg     NUMERIC(8,2),    -- Average distance to comps (miles)
  comp_age_avg          INTEGER,          -- Average age of comp sales (days)
  
  -- ML scoring
  ml_score              NUMERIC(8,4),     -- 0-1 ML confidence score
  ml_model_version      TEXT,             -- Model version used
  ml_features           JSONB,            -- Feature vector used
  
  -- Shapira Formula outputs: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)
  max_bid               NUMERIC(12,2),    -- Calculated maximum bid
  repair_estimate       NUMERIC(12,2),    -- Estimated repair costs
  profit_potential      NUMERIC(12,2),    -- Expected profit
  deal_grade           TEXT,              -- A, B, C, D, F
  
  -- Metadata
  calculated_at         TIMESTAMPTZ DEFAULT now(),
  data_sources          TEXT[],           -- Array of data sources used
  notes                 TEXT,
  
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_bd_case_number ON bid_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_bd_county ON bid_decisions(county_slug);
CREATE INDEX IF NOT EXISTS idx_bd_parcel ON bid_decisions(parcel_id);
CREATE INDEX IF NOT EXISTS idx_bd_deal_grade ON bid_decisions(deal_grade);
CREATE INDEX IF NOT EXISTS idx_bd_calculated_at ON bid_decisions(calculated_at);

-- RLS policies (inherit from multi_county_auctions pattern)
ALTER TABLE bid_decisions ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY IF NOT EXISTS "Enable all for service role" ON bid_decisions
  FOR ALL USING (true);

-- Public read access for authenticated users
CREATE POLICY IF NOT EXISTS "Enable read for authenticated users" ON bid_decisions
  FOR SELECT USING (auth.role() = 'authenticated');

COMMENT ON TABLE bid_decisions IS 'Gold Standard Letter J: Complete deal thesis calculations using Shapira Formula';
COMMENT ON COLUMN bid_decisions.case_number IS 'Foreign key to multi_county_auctions.case_number';
COMMENT ON COLUMN bid_decisions.max_bid IS 'Shapira Formula result: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)';
COMMENT ON COLUMN bid_decisions.triangle_composite IS 'Weighted average: location(40%) + condition(30%) + market(30%)';
COMMENT ON COLUMN bid_decisions.deal_grade IS 'A-F grade based on profit potential and ML confidence';