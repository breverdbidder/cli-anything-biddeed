-- ============================================================
-- LETTER B: Verified Independent Outcomes Tables
-- Migration: 20260610_letter_b_verified_outcomes.sql
-- Purpose: Support FL Gold Standard Criterion B (≥95% verified outcomes)
-- ============================================================

-- Table for verified tax deed sale outcomes from independent clerk sources
CREATE TABLE IF NOT EXISTS tax_deed_outcomes (
    id              BIGSERIAL PRIMARY KEY,
    county          TEXT NOT NULL,
    case_number     TEXT NOT NULL,
    auction_date    DATE NOT NULL,
    verified_outcome TEXT NOT NULL,          -- 'sold', 'no_sale', 'cancelled', 'postponed'
    sale_price      NUMERIC(14,2),           -- NULL if no_sale
    buyer_name      TEXT,                    -- winner name if sold
    data_source     TEXT NOT NULL,           -- e.g. 'brevard_clerk', 'charlotte_clerk'
    source_url      TEXT,                    -- URL where outcome was verified
    verified_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_data        JSONB,                   -- raw clerk record for audit
    UNIQUE (county, case_number, auction_date)
);

-- Table for verified foreclosure sale outcomes from independent clerk sources  
CREATE TABLE IF NOT EXISTS foreclosure_outcomes (
    id              BIGSERIAL PRIMARY KEY,
    county          TEXT NOT NULL,
    case_number     TEXT NOT NULL,
    auction_date    DATE NOT NULL,
    verified_outcome TEXT NOT NULL,          -- 'sold', 'no_sale', 'cancelled', 'postponed'
    sale_price      NUMERIC(14,2),           -- NULL if no_sale
    buyer_name      TEXT,                    -- winner name if sold
    certificate_number TEXT,                 -- certificate of sale number
    data_source     TEXT NOT NULL,           -- e.g. 'brevard_clerk_docket', 'charlotte_clerk'
    source_url      TEXT,                    -- URL where outcome was verified
    verified_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_data        JSONB,                   -- raw clerk record for audit
    UNIQUE (county, case_number, auction_date)
);

-- Indexes for efficient lookups during gold standard evaluation
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_county ON tax_deed_outcomes(county);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_date ON tax_deed_outcomes(auction_date);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_lookup ON tax_deed_outcomes(county, case_number, auction_date);

CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_county ON foreclosure_outcomes(county);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_date ON foreclosure_outcomes(auction_date);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_lookup ON foreclosure_outcomes(county, case_number, auction_date);

-- Enable RLS (row-level security) 
ALTER TABLE tax_deed_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE foreclosure_outcomes ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read
CREATE POLICY "tax_deed_outcomes_read" ON tax_deed_outcomes
    FOR SELECT USING (true);

CREATE POLICY "foreclosure_outcomes_read" ON foreclosure_outcomes
    FOR SELECT USING (true);

-- Comments documenting Letter B requirements
COMMENT ON TABLE tax_deed_outcomes IS
    'Letter B: Verified tax deed sale outcomes from INDEPENDENT clerk sources. '
    'data_source must NOT be PropertyOnion-derived. Required for Gold Standard Criterion B.';

COMMENT ON TABLE foreclosure_outcomes IS
    'Letter B: Verified foreclosure sale outcomes from INDEPENDENT clerk sources. '
    'For Brevard: clerk-recorded sale results from courthouse docket, NOT RealAuction. '
    'Required for Gold Standard Criterion B (≥95% verified outcomes).';

COMMENT ON COLUMN foreclosure_outcomes.data_source IS
    'CRITICAL: Must be independent clerk source. PropertyOnion-derived = HARD FAIL of canon.';

COMMENT ON COLUMN tax_deed_outcomes.data_source IS
    'CRITICAL: Must be independent clerk source. PropertyOnion-derived = HARD FAIL of canon.';