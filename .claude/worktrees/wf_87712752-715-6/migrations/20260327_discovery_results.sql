-- Migration: 20260327_discovery_results.sql
-- Purpose: Shared discovery layer for Exa semantic search results
-- Feeds: ZoneWise county expansion + BidDeed auction intelligence + GTM

CREATE TABLE IF NOT EXISTS discovery_results (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  mode TEXT NOT NULL CHECK (mode IN ('zonewise', 'auction', 'gtm')),
  county TEXT,
  state TEXT DEFAULT 'FL',
  query TEXT NOT NULL,
  url TEXT NOT NULL,
  title TEXT,
  classification TEXT CHECK (classification IN (
    'GIS_PORTAL', 'ZONING_PDF', 'CLERK_SEARCH', 
    'TAX_PORTAL', 'APPRAISER', 'PERMIT_PORTAL',
    'AUCTION_CALENDAR', 'LIEN_SEARCH', 'COMPANY', 'OTHER'
  )),
  confidence NUMERIC(3,2) DEFAULT 0.00,
  highlight_text TEXT,
  exa_score NUMERIC(5,4),
  firecrawl_status TEXT DEFAULT 'pending' 
    CHECK (firecrawl_status IN ('pending', 'queued', 'scraped', 'failed', 'skipped')),
  cost_dollars NUMERIC(6,4) DEFAULT 0.0000,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(mode, county, url)
);

-- Indexes
CREATE INDEX idx_discovery_county ON discovery_results(county, mode);
CREATE INDEX idx_discovery_status ON discovery_results(firecrawl_status);
CREATE INDEX idx_discovery_classification ON discovery_results(classification);
CREATE INDEX idx_discovery_created ON discovery_results(created_at DESC);

-- RLS
ALTER TABLE discovery_results ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access" ON discovery_results
  FOR ALL USING (auth.role() = 'service_role');

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_discovery_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER discovery_results_updated
  BEFORE UPDATE ON discovery_results
  FOR EACH ROW EXECUTE FUNCTION update_discovery_timestamp();

-- View: Discovery stats per county
CREATE OR REPLACE VIEW discovery_county_stats AS
SELECT 
  county,
  mode,
  COUNT(*) as total_discovered,
  COUNT(*) FILTER (WHERE classification = 'GIS_PORTAL') as gis_portals,
  COUNT(*) FILTER (WHERE classification = 'ZONING_PDF') as zoning_pdfs,
  COUNT(*) FILTER (WHERE classification = 'CLERK_SEARCH') as clerk_portals,
  COUNT(*) FILTER (WHERE classification = 'TAX_PORTAL') as tax_portals,
  COUNT(*) FILTER (WHERE firecrawl_status = 'scraped') as scraped,
  COUNT(*) FILTER (WHERE firecrawl_status = 'pending') as pending_scrape,
  ROUND(SUM(cost_dollars), 4) as total_cost,
  MAX(created_at) as last_discovery
FROM discovery_results
GROUP BY county, mode
ORDER BY county;
