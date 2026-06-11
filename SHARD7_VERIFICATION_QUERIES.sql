-- SHARD-7 Gold Standard Verification Queries
-- Execute these queries AFTER running the implementation scripts
-- to verify Letter improvements per county

-- =============================================================================
-- PRE-IMPLEMENTATION BASELINE (run these first to capture current state)
-- =============================================================================

-- Current county scores
SELECT county_slug, pass_count, total_letters, 
       ROUND(pass_count::numeric / total_letters * 100, 1) as pass_percentage,
       last_evaluated_at
FROM gold_standard_county_status 
WHERE county_slug IN ('hillsborough','suwannee','lake','columbia','madison')
ORDER BY county_slug;

-- Current auction counts (Letter A baseline)
SELECT county, COUNT(*) as current_auction_count, 
       MIN(auction_date) as earliest_auction,
       MAX(auction_date) as latest_auction
FROM multi_county_auctions 
WHERE county IN ('hillsborough','suwannee','lake','columbia','madison')
GROUP BY county
ORDER BY county;

-- Current parcel linkage rates (Letter E baseline)
SELECT county, 
       COUNT(*) as total_auctions,
       COUNT(parcel_id) as linked_auctions,
       ROUND(COUNT(parcel_id)::numeric / COUNT(*) * 100, 1) as current_link_percentage
FROM multi_county_auctions 
WHERE county IN ('hillsborough','lake') -- Only GIS-enabled counties
GROUP BY county;

-- Current verified outcomes (Letter B baseline)
SELECT mca.county,
       COUNT(DISTINCT mca.case_number) as total_closed_auctions,
       COUNT(DISTINCT vo.case_number) as currently_verified,
       ROUND(COUNT(DISTINCT vo.case_number)::numeric / COUNT(DISTINCT mca.case_number) * 100, 1) as current_verified_percentage
FROM multi_county_auctions mca
LEFT JOIN verified_outcomes vo ON mca.county = vo.county AND mca.case_number = vo.case_number
WHERE mca.county IN ('hillsborough','suwannee','lake','columbia','madison')
  AND mca.auction_status IN ('sold','completed')
GROUP BY mca.county;

-- =============================================================================
-- POST-IMPLEMENTATION VERIFICATION (run after executing SHARD-7 fixes)
-- =============================================================================

-- 1. LETTER A VERIFICATION: Basic auction coverage
-- Expected: columbia and madison should have >0 auctions
SELECT county, COUNT(*) as post_implementation_auction_count,
       COUNT(*) - LAG(COUNT(*), 1) OVER (ORDER BY county) as net_increase
FROM multi_county_auctions 
WHERE county IN ('columbia','madison','suwannee')
  AND created_at >= CURRENT_DATE -- New auctions from today
GROUP BY county
ORDER BY county;

-- 2. LETTER H VERIFICATION: Freshness <=48h  
-- Expected: suwannee and lake should show recent timestamps
SELECT county, last_scraped_at,
       EXTRACT(EPOCH FROM (NOW() - last_scraped_at)) / 3600 as hours_since_last_scrape,
       CASE WHEN EXTRACT(EPOCH FROM (NOW() - last_scraped_at)) / 3600 <= 48 
            THEN 'PASS' ELSE 'FAIL' END as freshness_status
FROM county_auction_sources 
WHERE county IN ('suwannee','lake') AND state = 'FL';

-- 3. LETTER E VERIFICATION: Parcel linkage >=95%
-- Expected: hillsborough and lake should show >95% linkage
SELECT county, 
       COUNT(*) as total_auctions,
       COUNT(parcel_id) as linked_auctions,
       ROUND(COUNT(parcel_id)::numeric / COUNT(*) * 100, 1) as link_percentage,
       CASE WHEN COUNT(parcel_id)::numeric / COUNT(*) >= 0.95 
            THEN 'PASS' ELSE 'FAIL' END as letter_e_status
FROM multi_county_auctions 
WHERE county IN ('hillsborough','lake')
GROUP BY county;

-- 4. LETTER B VERIFICATION: Verified outcomes >=95%
-- Expected: All counties should show independent verified outcomes
SELECT vo.county,
       COUNT(DISTINCT vo.case_number) as verified_outcomes_count,
       COUNT(DISTINCT mca.case_number) as total_closed_auctions,
       ROUND(COUNT(DISTINCT vo.case_number)::numeric / COUNT(DISTINCT mca.case_number) * 100, 1) as verified_percentage,
       CASE WHEN COUNT(DISTINCT vo.case_number)::numeric / COUNT(DISTINCT mca.case_number) >= 0.95 
            THEN 'PASS' ELSE 'FAIL' END as letter_b_status,
       STRING_AGG(DISTINCT vo.data_source, ', ') as data_sources_used
FROM verified_outcomes vo
RIGHT JOIN multi_county_auctions mca ON vo.county = mca.county AND vo.case_number = mca.case_number
WHERE mca.county IN ('hillsborough','suwannee','lake','columbia','madison')
  AND mca.auction_status IN ('sold','completed')
  AND vo.data_source LIKE 'clerk_%_independent' -- Only independent sources
GROUP BY vo.county;

-- =============================================================================
-- COMPREHENSIVE COUNTY EVALUATIONS (run for final scoring)
-- =============================================================================

-- Run pencil_dod_evaluate_county for each SHARD-7 county
-- Expected: All counties should show improvement in targeted letters

-- Hillsborough evaluation (targeting A,B,E,H)
SELECT 'hillsborough' as county, * FROM public.pencil_dod_evaluate_county('hillsborough');

-- Suwannee evaluation (targeting A,B,H) 
SELECT 'suwannee' as county, * FROM public.pencil_dod_evaluate_county('suwannee');

-- Lake evaluation (targeting A,B,E,H)
SELECT 'lake' as county, * FROM public.pencil_dod_evaluate_county('lake');

-- Columbia evaluation (targeting A,B,H)
SELECT 'columbia' as county, * FROM public.pencil_dod_evaluate_county('columbia');

-- Madison evaluation (targeting A,B,H)
SELECT 'madison' as county, * FROM public.pencil_dod_evaluate_county('madison');

-- =============================================================================
-- SCORE DELTA ANALYSIS (compare before/after)
-- =============================================================================

-- Updated county scores after implementation
SELECT county_slug, pass_count, total_letters, 
       ROUND(pass_count::numeric / total_letters * 100, 1) as new_pass_percentage,
       last_evaluated_at,
       pass_count - LAG(pass_count, 1) OVER (ORDER BY last_evaluated_at) as score_improvement
FROM gold_standard_county_status 
WHERE county_slug IN ('hillsborough','suwannee','lake','columbia','madison')
  AND last_evaluated_at >= CURRENT_DATE -- Today's evaluations only
ORDER BY county_slug, last_evaluated_at DESC;

-- =============================================================================
-- CONFIGURATION VERIFICATION (check that setup was applied correctly)
-- =============================================================================

-- Verify county auction sources were added
SELECT county, state, platform, source_url, status, added_by, added_at
FROM county_auction_sources 
WHERE county IN ('hillsborough','suwannee','lake','columbia','madison')
ORDER BY county;

-- Verify GIS configuration for parcel linkage
SELECT county, state, gis_endpoint, parcel_linkage_enabled, configured_by, configured_at
FROM county_gis_config 
WHERE county IN ('hillsborough','lake') -- Only GIS-enabled counties  
ORDER BY county;

-- Verify verified outcomes configuration
SELECT county, state, clerk_system, clerk_base_url, data_source, configured_by, configured_at
FROM verified_outcomes_config 
WHERE county IN ('hillsborough','suwannee','lake','columbia','madison')
ORDER BY county;

-- =============================================================================
-- SUCCESS CRITERIA SUMMARY
-- =============================================================================

-- Final success validation - all targeted letters should show PASS
WITH evaluation_results AS (
  SELECT county_slug,
         SUM(CASE WHEN letter IN ('A','B','E','H') AND pass = true THEN 1 ELSE 0 END) as target_letter_passes,
         COUNT(CASE WHEN letter IN ('A','B','E','H') THEN 1 END) as target_letters_applicable
  FROM (
    SELECT 'hillsborough' as county_slug, * FROM public.pencil_dod_evaluate_county('hillsborough')
    UNION ALL
    SELECT 'suwannee' as county_slug, * FROM public.pencil_dod_evaluate_county('suwannee')  
    UNION ALL
    SELECT 'lake' as county_slug, * FROM public.pencil_dod_evaluate_county('lake')
    UNION ALL
    SELECT 'columbia' as county_slug, * FROM public.pencil_dod_evaluate_county('columbia')
    UNION ALL
    SELECT 'madison' as county_slug, * FROM public.pencil_dod_evaluate_county('madison')
  ) all_evaluations
  GROUP BY county_slug
)
SELECT county_slug,
       target_letter_passes,
       target_letters_applicable,
       ROUND(target_letter_passes::numeric / target_letters_applicable * 100, 1) as target_success_rate,
       CASE WHEN target_letter_passes::numeric / target_letters_applicable >= 0.75 
            THEN '✅ SUCCESS' ELSE '❌ NEEDS_MORE_WORK' END as implementation_status
FROM evaluation_results
ORDER BY county_slug;

-- =============================================================================
-- EXECUTION NOTES
-- =============================================================================

/*
EXECUTION ORDER:
1. Run PRE-IMPLEMENTATION queries to capture baseline
2. Apply database migration: migrations/20260611_shard7_gold_standard_setup.sql  
3. Execute processing scripts:
   - python scripts/shard7_gold_standard_fixes.py
   - python scripts/shard7_parcel_linkage.py  
   - python scripts/shard7_verified_outcomes.py
4. Run POST-IMPLEMENTATION queries to verify improvements
5. Run COMPREHENSIVE EVALUATIONS to get final scores
6. Run SCORE DELTA ANALYSIS to confirm improvements  
7. Run SUCCESS CRITERIA SUMMARY for final validation

EXPECTED RESULTS:
- Letters A,H should PASS for all counties
- Letter B should PASS for counties with sufficient closed auction data  
- Letter E should PASS for hillsborough and lake (GIS-enabled)
- Overall scores should improve by 2-4 letters per county

HONESTY PROTOCOL:
- Only claim SUCCESS if verification queries return expected results
- Document any deviations or partial results
- Mark queries as UNTESTED until actually executed against live DB
*/