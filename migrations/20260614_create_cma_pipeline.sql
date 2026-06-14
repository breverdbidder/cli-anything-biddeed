-- Create CMA (Comparative Market Analysis) pipeline for J Generator
-- This table stores distressed vs retail comparable sales for each auction property

CREATE TABLE IF NOT EXISTS public.gen_valuations_comps_batch (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    case_number TEXT NOT NULL,
    county_slug TEXT NOT NULL,
    property_address TEXT,
    parcel_id TEXT,
    
    -- Distressed comparables (foreclosures, short sales, REO)
    cma_distressed DECIMAL,
    distressed_comp_count INTEGER DEFAULT 0,
    distressed_avg_sqft_price DECIMAL,
    distressed_median_price DECIMAL,
    distressed_price_range_low DECIMAL,
    distressed_price_range_high DECIMAL,
    
    -- Retail/resale comparables (arms-length market sales)
    cma_resale DECIMAL,
    resale_comp_count INTEGER DEFAULT 0,
    resale_avg_sqft_price DECIMAL,
    resale_median_price DECIMAL,
    resale_price_range_low DECIMAL,
    resale_price_range_high DECIMAL,
    
    -- Analysis metadata
    comp_search_radius_miles DECIMAL DEFAULT 1.0,
    comp_search_date_range_months INTEGER DEFAULT 12,
    property_sqft INTEGER,
    bedrooms INTEGER,
    bathrooms DECIMAL,
    year_built INTEGER,
    
    -- Data sources and quality
    data_source TEXT DEFAULT 'propertyonion',
    confidence_score DECIMAL DEFAULT 0.8,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Analysis flags
    sufficient_comps_found BOOLEAN DEFAULT false,
    market_adjustment_applied BOOLEAN DEFAULT false,
    notes TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_case_number_county UNIQUE(case_number, county_slug)
);

-- Add indexes for performance
CREATE INDEX idx_gen_valuations_comps_case_number ON public.gen_valuations_comps_batch(case_number);
CREATE INDEX idx_gen_valuations_comps_county ON public.gen_valuations_comps_batch(county_slug);
CREATE INDEX idx_gen_valuations_comps_parcel ON public.gen_valuations_comps_batch(parcel_id) WHERE parcel_id IS NOT NULL;
CREATE INDEX idx_gen_valuations_comps_updated ON public.gen_valuations_comps_batch(last_updated);

-- Add RLS (Row Level Security)
ALTER TABLE public.gen_valuations_comps_batch ENABLE ROW LEVEL SECURITY;

-- Policy for authenticated users
CREATE POLICY "Allow authenticated read" ON public.gen_valuations_comps_batch
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow authenticated write" ON public.gen_valuations_comps_batch
    FOR ALL
    TO authenticated
    USING (true);

-- Policy for service role (full access)
CREATE POLICY "Allow service role all" ON public.gen_valuations_comps_batch
    FOR ALL
    TO service_role
    USING (true);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_gen_valuations_comps_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to automatically update updated_at
CREATE TRIGGER trigger_gen_valuations_comps_updated_at
    BEFORE UPDATE ON public.gen_valuations_comps_batch
    FOR EACH ROW EXECUTE PROCEDURE update_gen_valuations_comps_updated_at();

-- Helper function to populate CMA data for a single case
CREATE OR REPLACE FUNCTION populate_cma_for_case(
    p_case_number TEXT,
    p_county_slug TEXT,
    p_search_radius_miles DECIMAL DEFAULT 1.0,
    p_search_months INTEGER DEFAULT 12
) 
RETURNS JSON 
LANGUAGE plpgsql
AS $$
DECLARE
    auction_record RECORD;
    comp_record RECORD;
    distressed_avg DECIMAL := 0;
    distressed_count INTEGER := 0;
    resale_avg DECIMAL := 0;
    resale_count INTEGER := 0;
    result JSON;
BEGIN
    -- Get the auction property details
    SELECT property_address, parcel_id, assessed_value
    INTO auction_record
    FROM multi_county_auctions 
    WHERE case_number = p_case_number AND county = p_county_slug;
    
    IF NOT FOUND THEN
        RETURN json_build_object('error', 'Auction not found');
    END IF;
    
    -- Simulate CMA data generation (in production, this would call external APIs)
    -- For now, we'll use assessed value with market adjustments
    
    -- Generate distressed comparables (70-85% of assessed value)
    distressed_avg := auction_record.assessed_value * (0.70 + random() * 0.15);
    distressed_count := 3 + floor(random() * 5); -- 3-7 comps
    
    -- Generate resale comparables (95-120% of assessed value) 
    resale_avg := auction_record.assessed_value * (0.95 + random() * 0.25);
    resale_count := 2 + floor(random() * 4); -- 2-5 comps
    
    -- Insert or update the CMA record
    INSERT INTO gen_valuations_comps_batch (
        case_number,
        county_slug,
        property_address,
        parcel_id,
        cma_distressed,
        distressed_comp_count,
        distressed_median_price,
        cma_resale,
        resale_comp_count,
        resale_median_price,
        comp_search_radius_miles,
        comp_search_date_range_months,
        sufficient_comps_found,
        confidence_score,
        data_source,
        notes
    ) VALUES (
        p_case_number,
        p_county_slug,
        auction_record.property_address,
        auction_record.parcel_id,
        distressed_avg,
        distressed_count,
        distressed_avg * 0.95, -- median slightly lower than avg
        resale_avg,
        resale_count,
        resale_avg * 1.02, -- median slightly higher than avg
        p_search_radius_miles,
        p_search_months,
        (distressed_count >= 2 AND resale_count >= 2),
        CASE 
            WHEN distressed_count >= 3 AND resale_count >= 3 THEN 0.9
            WHEN distressed_count >= 2 AND resale_count >= 2 THEN 0.8
            ELSE 0.6
        END,
        'simulated_propertyonion',
        format('Generated %s distressed comps, %s resale comps', distressed_count, resale_count)
    )
    ON CONFLICT (case_number, county_slug)
    DO UPDATE SET
        cma_distressed = EXCLUDED.cma_distressed,
        distressed_comp_count = EXCLUDED.distressed_comp_count,
        distressed_median_price = EXCLUDED.distressed_median_price,
        cma_resale = EXCLUDED.cma_resale,
        resale_comp_count = EXCLUDED.resale_comp_count,
        resale_median_price = EXCLUDED.resale_median_price,
        sufficient_comps_found = EXCLUDED.sufficient_comps_found,
        confidence_score = EXCLUDED.confidence_score,
        last_updated = NOW();
    
    -- Build result object
    result := json_build_object(
        'case_number', p_case_number,
        'county_slug', p_county_slug,
        'cma_distressed', distressed_avg,
        'cma_resale', resale_avg,
        'distressed_comp_count', distressed_count,
        'resale_comp_count', resale_count,
        'sufficient_comps', (distressed_count >= 2 AND resale_count >= 2)
    );
    
    RETURN result;
END;
$$;

-- Batch function to populate CMA for multiple cases
CREATE OR REPLACE FUNCTION populate_cma_batch(
    p_county_slug TEXT,
    p_limit INTEGER DEFAULT 100
)
RETURNS JSON
LANGUAGE plpgsql
AS $$
DECLARE
    case_record RECORD;
    processed_count INTEGER := 0;
    success_count INTEGER := 0;
    error_count INTEGER := 0;
    result JSON;
    case_result JSON;
BEGIN
    -- Process auctions that don't have CMA data yet
    FOR case_record IN 
        SELECT mca.case_number, mca.county
        FROM multi_county_auctions mca
        LEFT JOIN gen_valuations_comps_batch gcb ON gcb.case_number = mca.case_number AND gcb.county_slug = mca.county
        WHERE mca.county = p_county_slug 
        AND gcb.case_number IS NULL
        AND mca.assessed_value > 0
        LIMIT p_limit
    LOOP
        processed_count := processed_count + 1;
        
        BEGIN
            -- Generate CMA for this case
            case_result := populate_cma_for_case(case_record.case_number, case_record.county);
            
            IF case_result->>'error' IS NULL THEN
                success_count := success_count + 1;
            ELSE
                error_count := error_count + 1;
            END IF;
            
        EXCEPTION WHEN OTHERS THEN
            error_count := error_count + 1;
        END;
    END LOOP;
    
    result := json_build_object(
        'county', p_county_slug,
        'processed', processed_count,
        'success', success_count,
        'errors', error_count,
        'timestamp', NOW()
    );
    
    RETURN result;
END;
$$;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON public.gen_valuations_comps_batch TO authenticated;
GRANT ALL ON public.gen_valuations_comps_batch TO service_role;
GRANT EXECUTE ON FUNCTION populate_cma_for_case TO authenticated;
GRANT EXECUTE ON FUNCTION populate_cma_for_case TO service_role;
GRANT EXECUTE ON FUNCTION populate_cma_batch TO authenticated;
GRANT EXECUTE ON FUNCTION populate_cma_batch TO service_role;