-- ============================================================
-- SHARD-13 COUNTY SETUP MIGRATION
-- Migration: 20260611_shard13_county_setup.sql  
-- Sets up palm_beach, clay, okaloosa, gulf counties for Gold Standard pipeline
-- ============================================================

-- Add SHARD-13 county slug mappings to fl_counties
-- Using correct co_no from fl_counties_manifest.yml:
-- Clay = 20, Gulf = 33, Okaloosa = 56, Palm Beach = 60
INSERT INTO fl_counties (co_no, name, fips_code, slug, region) VALUES 
  (20, 'Clay', '12019', 'clay', 'northeast'),
  (33, 'Gulf', '12045', 'gulf', 'panhandle'),
  (56, 'Okaloosa', '12091', 'okaloosa', 'panhandle'),
  (60, 'Palm Beach', '12099', 'palm_beach', 'southeast')
ON CONFLICT (co_no) DO UPDATE SET 
  slug = EXCLUDED.slug,
  fips_code = EXCLUDED.fips_code,
  region = EXCLUDED.region
WHERE fl_counties.slug IS NULL OR fl_counties.slug != EXCLUDED.slug;

-- Ensure multi_county_auctions table is ready for SHARD-13 data
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

  -- Add address columns for Letter I property card completeness
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'property_address') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN property_address TEXT;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'property_latitude') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN property_latitude NUMERIC(9,6);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'property_longitude') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN property_longitude NUMERIC(9,6);
  END IF;

  -- Add property valuation for Letter I completeness
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'assessed_value') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN assessed_value NUMERIC(12,2);
  END IF;

  -- Add parcel_id for Letter E linkage
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'parcel_id') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN parcel_id TEXT;
    CREATE INDEX IF NOT EXISTS idx_mca_parcel_id ON multi_county_auctions(parcel_id);
  END IF;
END $$;

-- Ensure bid_decisions table exists for Letter J (Shapira Formula)
CREATE TABLE IF NOT EXISTS bid_decisions (
  id                    BIGSERIAL PRIMARY KEY,
  case_number          TEXT NOT NULL,
  county_slug          TEXT NOT NULL,
  auction_date         DATE NOT NULL,
  property_address     TEXT,
  
  -- Core Shapira Formula inputs
  arv                  NUMERIC(12,2),              -- After Repair Value
  repair_estimate      NUMERIC(12,2),              -- Repair costs
  max_bid              NUMERIC(12,2),              -- 70% ARV - repairs - $10K - MIN($25K, 15%*ARV)
  
  -- ML scoring inputs  
  ml_score             NUMERIC(4,2),               -- Machine learning confidence score
  confidence_factors   JSONB,                      -- Detailed factor breakdown
  
  -- Two-arm CMA components
  comps_used           JSONB,                      -- Comparable sales data
  price_per_sqft       NUMERIC(8,2),               -- $/sqft analysis
  neighborhood_trend   TEXT,                       -- trending up/down/stable
  
  -- Triangle factors (location, condition, timing)
  location_score       NUMERIC(3,1),               -- 1-10 location desirability
  condition_score      NUMERIC(3,1),               -- 1-10 property condition
  timing_score         NUMERIC(3,1),               -- 1-10 market timing
  
  -- Computed decision
  bid_recommendation   TEXT CHECK (bid_recommendation IN ('BID', 'PASS', 'WATCH')),
  recommended_amount   NUMERIC(12,2),
  profit_projection    NUMERIC(12,2),
  
  -- Meta
  created_at           TIMESTAMPTZ DEFAULT NOW(),
  data_source          TEXT DEFAULT 'shapira_formula_v2',
  
  UNIQUE(case_number, county_slug, auction_date)
);

-- Create indexes for bid_decisions performance
CREATE INDEX IF NOT EXISTS idx_bid_decisions_county_date ON bid_decisions(county_slug, auction_date);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON bid_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_max_bid ON bid_decisions(max_bid) WHERE max_bid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bid_decisions_recommendation ON bid_decisions(bid_recommendation);

-- Ensure foreclosure_outcomes table exists for Letter B independent verification
CREATE TABLE IF NOT EXISTS foreclosure_outcomes (
  id                    BIGSERIAL PRIMARY KEY,
  case_number          TEXT NOT NULL,
  county_slug          TEXT NOT NULL,
  auction_date         DATE,
  sale_date            DATE,
  
  -- Outcome details
  status               TEXT NOT NULL CHECK (status IN ('sold', 'canceled', 'postponed', 'withdrawn', 'no_bidders')),
  winning_bid          NUMERIC(12,2),
  winning_bidder       TEXT,
  
  -- Property details  
  property_address     TEXT,
  parcel_id           TEXT,
  
  -- Meta tracking
  data_source         TEXT NOT NULL,               -- MUST be independent (not PropertyOnion)
  scraped_at          TIMESTAMPTZ DEFAULT NOW(),
  verified_at         TIMESTAMPTZ,
  
  UNIQUE(case_number, county_slug, data_source)
);

CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_county ON foreclosure_outcomes(county_slug);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_case_number ON foreclosure_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_sale_date ON foreclosure_outcomes(sale_date);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_data_source ON foreclosure_outcomes(data_source);

-- Ensure tax_deed_outcomes table exists for Letter B independent verification
CREATE TABLE IF NOT EXISTS tax_deed_outcomes (
  id                    BIGSERIAL PRIMARY KEY,
  case_number          TEXT NOT NULL,
  county_slug          TEXT NOT NULL,
  auction_date         DATE,
  sale_date            DATE,
  
  -- Outcome details
  status               TEXT NOT NULL CHECK (status IN ('sold', 'canceled', 'postponed', 'withdrawn', 'no_bidders')),
  winning_bid          NUMERIC(12,2),
  winning_bidder       TEXT,
  
  -- Property details
  property_address     TEXT,
  parcel_id           TEXT,
  
  -- Meta tracking
  data_source         TEXT NOT NULL,               -- MUST be independent (not PropertyOnion)
  scraped_at          TIMESTAMPTZ DEFAULT NOW(),
  verified_at         TIMESTAMPTZ,
  
  UNIQUE(case_number, county_slug, data_source)
);

CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_county ON tax_deed_outcomes(county_slug);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_case_number ON tax_deed_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_sale_date ON tax_deed_outcomes(sale_date);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_data_source ON tax_deed_outcomes(data_source);

-- Update the pencil_dod_evaluate_county function for SHARD-13 counties
CREATE OR REPLACE FUNCTION public.pencil_dod_evaluate_county(county_slug_arg TEXT)
RETURNS TABLE (
  letter TEXT,
  pass BOOLEAN,
  metric NUMERIC,
  detail TEXT,
  threshold NUMERIC,
  raw_count INTEGER,
  denominator INTEGER
) 
LANGUAGE plpgsql 
AS $$
DECLARE
  county_match_count INTEGER;
  target_county TEXT := county_slug_arg;
BEGIN
  -- Verify county exists and is properly configured
  SELECT COUNT(*) INTO county_match_count 
  FROM fl_counties 
  WHERE slug = target_county;
  
  IF county_match_count = 0 THEN
    -- Return error result for unknown county
    RETURN QUERY SELECT 'ERROR'::TEXT, false, 0.0, 
      format('County slug "%s" not found in fl_counties', target_county),
      0.0, 0, 0;
    RETURN;
  END IF;
  
  -- Letter A: Dual-product coverage (foreclosure + tax deed count)
  RETURN QUERY
  WITH a_metrics AS (
    SELECT 
      COUNT(*) FILTER (WHERE source_platform LIKE '%foreclosure%' OR source_platform LIKE '%fc%') as fc_count,
      COUNT(*) FILTER (WHERE source_platform LIKE '%tax%' OR source_platform LIKE '%td%') as td_count,
      COUNT(*) as total_count
    FROM multi_county_auctions 
    WHERE county = target_county
  )
  SELECT 
    'A'::TEXT,
    CASE WHEN fc_count > 0 AND td_count > 0 THEN true ELSE false END,
    LEAST(fc_count, td_count)::NUMERIC,
    format('fc=%s td=%s', fc_count, td_count),
    1.0::NUMERIC,
    LEAST(fc_count, td_count)::INTEGER,
    GREATEST(fc_count + td_count, 1)::INTEGER
  FROM a_metrics;

  -- Letter B: Verified independent outcomes >=95% of closed sales
  RETURN QUERY
  WITH b_metrics AS (
    SELECT 
      COUNT(*) FILTER (WHERE sale_status = 'closed' OR sale_status = 'sold') as closed_sales,
      (
        SELECT COUNT(*) 
        FROM foreclosure_outcomes fo 
        WHERE fo.county_slug = target_county 
          AND fo.data_source NOT LIKE '%propertyonion%'
          AND fo.data_source NOT LIKE '%PO-%'
      ) +
      (
        SELECT COUNT(*) 
        FROM tax_deed_outcomes tdo 
        WHERE tdo.county_slug = target_county 
          AND tdo.data_source NOT LIKE '%propertyonion%'
          AND tdo.data_source NOT LIKE '%PO-%'
      ) as verified_outcomes
    FROM multi_county_auctions 
    WHERE county = target_county
  )
  SELECT 
    'B'::TEXT,
    CASE WHEN closed_sales > 0 AND (verified_outcomes::FLOAT / closed_sales::FLOAT) >= 0.95 THEN true ELSE false END,
    CASE WHEN closed_sales > 0 THEN (verified_outcomes::FLOAT / closed_sales::FLOAT * 100.0)::NUMERIC ELSE NULL END,
    format('verified=%s closed_sold=%s', verified_outcomes, closed_sales),
    95.0::NUMERIC,
    verified_outcomes::INTEGER,
    closed_sales::INTEGER
  FROM b_metrics;

  -- Letter C: PropertyOnion parity clean match >=95%
  RETURN QUERY
  WITH c_metrics AS (
    SELECT 
      COUNT(*) FILTER (WHERE parity_status = 'matched_clean') as matched_clean,
      COUNT(*) as total_auctions
    FROM multi_county_auctions 
    WHERE county = target_county
  )
  SELECT 
    'C'::TEXT,
    CASE WHEN total_auctions > 0 AND (matched_clean::FLOAT / total_auctions::FLOAT) >= 0.95 THEN true ELSE false END,
    CASE WHEN total_auctions > 0 THEN (matched_clean::FLOAT / total_auctions::FLOAT * 100.0)::NUMERIC ELSE NULL END,
    format('matched_clean=%s of %s', matched_clean, total_auctions),
    95.0::NUMERIC,
    matched_clean::INTEGER,
    total_auctions::INTEGER
  FROM c_metrics;

  -- Letter D: PropertyOnion parity any match >=95%
  RETURN QUERY
  WITH d_metrics AS (
    SELECT 
      COUNT(*) FILTER (WHERE parity_status IN ('matched_clean', 'matched_any')) as matched_any,
      COUNT(*) as total_auctions
    FROM multi_county_auctions 
    WHERE county = target_county
  )
  SELECT 
    'D'::TEXT,
    CASE WHEN total_auctions > 0 AND (matched_any::FLOAT / total_auctions::FLOAT) >= 0.95 THEN true ELSE false END,
    CASE WHEN total_auctions > 0 THEN (matched_any::FLOAT / total_auctions::FLOAT * 100.0)::NUMERIC ELSE NULL END,
    format('matched_any=%s of %s', matched_any, total_auctions),
    95.0::NUMERIC,
    matched_any::INTEGER,
    total_auctions::INTEGER
  FROM d_metrics;

  -- Letter E: Parcel linkage >=95%
  RETURN QUERY
  WITH e_metrics AS (
    SELECT 
      COUNT(*) FILTER (WHERE parcel_id IS NOT NULL AND parcel_id != '') as parcel_linked,
      COUNT(*) as total_auctions
    FROM multi_county_auctions 
    WHERE county = target_county
  )
  SELECT 
    'E'::TEXT,
    CASE WHEN total_auctions > 0 AND (parcel_linked::FLOAT / total_auctions::FLOAT) >= 0.95 THEN true ELSE false END,
    CASE WHEN total_auctions > 0 THEN (parcel_linked::FLOAT / total_auctions::FLOAT * 100.0)::NUMERIC ELSE NULL END,
    format('parcel_linked=%s of %s', parcel_linked, total_auctions),
    95.0::NUMERIC,
    parcel_linked::INTEGER,
    total_auctions::INTEGER
  FROM e_metrics;

  -- Letter F: Tier1 sold amount >=95% of closed sales
  RETURN QUERY
  WITH f_metrics AS (
    SELECT 
      COUNT(*) FILTER (WHERE sale_status = 'closed' OR sale_status = 'sold') as closed_sales,
      COUNT(*) FILTER (WHERE tier1_sold_amount IS NOT NULL) as tier1_sold
    FROM multi_county_auctions 
    WHERE county = target_county
  )
  SELECT 
    'F'::TEXT,
    CASE WHEN closed_sales > 0 AND (tier1_sold::FLOAT / closed_sales::FLOAT) >= 0.95 THEN true ELSE false END,
    CASE WHEN closed_sales > 0 THEN (tier1_sold::FLOAT / closed_sales::FLOAT * 100.0)::NUMERIC ELSE NULL END,
    format('tier1_sold=%s closed_sold=%s', tier1_sold, closed_sales),
    95.0::NUMERIC,
    tier1_sold::INTEGER,
    closed_sales::INTEGER
  FROM f_metrics;

  -- Letter G: Zoning standards coverage (density, FAR, parking >=95%)
  RETURN QUERY
  SELECT 
    'G'::TEXT,
    false,  -- Will be implemented when zoning data is loaded for SHARD-13 counties
    NULL::NUMERIC,
    'density= far= pk1000=',
    95.0::NUMERIC,
    0::INTEGER,
    0::INTEGER;

  -- Letter H: Data freshness <=48 hours
  RETURN QUERY
  WITH h_metrics AS (
    SELECT 
      EXTRACT(EPOCH FROM (NOW() - MAX(last_seen_at)))/3600 as hours_since_last_seen
    FROM multi_county_auctions 
    WHERE county = target_county AND last_seen_at IS NOT NULL
  )
  SELECT 
    'H'::TEXT,
    CASE WHEN hours_since_last_seen IS NOT NULL AND hours_since_last_seen <= 48 THEN true ELSE false END,
    hours_since_last_seen::NUMERIC,
    format('hours since last_seen (SLA 48h)'),
    48.0::NUMERIC,
    CASE WHEN hours_since_last_seen IS NOT NULL THEN 1 ELSE 0 END::INTEGER,
    1::INTEGER
  FROM h_metrics;

  -- Letter I: Property card completeness >=95%
  RETURN QUERY
  WITH i_metrics AS (
    SELECT 
      COUNT(*) FILTER (WHERE 
        property_address IS NOT NULL AND property_address != '' AND
        property_latitude IS NOT NULL AND property_longitude IS NOT NULL AND
        assessed_value IS NOT NULL AND 
        parcel_id IS NOT NULL AND parcel_id != ''
      ) as field_complete_parcels,
      COUNT(*) as total_auctions,
      0 as zoned_complete_parcels  -- Placeholder until zoning data loaded
    FROM multi_county_auctions 
    WHERE county = target_county
  )
  SELECT 
    'I'::TEXT,
    false,  -- Will pass when both field and zoning completeness >=95%
    NULL::NUMERIC,
    format('zoned_complete_parcels=%s field_complete_parcels=%s auctions=%s', 
           zoned_complete_parcels, field_complete_parcels, total_auctions),
    95.0::NUMERIC,
    zoned_complete_parcels::INTEGER,
    total_auctions::INTEGER
  FROM i_metrics;

  -- Letter J: Deal completeness >=95% (Shapira Formula pipeline)
  RETURN QUERY
  WITH j_metrics AS (
    SELECT 
      COUNT(*) FILTER (WHERE bd.case_number IS NOT NULL) as deal_complete,
      COUNT(*) as total_auctions
    FROM multi_county_auctions mca
    LEFT JOIN bid_decisions bd ON mca.case_number = bd.case_number AND mca.county = bd.county_slug
    WHERE mca.county = target_county
  )
  SELECT 
    'J'::TEXT,
    CASE WHEN total_auctions > 0 AND (deal_complete::FLOAT / total_auctions::FLOAT) >= 0.95 THEN true ELSE false END,
    CASE WHEN total_auctions > 0 THEN (deal_complete::FLOAT / total_auctions::FLOAT * 100.0)::NUMERIC ELSE 0.0 END,
    format('deal_complete=%s of %s (triangle + two-arm CMA + ml_score + max_bid)', deal_complete, total_auctions),
    95.0::NUMERIC,
    deal_complete::INTEGER,
    total_auctions::INTEGER
  FROM j_metrics;

END $$;

COMMENT ON FUNCTION pencil_dod_evaluate_county IS 'Evaluates Gold Standard A-J criteria for a single county, updated for SHARD-13 counties';

-- Create initial pipeline configurations for SHARD-13 counties
INSERT INTO pipeline.counties (
  slug, 
  name, 
  state, 
  foreclosure_platform, 
  tax_deed_platform, 
  foreclosure_url, 
  tax_deed_url,
  status
) VALUES 
  ('palm_beach', 'Palm Beach', 'FL', 'realauction', 'realauction', 
   'https://www.realauction.com/palm-beach', 'https://www.realauction.com/palm-beach-tax', 'active'),
  ('clay', 'Clay', 'FL', 'realauction', 'realauction', 
   'https://www.realauction.com/clay', 'https://www.realauction.com/clay-tax', 'active'),
  ('okaloosa', 'Okaloosa', 'FL', 'realauction', 'realauction', 
   'https://www.realauction.com/okaloosa', 'https://www.realauction.com/okaloosa-tax', 'active'),
  ('gulf', 'Gulf', 'FL', 'realauction', 'realauction', 
   'https://www.realauction.com/gulf', 'https://www.realauction.com/gulf-tax', 'active')
ON CONFLICT (slug) DO UPDATE SET
  foreclosure_platform = EXCLUDED.foreclosure_platform,
  tax_deed_platform = EXCLUDED.tax_deed_platform,
  foreclosure_url = EXCLUDED.foreclosure_url,
  tax_deed_url = EXCLUDED.tax_deed_url,
  status = EXCLUDED.status;

-- Success notification
DO $$ BEGIN
  RAISE NOTICE 'SHARD-13 county setup completed successfully';
  RAISE NOTICE 'Counties configured: palm_beach (60), clay (20), okaloosa (56), gulf (33)';
  RAISE NOTICE 'Database schema updated with required columns and indexes';
  RAISE NOTICE 'Functions updated for SHARD-13 compatibility';
END $$;