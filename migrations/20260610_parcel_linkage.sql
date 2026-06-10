-- ============================================================
-- PARCEL LINKAGE SCHEMA FOR LETTER E
-- Migration: 20260610_parcel_linkage.sql  
-- Adds parcel linkage tracking and evaluation for Letter E compliance
-- ============================================================

-- Add parcel linkage fields to multi_county_auctions
DO $$
BEGIN
  -- Linkage method tracking
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'link_method'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN link_method TEXT;
  END IF;
  
  -- Address matching metadata
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'matched_address'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN matched_address TEXT;
  END IF;
  
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'similarity_score'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN similarity_score NUMERIC(3,2);
  END IF;
  
  -- Coordinate matching metadata  
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'matched_coordinates'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN matched_coordinates TEXT;
  END IF;
  
  -- Linkage timestamps
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'linked_at'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN linked_at TIMESTAMPTZ;
  END IF;
  
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'linked_by'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN linked_by TEXT;
  END IF;
END $$;

-- Parcel linkage results tracking table
CREATE TABLE IF NOT EXISTS parcel_linkage_results (
  id                    SERIAL PRIMARY KEY,
  county                TEXT NOT NULL,
  evaluation_date       DATE NOT NULL DEFAULT CURRENT_DATE,
  total_auctions        INTEGER NOT NULL,
  linked_auctions       INTEGER NOT NULL,
  linkage_rate          NUMERIC(5,2) NOT NULL,
  address_matches       INTEGER DEFAULT 0,
  coordinate_matches    INTEGER DEFAULT 0,
  manual_matches        INTEGER DEFAULT 0,
  method_breakdown      JSONB,
  evaluation_notes      TEXT,
  created_at            TIMESTAMPTZ DEFAULT now(),
  UNIQUE(county, evaluation_date)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_multi_county_auctions_parcel_id ON multi_county_auctions(parcel_id);
CREATE INDEX IF NOT EXISTS idx_multi_county_auctions_link_method ON multi_county_auctions(link_method);
CREATE INDEX IF NOT EXISTS idx_multi_county_auctions_linked_at ON multi_county_auctions(linked_at);
CREATE INDEX IF NOT EXISTS idx_parcel_linkage_results_county ON parcel_linkage_results(county);

-- Gold Standard Letter E evaluation function
CREATE OR REPLACE FUNCTION evaluate_letter_e_county(p_county TEXT)
RETURNS JSON AS $$
DECLARE
  total_auctions INTEGER;
  linked_auctions INTEGER;
  linkage_rate NUMERIC(5,2);
  method_breakdown JSONB;
  result JSON;
BEGIN
  -- Count total auctions
  SELECT COUNT(*) INTO total_auctions
  FROM multi_county_auctions 
  WHERE county = p_county;
  
  -- Count linked auctions (with parcel_id)
  SELECT COUNT(*) INTO linked_auctions
  FROM multi_county_auctions 
  WHERE county = p_county 
    AND parcel_id IS NOT NULL
    AND parcel_id != '';
  
  -- Calculate linkage rate
  linkage_rate := CASE 
    WHEN total_auctions > 0 THEN (linked_auctions::numeric / total_auctions * 100)
    ELSE 0 
  END;
  
  -- Get method breakdown
  SELECT json_object_agg(
    COALESCE(link_method, 'unknown'), 
    count
  ) INTO method_breakdown
  FROM (
    SELECT 
      link_method,
      COUNT(*) as count
    FROM multi_county_auctions 
    WHERE county = p_county 
      AND parcel_id IS NOT NULL
    GROUP BY link_method
  ) sub;
  
  -- Build result
  result := json_build_object(
    'letter', 'E',
    'county', p_county,
    'total_auctions', total_auctions,
    'linked_auctions', linked_auctions,
    'linkage_rate', linkage_rate,
    'pass_threshold', 95.0,
    'passes', linkage_rate >= 95.0,
    'method_breakdown', COALESCE(method_breakdown, '{}'::jsonb),
    'evaluated_at', now()
  );
  
  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to find candidates for parcel linking
CREATE OR REPLACE FUNCTION find_parcel_linkage_candidates(p_county TEXT, p_limit INTEGER DEFAULT 100)
RETURNS TABLE(
  auction_id BIGINT,
  case_number TEXT,
  property_address TEXT,
  latitude NUMERIC,
  longitude NUMERIC,
  missing_parcel_id BOOLEAN
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    mca.id,
    mca.case_number,
    COALESCE(mca.property_address, mca.address) as property_address,
    mca.latitude,
    mca.longitude,
    (mca.parcel_id IS NULL OR mca.parcel_id = '') as missing_parcel_id
  FROM multi_county_auctions mca
  WHERE mca.county = p_county
    AND (mca.parcel_id IS NULL OR mca.parcel_id = '')
    AND (
      mca.property_address IS NOT NULL 
      OR mca.address IS NOT NULL 
      OR (mca.latitude IS NOT NULL AND mca.longitude IS NOT NULL)
    )
  ORDER BY mca.auction_date DESC, mca.created_at DESC
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to record parcel linkage results
CREATE OR REPLACE FUNCTION record_parcel_linkage_results(
  p_county TEXT,
  p_total_auctions INTEGER,
  p_linked_auctions INTEGER,
  p_method_breakdown JSONB DEFAULT NULL,
  p_notes TEXT DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
  calculated_rate NUMERIC(5,2);
BEGIN
  calculated_rate := CASE 
    WHEN p_total_auctions > 0 THEN (p_linked_auctions::numeric / p_total_auctions * 100)
    ELSE 0 
  END;
  
  INSERT INTO parcel_linkage_results (
    county,
    total_auctions,
    linked_auctions,
    linkage_rate,
    method_breakdown,
    evaluation_notes
  ) VALUES (
    p_county,
    p_total_auctions,
    p_linked_auctions,
    calculated_rate,
    p_method_breakdown,
    p_notes
  )
  ON CONFLICT (county, evaluation_date)
  DO UPDATE SET
    total_auctions = EXCLUDED.total_auctions,
    linked_auctions = EXCLUDED.linked_auctions,
    linkage_rate = EXCLUDED.linkage_rate,
    method_breakdown = EXCLUDED.method_breakdown,
    evaluation_notes = EXCLUDED.evaluation_notes,
    created_at = now();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to update linkage statistics when parcel_id is set
CREATE OR REPLACE FUNCTION update_linkage_stats()
RETURNS TRIGGER AS $$
BEGIN
  -- If parcel_id was added/changed, update linked_at timestamp
  IF (OLD.parcel_id IS NULL OR OLD.parcel_id = '') AND NEW.parcel_id IS NOT NULL AND NEW.parcel_id != '' THEN
    NEW.linked_at := COALESCE(NEW.linked_at, now());
    NEW.linked_by := COALESCE(NEW.linked_by, 'auto_trigger');
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger if it doesn't exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger 
    WHERE tgname = 'trg_update_linkage_stats'
  ) THEN
    CREATE TRIGGER trg_update_linkage_stats
      BEFORE UPDATE ON multi_county_auctions
      FOR EACH ROW
      EXECUTE FUNCTION update_linkage_stats();
  END IF;
END $$;

-- Create parcel linkage status view
CREATE OR REPLACE VIEW v_parcel_linkage_status AS
SELECT 
  county,
  COUNT(*) as total_auctions,
  COUNT(*) FILTER (WHERE parcel_id IS NOT NULL AND parcel_id != '') as linked_auctions,
  ROUND(
    COUNT(*) FILTER (WHERE parcel_id IS NOT NULL AND parcel_id != '')::numeric / 
    NULLIF(COUNT(*), 0) * 100, 
    1
  ) as linkage_rate,
  COUNT(*) FILTER (WHERE link_method = 'address_match') as address_matches,
  COUNT(*) FILTER (WHERE link_method = 'coordinate_match') as coordinate_matches,
  COUNT(*) FILTER (WHERE link_method IS NULL AND parcel_id IS NOT NULL) as legacy_matches,
  MAX(linked_at) as last_linkage_update
FROM multi_county_auctions
GROUP BY county
ORDER BY linkage_rate DESC;

-- Grant access
GRANT SELECT ON v_parcel_linkage_status TO anon;
GRANT SELECT ON v_parcel_linkage_status TO authenticated;