-- ============================================================
-- INDEPENDENT VERIFIED OUTCOMES SCHEMA
-- Migration: 20260610_independent_outcomes.sql
-- For Gold Standard Letter B: verified INDEPENDENT outcomes
-- ============================================================

-- Foreclosure outcomes (independent clerk-source verification)
CREATE TABLE IF NOT EXISTS foreclosure_outcomes (
  id                  SERIAL PRIMARY KEY,
  case_number         TEXT NOT NULL,
  county              TEXT NOT NULL,
  auction_date        DATE NOT NULL,
  status              TEXT NOT NULL,                    -- sold, cancelled, postponed, etc
  winning_bid         NUMERIC(15,2),                   -- sale price if sold
  buyer_name          TEXT,                            -- winning bidder name
  buyer_type          TEXT,                            -- third_party, plaintiff, etc
  sale_confirmed      BOOLEAN DEFAULT NULL,            -- whether sale was confirmed by court
  confirmation_date   DATE,                           -- when sale was confirmed
  data_source         TEXT NOT NULL,                   -- clerk_portal, realforeclose_api, etc - MUST be independent
  clerk_source_url    TEXT,                            -- exact URL scraped from
  scraped_at          TIMESTAMPTZ DEFAULT now(),
  scraped_by          TEXT DEFAULT 'shard_4_scraper',
  raw_data            JSONB,                           -- full HTML/API response for audit
  verified            BOOLEAN DEFAULT false,           -- manual verification flag
  UNIQUE(case_number, county, auction_date, data_source)
);

-- Tax deed outcomes (independent clerk-source verification)  
CREATE TABLE IF NOT EXISTS tax_deed_outcomes (
  id                  SERIAL PRIMARY KEY,
  case_number         TEXT NOT NULL,
  county              TEXT NOT NULL,
  sale_date           DATE NOT NULL,
  status              TEXT NOT NULL,                    -- sold, no_bidders, cancelled, etc
  winning_bid         NUMERIC(15,2),                   -- sale price if sold
  buyer_name          TEXT,                            -- winning bidder name
  buyer_type          TEXT,                            -- individual, investor, etc
  minimum_bid         NUMERIC(15,2),                   -- minimum bid required
  data_source         TEXT NOT NULL,                   -- clerk_portal, tax_deed_api, etc - MUST be independent
  clerk_source_url    TEXT,                            -- exact URL scraped from
  scraped_at          TIMESTAMPTZ DEFAULT now(),
  scraped_by          TEXT DEFAULT 'shard_4_scraper',
  raw_data            JSONB,                           -- full HTML/API response for audit
  verified            BOOLEAN DEFAULT false,           -- manual verification flag
  UNIQUE(case_number, county, sale_date, data_source)
);

-- Indices for performance
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_county_date ON foreclosure_outcomes(county, auction_date);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_case ON foreclosure_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_county_date ON tax_deed_outcomes(county, sale_date);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_case ON tax_deed_outcomes(case_number);

-- RLS policies
ALTER TABLE foreclosure_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_deed_outcomes ENABLE ROW LEVEL SECURITY;

-- Read access for all authenticated users
CREATE POLICY "foreclosure_outcomes_read" ON foreclosure_outcomes FOR SELECT USING (true);
CREATE POLICY "tax_deed_outcomes_read" ON tax_deed_outcomes FOR SELECT USING (true);

-- Service role can do everything
CREATE POLICY "foreclosure_outcomes_admin" ON foreclosure_outcomes FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "tax_deed_outcomes_admin" ON tax_deed_outcomes FOR ALL USING (true) WITH CHECK (true);

-- Function to verify outcome independence (NEVER-LIE enforcement)
CREATE OR REPLACE FUNCTION verify_outcome_independence(p_data_source TEXT)
RETURNS BOOLEAN AS $$
BEGIN
  -- HARD FAIL for PropertyOnion-derived sources
  IF p_data_source ILIKE '%propertyonion%' OR p_data_source ILIKE '%property_onion%' THEN
    RETURN false;
  END IF;
  
  -- HARD FAIL for secondary aggregators
  IF p_data_source ILIKE '%auction.com%' OR p_data_source ILIKE '%hubzu%' THEN
    RETURN false;
  END IF;
  
  -- PASS for clerk sources
  IF p_data_source ILIKE '%clerk%' OR p_data_source ILIKE '%court%' OR p_data_source = 'realforeclose_direct' THEN
    RETURN true;
  END IF;
  
  -- Default: require manual review
  RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Gold Standard Letter B evaluation function
CREATE OR REPLACE FUNCTION evaluate_letter_b_county(p_county TEXT)
RETURNS JSON AS $$
DECLARE
  total_closed INTEGER;
  verified_outcomes INTEGER;
  verification_rate NUMERIC(5,2);
  result JSON;
BEGIN
  -- Count closed sales from multi_county_auctions
  SELECT COUNT(*) INTO total_closed
  FROM multi_county_auctions 
  WHERE county = p_county 
    AND auction_status IN ('sold', 'confirmed');
  
  -- Count verified independent outcomes
  SELECT COUNT(*) INTO verified_outcomes
  FROM foreclosure_outcomes 
  WHERE county = p_county 
    AND verify_outcome_independence(data_source) = true
    AND status = 'sold';
  
  -- Calculate verification rate
  verification_rate := CASE 
    WHEN total_closed > 0 THEN (verified_outcomes::numeric / total_closed * 100)
    ELSE 0 
  END;
  
  -- Build result
  result := json_build_object(
    'letter', 'B',
    'county', p_county,
    'total_closed', total_closed,
    'verified_outcomes', verified_outcomes,
    'verification_rate', verification_rate,
    'pass_threshold', 95.0,
    'passes', verification_rate >= 95.0,
    'data_sources', (
      SELECT json_agg(DISTINCT data_source) 
      FROM foreclosure_outcomes 
      WHERE county = p_county
    )
  );
  
  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;