-- SHARD-30 Migration: Setup bid_decisions table for my assigned counties
-- Purpose: Support Letter J (Shapira deal thesis) evaluation
-- Target: charlotte, volusia, jackson, seminole, hardee
-- Priority: J=0.0% → 95%+ completion (highest impact - all 5 counties failing)

-- Ensure bid_decisions table exists (reference latest schema)
CREATE TABLE IF NOT EXISTS bid_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_number TEXT NOT NULL UNIQUE,
    county_slug TEXT NOT NULL,
    parcel_id TEXT,
    
    -- Core Shapira formula components (required by evaluator contract)
    arv DECIMAL(12,2),
    max_bid DECIMAL(12,2),
    ml_score DECIMAL(5,4),
    ml_model_version TEXT,
    factors JSONB, -- Must contain all 5 keys: distress_location, distress_property, distress_owner, cma_distressed, cma_resale
    
    -- Additional decision factors
    repair_estimate DECIMAL(12,2),
    profit_potential DECIMAL(12,2),
    deal_grade TEXT,
    confidence_score DECIMAL(3,2),
    
    -- Metadata
    data_sources TEXT[],
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT bid_decisions_valid_ml_score CHECK (ml_score BETWEEN 0 AND 1),
    CONSTRAINT bid_decisions_valid_confidence CHECK (confidence_score BETWEEN 0 AND 1),
    CONSTRAINT bid_decisions_valid_grade CHECK (deal_grade IN ('A', 'B', 'C', 'D', 'F'))
);

-- Create performance indexes
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON bid_decisions (case_number);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_county ON bid_decisions (county_slug);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_parcel ON bid_decisions (parcel_id);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_grade ON bid_decisions (deal_grade);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_ml_score ON bid_decisions (ml_score DESC);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_created ON bid_decisions (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_factors ON bid_decisions USING GIN (factors);

-- Validation function for the required 5 factor keys
CREATE OR REPLACE FUNCTION validate_bid_decision_factors(factors_json JSONB)
RETURNS BOOLEAN AS $$
BEGIN
    -- Check that all required factor keys exist
    IF NOT (factors_json ? 'distress_location' AND 
            factors_json ? 'distress_property' AND 
            factors_json ? 'distress_owner' AND 
            factors_json ? 'cma_distressed' AND 
            factors_json ? 'cma_resale') THEN
        RETURN FALSE;
    END IF;
    
    -- Validate numeric values where expected
    IF NOT (jsonb_typeof(factors_json->'distress_location') IN ('number') AND
            jsonb_typeof(factors_json->'distress_property') IN ('number') AND  
            jsonb_typeof(factors_json->'distress_owner') IN ('number') AND
            jsonb_typeof(factors_json->'cma_distressed') IN ('number') AND
            jsonb_typeof(factors_json->'cma_resale') IN ('number')) THEN
        RETURN FALSE;
    END IF;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Add check constraint for factors validation
ALTER TABLE bid_decisions 
ADD CONSTRAINT IF NOT EXISTS bid_decisions_valid_factors 
CHECK (validate_bid_decision_factors(factors));

-- Row Level Security
ALTER TABLE bid_decisions ENABLE ROW LEVEL SECURITY;

-- Policies for SHARD-30 counties access
CREATE POLICY IF NOT EXISTS "Enable SHARD-30 counties read" ON bid_decisions
    FOR SELECT USING (county_slug IN ('charlotte', 'volusia', 'jackson', 'seminole', 'hardee'));

CREATE POLICY IF NOT EXISTS "Enable SHARD-30 counties insert" ON bid_decisions
    FOR INSERT WITH CHECK (county_slug IN ('charlotte', 'volusia', 'jackson', 'seminole', 'hardee'));

CREATE POLICY IF NOT EXISTS "Enable SHARD-30 counties update" ON bid_decisions
    FOR UPDATE USING (county_slug IN ('charlotte', 'volusia', 'jackson', 'seminole', 'hardee'));

-- Table and column comments
COMMENT ON TABLE bid_decisions IS 'SHARD-30: Shapira deal evaluation decisions for Letter J gold standard criterion';
COMMENT ON COLUMN bid_decisions.case_number IS 'Foreign key to multi_county_auctions.case_number';
COMMENT ON COLUMN bid_decisions.arv IS 'After Repair Value estimate (Florida market analysis)';
COMMENT ON COLUMN bid_decisions.max_bid IS 'Maximum recommended bid per Shapira Formula: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)';
COMMENT ON COLUMN bid_decisions.ml_score IS 'ML confidence score from Shapira V14 model (AUC 0.78)';
COMMENT ON COLUMN bid_decisions.factors IS 'Required JSON with 5 keys per evaluator contract: distress_location, distress_property, distress_owner, cma_distressed, cma_resale';
COMMENT ON COLUMN bid_decisions.county_slug IS 'SHARD-30 target counties: charlotte, volusia, jackson, seminole, hardee';

-- Insert migration log
INSERT INTO migration_log (migration_id, description, applied_at)
VALUES (
  '20260615_shard30_bid_decisions_setup',
  'SHARD-30 bid_decisions table setup for J letter (charlotte, volusia, jackson, seminole, hardee) - Shapira Formula pipeline',
  NOW()
) ON CONFLICT (migration_id) DO NOTHING;