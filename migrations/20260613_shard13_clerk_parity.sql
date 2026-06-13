-- SHARD-13 Clerk Parity Records Migration
-- Target counties: orange, flagler, santa_rosa, gulf
-- Required for C/D letter supplementary litmus (pre-authorized)

-- Create clerk_parity_records table for supplementary litmus
CREATE TABLE IF NOT EXISTS clerk_parity_records (
    id SERIAL PRIMARY KEY,
    county_slug TEXT NOT NULL,
    case_number TEXT NOT NULL,
    record_type TEXT NOT NULL,
    sale_date DATE,
    parcel_id TEXT,
    document_id TEXT,
    clerk_url TEXT,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Ensure unique records per county/case/type
    UNIQUE(county_slug, case_number, record_type)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_clerk_parity_county_case 
    ON clerk_parity_records(county_slug, case_number);
CREATE INDEX IF NOT EXISTS idx_clerk_parity_parcel 
    ON clerk_parity_records(parcel_id);
CREATE INDEX IF NOT EXISTS idx_clerk_parity_sale_date 
    ON clerk_parity_records(sale_date);
CREATE INDEX IF NOT EXISTS idx_clerk_parity_document 
    ON clerk_parity_records(document_id);

-- Add clerk matching columns to multi_county_auctions
ALTER TABLE multi_county_auctions ADD COLUMN IF NOT EXISTS clerk_document_id TEXT;
ALTER TABLE multi_county_auctions ADD COLUMN IF NOT EXISTS clerk_match_source TEXT;

-- Index for clerk matching performance
CREATE INDEX IF NOT EXISTS idx_mca_clerk_document 
    ON multi_county_auctions(clerk_document_id);

-- RLS policies for clerk_parity_records
ALTER TABLE clerk_parity_records ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY IF NOT EXISTS "Enable all for service role" ON clerk_parity_records
  FOR ALL USING (true);

-- Public read access for authenticated users
CREATE POLICY IF NOT EXISTS "Enable read for authenticated users" ON clerk_parity_records
  FOR SELECT USING (auth.role() = 'authenticated');

-- Specific policy for SHARD-13 counties
CREATE POLICY IF NOT EXISTS "Enable SHARD-13 counties" ON clerk_parity_records
  FOR ALL USING (county_slug IN ('orange', 'flagler', 'santa_rosa', 'gulf'));

-- Function to update parity status with clerk data
CREATE OR REPLACE FUNCTION update_parity_with_clerk_data(target_county TEXT)
RETURNS TABLE(
  updated_count BIGINT,
  enhanced_clean_count BIGINT,
  enhanced_any_count BIGINT,
  verification_timestamp TIMESTAMPTZ
) AS $$
DECLARE
  update_count BIGINT := 0;
  clean_count BIGINT := 0;
  any_count BIGINT := 0;
BEGIN
  -- Update multi_county_auctions with clerk parity data
  UPDATE multi_county_auctions mca 
  SET 
      parity_status = CASE 
          WHEN mca.property_onion_id IS NOT NULL AND cpr.document_id IS NOT NULL THEN 'both_sources'
          WHEN mca.property_onion_id IS NOT NULL THEN 'po_only'
          WHEN cpr.document_id IS NOT NULL THEN 'clerk_only'
          ELSE COALESCE(mca.parity_status, 'no_match')
      END,
      parity_clean = (
          mca.property_onion_id IS NOT NULL 
          OR cpr.document_id IS NOT NULL
      ),
      clerk_document_id = cpr.document_id,
      clerk_match_source = CASE 
          WHEN cpr.document_id IS NOT NULL THEN 'clerk_parity_records'
          ELSE mca.clerk_match_source
      END
  FROM clerk_parity_records cpr
  WHERE mca.case_number = cpr.case_number 
      AND mca.county_slug = cpr.county_slug
      AND mca.county_slug = target_county;
  
  GET DIAGNOSTICS update_count = ROW_COUNT;
  
  -- Get enhanced counts for verification
  SELECT 
      COUNT(CASE WHEN mca.parity_clean THEN 1 END),
      COUNT(CASE WHEN mca.property_onion_id IS NOT NULL OR mca.clerk_document_id IS NOT NULL THEN 1 END)
  INTO clean_count, any_count
  FROM multi_county_auctions mca
  WHERE mca.county_slug = target_county;
  
  RETURN QUERY SELECT update_count, clean_count, any_count, NOW();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_parity_with_clerk_data IS 'Updates parity status with clerk records for specified county';

-- View to track C/D improvement metrics
CREATE OR REPLACE VIEW v_shard13_cd_improvement AS
WITH baseline_metrics AS (
    SELECT 
        county_slug,
        COUNT(*) as total_auctions,
        COUNT(CASE WHEN property_onion_id IS NOT NULL THEN 1 END) as po_only_matches,
        COUNT(CASE WHEN parity_clean AND property_onion_id IS NOT NULL THEN 1 END) as po_clean_matches
    FROM multi_county_auctions
    WHERE county_slug IN ('orange', 'flagler', 'santa_rosa', 'gulf')
    GROUP BY county_slug
),
enhanced_metrics AS (
    SELECT 
        mca.county_slug,
        COUNT(*) as total_auctions,
        COUNT(CASE WHEN mca.property_onion_id IS NOT NULL OR mca.clerk_document_id IS NOT NULL THEN 1 END) as enhanced_any_matches,
        COUNT(CASE WHEN mca.parity_clean OR cpr.document_id IS NOT NULL THEN 1 END) as enhanced_clean_matches,
        COUNT(cpr.document_id) as clerk_only_matches
    FROM multi_county_auctions mca
    LEFT JOIN clerk_parity_records cpr ON mca.case_number = cpr.case_number AND mca.county_slug = cpr.county_slug
    WHERE mca.county_slug IN ('orange', 'flagler', 'santa_rosa', 'gulf')
    GROUP BY mca.county_slug
)
SELECT 
    bm.county_slug,
    bm.total_auctions,
    
    -- Baseline metrics (PropertyOnion only)
    bm.po_only_matches,
    bm.po_clean_matches,
    ROUND(bm.po_clean_matches * 100.0 / bm.total_auctions, 2) as baseline_c_pct,
    ROUND(bm.po_only_matches * 100.0 / bm.total_auctions, 2) as baseline_d_pct,
    
    -- Enhanced metrics (PropertyOnion + Clerk)
    em.enhanced_any_matches,
    em.enhanced_clean_matches,
    em.clerk_only_matches,
    ROUND(em.enhanced_clean_matches * 100.0 / em.total_auctions, 2) as enhanced_c_pct,
    ROUND(em.enhanced_any_matches * 100.0 / em.total_auctions, 2) as enhanced_d_pct,
    
    -- Improvement deltas
    ROUND(em.enhanced_clean_matches * 100.0 / em.total_auctions, 2) - 
    ROUND(bm.po_clean_matches * 100.0 / bm.total_auctions, 2) as c_improvement,
    ROUND(em.enhanced_any_matches * 100.0 / em.total_auctions, 2) - 
    ROUND(bm.po_only_matches * 100.0 / bm.total_auctions, 2) as d_improvement
FROM baseline_metrics bm
JOIN enhanced_metrics em ON bm.county_slug = em.county_slug;

COMMENT ON VIEW v_shard13_cd_improvement IS 'Tracks C/D metric improvements from clerk supplementary litmus for SHARD-13 counties';

-- Sample data insertion function for testing
CREATE OR REPLACE FUNCTION insert_sample_clerk_data()
RETURNS TABLE(
  inserted_count BIGINT,
  sample_counties TEXT[],
  verification_timestamp TIMESTAMPTZ
) AS $$
DECLARE
  insert_count BIGINT := 0;
BEGIN
  -- Insert sample clerk parity records for testing
  INSERT INTO clerk_parity_records (county_slug, case_number, record_type, sale_date, document_id, clerk_url)
  VALUES 
    ('orange', '2024-CA-001234', 'Final Judgment Foreclosure', '2024-03-15', 'OR-2024-031234', 'https://or.ocfl.net/AcclaimWeb/search/DetailDocumentMain.aspx?docid=OR-2024-031234'),
    ('flagler', '2024-CA-000567', 'Certificate of Title', '2024-04-01', 'FL-2024-040567', 'https://flaglercounty.org/records/FL-2024-040567'),
    ('santa_rosa', '2024-CA-000123', 'Sheriff Sale Certificate', '2024-02-20', 'SR-2024-020123', 'https://www.santarosa.fl.gov/records/SR-2024-020123'),
    ('gulf', '2024-TD-000045', 'Tax Deed Certificate', '2024-01-10', 'GF-2024-010045', 'https://www.gulfcounty-fl.gov/records/GF-2024-010045')
  ON CONFLICT (county_slug, case_number, record_type) DO UPDATE SET
    document_id = EXCLUDED.document_id,
    clerk_url = EXCLUDED.clerk_url,
    scraped_at = NOW();
  
  GET DIAGNOSTICS insert_count = ROW_COUNT;
  
  RETURN QUERY SELECT insert_count, ARRAY['orange', 'flagler', 'santa_rosa', 'gulf'], NOW();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION insert_sample_clerk_data IS 'Inserts sample clerk parity data for SHARD-13 testing';

-- Comments for documentation
COMMENT ON TABLE clerk_parity_records IS 'SHARD-13 clerk/official records for supplementary parity litmus - addresses PropertyOnion coverage ceiling';
COMMENT ON COLUMN clerk_parity_records.case_number IS 'Foreign key to multi_county_auctions.case_number';
COMMENT ON COLUMN clerk_parity_records.record_type IS 'Type of clerk record: Certificate of Title, Final Judgment, Sheriff Sale, Tax Deed';
COMMENT ON COLUMN clerk_parity_records.document_id IS 'Unique document identifier from clerk system';
COMMENT ON COLUMN clerk_parity_records.clerk_url IS 'Direct URL to clerk record for verification';

-- Log this migration
INSERT INTO migration_log (migration_name, applied_at, description)
VALUES (
  '20260613_shard13_clerk_parity',
  NOW(),
  'SHARD-13 clerk parity records for C/D letter supplementary litmus (orange, flagler, santa_rosa, gulf)'
) ON CONFLICT (migration_name) DO NOTHING;