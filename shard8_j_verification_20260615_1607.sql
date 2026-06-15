-- SHARD-8 J GENERATOR VERIFICATION - Generated at 2026-06-15T16:07:00Z
-- Run this AFTER executing the J generator SQL

-- VERIFICATION: Check J letter impact for SHARD-8 counties
-- Run this AFTER executing the J generator SQL

SELECT 
    'SHARD-8 J GENERATOR IMPACT' as check_type,
    county_slug as county,
    COUNT(*) as total_auctions_closed,
    COUNT(bd.case_number) as auctions_with_bid_decisions,
    COUNT(CASE 
        WHEN bd.arv IS NOT NULL 
            AND bd.max_bid IS NOT NULL 
            AND bd.ml_score IS NOT NULL 
            AND bd.factors ? 'distress_location'
            AND bd.factors ? 'distress_property'
            AND bd.factors ? 'distress_owner'
            AND bd.factors ? 'cma_distressed'
            AND bd.factors ? 'cma_resale'
        THEN 1 
    END) as j_compliant_decisions,
    ROUND(
        COUNT(CASE 
            WHEN bd.arv IS NOT NULL 
                AND bd.max_bid IS NOT NULL 
                AND bd.ml_score IS NOT NULL 
                AND bd.factors ? 'distress_location'
                AND bd.factors ? 'distress_property'
                AND bd.factors ? 'distress_owner'
                AND bd.factors ? 'cma_distressed'
                AND bd.factors ? 'cma_resale'
            THEN 1 
        END) * 100.0 / NULLIF(COUNT(*), 0),
        2
    ) as j_metric_percentage
FROM multi_county_auctions mca
LEFT JOIN bid_decisions bd ON mca.case_number = bd.case_number
WHERE mca.county IN ('marion', 'collier', 'nassau', 'desoto', 'monroe')
    AND mca.auction_status IN ('sold', 'no_sale', 'canceled')
GROUP BY county_slug
ORDER BY county_slug;

-- Sample of created bid_decisions per county
SELECT 
    'SAMPLE DECISIONS' as check_type,
    county_slug,
    COUNT(*) as total_decisions,
    AVG(arv) as avg_arv,
    AVG(max_bid) as avg_max_bid,
    AVG(ml_score) as avg_ml_score,
    COUNT(CASE WHEN deal_grade = 'A' THEN 1 END) as grade_a_count,
    COUNT(CASE WHEN deal_grade = 'B' THEN 1 END) as grade_b_count,
    COUNT(CASE WHEN deal_grade = 'C' THEN 1 END) as grade_c_count,
    COUNT(CASE WHEN deal_grade = 'D' THEN 1 END) as grade_d_count,
    COUNT(CASE WHEN deal_grade = 'F' THEN 1 END) as grade_f_count
FROM bid_decisions 
WHERE county_slug IN ('marion', 'collier', 'nassau', 'desoto', 'monroe')
    AND created_at >= NOW() - INTERVAL '1 hour'  -- Recent decisions only
GROUP BY county_slug
ORDER BY county_slug;

-- Final verification via pencil_dod_evaluate_county
SELECT 'J VERIFICATION marion' as check_type, * FROM public.pencil_dod_evaluate_county('marion');
SELECT 'J VERIFICATION collier' as check_type, * FROM public.pencil_dod_evaluate_county('collier');  
SELECT 'J VERIFICATION nassau' as check_type, * FROM public.pencil_dod_evaluate_county('nassau');
SELECT 'J VERIFICATION desoto' as check_type, * FROM public.pencil_dod_evaluate_county('desoto');
SELECT 'J VERIFICATION monroe' as check_type, * FROM public.pencil_dod_evaluate_county('monroe');

-- Check factors JSON structure
SELECT 
    'FACTORS VALIDATION' as check_type,
    county_slug,
    COUNT(*) as total_with_factors,
    COUNT(CASE WHEN factors ? 'distress_location' THEN 1 END) as has_location,
    COUNT(CASE WHEN factors ? 'distress_property' THEN 1 END) as has_property,
    COUNT(CASE WHEN factors ? 'distress_owner' THEN 1 END) as has_owner,
    COUNT(CASE WHEN factors ? 'cma_distressed' THEN 1 END) as has_cma_distressed,
    COUNT(CASE WHEN factors ? 'cma_resale' THEN 1 END) as has_cma_resale
FROM bid_decisions
WHERE county_slug IN ('marion', 'collier', 'nassau', 'desoto', 'monroe')
    AND created_at >= NOW() - INTERVAL '1 hour'
GROUP BY county_slug
ORDER BY county_slug;