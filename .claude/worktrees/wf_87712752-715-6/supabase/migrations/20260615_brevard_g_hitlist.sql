-- SHARD-28 BREVARD G HIT LIST - zone_standards NULL backfill migration  
-- Migration: 20260615_brevard_g_hitlist.sql
-- Target: Move Brevard G from 48.9% to 95% (FAR binding constraint)
-- HONESTY PROTOCOL: Values from verified ordinance text only, no guessing

SET statement_timeout = 0;

-- Create table to track ordinance value sources (HONESTY PROTOCOL)
CREATE TABLE IF NOT EXISTS brevard_ordinance_values (
    id                    SERIAL PRIMARY KEY,
    jurisdiction_name     TEXT NOT NULL,
    zone_district_id      INTEGER NOT NULL,
    district_code         TEXT NOT NULL,
    parameter_name        TEXT NOT NULL,  -- 'max_density_du_acre', 'max_far', 'parking_per_1000sf'
    parameter_value       NUMERIC,
    ordinance_section     TEXT NOT NULL,  -- e.g. "Section 21-71.5"
    ordinance_text        TEXT NOT NULL,  -- Exact text from ordinance
    municode_url          TEXT,
    extracted_at          TIMESTAMPTZ DEFAULT now(),
    honesty_marker        TEXT NOT NULL,  -- 'VERIFIED' or 'INFERRED'
    verification_notes    TEXT,
    
    created_at            TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(zone_district_id, parameter_name)
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_bov_district_param ON brevard_ordinance_values(zone_district_id, parameter_name);
CREATE INDEX IF NOT EXISTS idx_bov_honesty ON brevard_ordinance_values(honesty_marker);

-- Function to apply verified values to zone_standards
CREATE OR REPLACE FUNCTION apply_brevard_ordinance_values()
RETURNS INTEGER AS $$
DECLARE
    update_count INTEGER := 0;
    ordinance_record RECORD;
BEGIN
    -- Apply only VERIFIED values to zone_standards
    FOR ordinance_record IN
        SELECT 
            zone_district_id,
            parameter_name,
            parameter_value
        FROM brevard_ordinance_values 
        WHERE honesty_marker = 'VERIFIED'  -- Only apply verified values
    LOOP
        -- Update zone_standards based on parameter type
        CASE ordinance_record.parameter_name
            WHEN 'max_density_du_acre' THEN
                UPDATE zone_standards 
                SET max_density_du_acre = ordinance_record.parameter_value,
                    updated_at = NOW()
                WHERE zone_district_id = ordinance_record.zone_district_id;
                    
            WHEN 'max_far' THEN
                UPDATE zone_standards
                SET max_far = ordinance_record.parameter_value,
                    updated_at = NOW()
                WHERE zone_district_id = ordinance_record.zone_district_id;
                    
            WHEN 'parking_per_1000sf' THEN
                UPDATE zone_standards
                SET parking_per_1000sf = ordinance_record.parameter_value,
                    updated_at = NOW()
                WHERE zone_district_id = ordinance_record.zone_district_id;
        END CASE;
        
        update_count := update_count + 1;
    END LOOP;
    
    RETURN update_count;
END;
$$ LANGUAGE plpgsql;

-- Insert framework for priority districts (to be populated with VERIFIED values)
-- Priority districts from issue analysis:
-- R-1AAA Melbourne: 53,435 parcels (PRIORITY 1)
-- R-1AAA Titusville: 22,252 parcels (PRIORITY 2)
-- R-1A Rockledge: 17,085 parcels (PRIORITY 3)
-- R-1B Titusville: 9,855 parcels (PRIORITY 4)
-- R-1AAA West Melbourne: 9,024 parcels (PRIORITY 5)  
-- RU-2-15 Melbourne: 5,601 parcels (FAR critical)
-- R-3 Titusville: 2,530 parcels (FAR critical)

-- NOTE: This creates framework only - actual ordinance values must be verified
-- Per HONESTY PROTOCOL: No placeholder values applied until VERIFIED

COMMENT ON TABLE brevard_ordinance_values IS 'HONESTY PROTOCOL: Only VERIFIED ordinance values used for zone_standards. Framework for ~15 priority districts covering 120,000+ parcels.';

-- Log this migration  
INSERT INTO migration_log (migration_name, applied_at, description)
VALUES (
    '20260615_brevard_g_hitlist',
    NOW(),
    'SHARD-28 Brevard G hit list framework - zone_standards ordinance value tracking with HONESTY PROTOCOL'
) ON CONFLICT (migration_name) DO NOTHING;