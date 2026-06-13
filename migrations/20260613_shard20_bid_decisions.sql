-- SHARD-20 Gold Standard Letter J: Bid Decisions Migration
-- Target counties: charlotte, citrus, broward
-- Required for deal thesis pipeline (Shapira Formula)

-- Ensure bid_decisions table exists with all required columns
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
  
  -- ML scoring (Shapira V14)
  ml_score              NUMERIC(8,4),     -- 0-1 ML confidence score
  ml_model_version      TEXT,             -- Model version used
  ml_features           JSONB,            -- Feature vector used
  
  -- Shapira Formula outputs: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)
  max_bid               NUMERIC(12,2),    -- Calculated maximum bid
  repair_estimate       NUMERIC(12,2),    -- Estimated repair costs
  profit_potential      NUMERIC(12,2),    -- Expected profit
  deal_grade           TEXT,              -- A, B, C, D, F
  
  -- J Letter evaluator contract requirements
  factors               JSONB,            -- Must contain: distress_location, distress_property, distress_owner, cma_distressed, cma_resale
  
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
CREATE INDEX IF NOT EXISTS idx_bd_ml_score ON bid_decisions(ml_score);

-- Index on factors for J evaluator performance
CREATE INDEX IF NOT EXISTS idx_bd_factors_gin ON bid_decisions USING gin(factors);

-- RLS policies (inherit from multi_county_auctions pattern)
ALTER TABLE bid_decisions ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY IF NOT EXISTS "Enable all for service role" ON bid_decisions
  FOR ALL USING (true);

-- Public read access for authenticated users
CREATE POLICY IF NOT EXISTS "Enable read for authenticated users" ON bid_decisions
  FOR SELECT USING (auth.role() = 'authenticated');

-- Specific policy for SHARD-20 counties
CREATE POLICY IF NOT EXISTS "Enable SHARD-20 counties" ON bid_decisions
  FOR ALL USING (county_slug IN ('charlotte', 'citrus', 'broward'));

-- Comments for documentation
COMMENT ON TABLE bid_decisions IS 'Gold Standard Letter J: Complete deal thesis calculations using Shapira Formula';
COMMENT ON COLUMN bid_decisions.case_number IS 'Foreign key to multi_county_auctions.case_number';
COMMENT ON COLUMN bid_decisions.max_bid IS 'Shapira Formula result: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)';
COMMENT ON COLUMN bid_decisions.triangle_composite IS 'Weighted average: location(40%) + condition(30%) + market(30%)';
COMMENT ON COLUMN bid_decisions.deal_grade IS 'A-F grade based on profit potential and ML confidence';
COMMENT ON COLUMN bid_decisions.factors IS 'J evaluator contract: must contain distress_location, distress_property, distress_owner, cma_distressed, cma_resale';
COMMENT ON COLUMN bid_decisions.ml_score IS 'Shapira V14 ML confidence score (AUC .78)';

-- Function to validate factors JSON structure for J letter compliance
CREATE OR REPLACE FUNCTION validate_bid_decisions_factors(factors_json JSONB)
RETURNS BOOLEAN AS $$
BEGIN
  -- Check that all required factor keys are present
  RETURN (
    factors_json ? 'distress_location' AND
    factors_json ? 'distress_property' AND 
    factors_json ? 'distress_owner' AND
    factors_json ? 'cma_distressed' AND
    factors_json ? 'cma_resale'
  );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION validate_bid_decisions_factors IS 'Validates factors JSON has all required keys for J letter evaluation';

-- Trigger to validate factors on insert/update  
CREATE OR REPLACE FUNCTION bid_decisions_validate_factors_trigger()
RETURNS TRIGGER AS $$
BEGIN
  -- Only validate if factors is not null
  IF NEW.factors IS NOT NULL THEN
    IF NOT validate_bid_decisions_factors(NEW.factors) THEN
      RAISE EXCEPTION 'Invalid factors JSON: missing required keys (distress_location, distress_property, distress_owner, cma_distressed, cma_resale)';
    END IF;
  END IF;
  
  -- Update the updated_at timestamp
  NEW.updated_at = NOW();
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER bid_decisions_validate_factors
  BEFORE INSERT OR UPDATE ON bid_decisions
  FOR EACH ROW
  EXECUTE FUNCTION bid_decisions_validate_factors_trigger();

-- View for J letter evaluation (what pencil_dod_evaluate_county looks for)
CREATE OR REPLACE VIEW v_bid_decisions_j_metrics AS
SELECT 
  mca.county_slug,
  COUNT(mca.case_number) as total_auctions,
  COUNT(bd.case_number) as auctions_with_decisions,
  COUNT(CASE 
    WHEN bd.arv IS NOT NULL 
      AND bd.max_bid IS NOT NULL 
      AND bd.ml_score IS NOT NULL 
      AND validate_bid_decisions_factors(bd.factors) 
    THEN 1 
  END) as complete_decisions,
  ROUND(
    COUNT(CASE 
      WHEN bd.arv IS NOT NULL 
        AND bd.max_bid IS NOT NULL 
        AND bd.ml_score IS NOT NULL 
        AND validate_bid_decisions_factors(bd.factors) 
      THEN 1 
    END) * 100.0 / NULLIF(COUNT(mca.case_number), 0),
    2
  ) as j_metric_percentage
FROM multi_county_auctions mca
LEFT JOIN bid_decisions bd ON mca.case_number = bd.case_number
WHERE mca.county_slug IN ('charlotte', 'citrus', 'broward')
GROUP BY mca.county_slug;

COMMENT ON VIEW v_bid_decisions_j_metrics IS 'J letter metrics for SHARD-20 counties: bid_decisions completeness per Shapira Formula contract';

-- SHARD-20 specific verification query for ULTRALOOP protocol
-- This can be used in verification scripts to confirm J letter improvement
CREATE OR REPLACE FUNCTION shard20_j_verification(county_name TEXT)
RETURNS TABLE(
  county TEXT,
  total_auctions BIGINT,
  complete_decisions BIGINT,
  j_metric_percentage NUMERIC,
  sample_case_numbers TEXT[],
  verification_timestamp TIMESTAMPTZ
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    v.county_slug::TEXT,
    v.total_auctions,
    v.complete_decisions,
    v.j_metric_percentage,
    ARRAY(
      SELECT bd.case_number 
      FROM bid_decisions bd 
      JOIN multi_county_auctions mca ON bd.case_number = mca.case_number
      WHERE mca.county_slug = county_name 
        AND bd.arv IS NOT NULL 
        AND bd.max_bid IS NOT NULL 
        AND bd.ml_score IS NOT NULL 
        AND validate_bid_decisions_factors(bd.factors)
      LIMIT 5
    ) as sample_case_numbers,
    NOW() as verification_timestamp
  FROM v_bid_decisions_j_metrics v
  WHERE v.county_slug = county_name;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION shard20_j_verification IS 'ULTRALOOP verification function for SHARD-20 J letter status with evidence';

-- Log this migration
INSERT INTO migration_log (migration_name, applied_at, description)
VALUES (
  '20260613_shard20_bid_decisions',
  NOW(),
  'SHARD-20 bid_decisions table setup for J letter (charlotte, citrus, broward) - Shapira Formula pipeline'
) ON CONFLICT (migration_name) DO NOTHING;