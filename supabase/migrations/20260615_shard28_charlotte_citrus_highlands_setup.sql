-- SHARD-28 CHARLOTTE, CITRUS, HIGHLANDS SETUP
-- Migration for Gold Standard improvements for charlotte, citrus, highlands counties
-- Created: 2026-06-15
-- Session: 9ec217ea-c205-4df4-9573-3216dd9a3cb0

BEGIN;

-- Ensure we have the basic Gold Standard tables if they don't exist
CREATE TABLE IF NOT EXISTS gold_standard_ultraloop_audit (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    dispatch_id uuid NOT NULL,
    ultraloop_mode text NOT NULL CHECK (ultraloop_mode IN ('native', 'fallback')),
    county_slug text NOT NULL,
    letter text NOT NULL CHECK (letter ~ '^[A-J]$'),
    claim text NOT NULL,
    refuter_evidence jsonb DEFAULT '{}',
    survived boolean NOT NULL,
    created_at timestamptz DEFAULT now()
);

-- Index for efficient queries
CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_county_letter 
    ON gold_standard_ultraloop_audit (county_slug, letter, created_at DESC);

-- Create county-specific tracking for our shard
CREATE TABLE IF NOT EXISTS shard28_county_work_log (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    county_slug text NOT NULL CHECK (county_slug IN ('charlotte', 'citrus', 'highlands')),
    work_type text NOT NULL, -- 'verified_outcomes', 'property_cards', 'deal_thesis', 'parity_fix', 'parcel_linkage'
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    details jsonb DEFAULT '{}',
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_shard28_county_work_log_updated_at ON shard28_county_work_log;
CREATE TRIGGER update_shard28_county_work_log_updated_at 
    BEFORE UPDATE ON shard28_county_work_log 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Insert initial work items for each county
INSERT INTO shard28_county_work_log (county_slug, work_type, details) VALUES 
-- Charlotte County work items
('charlotte', 'verified_outcomes', '{"priority": 1, "description": "Build Charlotte County Clerk verified outcomes scraper"}'),
('charlotte', 'property_cards', '{"priority": 2, "description": "Implement property card completion pipeline"}'),
('charlotte', 'deal_thesis', '{"priority": 3, "description": "Build bid_decisions generator with Shapira V14"}'),
('charlotte', 'parity_fix', '{"priority": 4, "description": "Fix C/D parity gaps with clerk supplementation"}'),
('charlotte', 'parcel_linkage', '{"priority": 5, "description": "Link parcels via Charlotte PA ArcGIS"}'),

-- Citrus County work items
('citrus', 'verified_outcomes', '{"priority": 1, "description": "Build Citrus County Clerk verified outcomes scraper"}'),
('citrus', 'property_cards', '{"priority": 2, "description": "Implement property card completion pipeline"}'),
('citrus', 'deal_thesis', '{"priority": 3, "description": "Build bid_decisions generator with Shapira V14"}'),
('citrus', 'parity_fix', '{"priority": 4, "description": "Fix C/D parity gaps with clerk supplementation"}'),
('citrus', 'parcel_linkage', '{"priority": 5, "description": "Link parcels via Citrus PA ArcGIS"}'),

-- Highlands County work items  
('highlands', 'verified_outcomes', '{"priority": 1, "description": "Build Highlands County Clerk verified outcomes scraper"}'),
('highlands', 'property_cards', '{"priority": 2, "description": "Implement property card completion pipeline"}'),
('highlands', 'deal_thesis', '{"priority": 3, "description": "Build bid_decisions generator with Shapira V14"}'),
('highlands', 'parity_fix', '{"priority": 4, "description": "Fix C/D parity gaps with clerk supplementation"}'),
('highlands', 'parcel_linkage', '{"priority": 5, "description": "Link parcels via Highlands PA ArcGIS"})
ON CONFLICT DO NOTHING;

-- Create function to update work status
CREATE OR REPLACE FUNCTION update_shard28_work_status(
    p_county_slug text,
    p_work_type text, 
    p_status text,
    p_details jsonb DEFAULT NULL
)
RETURNS void AS $$
BEGIN
    UPDATE shard28_county_work_log 
    SET 
        status = p_status,
        details = COALESCE(p_details, details),
        started_at = CASE WHEN p_status = 'in_progress' AND started_at IS NULL THEN now() ELSE started_at END,
        completed_at = CASE WHEN p_status IN ('completed', 'failed') AND completed_at IS NULL THEN now() ELSE completed_at END
    WHERE county_slug = p_county_slug AND work_type = p_work_type;
END;
$$ LANGUAGE plpgsql;

-- Create view for current shard status
CREATE OR REPLACE VIEW shard28_status_summary AS
SELECT 
    county_slug,
    COUNT(*) as total_work_items,
    COUNT(*) FILTER (WHERE status = 'completed') as completed_items,
    COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress_items,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_items,
    COUNT(*) FILTER (WHERE status = 'pending') as pending_items,
    ROUND(
        (COUNT(*) FILTER (WHERE status = 'completed')::decimal / COUNT(*)) * 100, 
        1
    ) as completion_percentage
FROM shard28_county_work_log
GROUP BY county_slug
ORDER BY county_slug;

-- Grant necessary permissions (assuming standard service role)
GRANT ALL ON shard28_county_work_log TO authenticated, anon, service_role;
GRANT ALL ON shard28_status_summary TO authenticated, anon, service_role;
GRANT EXECUTE ON FUNCTION update_shard28_work_status TO authenticated, anon, service_role;

COMMIT;

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'SHARD-28 setup migration completed for charlotte, citrus, highlands counties at %', now();
END $$;