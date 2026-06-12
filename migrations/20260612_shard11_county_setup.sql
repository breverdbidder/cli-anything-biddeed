-- ============================================================
-- SHARD-11 COUNTY SETUP MIGRATION
-- Migration: 20260612_shard11_county_setup.sql  
-- Sets up manatee, washington, miami_dade, gadsden, wakulla counties for Gold Standard pipeline
-- ============================================================

-- Add SHARD-11 county slug mappings to fl_counties
-- Using correct co_no from fl_counties_manifest.yml:
-- Manatee = 51, Washington = 77, Miami-Dade = 23, Gadsden = 30, Wakulla = 75
INSERT INTO fl_counties (co_no, name, fips_code, slug, region) VALUES 
  (51, 'Manatee', '12081', 'manatee', 'gulf_coast'),
  (77, 'Washington', '12133', 'washington', 'panhandle'),
  (23, 'Miami-Dade', '12086', 'miami_dade', 'southeast'),  -- Already exists but ensure consistent  
  (30, 'Gadsden', '12039', 'gadsden', 'panhandle'),
  (75, 'Wakulla', '12129', 'wakulla', 'panhandle')
ON CONFLICT (co_no) DO UPDATE SET 
  slug = EXCLUDED.slug,
  fips_code = EXCLUDED.fips_code,
  region = EXCLUDED.region
WHERE fl_counties.slug IS NULL OR fl_counties.slug != EXCLUDED.slug;

-- Ensure pipeline.counties table has entries for SHARD-11 counties
-- This is critical for auction scraping to work
INSERT INTO pipeline.counties (county_slug, state, foreclosure_url, foreclosure_platform, tax_deed_url, tax_deed_platform, active, last_scraped_at) VALUES
  ('manatee', 'FL', 'https://www.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&GROUPID=100000', 'realauction', 'https://www.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&GROUPID=100000', 'realauction', true, NULL),
  ('washington', 'FL', 'https://www.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&GROUPID=100000', 'realauction', 'https://www.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&GROUPID=100000', 'realauction', true, NULL),
  ('gadsden', 'FL', 'https://www.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&GROUPID=100000', 'realauction', 'https://www.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&GROUPID=100000', 'realauction', true, NULL),
  ('wakulla', 'FL', 'https://www.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&GROUPID=100000', 'realauction', 'https://www.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&GROUPID=100000', 'realauction', true, NULL)
ON CONFLICT (county_slug) DO UPDATE SET
  foreclosure_url = EXCLUDED.foreclosure_url,
  foreclosure_platform = EXCLUDED.foreclosure_platform,
  tax_deed_url = EXCLUDED.tax_deed_url,
  tax_deed_platform = EXCLUDED.tax_deed_platform,
  active = EXCLUDED.active;

-- Miami-Dade already has auction data, just ensure pipeline entry exists
INSERT INTO pipeline.counties (county_slug, state, foreclosure_url, foreclosure_platform, tax_deed_url, tax_deed_platform, active, last_scraped_at) VALUES
  ('miami_dade', 'FL', 'https://www.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&GROUPID=100000', 'realauction', 'https://www.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&GROUPID=100000', 'realauction', true, NULL)
ON CONFLICT (county_slug) DO NOTHING;

-- Ensure multi_county_auctions table is ready for SHARD-11 data
-- Add any missing columns that might be needed for Letter improvements
DO $$ 
BEGIN
  -- Add parity_status column if it doesn't exist (needed for Letters C/D)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'parity_status') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN parity_status TEXT;
    CREATE INDEX IF NOT EXISTS idx_mca_parity_status ON multi_county_auctions(parity_status);
  END IF;

  -- Add tier1_sold_amount column if it doesn't exist (needed for Letter F)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'tier1_sold_amount') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN tier1_sold_amount NUMERIC(12,2);
    CREATE INDEX IF NOT EXISTS idx_mca_tier1_sold ON multi_county_auctions(tier1_sold_amount);
  END IF;

  -- Add tier1_verified_at column if it doesn't exist (needed for Letter F timing)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'tier1_verified_at') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN tier1_verified_at TIMESTAMPTZ;
    CREATE INDEX IF NOT EXISTS idx_mca_tier1_verified_at ON multi_county_auctions(tier1_verified_at);
  END IF;

  -- Add last_seen_at column if it doesn't exist (needed for Letter H freshness)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'last_seen_at') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN last_seen_at TIMESTAMPTZ;
    CREATE INDEX IF NOT EXISTS idx_mca_last_seen_at ON multi_county_auctions(last_seen_at);
  END IF;
END $$;

-- Create property appraiser lookup table for Letter E (parcel linkage)
CREATE TABLE IF NOT EXISTS county_property_appraisers (
  county_slug TEXT PRIMARY KEY,
  pa_name TEXT NOT NULL,
  pa_website TEXT,
  arcgis_rest_url TEXT,
  parcel_id_field TEXT DEFAULT 'PARCEL_ID',
  address_field TEXT DEFAULT 'SITE_ADDR',
  owner_field TEXT DEFAULT 'OWNER_NAME',
  value_field TEXT DEFAULT 'JUST_VAL',
  geom_field TEXT DEFAULT 'SHAPE',
  max_record_count INTEGER DEFAULT 2000,
  active BOOLEAN DEFAULT true,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Insert property appraiser configurations for SHARD-11 counties
INSERT INTO county_property_appraisers (county_slug, pa_name, pa_website, arcgis_rest_url, notes) VALUES
  ('manatee', 'Manatee County Property Appraiser', 'https://www.manateepao.com/', 
   'https://gis1.manateegov.com/arcgis/rest/services/Property/PropertyAppraiser/MapServer/0', 
   'Manatee County GIS - verify field names'),
  ('washington', 'Washington County Property Appraiser', 'https://www.wcpao.com/',
   NULL, 'Need to discover ArcGIS REST endpoint'),
  ('miami_dade', 'Miami-Dade Property Appraiser', 'https://www.miamidade.gov/pa/',
   'https://gisweb.miamidade.gov/arcgis/rest/services/MDProperty/PropertySearch/MapServer/0',
   'Miami-Dade GIS - large dataset, verify pagination'),
  ('gadsden', 'Gadsden County Property Appraiser', 'http://www.gadsdenpa.com/',
   NULL, 'Small county - may need manual parcel linking'),  
  ('wakulla', 'Wakulla County Property Appraiser', 'https://qpublic.schneidercorp.com/Application.aspx?AppID=1070&LayerID=22896&PageTypeID=4',
   NULL, 'Uses QPublic system - need custom integration')
ON CONFLICT (county_slug) DO UPDATE SET
  pa_name = EXCLUDED.pa_name,
  pa_website = EXCLUDED.pa_website,
  arcgis_rest_url = EXCLUDED.arcgis_rest_url,
  notes = EXCLUDED.notes,
  updated_at = now();

-- Create auction_parity_queue table for Letters C/D improvements
CREATE TABLE IF NOT EXISTS auction_parity_queue (
  id SERIAL PRIMARY KEY,
  county_slug TEXT NOT NULL,
  case_number TEXT,
  auction_date DATE,
  property_address TEXT,
  parcel_id TEXT,
  opening_bid NUMERIC(12,2),
  
  -- Parity check fields
  propertyonion_match_attempted BOOLEAN DEFAULT false,
  propertyonion_match_date TIMESTAMPTZ,
  propertyonion_result JSONB,
  parity_status TEXT, -- 'pending', 'matched_clean', 'matched_divergent', 'no_match', 'error'
  
  -- Match metadata
  match_confidence NUMERIC(3,2), -- 0.0 to 1.0
  match_method TEXT, -- 'address', 'parcel_id', 'auction_date_address', 'fuzzy'
  divergence_fields TEXT[], -- ['opening_bid', 'auction_date', 'address']
  
  created_at TIMESTAMPTZ DEFAULT now(),
  processed_at TIMESTAMPTZ,
  
  CONSTRAINT chk_match_confidence CHECK (match_confidence BETWEEN 0 AND 1 OR match_confidence IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_auction_parity_queue_county ON auction_parity_queue(county_slug);
CREATE INDEX IF NOT EXISTS idx_auction_parity_queue_status ON auction_parity_queue(parity_status);
CREATE INDEX IF NOT EXISTS idx_auction_parity_queue_match_attempted ON auction_parity_queue(propertyonion_match_attempted);

-- Create verified_outcomes_queue for Letter B improvements  
CREATE TABLE IF NOT EXISTS verified_outcomes_queue (
  id SERIAL PRIMARY KEY,
  county_slug TEXT NOT NULL,
  case_number TEXT NOT NULL,
  auction_date DATE,
  sale_type TEXT, -- 'foreclosure', 'tax_deed'
  
  -- Verification targets
  clerk_records_checked BOOLEAN DEFAULT false,
  clerk_records_date TIMESTAMPTZ,
  clerk_result JSONB,
  
  realauction_checked BOOLEAN DEFAULT false,
  realauction_date TIMESTAMPTZ, 
  realauction_result JSONB,
  
  -- Outcome data
  outcome_status TEXT, -- 'sold', 'no_sale', 'canceled', 'unknown'
  winning_bid NUMERIC(12,2),
  winner_name TEXT,
  outcome_source TEXT, -- 'clerk_records', 'realauction', 'manual'
  outcome_confidence NUMERIC(3,2), -- 0.0 to 1.0
  
  created_at TIMESTAMPTZ DEFAULT now(),
  verified_at TIMESTAMPTZ,
  
  CONSTRAINT uq_verified_outcomes_case_county UNIQUE(county_slug, case_number),
  CONSTRAINT chk_outcome_confidence CHECK (outcome_confidence BETWEEN 0 AND 1 OR outcome_confidence IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_verified_outcomes_queue_county ON verified_outcomes_queue(county_slug);
CREATE INDEX IF NOT EXISTS idx_verified_outcomes_queue_clerk_checked ON verified_outcomes_queue(clerk_records_checked);
CREATE INDEX IF NOT EXISTS idx_verified_outcomes_queue_realauction_checked ON verified_outcomes_queue(realauction_checked);

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON county_property_appraisers TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON auction_parity_queue TO anon, authenticated;  
GRANT SELECT, INSERT, UPDATE ON verified_outcomes_queue TO anon, authenticated;

-- Comments for documentation
COMMENT ON TABLE county_property_appraisers IS 'Property appraiser configurations for Letter E (parcel linkage) improvements';
COMMENT ON TABLE auction_parity_queue IS 'Queue for PropertyOnion parity checking (Letters C/D) - LITMUS ONLY, not data source';
COMMENT ON TABLE verified_outcomes_queue IS 'Queue for independent outcome verification (Letter B) from clerk records and RealAuction';

-- Update schema permissions
GRANT USAGE ON SCHEMA pipeline TO anon, authenticated;