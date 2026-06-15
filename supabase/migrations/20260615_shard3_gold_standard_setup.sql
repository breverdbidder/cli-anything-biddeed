-- SHARD-3 Gold Standard Setup Migration
-- Support tables and functions for autonomous session improvements
-- Counties: broward, alachua, lee, st_lucie, jefferson

-- Ensure pipeline.counties table exists with required columns
CREATE TABLE IF NOT EXISTS pipeline.counties (
    id SERIAL PRIMARY KEY,
    county_slug TEXT UNIQUE NOT NULL,
    co_no INTEGER,
    name TEXT,
    state TEXT DEFAULT 'FL',
    foreclosure_platform TEXT,
    foreclosure_url TEXT,
    taxdeed_platform TEXT, 
    taxdeed_url TEXT,
    enabled BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 5,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure gold standard tables exist (may already be created by other migrations)
CREATE TABLE IF NOT EXISTS tax_deed_outcomes (
    id SERIAL PRIMARY KEY,
    county_slug TEXT NOT NULL,
    case_number TEXT,
    parcel_id TEXT,
    winning_bid DECIMAL(12,2),
    sale_date DATE,
    data_source TEXT, -- e.g., 'clerk_official:BROWARD-TD-V1'
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(county_slug, case_number, data_source)
);

CREATE TABLE IF NOT EXISTS foreclosure_outcomes (
    id SERIAL PRIMARY KEY,
    county_slug TEXT NOT NULL,
    case_number TEXT,
    parcel_id TEXT,
    winning_bid DECIMAL(12,2),
    sale_date DATE,
    data_source TEXT, -- e.g., 'clerk_official:BROWARD-FC-V1'
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(county_slug, case_number, data_source)
);

CREATE TABLE IF NOT EXISTS gold_standard_county_status (
    id SERIAL PRIMARY KEY,
    county_slug TEXT UNIQUE NOT NULL,
    score_snapshot JSONB, -- Latest pencil_dod_evaluate_county result
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    certification_level TEXT DEFAULT 'uncertified', -- uncertified, candidate, certified, gold
    notes TEXT
);

-- Ensure audit table exists for tracking session work
CREATE TABLE IF NOT EXISTS gold_standard_session_audit (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL, -- shard3-20260615
    county_slug TEXT NOT NULL,
    action_type TEXT NOT NULL, -- setup, fix_a, fix_b, fix_e, fix_h, verify
    action_detail TEXT,
    before_state JSONB,
    after_state JSONB,
    success BOOLEAN DEFAULT false,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Function to log session actions
CREATE OR REPLACE FUNCTION log_session_action(
    session_id TEXT,
    county_slug TEXT,
    action_type TEXT,
    action_detail TEXT DEFAULT NULL,
    before_state JSONB DEFAULT NULL,
    after_state JSONB DEFAULT NULL,
    success BOOLEAN DEFAULT true,
    error_message TEXT DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    audit_id UUID;
BEGIN
    INSERT INTO gold_standard_session_audit (
        session_id, county_slug, action_type, action_detail,
        before_state, after_state, success, error_message
    ) VALUES (
        session_id, county_slug, action_type, action_detail,
        before_state, after_state, success, error_message
    ) RETURNING id INTO audit_id;
    
    RETURN audit_id;
END;
$$ LANGUAGE plpgsql;

-- Helper function for shard-3 status summary  
CREATE OR REPLACE FUNCTION shard3_status_summary()
RETURNS TABLE (
    county_slug TEXT,
    current_score TEXT,
    pass_letters TEXT[],
    fail_letters TEXT[],
    critical_issues JSONB,
    last_evaluation TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    WITH shard3_counties AS (
        SELECT unnest(ARRAY['broward', 'alachua', 'lee', 'st_lucie', 'jefferson']) as county
    ),
    evaluations AS (
        SELECT 
            s.county as county_slug,
            pencil_dod_evaluate_county(s.county) as eval_result
        FROM shard3_counties s
    )
    SELECT 
        e.county_slug,
        CASE 
            WHEN jsonb_array_length(e.eval_result) > 0 THEN
                (SELECT COUNT(*) FROM jsonb_array_elements(e.eval_result) elem WHERE (elem->>'pass')::boolean)::TEXT || '/10'
            ELSE '0/10'
        END as current_score,
        ARRAY(
            SELECT elem->>'letter' 
            FROM jsonb_array_elements(e.eval_result) elem 
            WHERE (elem->>'pass')::boolean
        ) as pass_letters,
        ARRAY(
            SELECT elem->>'letter' 
            FROM jsonb_array_elements(e.eval_result) elem 
            WHERE NOT (elem->>'pass')::boolean
        ) as fail_letters,
        jsonb_object_agg(
            elem->>'letter', 
            jsonb_build_object(
                'metric', elem->'metric',
                'threshold', elem->'threshold', 
                'detail', elem->'detail'
            )
        ) FILTER (WHERE NOT (elem->>'pass')::boolean) as critical_issues,
        NOW() as last_evaluation
    FROM evaluations e
    WHERE jsonb_array_length(e.eval_result) > 0;
END;
$$ LANGUAGE plpgsql;

-- Update pipeline.counties with shard-3 county configurations if missing
INSERT INTO pipeline.counties (county_slug, co_no, name, state, foreclosure_platform, foreclosure_url, taxdeed_platform, taxdeed_url, enabled)
VALUES 
    ('broward', 11, 'Broward County', 'FL', 'realauction', 'https://broward.realauction.com', 'realauction', 'https://broward.realauction.com/taxdeeds', true),
    ('alachua', 1, 'Alachua County', 'FL', 'realauction', 'https://alachua.realauction.com', 'realauction', 'https://alachua.realauction.com/taxdeeds', true),
    ('lee', 39, 'Lee County', 'FL', 'realauction', 'https://lee.realauction.com', 'realauction', 'https://lee.realauction.com/taxdeeds', true),
    ('st_lucie', 59, 'St. Lucie County', 'FL', 'realauction', 'https://st-lucie.realauction.com', 'realauction', 'https://st-lucie.realauction.com/taxdeeds', true),
    ('jefferson', 35, 'Jefferson County', 'FL', 'realauction', 'https://jefferson.realauction.com', 'realauction', 'https://jefferson.realauction.com/taxdeeds', true)
ON CONFLICT (county_slug) DO UPDATE SET
    enabled = EXCLUDED.enabled,
    updated_at = NOW();

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_county_case ON tax_deed_outcomes(county_slug, case_number);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_county_case ON foreclosure_outcomes(county_slug, case_number);
CREATE INDEX IF NOT EXISTS idx_session_audit_session_county ON gold_standard_session_audit(session_id, county_slug);
CREATE INDEX IF NOT EXISTS idx_multi_county_auctions_county ON multi_county_auctions(county) WHERE county IN ('broward', 'alachua', 'lee', 'st_lucie', 'jefferson');

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE ON pipeline.counties TO service_role;
GRANT SELECT, INSERT, UPDATE ON tax_deed_outcomes TO service_role;
GRANT SELECT, INSERT, UPDATE ON foreclosure_outcomes TO service_role;
GRANT SELECT, INSERT, UPDATE ON gold_standard_county_status TO service_role;
GRANT SELECT, INSERT ON gold_standard_session_audit TO service_role;
GRANT EXECUTE ON FUNCTION log_session_action TO service_role;
GRANT EXECUTE ON FUNCTION shard3_status_summary TO service_role;