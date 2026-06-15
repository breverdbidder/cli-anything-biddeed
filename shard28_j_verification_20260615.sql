-- SHARD-28 J GENERATOR VERIFICATION - Generated at 2026-06-15T00:05:00Z
-- Run this AFTER executing the J generator SQL

-- VERIFICATION: Check J letter impact for brevard and duval
-- Run this AFTER executing the J generator SQL

SELECT 
    'BEFORE/AFTER J GENERATOR IMPACT' as check_type,
    'brevard' as county,
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
WHERE mca.county = 'brevard' 
    AND mca.auction_status IN ('sold', 'no_sale', 'canceled')

UNION ALL

SELECT 
    'BEFORE/AFTER J GENERATOR IMPACT' as check_type,
    'duval' as county,
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
WHERE mca.county = 'duval'
    AND mca.auction_status IN ('sold', 'no_sale', 'canceled');

-- Sample of created bid_decisions
SELECT 'SAMPLE CREATED DECISIONS' as check_type, * 
FROM bid_decisions 
WHERE county_slug IN ('brevard', 'duval')
ORDER BY created_at DESC 
LIMIT 5;

-- Final verification via pencil_dod_evaluate_county
SELECT 'FINAL VERIFICATION' as check_type, * FROM public.pencil_dod_evaluate_county('brevard') WHERE letter = 'J';
SELECT 'FINAL VERIFICATION' as check_type, * FROM public.pencil_dod_evaluate_county('duval') WHERE letter = 'J';