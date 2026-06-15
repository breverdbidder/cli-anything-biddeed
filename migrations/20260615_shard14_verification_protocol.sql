-- SHARD-14 COMPREHENSIVE VERIFICATION PROTOCOL
-- Generated: 2026-06-15T16:20:00Z
-- Purpose: Verify all SHARD-14 Gold Standard improvements

SET statement_timeout = 0;

-- J GENERATOR VERIFICATION for SHARD-14
SELECT 
    'J_GENERATOR_VERIFICATION' as check_type,
    county,
    COUNT(*) as bid_decisions_count,
    COUNT(CASE WHEN arv IS NOT NULL THEN 1 END) as with_arv,
    COUNT(CASE WHEN max_bid IS NOT NULL THEN 1 END) as with_max_bid,
    COUNT(CASE WHEN ml_score IS NOT NULL THEN 1 END) as with_ml_score,
    COUNT(CASE WHEN factors IS NOT NULL THEN 1 END) as with_factors,
    -- Check for required factor keys
    COUNT(CASE WHEN jsonb_extract_path_text(factors, 'distress_location') IS NOT NULL THEN 1 END) as with_distress_location,
    COUNT(CASE WHEN jsonb_extract_path_text(factors, 'distress_property') IS NOT NULL THEN 1 END) as with_distress_property,
    COUNT(CASE WHEN jsonb_extract_path_text(factors, 'distress_owner') IS NOT NULL THEN 1 END) as with_distress_owner,
    COUNT(CASE WHEN jsonb_extract_path_text(factors, 'cma_distressed') IS NOT NULL THEN 1 END) as with_cma_distressed,
    COUNT(CASE WHEN jsonb_extract_path_text(factors, 'cma_resale') IS NOT NULL THEN 1 END) as with_cma_resale,
    ROUND(AVG(arv), 0) as avg_arv,
    ROUND(AVG(max_bid), 0) as avg_max_bid,
    ROUND(AVG(ml_score), 3) as avg_ml_score,
    ROUND(MIN(ml_score), 3) as min_ml_score,
    ROUND(MAX(ml_score), 3) as max_ml_score
FROM bid_decisions 
WHERE county IN ('sumter', 'hernando', 'santa_rosa', 'hamilton')
    AND created_at >= NOW() - INTERVAL '2 hours'  -- Recent entries from this session
GROUP BY county
ORDER BY county;

-- B RECONCILIATION VERIFICATION for SHARD-14
SELECT 
    'B_RECONCILIATION_VERIFICATION' as check_type,
    county,
    auction_type,
    COUNT(*) as verified_outcomes_count,
    COUNT(CASE WHEN outcome_type = 'sold' THEN 1 END) as sold_outcomes,
    COUNT(CASE WHEN winning_bid IS NOT NULL THEN 1 END) as with_winning_bid,
    ROUND(AVG(winning_bid), 0) as avg_winning_bid,
    data_source,
    MIN(scraped_at) as first_scraped,
    MAX(scraped_at) as last_scraped
FROM v_verified_outcomes_combined
WHERE county IN ('sumter', 'hernando', 'santa_rosa', 'hamilton')
    AND scraped_at >= NOW() - INTERVAL '2 hours'
GROUP BY county, auction_type, data_source
ORDER BY county, auction_type;

-- Check for independent data sources (not PropertyOnion)
SELECT 
    'INDEPENDENT_DATA_SOURCE_CHECK' as check_type,
    county,
    data_source,
    CASE 
        WHEN data_source LIKE '%clerk%' THEN 'INDEPENDENT ✅'
        WHEN data_source LIKE '%propertyonion%' OR data_source LIKE '%PO-%' THEN 'NOT_INDEPENDENT ❌'
        ELSE 'VERIFY_MANUALLY ⚠️'
    END as independence_status,
    COUNT(*) as outcome_count
FROM v_verified_outcomes_combined  
WHERE county IN ('sumter', 'hernando', 'santa_rosa', 'hamilton')
    AND scraped_at >= NOW() - INTERVAL '2 hours'
GROUP BY county, data_source
ORDER BY county, data_source;

-- HAMILTON LANE CONFIGURATION VERIFICATION
SELECT 
    'HAMILTON_LANE_CONFIG_VERIFICATION' as check_type,
    county_slug,
    county_name,
    foreclosure_platform,
    foreclosure_url,
    CASE WHEN foreclosure_url IS NOT NULL THEN 'CONFIGURED ✅' ELSE 'MISSING ❌' END as fc_status,
    tax_deed_platform,
    tax_deed_url,
    CASE WHEN tax_deed_url IS NOT NULL THEN 'CONFIGURED ✅' ELSE 'MISSING ❌' END as td_status,
    CASE 
        WHEN foreclosure_platform IS NOT NULL AND tax_deed_platform IS NOT NULL THEN 'DUAL_PRODUCT ✅'
        WHEN foreclosure_platform IS NOT NULL OR tax_deed_platform IS NOT NULL THEN 'SINGLE_PRODUCT ⚠️'
        ELSE 'NO_LANES ❌'
    END as dual_product_status,
    active,
    updated_at
FROM pipeline.counties
WHERE county_slug IN ('hamilton', 'sumter', 'hernando', 'santa_rosa')
ORDER BY county_slug;

-- Verify A letter criterion (dual product coverage) will pass
SELECT 
    'DUAL_PRODUCT_COVERAGE_CHECK' as check_type,
    county_slug,
    CASE 
        WHEN foreclosure_platform IS NOT NULL AND tax_deed_platform IS NOT NULL THEN 'LETTER_A_PASS ✅'
        ELSE 'LETTER_A_FAIL ❌'
    END as letter_a_projection
FROM pipeline.counties
WHERE county_slug IN ('hamilton', 'sumter', 'hernando', 'santa_rosa')
ORDER BY county_slug;

-- GOLD STANDARD EVALUATION for SHARD-14 counties
-- Run pencil_dod_evaluate_county for each county to see metric improvements

-- Note: This would normally be executed via RPC calls:
-- SELECT public.pencil_dod_evaluate_county('sumter');
-- SELECT public.pencil_dod_evaluate_county('hernando'); 
-- SELECT public.pencil_dod_evaluate_county('santa_rosa');
-- SELECT public.pencil_dod_evaluate_county('hamilton');

-- Alternative: Check components that feed into the evaluation

-- Check multi_county_auctions counts (baseline data)
SELECT 
    'AUCTION_COUNTS' as metric,
    county_slug as county,
    COUNT(*) as total_auctions,
    COUNT(CASE WHEN auction_status = 'sold' THEN 1 END) as sold_auctions,
    COUNT(CASE WHEN auction_status IN ('sold', 'no_sale', 'canceled') THEN 1 END) as closed_auctions
FROM multi_county_auctions 
WHERE county_slug IN ('sumter', 'hernando', 'santa_rosa', 'hamilton')
GROUP BY county_slug
ORDER BY county_slug;

-- Check if J letter improvements are reflected
SELECT 
    'LETTER_J_READINESS' as metric,
    mca.county_slug as county,
    COUNT(*) as total_auctions,
    COUNT(bd.case_number) as with_bid_decisions,
    ROUND(COUNT(bd.case_number) * 100.0 / COUNT(*), 1) as coverage_percentage,
    CASE 
        WHEN COUNT(bd.case_number) * 100.0 / COUNT(*) >= 95 THEN 'LETTER_J_READY ✅'
        WHEN COUNT(bd.case_number) > 0 THEN 'LETTER_J_PARTIAL ⚠️'
        ELSE 'LETTER_J_MISSING ❌'
    END as j_projection
FROM multi_county_auctions mca
LEFT JOIN bid_decisions bd ON mca.case_number = bd.case_number AND mca.county_slug = bd.county
WHERE mca.county_slug IN ('sumter', 'hernando', 'santa_rosa', 'hamilton')
GROUP BY mca.county_slug
ORDER BY mca.county_slug;

-- Check if B letter improvements are reflected  
SELECT 
    'LETTER_B_READINESS' as metric,
    mca.county_slug as county,
    COUNT(CASE WHEN mca.auction_status IN ('sold', 'no_sale', 'canceled') THEN 1 END) as closed_auctions,
    COUNT(vo.case_number) as with_verified_outcomes,
    CASE 
        WHEN COUNT(CASE WHEN mca.auction_status IN ('sold', 'no_sale', 'canceled') THEN 1 END) = 0 THEN 'NO_CLOSED_AUCTIONS'
        ELSE ROUND(COUNT(vo.case_number) * 100.0 / COUNT(CASE WHEN mca.auction_status IN ('sold', 'no_sale', 'canceled') THEN 1 END), 1)
    END as coverage_percentage,
    CASE 
        WHEN COUNT(CASE WHEN mca.auction_status IN ('sold', 'no_sale', 'canceled') THEN 1 END) = 0 THEN 'LETTER_B_N/A'
        WHEN COUNT(vo.case_number) * 100.0 / COUNT(CASE WHEN mca.auction_status IN ('sold', 'no_sale', 'canceled') THEN 1 END) >= 95 THEN 'LETTER_B_READY ✅'
        WHEN COUNT(vo.case_number) > 0 THEN 'LETTER_B_PARTIAL ⚠️'
        ELSE 'LETTER_B_MISSING ❌'
    END as b_projection
FROM multi_county_auctions mca
LEFT JOIN v_verified_outcomes_combined vo ON mca.case_number = vo.case_number AND mca.county_slug = vo.county
WHERE mca.county_slug IN ('sumter', 'hernando', 'santa_rosa', 'hamilton')
GROUP BY mca.county_slug
ORDER BY mca.county_slug;

-- Session Summary
SELECT 
    'SHARD14_SESSION_SUMMARY' as summary_type,
    NOW() as verification_timestamp,
    'J_GENERATOR + B_RECONCILIATION + HAMILTON_LANES' as implementations,
    'sumter,hernando,santa_rosa,hamilton' as target_counties,
    'AUTONOMOUS_SESSION_SHARD14' as session_mode;