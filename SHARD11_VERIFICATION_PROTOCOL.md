# SHARD-11 Verification Protocol

**Session**: SHARD-11-20260613-0001  
**Counties**: manatee, bay, okeechobee, gadsden, wakulla  
**Date**: 2026-06-13  
**Mode**: Ship-to-main autonomous session  

## Verification Queries

### County Evaluation Baseline
**VERIFIED** from issue body baseline scores:

```sql
-- Manatee (2/10): A_PASS H_PASS, others FAIL
SELECT public.pencil_dod_evaluate_county('manatee');

-- Bay (1/10): A_PASS only 
SELECT public.pencil_dod_evaluate_county('bay');

-- Okeechobee (1/10): A_PASS only
SELECT public.pencil_dod_evaluate_county('okeechobee');

-- Gadsden (0/10): ALL_FAIL
SELECT public.pencil_dod_evaluate_county('gadsden');

-- Wakulla (0/10): ALL_FAIL  
SELECT public.pencil_dod_evaluate_county('wakulla');
```

### C/D Parity Analysis Queries
**Implementation**: scripts/shard11_cd_parity_fix.py

```sql
-- Total auctions by county
SELECT 
    county_slug,
    COUNT(*) as total_auctions
FROM multi_county_auctions 
WHERE county_slug IN ('manatee', 'bay', 'okeechobee', 'gadsden', 'wakulla')
GROUP BY county_slug;

-- PropertyOnion vs Court format breakdown
SELECT 
    county_slug,
    COUNT(*) FILTER (WHERE case_number LIKE 'PO-%') as po_format,
    COUNT(*) FILTER (WHERE case_number NOT LIKE 'PO-%') as court_format,
    ROUND(100.0 * COUNT(*) FILTER (WHERE case_number LIKE 'PO-%') / COUNT(*), 1) as po_percentage
FROM multi_county_auctions 
WHERE county_slug IN ('manatee', 'bay', 'okeechobee', 'gadsden', 'wakulla')
GROUP BY county_slug;

-- Current C/D metrics verification
SELECT 
    county_slug,
    (public.pencil_dod_evaluate_county(county_slug))->>'metric_c' as metric_c,
    (public.pencil_dod_evaluate_county(county_slug))->>'metric_d' as metric_d,
    (public.pencil_dod_evaluate_county(county_slug))->>'grade_c' as grade_c,
    (public.pencil_dod_evaluate_county(county_slug))->>'grade_d' as grade_d
FROM (VALUES ('manatee'), ('bay'), ('okeechobee'), ('gadsden'), ('wakulla')) AS t(county_slug);
```

### J Generator Pipeline Verification
**Implementation**: scripts/shard11_j_generator.py

```sql
-- Current bid_decisions status
SELECT 
    COUNT(*) as total_bid_decisions,
    COUNT(*) FILTER (WHERE ml_score IS NOT NULL) as with_ml_score,
    COUNT(*) FILTER (WHERE factors->>'distress_location' IS NOT NULL) as with_factors
FROM bid_decisions;

-- J metric before/after comparison
SELECT 
    county_slug,
    (public.pencil_dod_evaluate_county(county_slug))->>'metric_j' as metric_j,
    (public.pencil_dod_evaluate_county(county_slug))->>'grade_j' as grade_j
FROM (VALUES ('manatee'), ('bay'), ('okeechobee'), ('gadsden'), ('wakulla')) AS t(county_slug);

-- Shapira V14 model availability check
SELECT 
    COUNT(*) as shapira_models,
    MAX(created_at) as latest_model
FROM shapira_models 
WHERE version = 'V14';
```

### B Reconciliation Verification
**Implementation**: scripts/shard11_b_reconciliation.py

```sql
-- B anomaly diagnosis - verified_outcomes vs closed_sold
SELECT 
    county_slug,
    (public.pencil_dod_evaluate_county(county_slug))->>'metric_b' as metric_b,
    (public.pencil_dod_evaluate_county(county_slug))->>'grade_b' as grade_b
FROM (VALUES ('manatee'), ('bay'), ('okeechobee'), ('gadsden'), ('wakulla')) AS t(county_slug);

-- Check for verified_outcomes > closed_sold anomaly
SELECT 
    county_slug,
    verified_outcomes,
    closed_sold,
    CASE 
        WHEN closed_sold > 0 THEN ROUND(100.0 * verified_outcomes / closed_sold, 1)
        ELSE NULL 
    END as verification_percentage
FROM gold_standard_county_status
WHERE county IN ('manatee', 'bay', 'okeechobee', 'gadsden', 'wakulla');
```

### G Hit List Analysis
**Implementation**: scripts/shard11_g_hitlist.py

```sql
-- G metric status and zoning completion
SELECT 
    county_slug,
    (public.pencil_dod_evaluate_county(county_slug))->>'metric_g' as metric_g,
    (public.pencil_dod_evaluate_county(county_slug))->>'grade_g' as grade_g
FROM (VALUES ('manatee'), ('bay'), ('okeechobee'), ('gadsden'), ('wakulla')) AS t(county_slug);

-- Zone standards completeness for target counties
SELECT 
    j.county,
    j.name as jurisdiction,
    COUNT(zs.*) as zone_standards_count,
    COUNT(zs.max_density_du_acre) as density_values,
    COUNT(zs.max_far) as far_values,
    COUNT(zs.parking_per_1000sf) as parking_values
FROM jurisdictions j
LEFT JOIN zoning_districts zd ON zd.jurisdiction_id = j.id
LEFT JOIN zone_standards zs ON zs.zoning_district_id = zd.id  
WHERE j.county IN ('manatee', 'bay', 'okeechobee', 'gadsden', 'wakulla')
GROUP BY j.county, j.name
ORDER BY j.county, j.name;
```

### Final Verification Protocol

```sql
-- COMPLETE county status after all fixes
SELECT 
    county_slug,
    public.pencil_dod_evaluate_county(county_slug) as full_evaluation
FROM (VALUES ('manatee'), ('bay'), ('okeechobee'), ('gadsden'), ('wakulla')) AS t(county_slug);

-- Gold standard scoreboard update
SELECT public.gold_standard_loop();

-- Certification check
SELECT public.gold_standard_certify();

-- ULTRALOOP audit evidence
SELECT 
    county_slug,
    COUNT(*) as ultraloop_audit_rows
FROM gold_standard_ultraloop_audit
WHERE county_slug IN ('manatee', 'bay', 'okeechobee', 'gadsden', 'wakulla')
    AND created_at > CURRENT_TIMESTAMP - INTERVAL '7 days'
    AND survived = true
GROUP BY county_slug;
```

## Evidence Requirements

Per SHIP GATE protocol and Honesty Protocol:

1. **Execute, not just commit**: All scripts must be run against live Supabase
2. **SQL proof required**: Every completion must include verification query output
3. **ULTRALOOP survival**: Claims must survive adversarial verification 
4. **No SHIPPED without**:
   - GHA run conclusion = success
   - Live DB query returns expected result
   - SQL VERIFICATION block in issue comment
   - Sentinel green OR disproved with evidence

## Implementation Status

- ✅ **Framework Ready**: All SHARD-11 priority scripts exist and verified
- ✅ **Database Connectivity**: Supabase connection patterns confirmed  
- ✅ **ULTRALOOP Protocol**: Adversarial verification framework prepared
- ✅ **Verification Queries**: SQL evidence protocol documented
- 🔄 **Pending Execution**: Scripts ready for live database execution

## Next Phase: Live Execution

Execute via master coordinator:
```bash
python scripts/shard11_master_coordinator.py
```

This will run all priority scripts in Brevard Sprint Order with ULTRALOOP verification.