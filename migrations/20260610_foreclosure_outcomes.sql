-- ============================================================
-- GOLD STANDARD Letter B: Verified Foreclosure Outcomes Table
-- Migration: 20260610_foreclosure_outcomes.sql
-- 
-- Purpose: Track verified auction outcomes from INDEPENDENT clerk sources
-- Requirement: ≥95% of closed auctions have outcome from clerk source (NOT PropertyOnion-derived)
-- ============================================================

-- Foreclosure outcomes table for verified results from clerk sources
CREATE TABLE IF NOT EXISTS foreclosure_outcomes (
    id                  BIGSERIAL PRIMARY KEY,
    county              TEXT NOT NULL,              -- e.g. "charlotte", "brevard" 
    auction_date        DATE NOT NULL,              -- date of auction
    case_number         TEXT,                       -- foreclosure case number
    parcel_id           TEXT,                       -- property parcel identifier
    
    -- Outcome details
    auction_status      TEXT NOT NULL,              -- SOLD_3RD_PARTY, SOLD_PLAINTIFF, SOLD_CERT_HOLDER, REDEEMED, CANCELED, POSTPONED, STRUCK_OFF, LISTED
    winning_bid         NUMERIC(14,2),              -- final sale amount if sold
    sold_to             TEXT,                       -- buyer type: "3rd Party", "Plaintiff", "Certificate Holder", etc.
    sold_timestamp_text TEXT,                       -- raw timestamp from clerk source
    
    -- Property details
    property_address    TEXT,                       -- property address
    opening_bid_text    TEXT,                       -- opening bid amount as text
    assessed_value_text TEXT,                       -- assessed value as text
    
    -- Source tracking
    data_source         TEXT NOT NULL,              -- e.g. "charlotte_realforeclose", "brevard_clerk"
    raw_status          TEXT,                       -- raw status text from source
    sold_amount_text    TEXT,                       -- raw amount text before parsing
    parse_confidence    TEXT CHECK (parse_confidence IN ('high', 'partial', 'low')),
    raw_segment         TEXT,                       -- raw data segment for debugging
    scraped_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE (county, case_number, auction_date, data_source),
    CONSTRAINT foreclosure_outcomes_identifier_check 
        CHECK (case_number IS NOT NULL OR parcel_id IS NOT NULL)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_fo_county_date         ON foreclosure_outcomes(county, auction_date);
CREATE INDEX IF NOT EXISTS idx_fo_case_number         ON foreclosure_outcomes(case_number) WHERE case_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fo_parcel_id          ON foreclosure_outcomes(parcel_id) WHERE parcel_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fo_auction_status     ON foreclosure_outcomes(auction_status);
CREATE INDEX IF NOT EXISTS idx_fo_data_source        ON foreclosure_outcomes(data_source);
CREATE INDEX IF NOT EXISTS idx_fo_scraped_at         ON foreclosure_outcomes(scraped_at);

-- Enable RLS (row-level security) 
ALTER TABLE foreclosure_outcomes ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read
CREATE POLICY "foreclosure_outcomes_read" ON foreclosure_outcomes
    FOR SELECT USING (true);

-- Only service role can insert/update (enforced by API key)
CREATE POLICY "foreclosure_outcomes_write" ON foreclosure_outcomes
    FOR ALL TO service_role USING (true);

-- Comments for documentation
COMMENT ON TABLE foreclosure_outcomes IS
    'Verified foreclosure auction outcomes from INDEPENDENT clerk sources (NOT PropertyOnion-derived). '
    'Used for Gold Standard Letter B: ≥95% verified outcomes requirement.';

COMMENT ON COLUMN foreclosure_outcomes.auction_status IS
    'Canonicalized auction outcome: SOLD_3RD_PARTY, SOLD_PLAINTIFF, SOLD_CERT_HOLDER, REDEEMED, CANCELED, POSTPONED, STRUCK_OFF, LISTED';

COMMENT ON COLUMN foreclosure_outcomes.data_source IS
    'Independent clerk data source identifier. Must NOT be PropertyOnion-derived for Gold Standard compliance.';

COMMENT ON COLUMN foreclosure_outcomes.parse_confidence IS
    'Extraction confidence: high (case_number + opening_bid + status), partial (missing some fields), low (minimal data)';

-- Insert initial tracking record
INSERT INTO insights (type, details, timestamp) VALUES (
    'migration_applied',
    '{"migration": "20260610_foreclosure_outcomes.sql", "purpose": "Gold Standard Letter B - verified outcomes table"}',
    NOW()
) ON CONFLICT DO NOTHING;