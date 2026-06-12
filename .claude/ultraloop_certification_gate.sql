-- ULTRALOOP Certification Gate - Gold Standard Session Verification
-- Usage: Run this query during/after session to verify certification eligibility
-- Per ULTRALOOP SSOT: gold_standard_certify MUST find ≥1 survived row per letter

-- Main certification gate query
WITH certification_requirements AS (
    SELECT 
        unnest(ARRAY['brevard', 'duval']) as target_county,
        unnest(ARRAY['B','C','D','G','I','J']) as target_letter
), current_metrics AS (
    -- Current session metrics (would be populated during session)
    SELECT 'brevard' as county_slug, 'B' as letter, 134.1 as current_metric
    UNION ALL SELECT 'brevard', 'C', 20.8
    UNION ALL SELECT 'brevard', 'D', 33.2  
    UNION ALL SELECT 'brevard', 'G', 48.9
    UNION ALL SELECT 'brevard', 'I', 18.6
    UNION ALL SELECT 'brevard', 'J', 0.0
    UNION ALL SELECT 'duval', 'B', 110.2
    UNION ALL SELECT 'duval', 'C', 16.1
    UNION ALL SELECT 'duval', 'D', 52.9
    UNION ALL SELECT 'duval', 'G', NULL  -- null status
    UNION ALL SELECT 'duval', 'I', NULL  -- null status  
    UNION ALL SELECT 'duval', 'J', 0.0
), audit_summary AS (
    SELECT 
        gua.county_slug,
        gua.letter,
        COUNT(*) as total_audits,
        COUNT(CASE WHEN gua.survived = true THEN 1 END) as survived_audits,
        COUNT(CASE WHEN gua.survived = false THEN 1 END) as refuted_audits,
        MAX(gua.created_at) as latest_audit_time,
        array_agg(DISTINCT gua.claim ORDER BY gua.claim) as claims_tested,
        -- Evidence summary
        jsonb_agg(
            CASE WHEN gua.survived = false 
            THEN jsonb_build_object(
                'refuted_claim', gua.claim,
                'refutation_evidence', gua.refuter_evidence->'evidence',
                'attack_type', gua.refuter_evidence->'attack_type'
            ) END
        ) FILTER (WHERE gua.survived = false) as refutation_evidence
    FROM gold_standard_ultraloop_audit gua
    WHERE gua.created_at >= CURRENT_DATE - INTERVAL '1 day'  -- Session window
      AND gua.county_slug IN ('brevard', 'duval')
      AND gua.letter IN ('B','C','D','G','I','J') 
    GROUP BY gua.county_slug, gua.letter
)

-- Final certification gate results
SELECT 
    cr.target_county as county,
    cr.target_letter as letter,
    cm.current_metric,
    
    -- Audit results
    COALESCE(aus.total_audits, 0) as total_audits,
    COALESCE(aus.survived_audits, 0) as survived_audits, 
    COALESCE(aus.refuted_audits, 0) as refuted_audits,
    aus.latest_audit_time,
    
    -- Gate decision logic
    CASE 
        -- Anomaly auto-fail rule
        WHEN cm.current_metric > 100.0 THEN 'ANOMALY_AUTO_FAIL'
        -- Standard survival gate
        WHEN COALESCE(aus.survived_audits, 0) > 0 THEN 'CERTIFICATION_ELIGIBLE'
        -- No audit data = gate fails closed
        WHEN COALESCE(aus.total_audits, 0) = 0 THEN 'NO_AUDIT_DATA_GATE_CLOSED'
        -- All claims refuted
        ELSE 'ALL_CLAIMS_REFUTED'
    END as certification_gate_status,
    
    -- Human readable summary
    CASE 
        WHEN cm.current_metric > 100.0 THEN 
            format('BLOCKED: %s%% ratio mathematically impossible', cm.current_metric)
        WHEN COALESCE(aus.survived_audits, 0) > 0 THEN 
            format('PASS: %s claim(s) survived adversarial attack', aus.survived_audits)
        WHEN COALESCE(aus.total_audits, 0) = 0 THEN 
            'BLOCKED: No ULTRALOOP audit performed (BLANK > WRONG)'
        ELSE 
            format('BLOCKED: All %s claim(s) refuted by adversarial analysis', aus.refuted_audits)
    END as gate_explanation,
    
    -- Evidence for review
    aus.claims_tested,
    aus.refutation_evidence

FROM certification_requirements cr
LEFT JOIN current_metrics cm ON cr.target_county = cm.county_slug AND cr.target_letter = cm.letter
LEFT JOIN audit_summary aus ON cr.target_county = aus.county_slug AND cr.target_letter = aus.letter
ORDER BY cr.target_county, cr.target_letter;

-- Session Summary for ULTRALOOP Protocol Compliance
SELECT 
    'ULTRALOOP SESSION SUMMARY' as section,
    COUNT(DISTINCT county_slug) as counties_audited,
    COUNT(DISTINCT letter) as letters_audited, 
    COUNT(*) as total_audit_attempts,
    COUNT(CASE WHEN survived = true THEN 1 END) as claims_survived,
    COUNT(CASE WHEN survived = false THEN 1 END) as claims_refuted,
    ROUND(100.0 * COUNT(CASE WHEN survived = true THEN 1 END) / COUNT(*), 2) as survival_rate_percent,
    MIN(created_at) as session_start,
    MAX(created_at) as session_end
FROM gold_standard_ultraloop_audit
WHERE created_at >= CURRENT_DATE - INTERVAL '1 day'
  AND county_slug IN ('brevard', 'duval');

-- Anomaly Detection Summary (Auto-Fail Cases)
SELECT 
    'ANOMALY AUTO-FAIL SUMMARY' as section,
    county_slug,
    letter,
    claim,
    refuter_evidence->>'ratio_reported' as anomaly_ratio,
    refuter_evidence->>'auto_fail_reason' as auto_fail_reason,
    created_at
FROM gold_standard_ultraloop_audit
WHERE created_at >= CURRENT_DATE - INTERVAL '1 day'
  AND county_slug IN ('brevard', 'duval')
  AND survived = false
  AND (claim ILIKE '%134.1%' OR claim ILIKE '%110.2%' OR (refuter_evidence->>'ratio_reported')::numeric > 100.0)
ORDER BY county_slug, letter;

-- Evidence Quality Check
SELECT 
    'EVIDENCE QUALITY AUDIT' as section,
    county_slug,
    letter, 
    COUNT(*) as audit_count,
    COUNT(CASE WHEN refuter_evidence ? 'sql_queries_executed' THEN 1 END) as with_sql_evidence,
    COUNT(CASE WHEN refuter_evidence ? 'attack_vectors' THEN 1 END) as with_attack_vectors,
    COUNT(CASE WHEN jsonb_array_length(refuter_evidence->'attack_vectors') >= 2 THEN 1 END) as multi_vector_attacks,
    ROUND(100.0 * COUNT(CASE WHEN refuter_evidence ? 'sql_queries_executed' THEN 1 END) / COUNT(*), 2) as sql_evidence_rate
FROM gold_standard_ultraloop_audit
WHERE created_at >= CURRENT_DATE - INTERVAL '1 day'
  AND county_slug IN ('brevard', 'duval')
GROUP BY county_slug, letter
ORDER BY county_slug, letter;

-- Final Certification Eligibility Report
WITH final_gate_check AS (
    SELECT 
        county_slug,
        COUNT(DISTINCT letter) as letters_with_audits,
        COUNT(CASE WHEN survived = true THEN 1 END) as total_survived_claims,
        COUNT(CASE WHEN survived = false AND (refuter_evidence->>'ratio_reported')::numeric > 100.0 THEN 1 END) as anomaly_auto_fails,
        array_agg(DISTINCT letter ORDER BY letter) as audited_letters,
        array_agg(DISTINCT letter ORDER BY letter) FILTER (WHERE survived = true) as eligible_letters
    FROM gold_standard_ultraloop_audit
    WHERE created_at >= CURRENT_DATE - INTERVAL '1 day'
      AND county_slug IN ('brevard', 'duval')  
    GROUP BY county_slug
)
SELECT 
    'FINAL CERTIFICATION REPORT' as section,
    county_slug,
    letters_with_audits,
    total_survived_claims,
    anomaly_auto_fails,
    audited_letters,
    eligible_letters,
    CASE 
        WHEN anomaly_auto_fails > 0 THEN 'BLOCKED_ANOMALIES'
        WHEN total_survived_claims >= letters_with_audits THEN 'CERTIFICATION_READY'
        WHEN total_survived_claims > 0 THEN 'PARTIAL_CERTIFICATION'  
        ELSE 'CERTIFICATION_BLOCKED'
    END as final_certification_status
FROM final_gate_check
ORDER BY county_slug;