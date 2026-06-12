# ULTRALOOP Duval Letter B Refuter Workflow

**Mission:** Break B=110.2% anomaly claim with mathematical evidence  
**Status:** ANOMALY AUTO-FAIL (ratio >100% impossible)  
**County:** duval  
**Letter:** B (Verified Realized Outcomes ≥95% of closed)  

## Refuter Analysis

### Current Anomaly Status
- **Metric:** B = 110.2%  
- **Definition:** Share of closed auctions with realized outcome from INDEPENDENT source
- **Mathematical Impossibility:** Cannot have 110.2% of anything - indicates denominator error or double-counting

### SQL Attack Vectors

#### Attack 1: Denominator Verification
```sql
-- ATTACK: What denominator produces 110.2%?
SELECT 
    'duval' as county,
    COUNT(*) as total_closed_auctions,
    COUNT(CASE WHEN verified_outcome_source IS NOT NULL 
               AND verified_outcome_source != 'derived' 
               AND verified_outcome_source != 'propertyonion' THEN 1 END) as independent_verified,
    COUNT(CASE WHEN verified_outcome_source IS NOT NULL THEN 1 END) as any_verified,
    ROUND(100.0 * COUNT(CASE WHEN verified_outcome_source IS NOT NULL 
                              AND verified_outcome_source != 'derived' 
                              AND verified_outcome_source != 'propertyonion' THEN 1 END) 
          / NULLIF(COUNT(*), 0), 2) as calculated_percentage
FROM multi_county_auctions 
WHERE county_slug = 'duval' 
  AND auction_status = 'closed'
  AND created_at >= '2026-01-01';
```

#### Attack 2: Double-Counting Detection
```sql
-- ATTACK: Are auctions counted multiple times?
SELECT 
    case_number,
    COUNT(*) as duplicate_rows,
    array_agg(DISTINCT verified_outcome_source) as outcome_sources,
    array_agg(DISTINCT id) as auction_ids
FROM multi_county_auctions 
WHERE county_slug = 'duval' 
  AND auction_status = 'closed'
  AND verified_outcome_source IS NOT NULL
GROUP BY case_number
HAVING COUNT(*) > 1
ORDER BY duplicate_rows DESC
LIMIT 10;
```

#### Attack 3: Source Independence Verification  
```sql
-- ATTACK: Are "independent" sources actually independent?
SELECT 
    verified_outcome_source,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) as percentage_of_verified,
    array_agg(case_number ORDER BY created_at DESC LIMIT 5) as sample_cases
FROM multi_county_auctions
WHERE county_slug = 'duval'
  AND auction_status = 'closed' 
  AND verified_outcome_source IS NOT NULL
GROUP BY verified_outcome_source
ORDER BY count DESC;
```

#### Attack 4: Temporal Analysis
```sql
-- ATTACK: When did this anomaly emerge? 
SELECT 
    DATE(created_at) as date_created,
    COUNT(*) as closed_auctions,
    COUNT(CASE WHEN verified_outcome_source IS NOT NULL 
               AND verified_outcome_source NOT IN ('derived', 'propertyonion') 
               THEN 1 END) as independent_verified,
    ROUND(100.0 * COUNT(CASE WHEN verified_outcome_source IS NOT NULL 
                              AND verified_outcome_source NOT IN ('derived', 'propertyonion') 
                              THEN 1 END) 
          / NULLIF(COUNT(*), 0), 2) as daily_percentage
FROM multi_county_auctions
WHERE county_slug = 'duval'
  AND auction_status = 'closed'
  AND created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date_created DESC;
```

#### Attack 5: Calculation Logic Audit
```sql
-- ATTACK: Reproduce the 110.2% calculation exactly
WITH duval_closed AS (
    SELECT 
        id, 
        case_number, 
        verified_outcome_source, 
        created_at,
        auction_date
    FROM multi_county_auctions
    WHERE county_slug = 'duval'
      AND auction_status = 'closed'
), calculation_breakdown AS (
    SELECT 
        COUNT(*) as total_closed,
        COUNT(CASE WHEN verified_outcome_source IS NOT NULL THEN 1 END) as any_outcome,
        COUNT(CASE WHEN verified_outcome_source IS NOT NULL 
                   AND verified_outcome_source NOT IN ('derived', 'propertyonion', 'inferred')
                   THEN 1 END) as independent_outcome,
        COUNT(CASE WHEN verified_outcome_source = 'derived' THEN 1 END) as derived_count,
        COUNT(CASE WHEN verified_outcome_source = 'propertyonion' THEN 1 END) as po_count
    FROM duval_closed
)
SELECT 
    total_closed,
    independent_outcome as numerator,
    CASE 
        WHEN total_closed > 0 
        THEN ROUND(100.0 * independent_outcome / total_closed, 2)
        ELSE NULL 
    END as calculated_percentage,
    '110.2%' as reported_percentage,
    CASE 
        WHEN ROUND(100.0 * independent_outcome / total_closed, 2) > 100 
        THEN 'MATHEMATICAL_IMPOSSIBILITY_CONFIRMED'
        ELSE 'WITHIN_BOUNDS'
    END as anomaly_status
FROM calculation_breakdown;
```

## Refutation Evidence Collection

### Expected Refutation Outcomes
1. **Mathematical Impossibility Confirmed:** Any ratio >100% is definitionally impossible
2. **Denominator Error:** Counting wrong subset of closed auctions
3. **Double-Counting:** Same auction appearing in multiple rows
4. **Source Contamination:** PropertyOnion/derived data counted as "independent"
5. **Temporal Artifacts:** Recent bulk import affecting calculation

### Survival Criteria
**This anomaly CANNOT survive** - ratios >100% auto-fail per ULTRALOOP protocol.

```yaml
survival_vote: AUTO_FAIL
rationale: "Mathematical impossibility - cannot have 110.2% of any finite set"
evidence_required: "SQL proof of calculation error or data contamination"
certification_block: true
```

### Audit Table Insert
```sql
INSERT INTO gold_standard_ultraloop_audit (
    dispatch_id, 
    ultraloop_mode,
    county_slug, 
    letter, 
    claim, 
    refuter_evidence, 
    survived
) VALUES (
    $dispatch_id,
    'native',
    'duval',
    'B',
    'B letter metric improvement to acceptable range',
    jsonb_build_object(
        'attack_vectors', ARRAY['denominator_error', 'double_counting', 'source_contamination', 'temporal_artifacts'],
        'sql_queries_executed', 5,
        'mathematical_impossibility', true,
        'ratio_reported', 110.2,
        'auto_fail_reason', 'Percentage >100% definitionally impossible',
        'refutation_timestamp', NOW(),
        'county_specific_notes', 'Duval may have bulk import artifacts affecting denominators'
    ),
    false  -- AUTO-FAIL: survived = false
);
```

## Duval-Specific Considerations

### Data Source Peculiarities
- Duval uses consolidated city-county (Jacksonville) which may affect record-keeping patterns
- Multiple GIS sources (maps.coj.net, jaxepics.coj.net) could create cross-contamination
- Large parcel count (~350K) may amplify calculation errors

### Integration with Duval Sprint Flow
This refuter executes during Phase 4 of Duval sprint (B reconciliation). The anomaly auto-fail means:
1. G/I null fixes in Phase 1 proceed normally  
2. C/D improvements in Phase 2 proceed normally
3. J generation in Phase 3 proceeds normally  
4. **B refutation in Phase 4 auto-fails the anomaly**

**Gate Impact:** Duval Letter B cannot be certified until the underlying calculation is fixed and metric reports ≤100%.