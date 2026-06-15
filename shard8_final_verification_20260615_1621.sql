-- SHARD-8 FINAL VERIFICATION PROTOCOL - Generated at 2026-06-15T16:21:00Z
-- Purpose: Comprehensive verification of all SHARD-8 improvements
-- Counties: marion, collier, nassau, desoto, monroe
-- Run this AFTER executing all SHARD-8 fixes

SET statement_timeout = 0;

-- 1. BASELINE vs POST-FIX METRICS COMPARISON
WITH baseline_metrics AS (
    SELECT 'BASELINE (from briefing)' as phase,
           'marion' as county, 2 as score, '9.6' as c_metric, '55.1' as d_metric, '0.0' as j_metric, 'PASS' as h_status
    UNION ALL
    SELECT 'BASELINE (from briefing)', 'collier', 1, '17.3', '59.2', '0.0', 'FAIL'
    UNION ALL  
    SELECT 'BASELINE (from briefing)', 'nassau', 1, '15.2', '55.9', '0.0', 'FAIL'
    UNION ALL
    SELECT 'BASELINE (from briefing)', 'desoto', 0, 'null', 'null', 'null', 'null'
    UNION ALL
    SELECT 'BASELINE (from briefing)', 'monroe', 0, 'null', 'null', 'null', 'null'
),
post_fix_evaluation AS (
    SELECT 
        'POST-FIX (live)' as phase,
        county_name as county,
        CASE 
            WHEN grade_a = 'PASS' THEN 1 ELSE 0 END +
            CASE WHEN grade_b = 'PASS' THEN 1 ELSE 0 END +
            CASE WHEN grade_c = 'PASS' THEN 1 ELSE 0 END +
            CASE WHEN grade_d = 'PASS' THEN 1 ELSE 0 END +
            CASE WHEN grade_e = 'PASS' THEN 1 ELSE 0 END +
            CASE WHEN grade_f = 'PASS' THEN 1 ELSE 0 END +
            CASE WHEN grade_g = 'PASS' THEN 1 ELSE 0 END +
            CASE WHEN grade_h = 'PASS' THEN 1 ELSE 0 END +
            CASE WHEN grade_i = 'PASS' THEN 1 ELSE 0 END +
            CASE WHEN grade_j = 'PASS' THEN 1 ELSE 0 END as score,
        COALESCE(metric_c::TEXT, 'null') as c_metric,
        COALESCE(metric_d::TEXT, 'null') as d_metric,
        COALESCE(metric_j::TEXT, 'null') as j_metric,
        grade_h as h_status
    FROM (
        SELECT * FROM public.pencil_dod_evaluate_county('marion')
        UNION ALL
        SELECT * FROM public.pencil_dod_evaluate_county('collier') 
        UNION ALL
        SELECT * FROM public.pencil_dod_evaluate_county('nassau')
        UNION ALL
        SELECT * FROM public.pencil_dod_evaluate_county('desoto')
        UNION ALL
        SELECT * FROM public.pencil_dod_evaluate_county('monroe')
    ) eval_results
)
SELECT 
    'SHARD-8 BEFORE/AFTER COMPARISON' as summary_type,
    b.county,
    b.score as baseline_score,
    p.score as post_fix_score,
    (p.score - b.score) as score_improvement,
    b.c_metric as baseline_c,
    p.c_metric as post_fix_c,
    b.d_metric as baseline_d,
    p.d_metric as post_fix_d,
    b.j_metric as baseline_j,
    p.j_metric as post_fix_j,
    b.h_status as baseline_h,
    p.h_status as post_fix_h
FROM baseline_metrics b
JOIN post_fix_evaluation p ON b.county = p.county
ORDER BY (p.score - b.score) DESC;

-- 2. J GENERATOR VERIFICATION
SELECT 
    'J GENERATOR IMPACT' as verification_type,
    county_slug as county,
    COUNT(*) as total_decisions_created,
    COUNT(CASE WHEN arv IS NOT NULL AND max_bid IS NOT NULL AND ml_score IS NOT NULL THEN 1 END) as complete_decisions,
    COUNT(CASE 
        WHEN factors ? 'distress_location' 
         AND factors ? 'distress_property' 
         AND factors ? 'distress_owner'
         AND factors ? 'cma_distressed'
         AND factors ? 'cma_resale'
        THEN 1 
    END) as decisions_with_all_factors,
    ROUND(AVG(arv), 0) as avg_arv,
    ROUND(AVG(max_bid), 0) as avg_max_bid,
    ROUND(AVG(ml_score), 3) as avg_ml_score
FROM bid_decisions
WHERE county_slug IN ('marion', 'collier', 'nassau', 'desoto', 'monroe')
    AND created_at >= NOW() - INTERVAL '2 hours'  -- Recent SHARD-8 work
GROUP BY county_slug
ORDER BY county_slug;

-- 3. A-LANE CONFIGURATION VERIFICATION
SELECT 
    'A-LANE CONFIG STATUS' as verification_type,
    county_slug,
    county_name,
    foreclosure_platform,
    tax_deed_platform,
    status,
    priority,
    notes
FROM pipeline.counties
WHERE county_slug IN ('desoto', 'monroe')
ORDER BY county_slug;

-- 4. C/D PARITY IMPROVEMENT
WITH cd_improvement AS (
    SELECT 
        county,
        COUNT(*) as total_auctions,
        COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) as matched_clean,
        COUNT(CASE WHEN parity_status IN ('matched_clean', 'matched_any', 'matched_partial') THEN 1 END) as matched_any,
        COUNT(CASE WHEN notes LIKE '%clerk supplementary litmus%' THEN 1 END) as clerk_processed,
        ROUND(COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 2) as c_metric_actual,
        ROUND(COUNT(CASE WHEN parity_status IN ('matched_clean', 'matched_any', 'matched_partial') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 2) as d_metric_actual
    FROM multi_county_auctions
    WHERE county IN ('marion', 'collier', 'nassau')
    GROUP BY county
)
SELECT 
    'C/D PARITY VERIFICATION' as verification_type,
    county,
    total_auctions,
    c_metric_actual,
    d_metric_actual,
    clerk_processed,
    ROUND(clerk_processed * 100.0 / total_auctions, 2) as clerk_coverage_pct
FROM cd_improvement
ORDER BY county;

-- 5. H FRESHNESS STATUS
WITH freshness_status AS (
    SELECT 
        county,
        COUNT(*) as total_auctions,
        COUNT(CASE WHEN last_seen_at > NOW() - INTERVAL '48 hours' THEN 1 END) as fresh_within_48h,
        ROUND(EXTRACT(EPOCH FROM NOW() - MAX(last_seen_at)) / 3600, 1) as hours_since_freshest,
        COUNT(CASE WHEN notes LIKE '%H freshness fix%' THEN 1 END) as freshness_fix_applied
    FROM multi_county_auctions
    WHERE county IN ('collier', 'nassau')
    GROUP BY county
)
SELECT 
    'H FRESHNESS VERIFICATION' as verification_type,
    county,
    total_auctions,
    fresh_within_48h,
    hours_since_freshest,
    CASE 
        WHEN hours_since_freshest <= 48 THEN 'PASS'
        ELSE 'FAIL'
    END as h_status_expected,
    freshness_fix_applied
FROM freshness_status
ORDER BY county;

-- 6. OVERALL SHARD-8 IMPACT SUMMARY
WITH county_final_scores AS (
    SELECT 
        county_name as county,
        (CASE WHEN grade_a = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_b = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_c = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_d = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_e = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_f = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_g = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_h = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_i = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_j = 'PASS' THEN 1 ELSE 0 END) as final_score,
        grade_a, grade_b, grade_c, grade_d, grade_e, 
        grade_f, grade_g, grade_h, grade_i, grade_j
    FROM (
        SELECT * FROM public.pencil_dod_evaluate_county('marion')
        UNION ALL
        SELECT * FROM public.pencil_dod_evaluate_county('collier')
        UNION ALL
        SELECT * FROM public.pencil_dod_evaluate_county('nassau')
        UNION ALL
        SELECT * FROM public.pencil_dod_evaluate_county('desoto')
        UNION ALL
        SELECT * FROM public.pencil_dod_evaluate_county('monroe')
    ) all_evaluations
),
baseline_scores AS (
    SELECT 'marion' as county, 2 as baseline_score
    UNION ALL SELECT 'collier', 1
    UNION ALL SELECT 'nassau', 1  
    UNION ALL SELECT 'desoto', 0
    UNION ALL SELECT 'monroe', 0
)
SELECT 
    'SHARD-8 FINAL IMPACT SUMMARY' as summary_type,
    cfs.county,
    bs.baseline_score,
    cfs.final_score,
    (cfs.final_score - bs.baseline_score) as points_gained,
    CONCAT(cfs.grade_a, cfs.grade_b, cfs.grade_c, cfs.grade_d, cfs.grade_e, 
           cfs.grade_f, cfs.grade_g, cfs.grade_h, cfs.grade_i, cfs.grade_j) as letter_status
FROM county_final_scores cfs
JOIN baseline_scores bs ON cfs.county = bs.county
ORDER BY points_gained DESC, final_score DESC;

-- 7. DEPLOYMENT VERIFICATION
SELECT 
    'DEPLOYMENT VERIFICATION' as verification_type,
    table_name,
    COUNT(*) as records_modified,
    MAX(updated_at) as latest_update
FROM (
    SELECT 'bid_decisions' as table_name, updated_at
    FROM bid_decisions 
    WHERE county_slug IN ('marion', 'collier', 'nassau', 'desoto', 'monroe')
        AND created_at >= NOW() - INTERVAL '2 hours'
    
    UNION ALL
    
    SELECT 'pipeline.counties', updated_at
    FROM pipeline.counties
    WHERE county_slug IN ('desoto', 'monroe')
        AND notes LIKE '%SHARD-8%'
    
    UNION ALL
    
    SELECT 'clerk_supplementary_litmus', updated_at
    FROM clerk_supplementary_litmus
    WHERE county IN ('marion', 'collier', 'nassau')
        AND created_at >= NOW() - INTERVAL '2 hours'
    
    UNION ALL
    
    SELECT 'multi_county_auctions', updated_at
    FROM multi_county_auctions
    WHERE county IN ('collier', 'nassau')
        AND notes LIKE '%freshness fix%'
        AND updated_at >= NOW() - INTERVAL '2 hours'
) deployment_evidence
GROUP BY table_name
ORDER BY table_name;

-- 8. CERTIFICATION READINESS CHECK
WITH certification_check AS (
    SELECT 
        county_name as county,
        CASE 
            WHEN (CASE WHEN grade_a = 'PASS' THEN 1 ELSE 0 END +
                  CASE WHEN grade_b = 'PASS' THEN 1 ELSE 0 END +
                  CASE WHEN grade_c = 'PASS' THEN 1 ELSE 0 END +
                  CASE WHEN grade_d = 'PASS' THEN 1 ELSE 0 END +
                  CASE WHEN grade_e = 'PASS' THEN 1 ELSE 0 END +
                  CASE WHEN grade_f = 'PASS' THEN 1 ELSE 0 END +
                  CASE WHEN grade_g = 'PASS' THEN 1 ELSE 0 END +
                  CASE WHEN grade_h = 'PASS' THEN 1 ELSE 0 END +
                  CASE WHEN grade_i = 'PASS' THEN 1 ELSE 0 END +
                  CASE WHEN grade_j = 'PASS' THEN 1 ELSE 0 END) >= 10
            THEN 'CERTIFICATION_READY'
            ELSE 'NEEDS_MORE_WORK'
        END as certification_status,
        (CASE WHEN grade_a = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_b = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_c = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_d = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_e = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_f = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_g = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_h = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_i = 'PASS' THEN 1 ELSE 0 END +
         CASE WHEN grade_j = 'PASS' THEN 1 ELSE 0 END) as current_score
    FROM (
        SELECT * FROM public.pencil_dod_evaluate_county('marion')
        UNION ALL
        SELECT * FROM public.pencil_dod_evaluate_county('collier')
        UNION ALL
        SELECT * FROM public.pencil_dod_evaluate_county('nassau')
        UNION ALL
        SELECT * FROM public.pencil_dod_evaluate_county('desoto')
        UNION ALL
        SELECT * FROM public.pencil_dod_evaluate_county('monroe')
    ) cert_eval
)
SELECT 
    'CERTIFICATION READINESS' as check_type,
    county,
    current_score,
    certification_status,
    CASE 
        WHEN certification_status = 'CERTIFICATION_READY' THEN 'Ready for gold standard certification'
        ELSE CONCAT('Needs ', (10 - current_score), ' more letters to reach 10/10')
    END as next_steps
FROM certification_check
ORDER BY current_score DESC;