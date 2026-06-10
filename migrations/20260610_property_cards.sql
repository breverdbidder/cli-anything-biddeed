-- ============================================================
-- PROPERTY CARD COMPLETION SCHEMA FOR LETTER I
-- Migration: 20260610_property_cards.sql
-- Adds property card completeness tracking to multi_county_auctions
-- ============================================================

-- Add property card completion fields to multi_county_auctions
DO $$
BEGIN
  -- Address completion
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'property_address'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN property_address TEXT;
  END IF;
  
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'address_complete'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN address_complete BOOLEAN DEFAULT false;
  END IF;
  
  -- Geo coordinates
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'latitude'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN latitude NUMERIC(10,6);
  END IF;
  
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'longitude'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN longitude NUMERIC(10,6);
  END IF;
  
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'geo_complete'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN geo_complete BOOLEAN DEFAULT false;
  END IF;
  
  -- Property value
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'assessed_value'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN assessed_value NUMERIC(15,2);
  END IF;
  
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'value_complete'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN value_complete BOOLEAN DEFAULT false;
  END IF;
  
  -- Zoned parcel linkage
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'zone_code'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN zone_code TEXT;
  END IF;
  
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'zoned_complete'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN zoned_complete BOOLEAN DEFAULT false;
  END IF;
  
  -- Overall property card completion
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'property_card_complete'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN property_card_complete BOOLEAN DEFAULT false;
  END IF;
  
  -- Enrichment metadata
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'enriched_at'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN enriched_at TIMESTAMPTZ;
  END IF;
  
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'multi_county_auctions' AND column_name = 'enriched_by'
  ) THEN
    ALTER TABLE multi_county_auctions ADD COLUMN enriched_by TEXT;
  END IF;
END $$;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_multi_county_auctions_property_card_complete 
ON multi_county_auctions(property_card_complete);

CREATE INDEX IF NOT EXISTS idx_multi_county_auctions_county_complete 
ON multi_county_auctions(county, property_card_complete);

-- Gold Standard Letter I evaluation function  
CREATE OR REPLACE FUNCTION evaluate_letter_i_county(p_county TEXT)
RETURNS JSON AS $$
DECLARE
  total_auctions INTEGER;
  complete_property_cards INTEGER;
  completion_rate NUMERIC(5,2);
  field_completeness JSON;
  result JSON;
BEGIN
  -- Count total auctions for county
  SELECT COUNT(*) INTO total_auctions
  FROM multi_county_auctions 
  WHERE county = p_county;
  
  -- Count complete property cards
  SELECT COUNT(*) INTO complete_property_cards
  FROM multi_county_auctions 
  WHERE county = p_county 
    AND property_card_complete = true;
  
  -- Calculate completion rate
  completion_rate := CASE 
    WHEN total_auctions > 0 THEN (complete_property_cards::numeric / total_auctions * 100)
    ELSE 0 
  END;
  
  -- Get field-level completeness breakdown
  SELECT json_build_object(
    'address_complete', COUNT(*) FILTER (WHERE address_complete = true),
    'geo_complete', COUNT(*) FILTER (WHERE geo_complete = true),
    'value_complete', COUNT(*) FILTER (WHERE value_complete = true),
    'zoned_complete', COUNT(*) FILTER (WHERE zoned_complete = true),
    'total_auctions', COUNT(*)
  ) INTO field_completeness
  FROM multi_county_auctions 
  WHERE county = p_county;
  
  -- Build result
  result := json_build_object(
    'letter', 'I',
    'county', p_county,
    'total_auctions', total_auctions,
    'complete_property_cards', complete_property_cards,
    'completion_rate', completion_rate,
    'pass_threshold', 95.0,
    'passes', completion_rate >= 95.0,
    'field_completeness', field_completeness
  );
  
  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to auto-update property_card_complete when component fields change
CREATE OR REPLACE FUNCTION update_property_card_complete()
RETURNS TRIGGER AS $$
BEGIN
  NEW.property_card_complete := COALESCE(NEW.address_complete, false) 
                             AND COALESCE(NEW.geo_complete, false)
                             AND COALESCE(NEW.value_complete, false) 
                             AND COALESCE(NEW.zoned_complete, false);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger if it doesn't exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger 
    WHERE tgname = 'trg_update_property_card_complete'
  ) THEN
    CREATE TRIGGER trg_update_property_card_complete
      BEFORE INSERT OR UPDATE ON multi_county_auctions
      FOR EACH ROW
      EXECUTE FUNCTION update_property_card_complete();
  END IF;
END $$;

-- Create view for property card status dashboard
CREATE OR REPLACE VIEW v_property_card_status AS
SELECT 
  county,
  COUNT(*) as total_auctions,
  COUNT(*) FILTER (WHERE property_card_complete = true) as complete_cards,
  ROUND(
    COUNT(*) FILTER (WHERE property_card_complete = true)::numeric / 
    NULLIF(COUNT(*), 0) * 100, 
    1
  ) as completion_pct,
  COUNT(*) FILTER (WHERE address_complete = true) as address_complete_count,
  COUNT(*) FILTER (WHERE geo_complete = true) as geo_complete_count,
  COUNT(*) FILTER (WHERE value_complete = true) as value_complete_count,
  COUNT(*) FILTER (WHERE zoned_complete = true) as zoned_complete_count
FROM multi_county_auctions
GROUP BY county
ORDER BY completion_pct DESC;

-- Grant access to view
GRANT SELECT ON v_property_card_status TO anon;
GRANT SELECT ON v_property_card_status TO authenticated;