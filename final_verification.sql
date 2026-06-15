-- FINAL VERIFICATION: SHARD-28 Gold Standard Impact
-- Run this to verify the autonomous session results

SET statement_timeout = 0;

-- Overall county status verification
SELECT 
    'FINAL COUNTY STATUS' as verification_type,
    county_slug,
    letter,
    metric,
    threshold,
    pass,
    CASE WHEN pass THEN '✅' ELSE '❌' END as status
FROM (
    SELECT * FROM public.pencil_dod_evaluate_county('brevard')
    UNION ALL
    SELECT * FROM public.pencil_dod_evaluate_county('duval')
) county_evaluations
ORDER BY county_slug, letter;

-- Score summary
SELECT 
    'SCORE SUMMARY' as report_type,
    county_slug,
    COUNT(*) as total_letters,
    COUNT(CASE WHEN pass THEN 1 END) as passing_letters,
    ROUND(COUNT(CASE WHEN pass THEN 1 END) * 100.0 / COUNT(*), 1) as pass_percentage,
    CASE 
        WHEN COUNT(CASE WHEN pass THEN 1 END) >= 10 THEN '🏆 GOLD STANDARD'
        WHEN COUNT(CASE WHEN pass THEN 1 END) >= 8 THEN '🥈 HIGH'
        WHEN COUNT(CASE WHEN pass THEN 1 END) >= 6 THEN '🥉 MEDIUM'
        ELSE '⚠️ NEEDS WORK'
    END as grade
FROM (
    SELECT * FROM public.pencil_dod_evaluate_county('brevard')
    UNION ALL
    SELECT * FROM public.pencil_dod_evaluate_county('duval')
) county_evaluations
GROUP BY county_slug
ORDER BY county_slug;

-- Specific improvements verification
SELECT 'BREVARD C/D IMPACT' as check_type,
    COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) as c_numerator,
    COUNT(CASE WHEN parity_status IN ('matched_clean', 'matched_divergent') THEN 1 END) as d_numerator,
    COUNT(*) as total_denominator,
    ROUND(COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) * 100.0 / COUNT(*), 2) as c_percentage,
    ROUND(COUNT(CASE WHEN parity_status IN ('matched_clean', 'matched_divergent') THEN 1 END) * 100.0 / COUNT(*), 2) as d_percentage
FROM multi_county_auctions 
WHERE county = 'brevard' 
    AND auction_status IN ('sold', 'no_sale', 'canceled');

-- J Generator impact verification
SELECT 'J GENERATOR IMPACT' as check_type,
    county_slug,
    COUNT(*) as total_decisions,
    COUNT(CASE 
        WHEN arv IS NOT NULL 
            AND max_bid IS NOT NULL 
            AND ml_score IS NOT NULL 
            AND factors ? 'distress_location'
            AND factors ? 'distress_property'
            AND factors ? 'distress_owner'
            AND factors ? 'cma_distressed'
            AND factors ? 'cma_resale'
        THEN 1 
    END) as j_compliant_decisions,
    ROUND(COUNT(CASE 
        WHEN arv IS NOT NULL 
            AND max_bid IS NOT NULL 
            AND ml_score IS NOT NULL 
            AND factors ? 'distress_location'
            AND factors ? 'distress_property'
            AND factors ? 'distress_owner'
            AND factors ? 'cma_distressed'
            AND factors ? 'cma_resale'
        THEN 1 
    END) * 100.0 / COUNT(*), 2) as j_compliance_rate
FROM bid_decisions
WHERE county_slug IN ('brevard', 'duval')
GROUP BY county_slug
ORDER BY county_slug;

-- G Hitlist verification for Brevard
SELECT 'BREVARD G STANDARDS' as check_type,
    COUNT(*) as total_districts,
    COUNT(CASE WHEN zs_far.value IS NOT NULL THEN 1 END) as districts_with_far,
    COUNT(CASE WHEN zs_density.value IS NOT NULL THEN 1 END) as districts_with_density,
    COUNT(CASE WHEN zs_parking.value IS NOT NULL THEN 1 END) as districts_with_parking,
    ROUND(COUNT(CASE WHEN zs_far.value IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 2) as far_coverage_pct,
    ROUND(COUNT(CASE WHEN zs_density.value IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 2) as density_coverage_pct,
    ROUND(COUNT(CASE WHEN zs_parking.value IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 2) as parking_coverage_pct
FROM zoning_districts zd
JOIN jurisdictions j ON zd.jurisdiction_id = j.id
LEFT JOIN zone_standards zs_far ON zd.id = zs_far.zoning_district_id AND zs_far.standard_type = 'max_far'
LEFT JOIN zone_standards zs_density ON zd.id = zs_density.zoning_district_id AND zs_density.standard_type = 'max_density_du_acre'
LEFT JOIN zone_standards zs_parking ON zd.id = zs_parking.zoning_district_id AND zs_parking.standard_type = 'parking_per_1000sf'
WHERE j.county = 'Brevard';

-- Duval G+I substrate verification
SELECT 'DUVAL G+I SUBSTRATE' as check_type,
    (SELECT COUNT(*) FROM zoning_districts zd 
     JOIN jurisdictions j ON zd.jurisdiction_id = j.id 
     WHERE j.county = 'Duval') as zoning_districts,
    (SELECT COUNT(*) FROM zone_standards zs 
     JOIN zoning_districts zd ON zs.zoning_district_id = zd.id
     JOIN jurisdictions j ON zd.jurisdiction_id = j.id 
     WHERE j.county = 'Duval') as zone_standards,
    (SELECT COUNT(*) FROM parcel_zones pz 
     JOIN jurisdictions j ON pz.jurisdiction_id = j.id 
     WHERE j.county = 'Duval') as parcels_zoned;

-- ULTRALOOP audit trail
SELECT 'ULTRALOOP AUDIT TRAIL' as check_type,
    county_slug,
    letter,
    COUNT(*) as audit_records,
    COUNT(CASE WHEN survived THEN 1 END) as survived_claims,
    ROUND(COUNT(CASE WHEN survived THEN 1 END) * 100.0 / COUNT(*), 1) as survival_rate
FROM gold_standard_ultraloop_audit
WHERE dispatch_id = 'f91ec638-bc15-4233-9dbe-239059e0f8b9'
GROUP BY county_slug, letter
ORDER BY county_slug, letter;

-- Migration log verification
SELECT 'MIGRATION LOG' as check_type,
    migration_name,
    applied_at,
    description
FROM migration_log
WHERE migration_name LIKE '%20260615%' OR migration_name LIKE '%shard28%'
ORDER BY applied_at DESC;

-- Session summary
SELECT 
    'SESSION SUMMARY' as report_type,
    'SHARD-28 GOLD STANDARD AUTOPILOT-BD' as session_type,
    NOW() as completed_at,
    'f91ec638-bc15-4233-9dbe-239059e0f8b9' as dispatch_id,
    'SHIP-TO-MAIN: All changes committed directly' as deployment_status;

-- Evidence collection for SQL VERIFICATION block per SHIP GATE
SELECT 
    'SQL VERIFICATION EVIDENCE' as evidence_type,
    current_timestamp as verification_timestamp,
    (SELECT COUNT(*) FROM bid_decisions WHERE county_slug IN ('brevard', 'duval') AND created_at >= '2026-06-15') as bid_decisions_created,
    (SELECT COUNT(*) FROM brevard_clerk_matches) as brevard_clerk_matches_created,
    (SELECT COUNT(*) FROM zoning_districts zd JOIN jurisdictions j ON zd.jurisdiction_id = j.id WHERE j.county = 'Duval') as duval_zoning_districts;

-- PASS/FAIL determination per gold standard criteria
WITH final_scores AS (
    SELECT 
        county_slug,
        COUNT(CASE WHEN pass THEN 1 END) as passing_letters,
        COUNT(*) as total_letters
    FROM (
        SELECT * FROM public.pencil_dod_evaluate_county('brevard')
        UNION ALL
        SELECT * FROM public.pencil_dod_evaluate_county('duval')
    ) evals
    GROUP BY county_slug
)
SELECT 
    'CERTIFICATION READINESS' as final_check,
    county_slug,
    passing_letters || '/' || total_letters as score,
    CASE 
        WHEN passing_letters >= 10 THEN 'CERTIFIED ✅'
        WHEN passing_letters >= 8 THEN 'NEAR CERTIFICATION 🔄'
        ELSE 'NEEDS MORE WORK ⚠️'
    END as certification_status
FROM final_scores
ORDER BY county_slug;