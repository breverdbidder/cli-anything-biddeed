-- ============================================================
-- SHAPIRA FORMULA SCHEMA FOR LETTER J
-- Migration: 20260610_shapira_formula.sql
-- Adds deal analysis and bid decisions for Letter J compliance  
-- ============================================================

-- Add Shapira Formula fields to multi_county_auctions
DO $$
BEGIN
  -- Bid decisions JSON (complete deal analysis)
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'bid_decisions'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN bid_decisions JSONB;
  END IF;
  
  -- Deal completeness flag
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'deal_complete'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN deal_complete BOOLEAN DEFAULT false;
  END IF;
  
  -- Analysis metadata
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'analyzed_at'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN analyzed_at TIMESTAMPTZ;
  END IF;
  
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'analyzed_by'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN analyzed_by TEXT;
  END IF;
  
  -- Individual Shapira components (extracted for easy querying)
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'arv'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN arv NUMERIC(15,2);
  END IF;
  
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'repair_estimate'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN repair_estimate NUMERIC(15,2);
  END IF;
  
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'max_bid'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN max_bid NUMERIC(15,2);
  END IF;
  
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'ml_score'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN ml_score NUMERIC(3,2);
  END IF;
END $$;

-- Deal analysis results tracking table
CREATE TABLE IF NOT EXISTS deal_analysis_results (
  id                    SERIAL PRIMARY KEY,
  county                TEXT NOT NULL,
  evaluation_date       DATE NOT NULL DEFAULT CURRENT_DATE,
  total_auctions        INTEGER NOT NULL,
  complete_deals        INTEGER NOT NULL,
  completion_rate       NUMERIC(5,2) NOT NULL,
  avg_arv               NUMERIC(15,2),
  avg_max_bid           NUMERIC(15,2),
  avg_ml_score          NUMERIC(3,2),
  analysis_method       TEXT DEFAULT 'shapira_formula_v1',
  evaluation_notes      TEXT,
  created_at            TIMESTAMPTZ DEFAULT now(),
  UNIQUE(county, evaluation_date)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_multi_county_auctions_deal_complete ON multi_county_auctions(deal_complete);
CREATE INDEX IF NOT EXISTS idx_multi_county_auctions_analyzed_at ON multi_county_auctions(analyzed_at);
CREATE INDEX IF NOT EXISTS idx_multi_county_auctions_bid_decisions ON multi_county_auctions USING GIN(bid_decisions);
CREATE INDEX IF NOT EXISTS idx_deal_analysis_results_county ON deal_analysis_results(county);

-- Gold Standard Letter J evaluation function
CREATE OR REPLACE FUNCTION evaluate_letter_j_county(p_county TEXT)
RETURNS JSON AS $$
DECLARE
  total_auctions INTEGER;
  complete_deals INTEGER;
  completion_rate NUMERIC(5,2);
  avg_arv NUMERIC(15,2);
  avg_max_bid NUMERIC(15,2);
  avg_ml_score NUMERIC(3,2);
  shapira_components JSON;
  result JSON;
BEGIN
  -- Count total auctions
  SELECT COUNT(*) INTO total_auctions
  FROM multi_county_auctions 
  WHERE county = p_county;
  
  -- Count complete deals (with full Shapira analysis)
  SELECT COUNT(*) INTO complete_deals
  FROM multi_county_auctions 
  WHERE county = p_county 
    AND deal_complete = true
    AND bid_decisions IS NOT NULL
    AND bid_decisions ? 'arv'
    AND bid_decisions ? 'max_bid'
    AND bid_decisions ? 'ml_score'
    AND bid_decisions ? 'triangle_factors';
  
  -- Calculate completion rate
  completion_rate := CASE 
    WHEN total_auctions > 0 THEN (complete_deals::numeric / total_auctions * 100)
    ELSE 0 
  END;
  
  -- Get average Shapira components
  SELECT 
    ROUND(AVG(arv), 0),
    ROUND(AVG(max_bid), 0),
    ROUND(AVG(ml_score), 2)
  INTO avg_arv, avg_max_bid, avg_ml_score
  FROM multi_county_auctions 
  WHERE county = p_county 
    AND deal_complete = true;
  
  -- Get component breakdown
  SELECT json_build_object(
    'with_arv', COUNT(*) FILTER (WHERE arv IS NOT NULL AND arv > 0),
    'with_max_bid', COUNT(*) FILTER (WHERE max_bid IS NOT NULL),
    'with_ml_score', COUNT(*) FILTER (WHERE ml_score IS NOT NULL),
    'with_triangle_factors', COUNT(*) FILTER (WHERE bid_decisions ? 'triangle_factors'),
    'with_cma', COUNT(*) FILTER (WHERE bid_decisions ? 'two_arm_cma'),
    'total_analyzed', COUNT(*)
  ) INTO shapira_components
  FROM multi_county_auctions 
  WHERE county = p_county 
    AND deal_complete = true;
  
  -- Build result
  result := json_build_object(
    'letter', 'J',
    'county', p_county,
    'total_auctions', total_auctions,
    'complete_deals', complete_deals,
    'completion_rate', completion_rate,
    'pass_threshold', 95.0,
    'passes', completion_rate >= 95.0,
    'shapira_averages', json_build_object(
      'avg_arv', avg_arv,
      'avg_max_bid', avg_max_bid,
      'avg_ml_score', avg_ml_score
    ),
    'component_breakdown', shapira_components,
    'evaluated_at', now()
  );
  
  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to extract Shapira components from bid_decisions JSON
CREATE OR REPLACE FUNCTION extract_shapira_components()
RETURNS TRIGGER AS $$
BEGIN
  -- Extract components from bid_decisions JSON for easy querying
  IF NEW.bid_decisions IS NOT NULL THEN
    NEW.arv := (NEW.bid_decisions->>'arv')::numeric;
    NEW.max_bid := (NEW.bid_decisions->>'max_bid')::numeric;
    NEW.ml_score := (NEW.bid_decisions->>'ml_score')::numeric;
    NEW.repair_estimate := (NEW.bid_decisions->>'repair_estimate')::numeric;
    
    -- Set deal_complete if all required components present
    IF NEW.bid_decisions ? 'arv' 
       AND NEW.bid_decisions ? 'max_bid'
       AND NEW.bid_decisions ? 'ml_score'
       AND NEW.bid_decisions ? 'triangle_factors' THEN
      NEW.deal_complete := true;
      NEW.analyzed_at := COALESCE(NEW.analyzed_at, now());
    END IF;
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger if it doesn't exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger 
    WHERE tgname = 'trg_extract_shapira_components'
  ) THEN
    CREATE TRIGGER trg_extract_shapira_components
      BEFORE INSERT OR UPDATE ON multi_county_auctions
      FOR EACH ROW
      WHEN (NEW.bid_decisions IS NOT NULL)
      EXECUTE FUNCTION extract_shapira_components();
  END IF;
END $$;

-- Function to find incomplete deals for analysis
CREATE OR REPLACE FUNCTION find_incomplete_deals(p_county TEXT, p_limit INTEGER DEFAULT 100)
RETURNS TABLE(
  auction_id BIGINT,
  case_number TEXT,
  property_address TEXT,
  assessed_value NUMERIC,
  opening_bid NUMERIC,
  has_coordinates BOOLEAN,
  has_parcel_id BOOLEAN
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    mca.id,
    mca.case_number,
    COALESCE(mca.property_address, mca.address) as property_address,
    mca.assessed_value,
    mca.opening_bid,
    (mca.latitude IS NOT NULL AND mca.longitude IS NOT NULL) as has_coordinates,
    (mca.parcel_id IS NOT NULL AND mca.parcel_id != '') as has_parcel_id
  FROM multi_county_auctions mca
  WHERE mca.county = p_county
    AND (mca.deal_complete IS NULL OR mca.deal_complete = false)
    AND mca.auction_date >= CURRENT_DATE - INTERVAL '2 years'  -- Recent auctions only
  ORDER BY 
    mca.assessed_value DESC NULLS LAST,  -- Prioritize higher value properties
    mca.auction_date DESC
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to record deal analysis results  
CREATE OR REPLACE FUNCTION record_deal_analysis_results(
  p_county TEXT,
  p_total_auctions INTEGER,
  p_complete_deals INTEGER,
  p_avg_arv NUMERIC DEFAULT NULL,
  p_avg_max_bid NUMERIC DEFAULT NULL,
  p_avg_ml_score NUMERIC DEFAULT NULL,
  p_notes TEXT DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
  calculated_rate NUMERIC(5,2);
BEGIN
  calculated_rate := CASE 
    WHEN p_total_auctions > 0 THEN (p_complete_deals::numeric / p_total_auctions * 100)
    ELSE 0 
  END;
  
  INSERT INTO deal_analysis_results (
    county,
    total_auctions,
    complete_deals,
    completion_rate,
    avg_arv,
    avg_max_bid,
    avg_ml_score,
    evaluation_notes
  ) VALUES (
    p_county,
    p_total_auctions,
    p_complete_deals,
    calculated_rate,
    p_avg_arv,
    p_avg_max_bid,
    p_avg_ml_score,
    p_notes
  )
  ON CONFLICT (county, evaluation_date)
  DO UPDATE SET
    total_auctions = EXCLUDED.total_auctions,
    complete_deals = EXCLUDED.complete_deals,
    completion_rate = EXCLUDED.completion_rate,
    avg_arv = EXCLUDED.avg_arv,
    avg_max_bid = EXCLUDED.avg_max_bid,
    avg_ml_score = EXCLUDED.avg_ml_score,
    evaluation_notes = EXCLUDED.evaluation_notes,
    created_at = now();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create deal completeness status view
CREATE OR REPLACE VIEW v_deal_completeness_status AS
SELECT 
  county,
  COUNT(*) as total_auctions,
  COUNT(*) FILTER (WHERE deal_complete = true) as complete_deals,
  ROUND(
    COUNT(*) FILTER (WHERE deal_complete = true)::numeric / 
    NULLIF(COUNT(*), 0) * 100, 
    1
  ) as completion_rate,
  ROUND(AVG(arv), 0) as avg_arv,
  ROUND(AVG(max_bid), 0) as avg_max_bid,
  ROUND(AVG(ml_score), 2) as avg_ml_score,
  COUNT(*) FILTER (WHERE bid_decisions ? 'arv') as with_arv,
  COUNT(*) FILTER (WHERE bid_decisions ? 'triangle_factors') as with_triangle_factors,
  MAX(analyzed_at) as last_analysis_update
FROM multi_county_auctions
WHERE auction_date >= CURRENT_DATE - INTERVAL '2 years'  -- Recent data only
GROUP BY county
ORDER BY completion_rate DESC;

-- Grant access
GRANT SELECT ON v_deal_completeness_status TO anon;
GRANT SELECT ON v_deal_completeness_status TO authenticated;