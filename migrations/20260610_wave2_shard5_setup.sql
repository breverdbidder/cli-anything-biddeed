-- ============================================================
-- GOLD STANDARD WAVE2-SHARD-5 COUNTY SETUP
-- Migration: 20260610_wave2_shard5_setup.sql
-- Sets up infrastructure for volusia, escambia, lee, santa_rosa, dixie, holmes, taylor
-- ============================================================

-- Add our shard counties to fl_counties if missing (with correct CO_NO mapping)
INSERT INTO fl_counties (co_no, name, fips_code, slug, region) VALUES 
  (30, 'Volusia', '12127', 'volusia', 'central'),
  (22, 'Escambia', '12033', 'escambia', 'northwest'),
  (36, 'Lee', '12071', 'lee', 'southwest'),  
  (69, 'Santa Rosa', '12113', 'santa_rosa', 'northwest'),
  (21, 'Dixie', '12029', 'dixie', 'north'),
  (35, 'Holmes', '12059', 'holmes', 'northwest'),
  (76, 'Taylor', '12123', 'taylor', 'north')
ON CONFLICT (co_no) DO UPDATE SET 
  slug = EXCLUDED.slug,
  name = EXCLUDED.name,
  fips_code = EXCLUDED.fips_code,
  region = EXCLUDED.region
WHERE fl_counties.slug IS NULL OR fl_counties.slug != EXCLUDED.slug;

-- Create pipeline counties configuration if it doesn't exist
CREATE TABLE IF NOT EXISTS pipeline.counties (
  id                     SERIAL PRIMARY KEY,
  county_slug            TEXT UNIQUE NOT NULL,
  county_name            TEXT NOT NULL,
  co_no                  INTEGER NOT NULL,
  state                  TEXT DEFAULT 'FL',
  
  -- Auction source configuration
  foreclosure_url        TEXT,
  foreclosure_platform   TEXT DEFAULT 'realauction',  -- 'realauction', 'clerk_html', 'county_portal'
  foreclosure_active     BOOLEAN DEFAULT TRUE,
  
  tax_deed_url          TEXT,
  tax_deed_platform     TEXT DEFAULT 'realauction',   -- 'realauction', 'clerk_html', 'county_portal'  
  tax_deed_active       BOOLEAN DEFAULT TRUE,
  
  -- Property appraiser configuration
  pa_base_url           TEXT,                         -- Property appraiser website
  pa_search_url         TEXT,                         -- Search endpoint
  pa_api_url            TEXT,                         -- ArcGIS REST API if available
  
  -- Clerk configuration
  clerk_url             TEXT,                         -- Clerk of court website
  clerk_foreclosure_url TEXT,                         -- Direct foreclosure calendar if available
  
  -- Status tracking
  letter_a_complete     BOOLEAN DEFAULT FALSE,        -- Dual product coverage
  letter_b_complete     BOOLEAN DEFAULT FALSE,        -- Verified outcomes
  letter_c_complete     BOOLEAN DEFAULT FALSE,        -- Parity clean
  letter_d_complete     BOOLEAN DEFAULT FALSE,        -- Parity any
  letter_e_complete     BOOLEAN DEFAULT FALSE,        -- Parcel linkage
  letter_f_complete     BOOLEAN DEFAULT FALSE,        -- Tier1 sold amount
  letter_g_complete     BOOLEAN DEFAULT FALSE,        -- Zoning KPI
  letter_h_complete     BOOLEAN DEFAULT FALSE,        -- Freshness
  letter_i_complete     BOOLEAN DEFAULT FALSE,        -- Property card
  letter_j_complete     BOOLEAN DEFAULT FALSE,        -- Deal thesis
  
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now()
);

-- Create schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS pipeline;

-- Insert our shard county configurations
INSERT INTO pipeline.counties (
  county_slug, county_name, co_no, 
  foreclosure_url, tax_deed_url,
  pa_base_url, clerk_url
) VALUES 
  (
    'volusia', 'Volusia', 30,
    'https://www.realauction.com/index.cfm?zaction=user&zmethod=CATALOG&AUCTIONEER=VOLUSIA',
    'https://www.realauction.com/index.cfm?zaction=user&zmethod=CATALOG&AUCTIONEER=VOLUSIA_TD',
    'https://www.vcpa.org/',
    'https://www.clerk.org/volusia-county/'
  ),
  (
    'escambia', 'Escambia', 22,
    'https://www.realauction.com/index.cfm?zaction=user&zmethod=CATALOG&AUCTIONEER=ESCAMBIA',
    'https://www.realauction.com/index.cfm?zaction=user&zmethod=CATALOG&AUCTIONEER=ESCAMBIA_TD', 
    'https://www.escambiapa.com/',
    'https://www.escambiaclerk.com/'
  ),
  (
    'lee', 'Lee', 36,
    'https://www.realauction.com/index.cfm?zaction=user&zmethod=CATALOG&AUCTIONEER=LEE',
    'https://www.realauction.com/index.cfm?zaction=user&zmethod=CATALOG&AUCTIONEER=LEE_TD',
    'https://www.leepa.org/',
    'https://www.leeclerk.org/'
  ),
  (
    'santa_rosa', 'Santa Rosa', 69,
    'https://www.realauction.com/index.cfm?zaction=user&zmethod=CATALOG&AUCTIONEER=SANTA_ROSA',
    'https://www.realauction.com/index.cfm?zaction=user&zmethod=CATALOG&AUCTIONEER=SANTA_ROSA_TD',
    'https://www.srpa.net/',
    'https://www.santarosaclerk.com/'
  ),
  (
    'dixie', 'Dixie', 21,
    'https://www.realauction.com/index.cfm?zaction=user&zmethod=CATALOG&AUCTIONEER=DIXIE',
    'https://www.realauction.com/index.cfm?zaction=user&zmethod=CATALOG&AUCTIONEER=DIXIE_TD',
    'https://www.dixiecountypa.com/',
    'https://www.dixieclerk.com/'
  ),
  (
    'holmes', 'Holmes', 35,
    'https://www.realauction.com/index.cfm?zaction=user&zmethod=CATALOG&AUCTIONEER=HOLMES',
    'https://www.realauction.com/index.cfm?zaction=user&zmethod=CATALOG&AUCTIONEER=HOLMES_TD',
    'https://www.holmescountypa.com/',
    'https://www.holmescountyclerk.com/'
  ),
  (
    'taylor', 'Taylor', 76,
    'https://www.realauction.com/index.cfm?zaction=user&zmethod=CATALOG&AUCTIONEER=TAYLOR',
    'https://www.realauction.com/index.cfm?zaction=user&zmethod=CATALOG&AUCTIONEER=TAYLOR_TD',
    'https://www.taylorcountypa.com/',
    'https://www.taylorclerk.com/'
  )
ON CONFLICT (county_slug) DO UPDATE SET
  county_name = EXCLUDED.county_name,
  co_no = EXCLUDED.co_no,
  foreclosure_url = EXCLUDED.foreclosure_url,
  tax_deed_url = EXCLUDED.tax_deed_url,
  pa_base_url = EXCLUDED.pa_base_url,
  clerk_url = EXCLUDED.clerk_url,
  updated_at = now();

-- Create county-specific tracking tables for verified outcomes
-- (Extending the base tables from the previous migration)

-- Add indexes for our shard counties specifically
CREATE INDEX IF NOT EXISTS idx_tdo_volusia ON tax_deed_outcomes(case_number, auction_date) WHERE county_slug = 'volusia';
CREATE INDEX IF NOT EXISTS idx_tdo_escambia ON tax_deed_outcomes(case_number, auction_date) WHERE county_slug = 'escambia';
CREATE INDEX IF NOT EXISTS idx_tdo_lee ON tax_deed_outcomes(case_number, auction_date) WHERE county_slug = 'lee';
CREATE INDEX IF NOT EXISTS idx_tdo_santa_rosa ON tax_deed_outcomes(case_number, auction_date) WHERE county_slug = 'santa_rosa';
CREATE INDEX IF NOT EXISTS idx_tdo_dixie ON tax_deed_outcomes(case_number, auction_date) WHERE county_slug = 'dixie';
CREATE INDEX IF NOT EXISTS idx_tdo_holmes ON tax_deed_outcomes(case_number, auction_date) WHERE county_slug = 'holmes';
CREATE INDEX IF NOT EXISTS idx_tdo_taylor ON tax_deed_outcomes(case_number, auction_date) WHERE county_slug = 'taylor';

CREATE INDEX IF NOT EXISTS idx_fco_volusia ON foreclosure_outcomes(case_number, auction_date) WHERE county_slug = 'volusia';
CREATE INDEX IF NOT EXISTS idx_fco_escambia ON foreclosure_outcomes(case_number, auction_date) WHERE county_slug = 'escambia';
CREATE INDEX IF NOT EXISTS idx_fco_lee ON foreclosure_outcomes(case_number, auction_date) WHERE county_slug = 'lee';
CREATE INDEX IF NOT EXISTS idx_fco_santa_rosa ON foreclosure_outcomes(case_number, auction_date) WHERE county_slug = 'santa_rosa';
CREATE INDEX IF NOT EXISTS idx_fco_dixie ON foreclosure_outcomes(case_number, auction_date) WHERE county_slug = 'dixie';
CREATE INDEX IF NOT EXISTS idx_fco_holmes ON foreclosure_outcomes(case_number, auction_date) WHERE county_slug = 'holmes';
CREATE INDEX IF NOT EXISTS idx_fco_taylor ON foreclosure_outcomes(case_number, auction_date) WHERE county_slug = 'taylor';

-- Add multi_county_auctions indexes for our counties
CREATE INDEX IF NOT EXISTS idx_mca_volusia ON multi_county_auctions(county, auction_date, auction_status) WHERE county = 'volusia';
CREATE INDEX IF NOT EXISTS idx_mca_escambia ON multi_county_auctions(county, auction_date, auction_status) WHERE county = 'escambia';
CREATE INDEX IF NOT EXISTS idx_mca_lee ON multi_county_auctions(county, auction_date, auction_status) WHERE county = 'lee';
CREATE INDEX IF NOT EXISTS idx_mca_santa_rosa ON multi_county_auctions(county, auction_date, auction_status) WHERE county = 'santa_rosa';
CREATE INDEX IF NOT EXISTS idx_mca_dixie ON multi_county_auctions(county, auction_date, auction_status) WHERE county = 'dixie';
CREATE INDEX IF NOT EXISTS idx_mca_holmes ON multi_county_auctions(county, auction_date, auction_status) WHERE county = 'holmes';
CREATE INDEX IF NOT EXISTS idx_mca_taylor ON multi_county_auctions(county, auction_date, auction_status) WHERE county = 'taylor';

-- Create function to bootstrap zero counties (Letter A fix)
CREATE OR REPLACE FUNCTION bootstrap_county_letter_a(county_slug_arg TEXT)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
  county_config RECORD;
  result_text TEXT;
BEGIN
  -- Get county configuration
  SELECT * INTO county_config 
  FROM pipeline.counties 
  WHERE county_slug = county_slug_arg;
  
  IF NOT FOUND THEN
    RETURN 'ERROR: County configuration not found for ' || county_slug_arg;
  END IF;
  
  -- Mark Letter A as in progress
  UPDATE pipeline.counties 
  SET letter_a_complete = FALSE, updated_at = now()
  WHERE county_slug = county_slug_arg;
  
  result_text := 'County ' || county_slug_arg || ' Letter A bootstrap initiated. ';
  result_text := result_text || 'Foreclosure URL: ' || COALESCE(county_config.foreclosure_url, 'NOT_SET') || '. ';
  result_text := result_text || 'Tax Deed URL: ' || COALESCE(county_config.tax_deed_url, 'NOT_SET') || '. ';
  result_text := result_text || 'Next: Run auction ingestion pipeline for both sale types.';
  
  RETURN result_text;
END;
$$;

-- Create function to log Gold Standard session progress
CREATE OR REPLACE FUNCTION log_gold_standard_session(
  session_id TEXT,
  county_slug_arg TEXT,
  action_type TEXT,
  action_detail TEXT,
  success BOOLEAN DEFAULT TRUE
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO gold_standard_session_log (
    session_id, county_slug, action_type, action_detail, success, logged_at
  ) VALUES (
    session_id, county_slug_arg, action_type, action_detail, success, now()
  );
END;
$$;

-- Create session log table
CREATE TABLE IF NOT EXISTS gold_standard_session_log (
  id             SERIAL PRIMARY KEY,
  session_id     TEXT NOT NULL,                    -- e.g. 'wave2-shard5-20260610'
  county_slug    TEXT NOT NULL,
  action_type    TEXT NOT NULL,                    -- 'bootstrap', 'fix_letter_b', 'verify', etc.
  action_detail  TEXT,
  success        BOOLEAN DEFAULT TRUE,
  logged_at      TIMESTAMPTZ DEFAULT now()
);

-- Grant permissions
GRANT SELECT ON pipeline.counties TO anon, authenticated;
GRANT SELECT ON gold_standard_session_log TO anon, authenticated;

-- Comments
COMMENT ON TABLE pipeline.counties IS 'County pipeline configuration for Gold Standard processing';
COMMENT ON FUNCTION bootstrap_county_letter_a IS 'Bootstrap Letter A (dual product coverage) for a county';
COMMENT ON FUNCTION log_gold_standard_session IS 'Log Gold Standard autonomous session actions';
COMMENT ON TABLE gold_standard_session_log IS 'Audit log for Gold Standard autonomous sessions';

-- Insert initial session start log
INSERT INTO gold_standard_session_log (
  session_id, county_slug, action_type, action_detail, success
) VALUES (
  'wave2-shard5-20260610', 'ALL', 'session_start', 
  'GOLD STANDARD WAVE2-SHARD-5: volusia, escambia, lee, santa_rosa, dixie, holmes, taylor', 
  TRUE
);