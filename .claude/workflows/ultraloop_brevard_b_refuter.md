# ULTRALOOP Brevard Letter B Refuter Workflow

**Mission:** Break B=134.1% anomaly claim with mathematical evidence  
**Status:** ANOMALY AUTO-FAIL (ratio >100% impossible)  
**County:** brevard  
**Letter:** B (Verified Realized Outcomes ≥95% of closed)  

## Refuter Analysis

### Current Anomaly Status
- **Metric:** B = 134.1%  
- **Definition:** Share of closed auctions with realized outcome from INDEPENDENT source
- **Mathematical Impossibility:** Cannot have 134.1% of anything - indicates denominator error or double-counting

### SQL Attack Vectors

#### Attack 1: Denominator Verification
```sql
-- ATTACK: What denominator produces 134.1%?
SELECT 
    'brevard' as county,
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
WHERE county_slug = 'brevard' 
  AND auction_status = 'closed'
  AND created_at >= '2026-01-01';
```

#### Attack 2: Double-Counting Detection
```sql
-- ATTACK: Are auctions counted multiple times?
SELECT 
    auction_id,
    COUNT(*) as count_occurrences,
    array_agg(DISTINCT verified_outcome_source) as outcome_sources
FROM multi_county_auctions 
WHERE county_slug = 'brevard' 
  AND auction_status = 'closed'
  AND verified_outcome_source IS NOT NULL
GROUP BY auction_id
HAVING COUNT(*) > 1
ORDER BY count_occurrences DESC
LIMIT 10;
```

#### Attack 3: Source Independence Verification  
```sql
-- ATTACK: Are "independent" sources actually independent?
SELECT 
    verified_outcome_source,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) as percentage
FROM multi_county_auctions
WHERE county_slug = 'brevard'
  AND auction_status = 'closed' 
  AND verified_outcome_source IS NOT NULL
GROUP BY verified_outcome_source
ORDER BY count DESC;
```

#### Attack 4: Calculation Logic Audit
```sql
-- ATTACK: Reproduce the 134.1% calculation step by step
WITH closed_auctions AS (
    SELECT id, case_number, verified_outcome_source, created_at
    FROM multi_county_auctions
    WHERE county_slug = 'brevard'
      AND auction_status = 'closed'
), independent_verified AS (
    SELECT COUNT(*) as numerator
    FROM closed_auctions
    WHERE verified_outcome_source IS NOT NULL
      AND verified_outcome_source NOT IN ('derived', 'propertyonion', 'inferred')
), total_closed AS (
    SELECT COUNT(*) as denominator  
    FROM closed_auctions
)
SELECT 
    i.numerator,
    t.denominator,
    CASE 
        WHEN t.denominator > 0 
        THEN ROUND(100.0 * i.numerator / t.denominator, 2)
        ELSE NULL 
    END as calculated_percentage,
    '134.1%' as reported_percentage,
    CASE 
        WHEN ROUND(100.0 * i.numerator / t.denominator, 2) = 134.1 THEN 'MATCHES'
        ELSE 'DOES_NOT_MATCH'
    END as verification_status
FROM independent_verified i, total_closed t;
```

## Refutation Evidence Collection

### Expected Refutation Outcomes
1. **Mathematical Impossibility Confirmed:** Any ratio >100% is definitionally impossible
2. **Denominator Error:** Wrong universe of auctions being counted  
3. **Double-Counting:** Same auction counted multiple times
4. **Source Contamination:** "Independent" sources include derived/PropertyOnion data
5. **Calculation Bug:** Logic error in percentage computation

### Survival Criteria
**This anomaly CANNOT survive** - ratios >100% auto-fail per ULTRALOOP protocol.

```yaml
survival_vote: AUTO_FAIL
rationale: "Mathematical impossibility - cannot have 134.1% of any finite set"
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
    'brevard',
    'B',
    'B letter metric improvement to acceptable range',
    jsonb_build_object(
        'attack_vectors', ARRAY['denominator_error', 'double_counting', 'source_contamination'],
        'sql_queries_executed', 4,
        'mathematical_impossibility', true,
        'ratio_reported', 134.1,
        'auto_fail_reason', 'Percentage >100% definitionally impossible',
        'refutation_timestamp', NOW()
    ),
    false  -- AUTO-FAIL: survived = false
);
```

## Integration with Session Flow

This refuter workflow will be executed during Phase 4 of the Brevard sprint (B reconciliation phase). However, the anomaly auto-fail means this letter should fail certification regardless of any "improvement" claims unless the metric is brought to ≤100%.

**Gate Impact:** Any certification attempt for Brevard Letter B will fail unless the underlying calculation error is fixed and the metric reports ≤100%.