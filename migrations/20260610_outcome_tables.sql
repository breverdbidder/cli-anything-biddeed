-- ============================================================
-- GOLD STANDARD OUTCOME TABLES
-- Migration: 20260610_outcome_tables.sql
-- Letter B: Verified INDEPENDENT outcomes for foreclosure & tax deed auctions
-- NEVER PropertyOnion-derived - only clerk/platform sources
-- ============================================================

-- Table for verified foreclosure auction outcomes
CREATE TABLE IF NOT EXISTS foreclosure_outcomes (
    id                  BIGSERIAL PRIMARY KEY,
    case_number         TEXT NOT NULL,
    county              TEXT NOT NULL,
    auction_date        DATE NOT NULL,
    outcome_status      TEXT NOT NULL,              -- SOLD | CANCELED | POSTPONED | REDEEMED | WITHDRAWN
    sold_amount         NUMERIC(14,2),              -- final sale price if SOLD
    buyer_type          TEXT,                       -- third_party | plaintiff | county 
    buyer_name          TEXT,                       -- if available from clerk records
    sale_timestamp      TIMESTAMPTZ,                -- exact time of sale completion
    data_source         TEXT NOT NULL,              -- clerk_website | realforeclose_tier1 | court_records
    source_url          TEXT,                       -- proof/audit trail
    verification_date   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_outcome_data    JSONB,                      -- preserve original clerk data
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (county, case_number, auction_date),
    CONSTRAINT chk_outcome_status CHECK (outcome_status IN ('SOLD', 'CANCELED', 'POSTPONED', 'REDEEMED', 'WITHDRAWN')),
    CONSTRAINT chk_data_source_not_propertyonion CHECK (data_source NOT LIKE '%propertyonion%')
);

-- Table for verified tax deed auction outcomes  
CREATE TABLE IF NOT EXISTS tax_deed_outcomes (
    id                  BIGSERIAL PRIMARY KEY,
    certificate_number  TEXT NOT NULL,
    county              TEXT NOT NULL,
    auction_date        DATE NOT NULL,
    outcome_status      TEXT NOT NULL,              -- SOLD | NO_BIDDERS | CANCELED | WITHDRAWN
    sold_amount         NUMERIC(14,2),              -- final bid amount if SOLD
    buyer_name          TEXT,                       -- winning bidder if available
    sale_timestamp      TIMESTAMPTZ,                -- exact time of sale
    data_source         TEXT NOT NULL,              -- clerk_website | realtaxdeed_tier1 | county_records
    source_url          TEXT,
    verification_date   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_outcome_data    JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (county, certificate_number, auction_date),
    CONSTRAINT chk_td_outcome_status CHECK (outcome_status IN ('SOLD', 'NO_BIDDERS', 'CANCELED', 'WITHDRAWN')),
    CONSTRAINT chk_td_data_source_not_propertyonion CHECK (data_source NOT LIKE '%propertyonion%')
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_county ON foreclosure_outcomes(county);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_date ON foreclosure_outcomes(auction_date);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_case ON foreclosure_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_status ON foreclosure_outcomes(outcome_status);

CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_county ON tax_deed_outcomes(county);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_date ON tax_deed_outcomes(auction_date);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_cert ON tax_deed_outcomes(certificate_number);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_status ON tax_deed_outcomes(outcome_status);

-- RLS (row-level security)
ALTER TABLE foreclosure_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_deed_outcomes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "foreclosure_outcomes_read" ON foreclosure_outcomes FOR SELECT USING (true);
CREATE POLICY "tax_deed_outcomes_read" ON tax_deed_outcomes FOR SELECT USING (true);

-- Table comments
COMMENT ON TABLE foreclosure_outcomes IS 
    'VERIFIED foreclosure auction outcomes from INDEPENDENT sources (NOT PropertyOnion). '
    'Required for Letter B of gold standard criteria. Populated by county-specific scrapers.';

COMMENT ON TABLE tax_deed_outcomes IS 
    'VERIFIED tax deed auction outcomes from INDEPENDENT sources (NOT PropertyOnion). ' 
    'Required for Letter B of gold standard criteria. Populated by county-specific scrapers.';