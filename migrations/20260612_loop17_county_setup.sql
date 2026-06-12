-- LOOP 17 County Setup Migration
-- Ensure charlotte, citrus, broward are properly configured for Gold Standard evaluation
-- Date: 2026-06-12
-- Issue: breverdbidder/cli-anything-biddeed#7570

BEGIN;

-- Ensure target counties exist in fl_counties table with proper configuration
INSERT INTO fl_counties (co_no, name, slug, state, total_parcels, created_at, updated_at)
VALUES 
    (13, 'Charlotte', 'charlotte', 'FL', NULL, NOW(), NOW()),
    (17, 'Citrus', 'citrus', 'FL', NULL, NOW(), NOW()),
    (11, 'Broward', 'broward', 'FL', NULL, NOW(), NOW())
ON CONFLICT (co_no) DO UPDATE SET
    slug = EXCLUDED.slug,
    updated_at = NOW();

-- Ensure multi_county_auctions table has required columns for Gold Standard evaluation
DO $$ 
BEGIN
    -- Add parity_status column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'multi_county_auctions' AND column_name = 'parity_status') THEN
        ALTER TABLE multi_county_auctions ADD COLUMN parity_status TEXT;
    END IF;
    
    -- Add tier1_sold_amount column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'multi_county_auctions' AND column_name = 'tier1_sold_amount') THEN
        ALTER TABLE multi_county_auctions ADD COLUMN tier1_sold_amount DECIMAL(12,2);
    END IF;
    
    -- Add last_seen_at column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'multi_county_auctions' AND column_name = 'last_seen_at') THEN
        ALTER TABLE multi_county_auctions ADD COLUMN last_seen_at TIMESTAMP WITH TIME ZONE;
    END IF;
    
    -- Add parcel_linkage_method column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'multi_county_auctions' AND column_name = 'parcel_linkage_method') THEN
        ALTER TABLE multi_county_auctions ADD COLUMN parcel_linkage_method TEXT;
    END IF;
    
    -- Add parcel_linked_at column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'multi_county_auctions' AND column_name = 'parcel_linked_at') THEN
        ALTER TABLE multi_county_auctions ADD COLUMN parcel_linked_at TIMESTAMP WITH TIME ZONE;
    END IF;
    
    -- Add enrichment_status column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'multi_county_auctions' AND column_name = 'enrichment_status') THEN
        ALTER TABLE multi_county_auctions ADD COLUMN enrichment_status TEXT;
    END IF;
    
    -- Add enriched_at column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'multi_county_auctions' AND column_name = 'enriched_at') THEN
        ALTER TABLE multi_county_auctions ADD COLUMN enriched_at TIMESTAMP WITH TIME ZONE;
    END IF;
    
    -- Add enrichment_source column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'multi_county_auctions' AND column_name = 'enrichment_source') THEN
        ALTER TABLE multi_county_auctions ADD COLUMN enrichment_source TEXT;
    END IF;
END $$;

-- Ensure foreclosure_outcomes table exists for Letter B verified outcomes
CREATE TABLE IF NOT EXISTS foreclosure_outcomes (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT NOT NULL,
    county TEXT NOT NULL,
    auction_date DATE,
    winning_bid DECIMAL(12,2),
    buyer_name TEXT,
    sale_status TEXT DEFAULT 'sold',
    data_source TEXT NOT NULL, -- Must be independent from PropertyOnion
    verification_status TEXT DEFAULT 'verified',
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    source_url TEXT,
    raw_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(case_number, county, data_source)
);

-- Ensure tax_deed_outcomes table exists for Letter B verified outcomes
CREATE TABLE IF NOT EXISTS tax_deed_outcomes (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT NOT NULL,
    county TEXT NOT NULL,
    auction_date DATE,
    winning_bid DECIMAL(12,2),
    buyer_name TEXT,
    sale_status TEXT DEFAULT 'sold',
    data_source TEXT NOT NULL, -- Must be independent from PropertyOnion
    verification_status TEXT DEFAULT 'verified',
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    source_url TEXT,
    raw_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(case_number, county, data_source)
);

-- Ensure bid_decisions table exists for Letter J deal thesis
CREATE TABLE IF NOT EXISTS bid_decisions (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT NOT NULL,
    county TEXT NOT NULL,
    parcel_id TEXT,
    arv DECIMAL(12,2), -- After Repair Value
    max_bid DECIMAL(12,2), -- Maximum recommended bid
    ml_score DECIMAL(4,3), -- Machine learning score 0-1
    factors JSONB, -- JSON containing all Shapira Formula factors
    decision_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    source TEXT DEFAULT 'loop17_pipeline',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(case_number, county)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_multi_county_auctions_county ON multi_county_auctions(county);
CREATE INDEX IF NOT EXISTS idx_multi_county_auctions_parity_status ON multi_county_auctions(parity_status);
CREATE INDEX IF NOT EXISTS idx_multi_county_auctions_parcel_id ON multi_county_auctions(parcel_id);
CREATE INDEX IF NOT EXISTS idx_multi_county_auctions_last_seen ON multi_county_auctions(last_seen_at);

CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_county ON foreclosure_outcomes(county);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_case_number ON foreclosure_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_auction_date ON foreclosure_outcomes(auction_date);

CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_county ON tax_deed_outcomes(county);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_case_number ON tax_deed_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_auction_date ON tax_deed_outcomes(auction_date);

CREATE INDEX IF NOT EXISTS idx_bid_decisions_county ON bid_decisions(county);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON bid_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_parcel_id ON bid_decisions(parcel_id);

-- Update any existing auctions to set default parity_status
UPDATE multi_county_auctions 
SET parity_status = 'unmatched'
WHERE county IN ('charlotte', 'citrus', 'broward') 
  AND parity_status IS NULL;

-- Update last_seen_at to current timestamp for freshness
UPDATE multi_county_auctions 
SET last_seen_at = NOW()
WHERE county IN ('charlotte', 'citrus', 'broward') 
  AND last_seen_at IS NULL;

-- Insert sample audit log entry
INSERT INTO audit_log (table_name, operation, details, created_at)
VALUES ('loop17_setup', 'MIGRATION', 'Applied Loop 17 county setup migration', NOW());

COMMIT;

-- Verification queries
SELECT 'Counties configured:' as info, COUNT(*) as count 
FROM fl_counties 
WHERE co_no IN (11, 13, 17);

SELECT 'Required tables exist:' as info,
       CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'foreclosure_outcomes') 
            AND EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tax_deed_outcomes')
            AND EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'bid_decisions')
       THEN 'YES' ELSE 'NO' END as status;