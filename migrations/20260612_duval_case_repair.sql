-- DUVAL CASE NUMBER REPAIR
-- Migration to repair PropertyOnion case numbers for C/D parity

-- Function to repair Duval PropertyOnion case numbers using parcel lookup
CREATE OR REPLACE FUNCTION public.repair_duval_case_numbers(limit_rows INTEGER DEFAULT 100)
RETURNS TABLE(
  po_case_number TEXT,
  court_case_number TEXT,
  parcel_id TEXT,
  auction_date DATE,
  repair_method TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
  repair_rec RECORD;
  repaired_count INTEGER := 0;
BEGIN
  -- Create temp table for results
  CREATE TEMP TABLE IF NOT EXISTS repair_results (
    po_case_number TEXT,
    court_case_number TEXT, 
    parcel_id TEXT,
    auction_date DATE,
    repair_method TEXT
  );
  
  -- Repair strategy 1: Direct parcel_id + auction_date lookup
  -- Look for court-format cases with same parcel_id and similar auction_date
  FOR repair_rec IN
    SELECT 
      po.case_number as po_case,
      court.case_number as court_case,
      po.parcel_id,
      po.auction_date,
      'parcel_date_match' as method
    FROM multi_county_auctions po
    JOIN multi_county_auctions court ON 
      court.county = 'duval'
      AND court.parcel_id = po.parcel_id  
      AND court.case_number NOT LIKE 'PO-%'
      AND ABS(EXTRACT(days FROM court.auction_date - po.auction_date)) <= 30
    WHERE 
      po.county = 'duval'
      AND po.case_number LIKE 'PO-%'
      AND po.parcel_id IS NOT NULL
    LIMIT limit_rows
  LOOP
    -- Insert to temp results
    INSERT INTO pg_temp.repair_results VALUES (
      repair_rec.po_case,
      repair_rec.court_case, 
      repair_rec.parcel_id,
      repair_rec.auction_date,
      repair_rec.method
    );
    
    repaired_count := repaired_count + 1;
  END LOOP;
  
  -- Return results
  RETURN QUERY SELECT * FROM pg_temp.repair_results;
  
END;
$$;

-- Function to apply case number repairs
CREATE OR REPLACE FUNCTION public.apply_duval_case_repairs()
RETURNS INTEGER
LANGUAGE plpgsql  
AS $$
DECLARE
  repair_rec RECORD;
  applied_count INTEGER := 0;
BEGIN
  -- Apply repairs found by repair function
  FOR repair_rec IN
    SELECT * FROM public.repair_duval_case_numbers(1000)
  LOOP
    -- Update the PropertyOnion case to use court case number
    UPDATE multi_county_auctions
    SET 
      case_number = repair_rec.court_case_number,
      updated_at = now(),
      case_number_source = 'repaired_from_' || repair_rec.po_case_number
    WHERE 
      county = 'duval'
      AND case_number = repair_rec.po_case_number;
      
    IF FOUND THEN
      applied_count := applied_count + 1;
    END IF;
  END LOOP;
  
  RETURN applied_count;
END;
$$;

-- Function to check repair progress
CREATE OR REPLACE FUNCTION public.duval_case_repair_status()
RETURNS TABLE(
  total_duval INTEGER,
  po_cases INTEGER,
  court_cases INTEGER,
  po_with_parcel INTEGER,
  repair_candidates INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT 
    (SELECT COUNT(*)::INTEGER FROM multi_county_auctions WHERE county = 'duval'),
    (SELECT COUNT(*)::INTEGER FROM multi_county_auctions WHERE county = 'duval' AND case_number LIKE 'PO-%'),
    (SELECT COUNT(*)::INTEGER FROM multi_county_auctions WHERE county = 'duval' AND case_number NOT LIKE 'PO-%'),
    (SELECT COUNT(*)::INTEGER FROM multi_county_auctions WHERE county = 'duval' AND case_number LIKE 'PO-%' AND parcel_id IS NOT NULL),
    -- Estimate repair candidates
    (SELECT COUNT(*)::INTEGER FROM multi_county_auctions po 
     WHERE po.county = 'duval' AND po.case_number LIKE 'PO-%' AND po.parcel_id IS NOT NULL
     AND EXISTS (
       SELECT 1 FROM multi_county_auctions court 
       WHERE court.county = 'duval' 
         AND court.parcel_id = po.parcel_id
         AND court.case_number NOT LIKE 'PO-%'
         AND ABS(EXTRACT(days FROM court.auction_date - po.auction_date)) <= 30
     ));
END;
$$;

-- Add case_number_source column if it doesn't exist
ALTER TABLE multi_county_auctions 
ADD COLUMN IF NOT EXISTS case_number_source TEXT;

-- Create index for efficient PropertyOnion case lookups
CREATE INDEX IF NOT EXISTS idx_mca_duval_po_cases 
ON multi_county_auctions(county, case_number) 
WHERE county = 'duval' AND case_number LIKE 'PO-%';

-- Create index for parcel-based lookups
CREATE INDEX IF NOT EXISTS idx_mca_duval_parcel_date 
ON multi_county_auctions(county, parcel_id, auction_date) 
WHERE county = 'duval';

-- Grant permissions
GRANT EXECUTE ON FUNCTION public.repair_duval_case_numbers(INTEGER) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.apply_duval_case_repairs() TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.duval_case_repair_status() TO anon, authenticated;

-- Comments
COMMENT ON FUNCTION public.repair_duval_case_numbers(INTEGER) IS 'Identifies PropertyOnion cases that can be repaired with court case numbers via parcel matching';
COMMENT ON FUNCTION public.apply_duval_case_repairs() IS 'Applies case number repairs to fix Duval C/D parity issues';
COMMENT ON FUNCTION public.duval_case_repair_status() IS 'Reports progress on Duval case number repair initiative';