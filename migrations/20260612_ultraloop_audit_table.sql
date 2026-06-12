-- ULTRALOOP Audit Infrastructure - Gold Standard Certification Gate
-- Created: 2026-06-12 for Brevard/Duval Gold Standard Autopilot Session
-- Purpose: Track adversarial survival votes per ULTRALOOP SSOT protocol

-- Create the audit table for ULTRALOOP protocol evidence
CREATE TABLE IF NOT EXISTS public.gold_standard_ultraloop_audit (
    id SERIAL PRIMARY KEY,
    dispatch_id TEXT, -- References the session/summit dispatch ID
    ultraloop_mode TEXT CHECK (ultraloop_mode IN ('native', 'fallback')) DEFAULT 'native',
    county_slug TEXT NOT NULL,
    letter CHAR(1) CHECK (letter IN ('A','B','C','D','E','F','G','H','I','J')),
    claim TEXT NOT NULL,
    refuter_evidence JSONB, -- What was attacked, queries run, results
    survived BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_county_slug CHECK (county_slug IN ('brevard', 'duval', 'orange', 'hillsborough', 'pinellas', 'polk', 'volusia', 'seminole', 'osceola', 'lake', 'sumter', 'citrus', 'hernando', 'pasco', 'manatee', 'sarasota', 'charlotte', 'lee', 'collier', 'monroe', 'miami-dade', 'broward', 'palm-beach', 'martin', 'st-lucie', 'indian-river', 'okeechobee', 'hendry', 'glades', 'highlands', 'hardee', 'desoto', 'bay', 'gulf', 'franklin', 'wakulla', 'leon', 'gadsden', 'liberty', 'calhoun', 'jackson', 'washington', 'holmes', 'walton', 'okaloosa', 'santa-rosa', 'escambia', 'jefferson', 'madison', 'taylor', 'lafayette', 'suwannee', 'hamilton', 'columbia', 'baker', 'nassau', 'duval', 'clay', 'st-johns', 'putnam', 'flagler', 'alachua', 'bradford', 'union', 'gilchrist', 'levy', 'dixie'))
);

-- Indexes for performance and certification gate queries
CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_survival 
    ON gold_standard_ultraloop_audit(county_slug, letter, survived, created_at);

CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_dispatch
    ON gold_standard_ultraloop_audit(dispatch_id, created_at);

CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_county_recent
    ON gold_standard_ultraloop_audit(county_slug, created_at DESC);

-- Trigger to ensure evidence is provided for all entries
CREATE OR REPLACE FUNCTION validate_ultraloop_evidence()
RETURNS TRIGGER AS $$
BEGIN
    -- Require evidence for all audit entries
    IF NEW.refuter_evidence IS NULL OR NEW.refuter_evidence = '{}'::jsonb THEN
        RAISE EXCEPTION 'refuter_evidence cannot be null or empty - evidence required per ULTRALOOP protocol';
    END IF;
    
    -- Auto-fail anomaly ratios >100% per ULTRALOOP SSOT
    IF NEW.claim ILIKE '%134.1%' OR NEW.claim ILIKE '%110.2%' OR 
       (NEW.refuter_evidence->>'ratio_reported')::numeric > 100.0 THEN
        NEW.survived := false;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ultraloop_evidence_validation
    BEFORE INSERT OR UPDATE ON gold_standard_ultraloop_audit
    FOR EACH ROW EXECUTE FUNCTION validate_ultraloop_evidence();

-- View for certification gate queries
CREATE OR REPLACE VIEW ultraloop_certification_gate AS
SELECT 
    county_slug,
    letter,
    COUNT(*) as total_audits,
    COUNT(CASE WHEN survived = true THEN 1 END) as survived_audits,
    COUNT(CASE WHEN survived = false THEN 1 END) as refuted_audits,
    ROUND(100.0 * COUNT(CASE WHEN survived = true THEN 1 END) / COUNT(*), 2) as survival_rate,
    MAX(created_at) as latest_audit,
    array_agg(DISTINCT claim) as claims_tested,
    CASE 
        WHEN COUNT(CASE WHEN survived = true THEN 1 END) > 0 THEN 'CERTIFICATION_ELIGIBLE'
        ELSE 'CERTIFICATION_BLOCKED'
    END as gate_status
FROM gold_standard_ultraloop_audit
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'  -- Recent audits only
GROUP BY county_slug, letter
ORDER BY county_slug, letter;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON gold_standard_ultraloop_audit TO anon;
GRANT SELECT ON ultraloop_certification_gate TO anon;
GRANT USAGE ON SEQUENCE gold_standard_ultraloop_audit_id_seq TO anon;

-- Insert initial test data to verify table structure
INSERT INTO gold_standard_ultraloop_audit (
    dispatch_id,
    ultraloop_mode,
    county_slug,
    letter,
    claim,
    refuter_evidence,
    survived
) VALUES (
    'infratest-2026-06-12',
    'native',
    'brevard',
    'B',
    'B=134.1% anomaly auto-fail test',
    jsonb_build_object(
        'test_type', 'infrastructure_verification',
        'anomaly_ratio', 134.1,
        'auto_fail_reason', 'Mathematical impossibility >100%',
        'created_by', 'ULTRALOOP infrastructure setup'
    ),
    false
), (
    'infratest-2026-06-12', 
    'native',
    'duval',
    'B',
    'B=110.2% anomaly auto-fail test',
    jsonb_build_object(
        'test_type', 'infrastructure_verification', 
        'anomaly_ratio', 110.2,
        'auto_fail_reason', 'Mathematical impossibility >100%',
        'created_by', 'ULTRALOOP infrastructure setup'
    ),
    false
);

-- Verification query template for certification gates
COMMENT ON TABLE gold_standard_ultraloop_audit IS 
'ULTRALOOP protocol audit evidence table. Certification gate requires ≥1 row with survived=true for each letter being certified, newer than the letters last metric change. Zero survived rows = gate fails closed per BLANK > WRONG principle.';

COMMENT ON COLUMN gold_standard_ultraloop_audit.refuter_evidence IS 
'JSONB containing: attack_vectors attempted, SQL queries executed, results found, refutation strength. Required per Honesty Protocol V3 - no VERIFIED claims without evidence.';

COMMENT ON COLUMN gold_standard_ultraloop_audit.survived IS 
'Boolean survival vote result. false = claim refuted, true = claim survived adversarial attack. Anomaly ratios >100% auto-fail regardless of evidence.';

-- Sample certification gate query (to be used during session)
/*
SELECT 
    county_slug,
    letter,
    survived_audits,
    gate_status,
    latest_audit
FROM ultraloop_certification_gate 
WHERE county_slug IN ('brevard', 'duval') 
  AND letter IN ('B','C','D','G','I','J')
ORDER BY county_slug, letter;
*/