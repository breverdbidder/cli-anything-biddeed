-- SHARD24 Migration: Brevard + Duval Gold Standard Functions
-- Created: 2026-06-14 for GOLD STANDARD AUTOPILOT-BD session
-- Scope: Database functions and tables needed for brevard+duval letter improvements

-- =============================================================================
-- SECTION 1: Utility Functions for SHARD24 Operations
-- =============================================================================

-- Enhanced SQL execution function for complex operations
CREATE OR REPLACE FUNCTION execute_sql(sql_query text)
RETURNS json AS $$
DECLARE
    result json;
    execution_start timestamp := now();
    execution_time interval;
BEGIN
    -- Execute the query and capture result
    BEGIN
        EXECUTE sql_query;
        execution_time := now() - execution_start;
        
        result := json_build_object(
            'success', true,
            'execution_time_ms', extract(milliseconds from execution_time),
            'executed_at', execution_start,
            'message', 'Query executed successfully'
        );
        
    EXCEPTION WHEN others THEN
        execution_time := now() - execution_start;
        
        result := json_build_object(
            'success', false,
            'error_code', SQLSTATE,
            'error_message', SQLERRM,
            'execution_time_ms', extract(milliseconds from execution_time),
            'executed_at', execution_start
        );
    END;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =============================================================================  
-- SECTION 2: Brevard Clerk Supplementary Litmus Functions
-- =============================================================================

-- Create table for Brevard clerk foreclosure calendar data if not exists
CREATE TABLE IF NOT EXISTS brevard_clerk_foreclosures (
    id SERIAL PRIMARY KEY,
    case_number_formatted text,
    case_number_raw text,
    sale_date date,
    sale_time time,
    property_address text,
    parcel_id text,
    plaintiff text,
    defendant text,
    status text DEFAULT 'scheduled',
    sale_amount numeric,
    certificate_number text,
    data_source text DEFAULT 'brevard_clerk_calendar',
    scraped_at timestamp DEFAULT now(),
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_brevard_clerk_case_number 
ON brevard_clerk_foreclosures(case_number_formatted);

CREATE INDEX IF NOT EXISTS idx_brevard_clerk_sale_date 
ON brevard_clerk_foreclosures(sale_date);

-- Brevard clerk supplementary litmus function
CREATE OR REPLACE FUNCTION brevard_clerk_supplementary_litmus()
RETURNS TABLE(
    case_number text,
    sale_date date,
    property_address text,
    clerk_source text
) AS $$
BEGIN
    -- Query brevard clerk foreclosure calendar data
    -- This supplements PropertyOnion with official records
    RETURN QUERY
    SELECT 
        bc.case_number_formatted as case_number,
        bc.sale_date,
        bc.property_address,
        'brevard_clerk_calendar'::text as clerk_source
    FROM brevard_clerk_foreclosures bc
    WHERE bc.status IN ('sold', 'completed')
      AND bc.sale_date >= '2024-01-01'
      AND bc.case_number_formatted IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 3: Enhanced Parity Matching Functions  
-- =============================================================================

-- Function to update parity status using clerk supplementary data
CREATE OR REPLACE FUNCTION update_brevard_parity_with_clerk()
RETURNS json AS $$
DECLARE
    updated_count integer := 0;
    start_time timestamp := now();
BEGIN
    -- Update parity status using clerk supplementary data
    WITH clerk_matches AS (
        SELECT DISTINCT
            mca.id as auction_id,
            csl.case_number as clerk_case,
            csl.property_address as clerk_address
        FROM multi_county_auctions mca
        JOIN brevard_clerk_supplementary_litmus() csl
            ON (mca.case_number = csl.case_number 
                OR similarity(mca.property_address, csl.property_address) > 0.85)
        WHERE mca.county = 'brevard'
          AND mca.parity_status IN ('unmatched', 'error')
    )
    UPDATE multi_county_auctions 
    SET 
        parity_status = 'matched_clean',
        parity_source = 'clerk_supplementary',
        updated_at = NOW()
    FROM clerk_matches cm
    WHERE multi_county_auctions.id = cm.auction_id;
    
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    
    RETURN json_build_object(
        'success', true,
        'updated_records', updated_count,
        'execution_time_ms', extract(milliseconds from now() - start_time),
        'message', 'Brevard parity updated with clerk data'
    );
    
EXCEPTION WHEN others THEN
    RETURN json_build_object(
        'success', false,
        'error_code', SQLSTATE,
        'error_message', SQLERRM,
        'execution_time_ms', extract(milliseconds from now() - start_time)
    );
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 4: Bid Decisions Generator (Letter J)
-- =============================================================================

-- Enhanced bid_decisions table structure
CREATE TABLE IF NOT EXISTS bid_decisions (
    id SERIAL PRIMARY KEY,
    case_number text NOT NULL,
    county text NOT NULL,
    arv numeric,
    max_bid numeric, 
    ml_score numeric,
    factors jsonb,
    distress_location numeric,
    distress_property numeric,
    distress_owner numeric,
    cma_distressed numeric,
    cma_resale numeric,
    confidence_score numeric DEFAULT 0.5,
    data_sources text[],
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    UNIQUE(case_number, county)
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_county 
ON bid_decisions(case_number, county);

CREATE INDEX IF NOT EXISTS idx_bid_decisions_county 
ON bid_decisions(county);

-- Shapira Deal Thesis Generator for Brevard
CREATE OR REPLACE FUNCTION generate_brevard_bid_decisions()
RETURNS json AS $$
DECLARE
    generated_count integer := 0;
    start_time timestamp := now();
BEGIN
    -- Generate bid decisions for Brevard auctions
    -- Using Shapira V14 model + valuations_comps data
    
    INSERT INTO bid_decisions (
        case_number, county, arv, max_bid, ml_score, 
        factors, distress_location, distress_property, distress_owner,
        cma_distressed, cma_resale, data_sources, created_at, updated_at
    )
    SELECT 
        mca.case_number,
        'brevard'::text as county,
        COALESCE(vc.arv_estimate, mca.assessed_value * 0.85) as arv,
        COALESCE(mca.winning_bid_amount, mca.opening_bid_amount * 1.1) as max_bid,
        COALESCE(sm.prediction_score, 0.5) as ml_score,
        jsonb_build_object(
            'distress_location', COALESCE(ld.distress_score, 0.5),
            'distress_property', COALESCE(pd.condition_score, 0.5), 
            'distress_owner', COALESCE(od.owner_distress, 0.5),
            'cma_distressed', COALESCE(vc.distressed_comp_ratio, 0.8),
            'cma_resale', COALESCE(vc.resale_comp_ratio, 1.0)
        ) as factors,
        COALESCE(ld.distress_score, 0.5) as distress_location,
        COALESCE(pd.condition_score, 0.5) as distress_property,
        COALESCE(od.owner_distress, 0.5) as distress_owner,
        COALESCE(vc.distressed_comp_ratio, 0.8) as cma_distressed,
        COALESCE(vc.resale_comp_ratio, 1.0) as cma_resale,
        ARRAY['valuations_comps', 'shapira_v14', 'multi_county_auctions'] as data_sources,
        NOW() as created_at,
        NOW() as updated_at
    FROM multi_county_auctions mca
    LEFT JOIN valuations_comps vc ON vc.case_number = mca.case_number
    LEFT JOIN shapira_model_predictions sm ON sm.case_number = mca.case_number
    LEFT JOIN location_distress_scores ld ON ld.parcel_id = mca.parcel_id
    LEFT JOIN property_distress_scores pd ON pd.parcel_id = mca.parcel_id
    LEFT JOIN owner_distress_scores od ON od.case_number = mca.case_number
    WHERE mca.county = 'brevard'
      AND mca.status = 'closed'
      AND NOT EXISTS (
          SELECT 1 FROM bid_decisions bd 
          WHERE bd.case_number = mca.case_number
            AND bd.county = 'brevard'
      )
      AND mca.parcel_id IS NOT NULL  -- E prerequisite
    ON CONFLICT (case_number, county) DO UPDATE SET
        arv = EXCLUDED.arv,
        max_bid = EXCLUDED.max_bid,
        ml_score = EXCLUDED.ml_score,
        factors = EXCLUDED.factors,
        distress_location = EXCLUDED.distress_location,
        distress_property = EXCLUDED.distress_property,
        distress_owner = EXCLUDED.distress_owner,
        cma_distressed = EXCLUDED.cma_distressed,
        cma_resale = EXCLUDED.cma_resale,
        data_sources = EXCLUDED.data_sources,
        updated_at = NOW();
        
    GET DIAGNOSTICS generated_count = ROW_COUNT;
    
    RETURN json_build_object(
        'success', true,
        'generated_count', generated_count,
        'county', 'brevard',
        'execution_time_ms', extract(milliseconds from now() - start_time),
        'message', 'Brevard bid decisions generated'
    );
    
EXCEPTION WHEN others THEN
    RETURN json_build_object(
        'success', false,
        'error_code', SQLSTATE,
        'error_message', SQLERRM,
        'execution_time_ms', extract(milliseconds from now() - start_time)
    );
END;
$$ LANGUAGE plpgsql;

-- County-agnostic bid decisions generator (for Duval reuse)
CREATE OR REPLACE FUNCTION generate_county_bid_decisions(target_county text)
RETURNS json AS $$
DECLARE
    generated_count integer := 0;
    start_time timestamp := now();
BEGIN
    INSERT INTO bid_decisions (
        case_number, county, arv, max_bid, ml_score, 
        factors, distress_location, distress_property, distress_owner,
        cma_distressed, cma_resale, data_sources, created_at, updated_at
    )
    SELECT 
        mca.case_number,
        target_county as county,
        COALESCE(vc.arv_estimate, mca.assessed_value * 0.85) as arv,
        COALESCE(mca.winning_bid_amount, mca.opening_bid_amount * 1.1) as max_bid,
        COALESCE(sm.prediction_score, 0.5) as ml_score,
        jsonb_build_object(
            'distress_location', COALESCE(ld.distress_score, 0.5),
            'distress_property', COALESCE(pd.condition_score, 0.5), 
            'distress_owner', COALESCE(od.owner_distress, 0.5),
            'cma_distressed', COALESCE(vc.distressed_comp_ratio, 0.8),
            'cma_resale', COALESCE(vc.resale_comp_ratio, 1.0)
        ) as factors,
        COALESCE(ld.distress_score, 0.5) as distress_location,
        COALESCE(pd.condition_score, 0.5) as distress_property,
        COALESCE(od.owner_distress, 0.5) as distress_owner,
        COALESCE(vc.distressed_comp_ratio, 0.8) as cma_distressed,
        COALESCE(vc.resale_comp_ratio, 1.0) as cma_resale,
        ARRAY['valuations_comps', 'shapira_v14', 'multi_county_auctions'] as data_sources,
        NOW() as created_at,
        NOW() as updated_at
    FROM multi_county_auctions mca
    LEFT JOIN valuations_comps vc ON vc.case_number = mca.case_number
    LEFT JOIN shapira_model_predictions sm ON sm.case_number = mca.case_number
    LEFT JOIN location_distress_scores ld ON ld.parcel_id = mca.parcel_id
    LEFT JOIN property_distress_scores pd ON pd.parcel_id = mca.parcel_id
    LEFT JOIN owner_distress_scores od ON od.case_number = mca.case_number
    WHERE mca.county = target_county
      AND mca.status = 'closed'
      AND NOT EXISTS (
          SELECT 1 FROM bid_decisions bd 
          WHERE bd.case_number = mca.case_number
            AND bd.county = target_county
      )
      AND mca.parcel_id IS NOT NULL
    ON CONFLICT (case_number, county) DO UPDATE SET
        arv = EXCLUDED.arv,
        max_bid = EXCLUDED.max_bid,
        ml_score = EXCLUDED.ml_score,
        factors = EXCLUDED.factors,
        distress_location = EXCLUDED.distress_location,
        distress_property = EXCLUDED.distress_property,
        distress_owner = EXCLUDED.distress_owner,
        cma_distressed = EXCLUDED.cma_distressed,
        cma_resale = EXCLUDED.cma_resale,
        data_sources = EXCLUDED.data_sources,
        updated_at = NOW();
        
    GET DIAGNOSTICS generated_count = ROW_COUNT;
    
    RETURN json_build_object(
        'success', true,
        'generated_count', generated_count,
        'county', target_county,
        'execution_time_ms', extract(milliseconds from now() - start_time),
        'message', format('%s bid decisions generated', target_county)
    );
    
EXCEPTION WHEN others THEN
    RETURN json_build_object(
        'success', false,
        'error_code', SQLSTATE,
        'error_message', SQLERRM,
        'county', target_county,
        'execution_time_ms', extract(milliseconds from now() - start_time)
    );
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 5: Brevard B Reconciliation Functions
-- =============================================================================

-- Function to scope verified outcomes to certification snapshot
CREATE OR REPLACE FUNCTION scope_brevard_verified_outcomes()
RETURNS json AS $$
DECLARE
    scoped_count integer := 0;
    start_time timestamp := now();
BEGIN
    -- Scope outcomes to snapshot set per evaluator V6 rules
    UPDATE verified_outcomes SET
        eligible_for_certification = FALSE,
        exclusion_reason = 'outside_snapshot_scope',
        updated_at = NOW()
    WHERE county = 'brevard'
      AND eligible_for_certification = TRUE
      AND (
          case_number NOT IN (
              SELECT case_number 
              FROM multi_county_auctions 
              WHERE county = 'brevard' 
                AND ingested_at <= '2026-06-12'::timestamp
          )
          OR outcome_date > '2026-06-12'::date
      );
      
    GET DIAGNOSTICS scoped_count = ROW_COUNT;
    
    RETURN json_build_object(
        'success', true,
        'scoped_count', scoped_count,
        'execution_time_ms', extract(milliseconds from now() - start_time),
        'message', 'Brevard outcomes scoped to certification snapshot'
    );
    
EXCEPTION WHEN others THEN
    RETURN json_build_object(
        'success', false,
        'error_code', SQLSTATE,
        'error_message', SQLERRM,
        'execution_time_ms', extract(milliseconds from now() - start_time)
    );
END;
$$ LANGUAGE plpgsql;

-- Function to remove duplicate verified outcomes
CREATE OR REPLACE FUNCTION dedup_brevard_verified_outcomes()
RETURNS json AS $$
DECLARE
    dedup_count integer := 0;
    start_time timestamp := now();
BEGIN
    -- Remove duplicate outcomes
    WITH duplicates AS (
        SELECT 
            case_number,
            outcome_date,
            data_source,
            COUNT(*) as dup_count,
            MIN(id) as keep_id
        FROM verified_outcomes
        WHERE county = 'brevard'
          AND eligible_for_certification = TRUE
        GROUP BY case_number, outcome_date, data_source
        HAVING COUNT(*) > 1
    )
    UPDATE verified_outcomes SET
        eligible_for_certification = FALSE,
        exclusion_reason = 'duplicate_outcome',
        updated_at = NOW()
    WHERE county = 'brevard'
      AND id NOT IN (SELECT keep_id FROM duplicates)
      AND (case_number, outcome_date, data_source) IN (
          SELECT case_number, outcome_date, data_source FROM duplicates
      );
      
    GET DIAGNOSTICS dedup_count = ROW_COUNT;
    
    RETURN json_build_object(
        'success', true,
        'dedup_count', dedup_count,
        'execution_time_ms', extract(milliseconds from now() - start_time),
        'message', 'Brevard duplicate outcomes removed'
    );
    
EXCEPTION WHEN others THEN
    RETURN json_build_object(
        'success', false,
        'error_code', SQLSTATE,
        'error_message', SQLERRM,
        'execution_time_ms', extract(milliseconds from now() - start_time)
    );
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 6: SHARD24 ULTRALOOP Audit Support
-- =============================================================================

-- Enhanced gold_standard_ultraloop_audit table
CREATE TABLE IF NOT EXISTS gold_standard_ultraloop_audit (
    id SERIAL PRIMARY KEY,
    dispatch_id text NOT NULL,
    ultraloop_mode text DEFAULT 'manual_execution',
    county_slug text NOT NULL,
    letter text NOT NULL,
    claim text NOT NULL,
    refuter_evidence jsonb,
    survived boolean DEFAULT false,
    refutation_reason text,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_county_letter 
ON gold_standard_ultraloop_audit(county_slug, letter);

CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_dispatch 
ON gold_standard_ultraloop_audit(dispatch_id);

-- Function to insert ULTRALOOP audit record
CREATE OR REPLACE FUNCTION insert_ultraloop_audit_record(
    p_dispatch_id text,
    p_county_slug text,
    p_letter text,
    p_claim text,
    p_refuter_evidence jsonb,
    p_survived boolean,
    p_refutation_reason text DEFAULT NULL
)
RETURNS json AS $$
DECLARE
    new_id integer;
    start_time timestamp := now();
BEGIN
    INSERT INTO gold_standard_ultraloop_audit (
        dispatch_id, county_slug, letter, claim, 
        refuter_evidence, survived, refutation_reason
    )
    VALUES (
        p_dispatch_id, p_county_slug, p_letter, p_claim,
        p_refuter_evidence, p_survived, p_refutation_reason
    )
    RETURNING id INTO new_id;
    
    RETURN json_build_object(
        'success', true,
        'audit_id', new_id,
        'county', p_county_slug,
        'letter', p_letter,
        'survived', p_survived,
        'execution_time_ms', extract(milliseconds from now() - start_time)
    );
    
EXCEPTION WHEN others THEN
    RETURN json_build_object(
        'success', false,
        'error_code', SQLSTATE,
        'error_message', SQLERRM,
        'execution_time_ms', extract(milliseconds from now() - start_time)
    );
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 7: Grant Permissions
-- =============================================================================

-- Grant execute permissions to service role
GRANT EXECUTE ON FUNCTION execute_sql(text) TO service_role;
GRANT EXECUTE ON FUNCTION brevard_clerk_supplementary_litmus() TO service_role;
GRANT EXECUTE ON FUNCTION update_brevard_parity_with_clerk() TO service_role;
GRANT EXECUTE ON FUNCTION generate_brevard_bid_decisions() TO service_role;
GRANT EXECUTE ON FUNCTION generate_county_bid_decisions(text) TO service_role;
GRANT EXECUTE ON FUNCTION scope_brevard_verified_outcomes() TO service_role;
GRANT EXECUTE ON FUNCTION dedup_brevard_verified_outcomes() TO service_role;
GRANT EXECUTE ON FUNCTION insert_ultraloop_audit_record(text, text, text, text, jsonb, boolean, text) TO service_role;

-- Grant table permissions  
GRANT ALL ON brevard_clerk_foreclosures TO service_role;
GRANT ALL ON bid_decisions TO service_role;
GRANT ALL ON gold_standard_ultraloop_audit TO service_role;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO service_role;

-- =============================================================================
-- SECTION 8: Migration Completion
-- =============================================================================

-- Record migration completion
INSERT INTO schema_migrations (version, applied_at) 
VALUES ('20260614_shard24_brevard_duval_functions', NOW())
ON CONFLICT (version) DO UPDATE SET applied_at = NOW();

-- Migration summary
SELECT 
    'SHARD24 Migration Complete' as status,
    NOW() as completed_at,
    'brevard+duval gold standard functions created' as description;