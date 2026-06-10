-- ============================================================
-- BID DECISIONS TABLE (Letter J - Deal Thesis)
-- Migration: 20260610_bid_decisions.sql
-- Shapira Formula implementation for gold standard Letter J
-- ============================================================

CREATE TABLE IF NOT EXISTS bid_decisions (
    id                  BIGSERIAL PRIMARY KEY,
    auction_id          BIGINT NOT NULL,                -- FK to multi_county_auctions.id
    case_number         TEXT NOT NULL,
    county              TEXT NOT NULL,
    
    -- Core Shapira Formula components
    arv                 NUMERIC(14,2),                  -- After Repair Value
    arv_confidence      TEXT,                           -- high | medium | low | none
    max_bid             NUMERIC(14,2),                  -- (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)
    max_bid_confidence  TEXT,                           -- calculated | estimated | none
    
    -- ML scoring
    ml_score            NUMERIC(4,3),                   -- 0.000-1.000 confidence score
    ml_components       JSONB,                          -- breakdown of score components
    
    -- Shapira Triangle factors  
    triangle_factors    JSONB NOT NULL,                 -- {market_factor, property_factor, legal_factor}
    
    -- Two-arm CMA results
    two_arm_cma         JSONB NOT NULL,                 -- {sold_arm, active_arm, valuation_range}
    
    -- Metadata and audit
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    algorithm_version   TEXT NOT NULL DEFAULT 'shapira_v1',
    input_data          JSONB,                          -- source data used for calculations
    
    -- Constraints
    UNIQUE (auction_id),
    CONSTRAINT chk_arv_positive CHECK (arv IS NULL OR arv > 0),
    CONSTRAINT chk_max_bid_positive CHECK (max_bid IS NULL OR max_bid >= 0),
    CONSTRAINT chk_ml_score_range CHECK (ml_score IS NULL OR (ml_score >= 0 AND ml_score <= 1))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_bid_decisions_auction_id ON bid_decisions(auction_id);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_county ON bid_decisions(county);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON bid_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_generated_at ON bid_decisions(generated_at);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_ml_score ON bid_decisions(ml_score);

-- RLS (row-level security)
ALTER TABLE bid_decisions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "bid_decisions_read" ON bid_decisions FOR SELECT USING (true);

-- Table comment
COMMENT ON TABLE bid_decisions IS 
    'Shapira Formula bid decisions for Letter J gold standard. Contains ARV, max bid, ML score, triangle factors, and two-arm CMA for each auction. Required for ≥95% completion rate.';