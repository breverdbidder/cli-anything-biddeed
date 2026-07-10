-- ============================================================
-- GOLD STANDARD VERIFIED OUTCOMES INFRASTRUCTURE
-- Migration: 20260610_gold_standard_verified_outcomes.sql
-- Creates independent verified outcome tables for Letter B compliance
-- ============================================================

-- Verified tax deed outcomes from independent clerk sources
CREATE TABLE IF NOT EXISTS tax_deed_outcomes (
  id                  SERIAL PRIMARY KEY,
  county_slug         TEXT NOT NULL,                    -- e.g. 'indian_river', 'osceola', 'sarasota'
  case_number         TEXT NOT NULL,                    -- matches multi_county_auctions.case_number
  certificate_number  TEXT,                             -- tax certificate number if available
  parcel_id           TEXT,                             -- matches sample_properties.parcel_id
  auction_date        DATE NOT NULL,
  sale_status         TEXT NOT NULL,                    -- 'sold', 'no_sale', 'withdrawn', 'redeemed'
  sale_amount         NUMERIC(12,2),                   -- winning bid amount
  buyer_name          TEXT,                            -- winning bidder name (public record)
  buyer_type          TEXT,                            -- 'third_party', 'county', 'state'
  redemption_amount   NUMERIC(12,2),                   -- if redeemed
  
  -- Data provenance (CRITICAL for Letter B independence)
  data_source         TEXT NOT NULL,                   -- 'clerk_direct', 'realauction_tier1', 'county_portal'
  source_url          TEXT,                            -- specific URL scraped
  scraped_at          TIMESTAMPTZ DEFAULT now(),
  verified_at         TIMESTAMPTZ DEFAULT now(),
  
  -- Quality tracking
  confidence_level    TEXT DEFAULT 'verified',         -- 'verified', 'probable', 'inferred'
  notes               TEXT,
  created_at          TIMESTAMPTZ DEFAULT now(),
  updated_at          TIMESTAMPTZ DEFAULT now(),
  
  -- Constraints
  UNIQUE(county_slug, case_number, auction_date),
  CHECK (sale_status IN ('sold', 'no_sale', 'withdrawn', 'redeemed', 'postponed')),
  CHECK (data_source NOT ILIKE '%propertyonion%'),     -- HARD BLOCK PropertyOnion
  CHECK (buyer_type IN ('third_party', 'county', 'state', 'city', 'unknown') OR buyer_type IS NULL)
);

-- Verified foreclosure outcomes from independent clerk sources  
CREATE TABLE IF NOT EXISTS foreclosure_outcomes (
  id                  SERIAL PRIMARY KEY,
  county_slug         TEXT NOT NULL,                    -- e.g. 'indian_river', 'osceola', 'sarasota'
  case_number         TEXT NOT NULL,                    -- matches multi_county_auctions.case_number
  parcel_id           TEXT,                             -- matches sample_properties.parcel_id
  auction_date        DATE NOT NULL,
  sale_status         TEXT NOT NULL,                    -- 'sold', 'canceled', 'redeemed', 'struck'
  sale_amount         NUMERIC(12,2),                   -- final judgment amount or winning bid
  high_bid            NUMERIC(12,2),                   -- highest bid amount
  buyer_name          TEXT,                            -- winning bidder name (public record)
  buyer_type          TEXT,                            -- 'third_party', 'plaintiff', 'bank'
  
  -- Court details
  plaintiff           TEXT,                            -- lending institution
  final_judgment_date DATE,
  final_judgment_amt  NUMERIC(12,2),
  court_case_number   TEXT,                            -- circuit court case number
  
  -- Data provenance (CRITICAL for Letter B independence)
  data_source         TEXT NOT NULL,                   -- 'clerk_direct', 'realforeclose_tier1', 'court_portal'
  source_url          TEXT,                            -- specific URL scraped
  scraped_at          TIMESTAMPTZ DEFAULT now(),
  verified_at         TIMESTAMPTZ DEFAULT now(),
  
  -- Quality tracking
  confidence_level    TEXT DEFAULT 'verified',         -- 'verified', 'probable', 'inferred'
  notes               TEXT,
  created_at          TIMESTAMPTZ DEFAULT now(),
  updated_at          TIMESTAMPTZ DEFAULT now(),
  
  -- Constraints
  UNIQUE(county_slug, case_number, auction_date),
  CHECK (sale_status IN ('sold', 'canceled', 'redeemed', 'struck', 'postponed')),
  CHECK (data_source NOT ILIKE '%propertyonion%'),     -- HARD BLOCK PropertyOnion
  CHECK (buyer_type IN ('third_party', 'plaintiff', 'bank', 'county', 'unknown') OR buyer_type IS NULL)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tdo_county_date ON tax_deed_outcomes(county_slug, auction_date);
CREATE INDEX IF NOT EXISTS idx_tdo_case_number ON tax_deed_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_tdo_parcel_id ON tax_deed_outcomes(parcel_id);
CREATE INDEX IF NOT EXISTS idx_tdo_data_source ON tax_deed_outcomes(data_source);
CREATE INDEX IF NOT EXISTS idx_tdo_sale_status ON tax_deed_outcomes(sale_status);

CREATE INDEX IF NOT EXISTS idx_fco_county_date ON foreclosure_outcomes(county_slug, auction_date);
CREATE INDEX IF NOT EXISTS idx_fco_case_number ON foreclosure_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_fco_parcel_id ON foreclosure_outcomes(parcel_id);
CREATE INDEX IF NOT EXISTS idx_fco_data_source ON foreclosure_outcomes(data_source);
CREATE INDEX IF NOT EXISTS idx_fco_sale_status ON foreclosure_outcomes(sale_status);

-- Add county slug mappings to fl_counties if missing
INSERT INTO fl_counties (co_no, name, fips_code, slug, region) VALUES 
  (41, 'Indian River', '12061', 'indian_river', 'central'),
  (59, 'Osceola', '12097', 'osceola', 'central'), 
  (68, 'Sarasota', '12115', 'sarasota', 'central')
ON CONFLICT (co_no) DO UPDATE SET 
  slug = EXCLUDED.slug 
WHERE fl_counties.slug IS NULL;

-- Create Gold Standard county status tracking if not exists
CREATE TABLE IF NOT EXISTS gold_standard_county_status (
  id                    SERIAL PRIMARY KEY,
  loop_run_id           INTEGER NOT NULL,              -- from gold_standard_loop_run_seq
  county_slug           TEXT NOT NULL,
  
  -- A-J letter status
  a_dual_product        BOOLEAN DEFAULT FALSE,
  a_metric              TEXT,
  a_detail              TEXT,
  
  b_verified_outcomes   BOOLEAN DEFAULT FALSE,
  b_metric              NUMERIC(5,1),                  -- percentage of closed with independent outcomes
  b_detail              TEXT,
  
  c_parity_clean        BOOLEAN DEFAULT FALSE, 
  c_metric              NUMERIC(5,1),                  -- percentage with matched_clean
  c_detail              TEXT,
  
  d_parity_any          BOOLEAN DEFAULT FALSE,
  d_metric              NUMERIC(5,1),                  -- percentage with matched_clean or matched_divergent  
  d_detail              TEXT,
  
  e_parcel_linkage      BOOLEAN DEFAULT FALSE,
  e_metric              NUMERIC(5,1),                  -- percentage with parcel_id linkage
  e_detail              TEXT,
  
  f_tier1_authoritative BOOLEAN DEFAULT FALSE,
  f_metric              NUMERIC(5,1),                  -- percentage of closed with tier1_sold_amount
  f_detail              TEXT,
  
  g_zoning              BOOLEAN DEFAULT FALSE,
  g_metric              NUMERIC(5,1),                  -- min(density, FAR, pk1000) percentage
  g_detail              TEXT,
  
  h_freshness           BOOLEAN DEFAULT FALSE, 
  h_metric              NUMERIC(8,1),                  -- hours since last activity
  h_detail              TEXT,
  
  i_property_card       BOOLEAN DEFAULT FALSE,
  i_metric              NUMERIC(5,1),                  -- percentage with complete property cards
  i_detail              TEXT,
  
  j_deal_thesis         BOOLEAN DEFAULT FALSE,
  j_metric              NUMERIC(5,1),                  -- percentage with complete bid_decisions
  j_detail              TEXT,
  
  -- Summary
  pass_count            INTEGER DEFAULT 0,             -- count of TRUE letters (0-10)
  gold_standard         BOOLEAN DEFAULT FALSE,         -- all 10 letters pass
  critical_three_pass   BOOLEAN DEFAULT FALSE,         -- B, I, J all pass
  
  evaluated_at          TIMESTAMPTZ DEFAULT now(),
  
  UNIQUE(loop_run_id, county_slug)
);

CREATE SEQUENCE IF NOT EXISTS gold_standard_loop_run_seq;

-- View for latest Gold Standard status per county
CREATE OR REPLACE VIEW gold_standard_scoreboard AS
SELECT 
  gcs.*,
  fc.name AS county_name,
  fc.co_no
FROM gold_standard_county_status gcs
JOIN fl_counties fc ON fc.slug = gcs.county_slug
WHERE gcs.loop_run_id = (
  SELECT MAX(loop_run_id) 
  FROM gold_standard_county_status gcs2 
  WHERE gcs2.county_slug = gcs.county_slug
)
ORDER BY gcs.pass_count DESC, gcs.county_slug;

-- Function to evaluate single county Gold Standard status
CREATE OR REPLACE FUNCTION public.pencil_dod_evaluate_county(county_slug_arg TEXT)
RETURNS TABLE(
  letter TEXT,
  pass BOOLEAN,
  metric NUMERIC,
  detail TEXT,
  threshold TEXT
) 
LANGUAGE plpgsql
AS $$
DECLARE
  total_closed INTEGER;
  verified_outcomes_count INTEGER;
  matched_clean_count INTEGER;
  matched_any_count INTEGER;
  parcel_linked_count INTEGER;
  tier1_sold_count INTEGER;
  zoned_complete_count INTEGER;
  deal_complete_count INTEGER;
  latest_activity TIMESTAMPTZ;
  hours_since_activity NUMERIC;
  county_exists BOOLEAN;
BEGIN
  -- Check if county exists
  SELECT EXISTS(SELECT 1 FROM fl_counties WHERE slug = county_slug_arg) INTO county_exists;
  IF NOT county_exists THEN
    RETURN QUERY SELECT 'ERROR', FALSE, 0.0, 'County not found: ' || county_slug_arg, '';
    RETURN;
  END IF;

  -- Get base counts for this county
  SELECT COUNT(*) INTO total_closed 
  FROM multi_county_auctions 
  WHERE county = county_slug_arg 
    AND auction_status IN ('sold', 'no_sale', 'canceled');
    
  IF total_closed = 0 THEN
    RETURN QUERY SELECT 'ERROR', FALSE, 0.0, 'No closed auctions found for county', '';
    RETURN;
  END IF;

  -- A: Dual product coverage (both foreclosure and tax_deed present)
  RETURN QUERY
  SELECT 'A', 
    (SELECT COUNT(DISTINCT sale_type) FROM multi_county_auctions WHERE county = county_slug_arg) >= 2,
    (SELECT COUNT(DISTINCT sale_type) FROM multi_county_auctions WHERE county = county_slug_arg)::NUMERIC,
    'fc=' || COALESCE((SELECT COUNT(*) FROM multi_county_auctions WHERE county = county_slug_arg AND sale_type = 'foreclosure')::TEXT, '0') || 
    ' td=' || COALESCE((SELECT COUNT(*) FROM multi_county_auctions WHERE county = county_slug_arg AND sale_type = 'tax_deed')::TEXT, '0'),
    'Both sale types present';

  -- B: Verified outcomes from independent sources (≥95%)
  SELECT COUNT(*) INTO verified_outcomes_count
  FROM (
    SELECT 1 FROM tax_deed_outcomes 
    WHERE county_slug = county_slug_arg AND data_source NOT ILIKE '%propertyonion%'
    UNION ALL
    SELECT 1 FROM foreclosure_outcomes 
    WHERE county_slug = county_slug_arg AND data_source NOT ILIKE '%propertyonion%'
  ) verified;

  RETURN QUERY
  SELECT 'B',
    verified_outcomes_count >= (total_closed * 0.95)::INTEGER,
    CASE WHEN total_closed > 0 THEN (verified_outcomes_count * 100.0 / total_closed) ELSE 0 END,
    'verified=' || verified_outcomes_count::TEXT || ' closed_sold=' || total_closed::TEXT,
    '≥95% with independent outcomes';

  -- C: Parity clean (≥95%) 
  SELECT COUNT(*) INTO matched_clean_count
  FROM multi_county_auctions 
  WHERE county = county_slug_arg AND parity_status = 'matched_clean';

  RETURN QUERY
  SELECT 'C',
    matched_clean_count >= (total_closed * 0.95)::INTEGER,
    CASE WHEN total_closed > 0 THEN (matched_clean_count * 100.0 / total_closed) ELSE 0 END,
    'matched_clean=' || matched_clean_count::TEXT || ' of ' || total_closed::TEXT,
    '≥95% parity_clean';

  -- D: Parity any (≥95%)
  SELECT COUNT(*) INTO matched_any_count
  FROM multi_county_auctions 
  WHERE county = county_slug_arg AND parity_status IN ('matched_clean', 'matched_divergent');

  RETURN QUERY
  SELECT 'D',
    matched_any_count >= (total_closed * 0.95)::INTEGER, 
    CASE WHEN total_closed > 0 THEN (matched_any_count * 100.0 / total_closed) ELSE 0 END,
    'matched_any=' || matched_any_count::TEXT || ' of ' || total_closed::TEXT,
    '≥95% matched_clean or matched_divergent';

  -- E: Parcel linkage (≥95%)
  SELECT COUNT(*) INTO parcel_linked_count
  FROM multi_county_auctions 
  WHERE county = county_slug_arg AND parcel_id IS NOT NULL;

  RETURN QUERY
  SELECT 'E',
    parcel_linked_count >= (total_closed * 0.95)::INTEGER,
    CASE WHEN total_closed > 0 THEN (parcel_linked_count * 100.0 / total_closed) ELSE 0 END,
    'parcel_linked=' || parcel_linked_count::TEXT || ' of ' || total_closed::TEXT,
    '≥95% with parcel_id';

  -- F: Tier1 sold amount (≥95%)
  SELECT COUNT(*) INTO tier1_sold_count
  FROM multi_county_auctions 
  WHERE county = county_slug_arg 
    AND auction_status IN ('sold', 'no_sale', 'canceled')
    AND tier1_sold_amount IS NOT NULL;

  RETURN QUERY
  SELECT 'F',
    tier1_sold_count >= (total_closed * 0.95)::INTEGER,
    CASE WHEN total_closed > 0 THEN (tier1_sold_count * 100.0 / total_closed) ELSE 0 END,
    'tier1_sold=' || tier1_sold_count::TEXT || ' closed_sold=' || total_closed::TEXT,
    '≥95% with tier1_sold_amount';

  -- G: Zoning coverage (≥95% min(density, FAR, pk1000))
  RETURN QUERY
  SELECT 'G',
    FALSE,  -- Placeholder - needs v_zoning_gold_standard_kpi_v3
    0.0,
    'density= far= pk1000=',
    '≥95% zoning KPI coverage';

  -- H: Freshness (≤48h since last activity)
  SELECT MAX(GREATEST(created_at, updated_at, tier1_verified_at)) INTO latest_activity
  FROM multi_county_auctions 
  WHERE county = county_slug_arg;

  hours_since_activity := EXTRACT(EPOCH FROM (now() - latest_activity)) / 3600;

  RETURN QUERY
  SELECT 'H',
    hours_since_activity <= 48,
    hours_since_activity,
    'hours since last_seen (SLA 48h)',
    '≤48h since last activity';

  -- I: Property card complete (≥95% with address + geo + value + zoned parcel)
  RETURN QUERY
  SELECT 'I', 
    FALSE,  -- Placeholder - depends on property enrichment
    0.0,
    'zoned_complete_parcels=0 field_complete_parcels=251 auctions=' || total_closed::TEXT,
    '≥95% complete property cards';

  -- J: Deal thesis complete (≥95% with bid_decisions)
  SELECT COUNT(*) INTO deal_complete_count
  FROM multi_county_auctions mca
  JOIN bid_decisions bd ON bd.case_number = mca.case_number
  WHERE mca.county = county_slug_arg
    AND bd.arv IS NOT NULL 
    AND bd.max_bid IS NOT NULL 
    AND bd.ml_score IS NOT NULL;

  RETURN QUERY
  SELECT 'J',
    deal_complete_count >= (total_closed * 0.95)::INTEGER,
    CASE WHEN total_closed > 0 THEN (deal_complete_count * 100.0 / total_closed) ELSE 0 END,
    'deal_complete=' || deal_complete_count::TEXT || ' of ' || total_closed::TEXT || ' (triangle + two-arm CMA + ml_score + max_bid)',
    '≥95% with complete deal thesis';

END;
$$;

-- Grant permissions
GRANT SELECT ON tax_deed_outcomes TO anon, authenticated;
GRANT SELECT ON foreclosure_outcomes TO anon, authenticated;
GRANT SELECT ON gold_standard_county_status TO anon, authenticated;
GRANT SELECT ON gold_standard_scoreboard TO anon, authenticated;

COMMENT ON TABLE tax_deed_outcomes IS 'Independent verified tax deed auction outcomes for Gold Standard Letter B compliance';
COMMENT ON TABLE foreclosure_outcomes IS 'Independent verified foreclosure auction outcomes for Gold Standard Letter B compliance';
COMMENT ON FUNCTION pencil_dod_evaluate_county IS 'Evaluates Gold Standard A-J criteria for a single county - used for ad-hoc audits';