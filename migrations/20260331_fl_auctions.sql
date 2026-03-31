-- ============================================================
-- FL AUCTIONS TABLE
-- Migration: 20260331_fl_auctions.sql
-- 67-county Florida auction data from realforeclose.com + realtaxdeed.com
-- ============================================================

CREATE TABLE IF NOT EXISTS fl_auctions (
    id              BIGSERIAL PRIMARY KEY,
    county          TEXT NOT NULL,              -- e.g. "brevard"
    co_no           INTEGER,                    -- FL DOR county number (1-67)
    sale_type       TEXT NOT NULL,              -- 'fc' = foreclosure, 'td' = tax deed
    case_number     TEXT NOT NULL,
    auction_date    DATE NOT NULL,
    status          TEXT NOT NULL DEFAULT 'SCHEDULED',
    plaintiff       TEXT,
    defendant       TEXT,
    address         TEXT,
    parcel_id       TEXT,
    judgment_amount NUMERIC(14,2),
    opening_bid     NUMERIC(14,2),
    details         TEXT,                       -- raw details column from site
    source_url      TEXT,
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (county, sale_type, case_number, auction_date)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_fl_auctions_county        ON fl_auctions(county);
CREATE INDEX IF NOT EXISTS idx_fl_auctions_auction_date  ON fl_auctions(auction_date);
CREATE INDEX IF NOT EXISTS idx_fl_auctions_sale_type     ON fl_auctions(sale_type);
CREATE INDEX IF NOT EXISTS idx_fl_auctions_county_date   ON fl_auctions(county, auction_date);
CREATE INDEX IF NOT EXISTS idx_fl_auctions_scraped_at    ON fl_auctions(scraped_at);
CREATE INDEX IF NOT EXISTS idx_fl_auctions_status        ON fl_auctions(status);

-- Enable RLS (row-level security) but allow service role full access
ALTER TABLE fl_auctions ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read
CREATE POLICY "fl_auctions_read" ON fl_auctions
    FOR SELECT USING (true);

-- Only service role can insert/update (enforced by API key used in scraper)
COMMENT ON TABLE fl_auctions IS
    '67-county FL auction data scraped from realforeclose.com (fc) and realtaxdeed.com (td). '
    'Populated daily by summit-fl-auctions GHA workflow.';
