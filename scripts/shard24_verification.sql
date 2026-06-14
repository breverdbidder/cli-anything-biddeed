-- SHARD-24 Verification Queries
-- Verify J generator results and gold standard metric improvements

-- 1. COUNT_BY_COUNTY: Check bid_decisions population per county
SELECT 
    county_slug,
    COUNT(*) as bid_decisions_count,
    COUNT(CASE WHEN ml_score IS NOT NULL THEN 1 END) as with_ml_score,
    COUNT(CASE WHEN factors IS NOT NULL THEN 1 END) as with_factors,
    AVG(ml_score) as avg_ml_score,
    AVG(arv) as avg_arv,
    AVG(max_bid) as avg_max_bid
FROM bid_decisions 
WHERE county_slug IN ('citrus', 'broward', 'charlotte')
GROUP BY county_slug
ORDER BY county_slug;

-- 2. FACTOR_COMPLETENESS: Verify all 5 required factor keys present
SELECT 
    county_slug,
    COUNT(*) as total_rows,
    COUNT(CASE WHEN factors ? 'distress_location' THEN 1 END) as has_distress_location,
    COUNT(CASE WHEN factors ? 'distress_property' THEN 1 END) as has_distress_property,
    COUNT(CASE WHEN factors ? 'distress_owner' THEN 1 END) as has_distress_owner,
    COUNT(CASE WHEN factors ? 'cma_distressed' THEN 1 END) as has_cma_distressed,
    COUNT(CASE WHEN factors ? 'cma_resale' THEN 1 END) as has_cma_resale,
    -- Percentage with all 5 factors
    ROUND(
        COUNT(CASE WHEN 
            factors ? 'distress_location' AND
            factors ? 'distress_property' AND 
            factors ? 'distress_owner' AND
            factors ? 'cma_distressed' AND
            factors ? 'cma_resale'
        THEN 1 END) * 100.0 / COUNT(*), 2
    ) as pct_complete_factors
FROM bid_decisions 
WHERE county_slug IN ('citrus', 'broward', 'charlotte')
GROUP BY county_slug
ORDER BY county_slug;

-- 3. SAMPLE_DECISIONS: Review sample bid decisions 
SELECT 
    county_slug,
    case_number,
    arv,
    max_bid,
    ROUND(ml_score, 3) as ml_score,
    deal_grade,
    profit_potential,
    ml_model_version,
    jsonb_extract_path_text(factors, 'distress_location') as distress_location,
    jsonb_extract_path_text(factors, 'cma_resale') as cma_resale
FROM bid_decisions 
WHERE county_slug IN ('citrus', 'broward', 'charlotte')
    AND ml_score IS NOT NULL
ORDER BY county_slug, ml_score DESC
LIMIT 15;

-- 4. J_METRIC_EVALUATION: Check live J metrics post-generator
-- This is the key verification - did J improve from 0.0%?
SELECT 
    'citrus' as county_slug,
    public.pencil_dod_evaluate_county('citrus') as evaluation
UNION ALL
SELECT 
    'broward' as county_slug,
    public.pencil_dod_evaluate_county('broward') as evaluation
UNION ALL
SELECT 
    'charlotte' as county_slug,
    public.pencil_dod_evaluate_county('charlotte') as evaluation;

-- 5. DEAL_QUALITY: Analyze deal grades and profitability
SELECT 
    county_slug,
    deal_grade,
    COUNT(*) as count,
    AVG(profit_potential) as avg_profit,
    AVG(arv) as avg_arv,
    AVG(max_bid) as avg_max_bid,
    ROUND(AVG(ml_score), 3) as avg_ml_score
FROM bid_decisions 
WHERE county_slug IN ('citrus', 'broward', 'charlotte')
GROUP BY county_slug, deal_grade
ORDER BY county_slug, deal_grade;

-- 6. DATA_SOURCES_AUDIT: Verify data lineage
SELECT 
    county_slug,
    ml_model_version,
    COUNT(*) as count,
    AVG(ml_score) as avg_confidence
FROM bid_decisions 
WHERE county_slug IN ('citrus', 'broward', 'charlotte')
GROUP BY county_slug, ml_model_version
ORDER BY county_slug, ml_model_version;