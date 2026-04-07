-- ============================================================
-- AUCTION OWNER INTEL TABLE
-- Migration: 20260407_auction_owner_intel.sql
-- Issue: https://github.com/breverdbidder/cli-anything-biddeed/issues/387
-- Owner OSINT enrichment from zw_parcels for auction defendants
-- ============================================================

CREATE TABLE IF NOT EXISTS auction_owner_intel (
    id                  BIGSERIAL PRIMARY KEY,
    auction_id          BIGINT,                     -- FK to fl_auctions.id (nullable for flexibility)
    case_number         TEXT NOT NULL,
    county              TEXT NOT NULL,
    defendant           TEXT NOT NULL,
    classification      TEXT NOT NULL DEFAULT 'UNKNOWN',  -- DISTRESSED_HOMEOWNER | INVESTOR | CORPORATE | ESTATE | UNKNOWN
    match_count         INTEGER DEFAULT 0,          -- parcels matched in zw_parcels
    total_portfolio_value INTEGER DEFAULT 0,        -- SUM(val_market) across all matched parcels
    parcels_owned       JSONB,                      -- array of {pin, site_addr, val_market, luse_code, ...}
    is_homestead        BOOLEAN,                    -- any parcel has homestead (luse_code 001x)
    is_out_of_state     BOOLEAN DEFAULT FALSE,      -- owner_state != 'FL'
    is_corporate        BOOLEAN DEFAULT FALSE,      -- LLC/INC/CORP/TRUST in name
    owner_state         TEXT,                       -- mailing state from zw_parcels
    last_sale_date      DATE,                       -- most recent sale_date across portfolio
    days_since_last_sale INTEGER,                   -- days from last_sale_date to now
    auction_date        DATE,
    judgment_amount     NUMERIC(14,2),
    plaintiff           TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (county, case_number)
);

CREATE INDEX IF NOT EXISTS idx_aoi_county ON auction_owner_intel(county);
CREATE INDEX IF NOT EXISTS idx_aoi_classification ON auction_owner_intel(classification);
CREATE INDEX IF NOT EXISTS idx_aoi_defendant ON auction_owner_intel(defendant);
CREATE INDEX IF NOT EXISTS idx_aoi_auction_date ON auction_owner_intel(auction_date);
CREATE INDEX IF NOT EXISTS idx_aoi_match_count ON auction_owner_intel(match_count);

ALTER TABLE auction_owner_intel ENABLE ROW LEVEL SECURITY;

CREATE POLICY "aoi_read" ON auction_owner_intel
    FOR SELECT USING (true);

COMMENT ON TABLE auction_owner_intel IS
    'Owner OSINT enrichment: classifies auction defendants using zw_parcels ownership data. '
    'Categories: DISTRESSED_HOMEOWNER, INVESTOR, CORPORATE, ESTATE, UNKNOWN. '
    'Populated by scripts/owner_osint.py (issue #387).';
