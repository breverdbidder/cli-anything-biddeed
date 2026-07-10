-- SHARD-28 Migration: Ensure bid_decisions table exists with proper schema
-- Purpose: Support Letter J (Shapira deal thesis) evaluation
-- Target: brevard J=0.0, duval J=0.0 → 95%+ completion

-- Create bid_decisions table if not exists
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

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_bid_decisions_county ON bid_decisions (county_slug);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_parcel ON bid_decisions (parcel_id);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_grade ON bid_decisions (deal_grade);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_ml_score ON bid_decisions (ml_score DESC);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_created ON bid_decisions (created_at DESC);

-- GIN index for factors JSONB
CREATE INDEX IF NOT EXISTS idx_bid_decisions_factors ON bid_decisions USING GIN (factors);

-- Enable RLS
ALTER TABLE bid_decisions ENABLE ROW LEVEL SECURITY;

-- RLS policies for authenticated access
CREATE POLICY IF NOT EXISTS "Enable read access for authenticated users" ON bid_decisions
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY IF NOT EXISTS "Enable insert for authenticated users" ON bid_decisions
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY IF NOT EXISTS "Enable update for authenticated users" ON bid_decisions
    FOR UPDATE USING (auth.role() = 'authenticated');

-- Comments
COMMENT ON TABLE bid_decisions IS 'Shapira deal evaluation decisions for Letter J gold standard criterion';
COMMENT ON COLUMN bid_decisions.case_number IS 'Foreign key to multi_county_auctions.case_number';
COMMENT ON COLUMN bid_decisions.arv IS 'After Repair Value estimate';
COMMENT ON COLUMN bid_decisions.max_bid IS 'Maximum recommended bid per Shapira Formula';
COMMENT ON COLUMN bid_decisions.ml_score IS 'ML confidence score from Shapira V14 model (0-1)';
COMMENT ON COLUMN bid_decisions.factors IS 'Required JSON with 5 keys: distress_location, distress_property, distress_owner, cma_distressed, cma_resale';

-- Validation function for factors JSON structure
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

-- Add check constraint using validation function
ALTER TABLE bid_decisions 
ADD CONSTRAINT IF NOT EXISTS bid_decisions_valid_factors 
CHECK (validate_bid_decision_factors(factors));

-- Create materialized view for J metric calculation
CREATE MATERIALIZED VIEW IF NOT EXISTS v_letter_j_metrics AS
SELECT 
    county_slug,
    COUNT(*) as total_auctions_with_decisions,
    COUNT(CASE WHEN arv IS NOT NULL 
                 AND max_bid IS NOT NULL 
                 AND ml_score IS NOT NULL 
                 AND validate_bid_decision_factors(factors) 
               THEN 1 END) as complete_decisions,
    ROUND(
        COUNT(CASE WHEN arv IS NOT NULL 
                     AND max_bid IS NOT NULL 
                     AND ml_score IS NOT NULL 
                     AND validate_bid_decision_factors(factors) 
                   THEN 1 END) * 100.0 / 
        GREATEST(COUNT(*), 1), 2
    ) as j_metric_percentage
FROM bid_decisions bd
JOIN multi_county_auctions mca ON bd.case_number = mca.case_number
WHERE mca.auction_status IN ('sold', 'no_sale', 'canceled')
GROUP BY county_slug;

-- Create index on the materialized view  
CREATE UNIQUE INDEX IF NOT EXISTS idx_letter_j_metrics_county ON v_letter_j_metrics (county_slug);

-- Refresh function for the materialized view
CREATE OR REPLACE FUNCTION refresh_letter_j_metrics()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW v_letter_j_metrics;
END;
$$ LANGUAGE plpgsql;