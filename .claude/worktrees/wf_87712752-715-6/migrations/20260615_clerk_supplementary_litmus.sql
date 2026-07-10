-- SHARD-28 Migration: Create clerk_supplementary_litmus table
-- Purpose: Support C/D parity improvement via clerk/official-records sources
-- Counties: brevard, duval
-- Author: SHARD-28 session 2026-06-15

CREATE TABLE IF NOT EXISTS clerk_supplementary_litmus (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    county_slug TEXT NOT NULL,
    case_number TEXT NOT NULL,
    parcel_id TEXT,
    sale_date DATE,
    data_source TEXT NOT NULL,
    match_confidence DECIMAL(3,2) DEFAULT 0.75,
    notes TEXT,
    raw_response JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT clerk_litmus_county_case_unique UNIQUE (county_slug, case_number)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_clerk_litmus_county_slug ON clerk_supplementary_litmus (county_slug);
CREATE INDEX IF NOT EXISTS idx_clerk_litmus_case_number ON clerk_supplementary_litmus (case_number);
CREATE INDEX IF NOT EXISTS idx_clerk_litmus_parcel_date ON clerk_supplementary_litmus (parcel_id, sale_date);
CREATE INDEX IF NOT EXISTS idx_clerk_litmus_confidence ON clerk_supplementary_litmus (match_confidence);

-- Create RLS policies if needed
ALTER TABLE clerk_supplementary_litmus ENABLE ROW LEVEL SECURITY;

-- Allow authenticated read/write access
CREATE POLICY IF NOT EXISTS "Enable read access for authenticated users" ON clerk_supplementary_litmus
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY IF NOT EXISTS "Enable insert for authenticated users" ON clerk_supplementary_litmus
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY IF NOT EXISTS "Enable update for authenticated users" ON clerk_supplementary_litmus
    FOR UPDATE USING (auth.role() = 'authenticated');

-- Add comments
COMMENT ON TABLE clerk_supplementary_litmus IS 'Supplementary property auction matching data from clerk/official records to improve C/D parity metrics';
COMMENT ON COLUMN clerk_supplementary_litmus.county_slug IS 'Target county for the supplementary match';
COMMENT ON COLUMN clerk_supplementary_litmus.case_number IS 'Case number from multi_county_auctions to supplement';
COMMENT ON COLUMN clerk_supplementary_litmus.data_source IS 'Source identifier (e.g., brevard_clerk_calendar, duval_acclaim_records)';
COMMENT ON COLUMN clerk_supplementary_litmus.match_confidence IS 'Confidence score 0.0-1.0 for the supplementary match';

-- Create helper function for PropertyOnion case number repair
CREATE OR REPLACE FUNCTION repair_po_case_numbers(target_county TEXT)
RETURNS TABLE (
    repaired_count INTEGER,
    court_format_found INTEGER
) AS $$
BEGIN
    -- For cases with PO-prefixed case numbers, attempt to find court case numbers
    -- via parcel_id + sale_date lookup against clerk records
    
    RETURN QUERY
    WITH po_repairs AS (
        UPDATE multi_county_auctions 
        SET 
            case_number = csl.case_number,
            data_sources = array_append(
                COALESCE(data_sources, ARRAY[]::text[]), 
                'po_case_repair'
            ),
            updated_at = NOW()
        FROM clerk_supplementary_litmus csl
        WHERE multi_county_auctions.county = target_county
            AND multi_county_auctions.case_number LIKE 'PO-%'
            AND multi_county_auctions.parcel_id = csl.parcel_id
            AND multi_county_auctions.sale_date = csl.sale_date
            AND csl.county_slug = target_county
            AND csl.match_confidence >= 0.75
        RETURNING 1
    ),
    stats AS (
        SELECT 
            COUNT(*) as repaired,
            (SELECT COUNT(*) FROM multi_county_auctions 
             WHERE county = target_county 
                 AND case_number NOT LIKE 'PO-%' 
                 AND case_number IS NOT NULL) as court_format
        FROM po_repairs
    )
    SELECT 
        repaired::INTEGER,
        court_format::INTEGER
    FROM stats;
END;
$$ LANGUAGE plpgsql;