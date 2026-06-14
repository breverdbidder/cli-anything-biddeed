-- SHARD-24 J Generator Migration: bid_decisions table
-- Contract: case_number + arv + max_bid + ml_score + factors[5 keys]
-- Per issue brief evaluator contract requirements

CREATE TABLE IF NOT EXISTS bid_decisions (
    id SERIAL PRIMARY KEY,
    case_number TEXT NOT NULL UNIQUE,
    county_slug TEXT NOT NULL,
    arv DECIMAL(12,2),
    max_bid DECIMAL(12,2), 
    ml_score DECIMAL(5,3),
    ml_model_version TEXT DEFAULT 'shapira_v14',
    factors JSONB,
    repair_estimate DECIMAL(12,2),
    profit_potential DECIMAL(12,2),
    deal_grade TEXT CHECK (deal_grade IN ('A', 'B', 'C', 'D', 'F')),
    data_sources TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints per evaluator contract
    CONSTRAINT valid_factors CHECK (
        factors ? 'distress_location' AND
        factors ? 'distress_property' AND 
        factors ? 'distress_owner' AND
        factors ? 'cma_distressed' AND
        factors ? 'cma_resale'
    )
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON bid_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_county_slug ON bid_decisions(county_slug);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_ml_score ON bid_decisions(ml_score DESC);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_factors ON bid_decisions USING GIN(factors);

-- Comment for documentation
COMMENT ON TABLE bid_decisions IS 'SHARD-24 J Generator: Shapira Formula bid decisions with required factors for gold standard evaluation';
COMMENT ON CONSTRAINT valid_factors ON bid_decisions IS 'Ensures all 5 required factor keys per evaluator contract';