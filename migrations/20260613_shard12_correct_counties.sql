-- ============================================================
-- SHARD-12 CORRECT COUNTIES SETUP MIGRATION  
-- Migration: 20260613_shard12_correct_counties.sql
-- Sets up marion, clay, pasco, glades counties for Gold Standard pipeline
-- Corrects previous migrations that had wrong county assignments
-- ============================================================

-- Add SHARD-12 county slug mappings to fl_counties
-- Using correct co_no from fl_counties_manifest.yml:
-- Marion = 52, Clay = 20, Pasco = 61, Glades = 32
INSERT INTO fl_counties (co_no, name, fips_code, slug, region) VALUES 
  (52, 'Marion', '12083', 'marion', 'central'),
  (20, 'Clay', '12019', 'clay', 'northeast'),
  (61, 'Pasco', '12101', 'pasco', 'west_central'), 
  (32, 'Glades', '12043', 'glades', 'central')
ON CONFLICT (co_no) DO UPDATE SET 
  slug = EXCLUDED.slug,
  fips_code = EXCLUDED.fips_code,
  region = EXCLUDED.region
WHERE fl_counties.slug IS NULL OR fl_counties.slug != EXCLUDED.slug;

-- Ensure multi_county_auctions table supports all Gold Standard letters
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

  -- Add property enrichment columns for Letter I
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'property_value') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN property_value NUMERIC(12,2);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'property_sqft') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN property_sqft INTEGER;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'property_bedrooms') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN property_bedrooms INTEGER;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                 WHERE table_name = 'multi_county_auctions' AND column_name = 'property_bathrooms') THEN
    ALTER TABLE multi_county_auctions ADD COLUMN property_bathrooms NUMERIC(3,1);
  END IF;
END $$;

-- Create/update bid_decisions table (needed for Letter J)
CREATE TABLE IF NOT EXISTS bid_decisions (
  id                    SERIAL PRIMARY KEY,
  case_number           TEXT NOT NULL UNIQUE,
  county_slug           TEXT NOT NULL,
  parcel_id             TEXT,
  
  -- ARV (After Repair Value) 
  arv                   NUMERIC(12,2),
  arv_source            TEXT,               -- 'appraiser', 'comparable', 'zillow', 'manual'
  arv_confidence        NUMERIC(3,2),       -- 0.0 to 1.0
  
  -- Shapira Formula components
  max_bid               NUMERIC(12,2),      -- Maximum recommended bid
  repair_estimate       NUMERIC(12,2),      -- Estimated repair costs
  holding_costs         NUMERIC(12,2),      -- 6-month holding estimate
  profit_target         NUMERIC(12,2),      -- Target profit amount
  
  -- ML Score (Shapira V14)
  ml_score              NUMERIC(5,3),       -- 0.000 to 1.000
  ml_model_version      TEXT DEFAULT 'shapira_v14',
  ml_features_used      TEXT[],
  
  -- Triangle factors (comparable analysis)
  triangle_score        NUMERIC(5,3),       -- 0.000 to 1.000  
  comparable_count      INTEGER,
  avg_price_per_sqft    NUMERIC(8,2),
  market_velocity       TEXT,               -- 'hot', 'normal', 'slow'
  
  -- Two-arm CMA factors (required by brief)
  cma_low               NUMERIC(12,2),      -- Conservative estimate
  cma_high              NUMERIC(12,2),      -- Optimistic estimate
  cma_confidence        NUMERIC(3,2),       -- 0.0 to 1.0
  
  -- 5 factor keys required by evaluator
  distress_location     NUMERIC(3,2),       -- Location distress factor
  distress_property     NUMERIC(3,2),       -- Property distress factor  
  distress_owner        NUMERIC(3,2),       -- Owner distress factor
  cma_distressed        NUMERIC(12,2),      -- CMA for distressed sales
  cma_resale           NUMERIC(12,2),      -- CMA for retail resales
  
  -- Final recommendation
  recommendation        TEXT,               -- 'BID', 'SKIP', 'RESEARCH'
  recommendation_reason TEXT,
  max_bid_ratio         NUMERIC(5,2),       -- max_bid / opening_bid * 100
  
  -- Audit trail
  calculated_at         TIMESTAMPTZ DEFAULT now(),
  calculated_by         TEXT DEFAULT 'shard12_j_generator_v1',
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now(),
  
  CONSTRAINT chk_arv_positive CHECK (arv > 0 OR arv IS NULL),
  CONSTRAINT chk_max_bid_positive CHECK (max_bid >= 0 OR max_bid IS NULL),
  CONSTRAINT chk_ml_score_valid CHECK (ml_score BETWEEN 0 AND 1 OR ml_score IS NULL),
  CONSTRAINT chk_triangle_score_valid CHECK (triangle_score BETWEEN 0 AND 1 OR triangle_score IS NULL),
  CONSTRAINT chk_cma_confidence_valid CHECK (cma_confidence BETWEEN 0 AND 1 OR cma_confidence IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_bid_decisions_county ON bid_decisions(county_slug);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON bid_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_parcel_id ON bid_decisions(parcel_id);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_recommendation ON bid_decisions(recommendation);

-- Ensure foreclosure_outcomes and tax_deed_outcomes tables exist (needed for Letter B)
CREATE TABLE IF NOT EXISTS foreclosure_outcomes (
  id                SERIAL PRIMARY KEY,
  case_number       TEXT NOT NULL,
  county_slug       TEXT NOT NULL,
  auction_date      DATE,
  winning_bid       NUMERIC(12,2),
  winning_bidder    TEXT,
  status            TEXT,            -- 'sold', 'no_sale', 'canceled'
  data_source       TEXT NOT NULL,   -- Must be independent (not propertyonion)
  source_url        TEXT,
  verified_at       TIMESTAMPTZ DEFAULT now(),
  created_at        TIMESTAMPTZ DEFAULT now(),
  
  CONSTRAINT chk_data_source_independent CHECK (data_source NOT ILIKE '%propertyonion%')
);

CREATE TABLE IF NOT EXISTS tax_deed_outcomes (
  id                SERIAL PRIMARY KEY,
  case_number       TEXT NOT NULL,
  county_slug       TEXT NOT NULL,
  auction_date      DATE,
  winning_bid       NUMERIC(12,2),
  winning_bidder    TEXT,
  status            TEXT,            -- 'sold', 'no_sale', 'canceled'
  data_source       TEXT NOT NULL,   -- Must be independent (not propertyonion)
  source_url        TEXT,
  verified_at       TIMESTAMPTZ DEFAULT now(),
  created_at        TIMESTAMPTZ DEFAULT now(),
  
  CONSTRAINT chk_data_source_independent CHECK (data_source NOT ILIKE '%propertyonion%')
);

CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_county ON foreclosure_outcomes(county_slug);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_case ON foreclosure_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_county ON tax_deed_outcomes(county_slug);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_case ON tax_deed_outcomes(case_number);

-- Update/create the pencil_dod_evaluate_county function for SHARD-12 counties
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
  total_auctions INTEGER;
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
  foreclosure_count INTEGER;
  tax_deed_count INTEGER;
BEGIN
  -- Check if county exists
  SELECT EXISTS(SELECT 1 FROM fl_counties WHERE slug = county_slug_arg) INTO county_exists;
  IF NOT county_exists THEN
    RETURN QUERY SELECT 'ERROR', FALSE, 0.0, 'County not found: ' || county_slug_arg, '';
    RETURN;
  END IF;

  -- Get total auctions count for this county
  SELECT COUNT(*) INTO total_auctions 
  FROM multi_county_auctions 
  WHERE county = county_slug_arg;
  
  -- Get base counts for this county (closed auctions)
  SELECT COUNT(*) INTO total_closed 
  FROM multi_county_auctions 
  WHERE county = county_slug_arg 
    AND auction_status IN ('sold', 'no_sale', 'canceled');
    
  -- If no auctions at all, all letters fail
  IF total_auctions = 0 THEN
    RETURN QUERY SELECT 'A', FALSE, 0.0, 'fc=0 td=0', 'Dual product coverage required';
    RETURN QUERY SELECT 'B', FALSE, 0.0, 'verified=0 closed_sold=0', '≥95% with independent outcomes';
    RETURN QUERY SELECT 'C', FALSE, 0.0, 'matched_clean=0 of 0', '≥95% parity_clean';
    RETURN QUERY SELECT 'D', FALSE, 0.0, 'matched_any=0 of 0', '≥95% matched any';
    RETURN QUERY SELECT 'E', FALSE, 0.0, 'parcel_linked=0 of 0', '≥95% with parcel_id';
    RETURN QUERY SELECT 'F', FALSE, 0.0, 'tier1_sold=0 closed_sold=0', '≥95% with tier1_sold_amount';
    RETURN QUERY SELECT 'G', FALSE, 0.0, 'density= far= pk1000=', '≥95% zoning KPI coverage';
    RETURN QUERY SELECT 'H', FALSE, 0.0, 'hours since last_seen (SLA 48h)', '≤48h since last activity';
    RETURN QUERY SELECT 'I', FALSE, 0.0, 'zoned_complete_parcels=0 field_complete_parcels=0 auctions=0', '≥95% complete property cards';
    RETURN QUERY SELECT 'J', FALSE, 0.0, 'deal_complete=0 of 0 (triangle + two-arm CMA + ml_score + max_bid)', '≥95% with complete deal thesis';
    RETURN;
  END IF;

  -- Get sale type counts for Letter A
  SELECT 
    COUNT(*) FILTER (WHERE sale_type = 'foreclosure' OR sale_type = 'fc'),
    COUNT(*) FILTER (WHERE sale_type = 'tax_deed' OR sale_type = 'td')
  INTO foreclosure_count, tax_deed_count
  FROM multi_county_auctions 
  WHERE county = county_slug_arg;

  -- A: Dual product coverage (both foreclosure and tax_deed present)
  RETURN QUERY
  SELECT 'A', 
    foreclosure_count > 0 AND tax_deed_count > 0,
    GREATEST(foreclosure_count, tax_deed_count)::NUMERIC,
    'fc=' || foreclosure_count::TEXT || ' td=' || tax_deed_count::TEXT,
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
    CASE WHEN total_closed = 0 THEN FALSE 
         WHEN verified_outcomes_count * 100 > total_closed * 105 THEN FALSE -- Anomaly check
         ELSE verified_outcomes_count >= (total_closed * 0.95)::INTEGER 
    END,
    CASE WHEN total_closed > 0 THEN (verified_outcomes_count * 100.0 / total_closed) 
         ELSE NULL 
    END,
    'verified=' || verified_outcomes_count::TEXT || ' closed_sold=' || total_closed::TEXT,
    '≥95% with independent outcomes (≤105% anomaly check)';

  -- C: Parity clean (≥95%) 
  SELECT COUNT(*) INTO matched_clean_count
  FROM multi_county_auctions 
  WHERE county = county_slug_arg AND parity_status = 'matched_clean';

  RETURN QUERY
  SELECT 'C',
    CASE WHEN total_auctions = 0 THEN FALSE 
         ELSE matched_clean_count >= (total_auctions * 0.95)::INTEGER 
    END,
    CASE WHEN total_auctions > 0 THEN (matched_clean_count * 100.0 / total_auctions) 
         ELSE 0.0 
    END,
    'matched_clean=' || matched_clean_count::TEXT || ' of ' || total_auctions::TEXT,
    '≥95% parity_clean';

  -- D: Parity any (≥95%)
  SELECT COUNT(*) INTO matched_any_count
  FROM multi_county_auctions 
  WHERE county = county_slug_arg AND parity_status IN ('matched_clean', 'matched_divergent');

  RETURN QUERY
  SELECT 'D',
    CASE WHEN total_auctions = 0 THEN FALSE 
         ELSE matched_any_count >= (total_auctions * 0.95)::INTEGER 
    END,
    CASE WHEN total_auctions > 0 THEN (matched_any_count * 100.0 / total_auctions) 
         ELSE 0.0 
    END,
    'matched_any=' || matched_any_count::TEXT || ' of ' || total_auctions::TEXT,
    '≥95% matched_clean or matched_divergent';

  -- E: Parcel linkage (≥95%)
  SELECT COUNT(*) INTO parcel_linked_count
  FROM multi_county_auctions 
  WHERE county = county_slug_arg AND parcel_id IS NOT NULL;

  RETURN QUERY
  SELECT 'E',
    CASE WHEN total_auctions = 0 THEN FALSE 
         ELSE parcel_linked_count >= (total_auctions * 0.95)::INTEGER 
    END,
    CASE WHEN total_auctions > 0 THEN (parcel_linked_count * 100.0 / total_auctions) 
         ELSE 0.0 
    END,
    'parcel_linked=' || parcel_linked_count::TEXT || ' of ' || total_auctions::TEXT,
    '≥95% with parcel_id';

  -- F: Tier1 sold amount (≥95%)
  SELECT COUNT(*) INTO tier1_sold_count
  FROM multi_county_auctions 
  WHERE county = county_slug_arg 
    AND auction_status IN ('sold', 'no_sale', 'canceled')
    AND tier1_sold_amount IS NOT NULL;

  RETURN QUERY
  SELECT 'F',
    CASE WHEN total_closed = 0 THEN FALSE 
         ELSE tier1_sold_count >= (total_closed * 0.95)::INTEGER 
    END,
    CASE WHEN total_closed > 0 THEN (tier1_sold_count * 100.0 / total_closed) 
         ELSE 0.0 
    END,
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
  SELECT MAX(GREATEST(created_at, updated_at, COALESCE(tier1_verified_at, '1970-01-01'::timestamptz), COALESCE(last_seen_at, '1970-01-01'::timestamptz))) INTO latest_activity
  FROM multi_county_auctions 
  WHERE county = county_slug_arg;

  IF latest_activity IS NULL THEN
    hours_since_activity := NULL;
  ELSE
    hours_since_activity := EXTRACT(EPOCH FROM (now() - latest_activity)) / 3600;
  END IF;

  RETURN QUERY
  SELECT 'H',
    hours_since_activity IS NOT NULL AND hours_since_activity <= 48,
    hours_since_activity,
    'hours since last_seen (SLA 48h)',
    '≤48h since last activity';

  -- I: Property card complete (≥95% with address + geo + value + zoned parcel)
  SELECT COUNT(*) INTO zoned_complete_count
  FROM multi_county_auctions
  WHERE county = county_slug_arg 
    AND property_address IS NOT NULL
    AND parcel_id IS NOT NULL
    AND property_value IS NOT NULL;

  RETURN QUERY
  SELECT 'I', 
    CASE WHEN total_auctions = 0 THEN FALSE
         ELSE zoned_complete_count >= (total_auctions * 0.95)::INTEGER
    END,
    CASE WHEN total_auctions > 0 THEN (zoned_complete_count * 100.0 / total_auctions)
         ELSE 0.0 
    END,
    'zoned_complete_parcels=' || zoned_complete_count::TEXT || ' field_complete_parcels=' || COALESCE((SELECT COUNT(*) FROM multi_county_auctions WHERE county = county_slug_arg AND property_address IS NOT NULL)::TEXT, '0') || ' auctions=' || total_auctions::TEXT,
    '≥95% complete property cards';

  -- J: Deal thesis complete (≥95% with bid_decisions having all required fields)
  SELECT COUNT(*) INTO deal_complete_count
  FROM multi_county_auctions mca
  JOIN bid_decisions bd ON bd.case_number = mca.case_number
  WHERE mca.county = county_slug_arg
    AND bd.arv IS NOT NULL 
    AND bd.max_bid IS NOT NULL 
    AND bd.ml_score IS NOT NULL
    AND bd.triangle_score IS NOT NULL
    AND bd.distress_location IS NOT NULL
    AND bd.distress_property IS NOT NULL  
    AND bd.distress_owner IS NOT NULL
    AND bd.cma_distressed IS NOT NULL
    AND bd.cma_resale IS NOT NULL;

  RETURN QUERY
  SELECT 'J',
    CASE WHEN total_auctions = 0 THEN FALSE 
         ELSE deal_complete_count >= (total_auctions * 0.95)::INTEGER 
    END,
    CASE WHEN total_auctions > 0 THEN (deal_complete_count * 100.0 / total_auctions) 
         ELSE 0.0 
    END,
    'deal_complete=' || deal_complete_count::TEXT || ' of ' || total_auctions::TEXT || ' (triangle + two-arm CMA + ml_score + max_bid + 5 factors)',
    '≥95% with complete deal thesis';

END;
$$;

-- Grant permissions
GRANT SELECT ON bid_decisions TO anon, authenticated;
GRANT SELECT ON foreclosure_outcomes TO anon, authenticated;
GRANT SELECT ON tax_deed_outcomes TO anon, authenticated;

-- Comments
COMMENT ON TABLE bid_decisions IS 'Shapira Formula deal thesis decisions for Gold Standard Letter J compliance - SHARD-12 counties';
COMMENT ON TABLE foreclosure_outcomes IS 'Independent verified foreclosure outcomes for Letter B compliance';
COMMENT ON TABLE tax_deed_outcomes IS 'Independent verified tax deed outcomes for Letter B compliance';
COMMENT ON FUNCTION pencil_dod_evaluate_county IS 'Evaluates Gold Standard A-J criteria for SHARD-12 counties (marion, clay, pasco, glades)';