# ULTRALOOP Brevard C/D Letters Verifier Workflow

**Mission:** Verify C/D parity improvements survive adversarial attack  
**Counties:** brevard  
**Letters:** C (Parity Clean ≥95%), D (Parity Any ≥95%)  
**Current Metrics:** C=20.8%, D=33.2% (both failing, improvement claimed)

## Verification Protocol

### Letter Definitions
- **C (Parity Clean):** Auctions matched clean (zero field divergence) against PropertyOnion litmus ≥95%
- **D (Parity Any):** Auctions locatable in litmus source (clean or divergent match) ≥95%
- **Relationship:** D ≥ C (you can't have more clean matches than total matches)

### SQL Attack Vectors

#### Attack 1: Denominator Universe Verification
```sql
-- ATTACK: Are we measuring against the right auction universe?
SELECT 
    'brevard' as county,
    COUNT(*) as total_auctions_all_time,
    COUNT(CASE WHEN auction_date >= CURRENT_DATE - INTERVAL '90 days' THEN 1 END) as recent_90_days,
    COUNT(CASE WHEN auction_date >= CURRENT_DATE - INTERVAL '30 days' THEN 1 END) as recent_30_days,
    COUNT(CASE WHEN parity_status IS NOT NULL THEN 1 END) as with_parity_status,
    ROUND(100.0 * COUNT(CASE WHEN parity_status IS NOT NULL THEN 1 END) 
          / NULLIF(COUNT(*), 0), 2) as parity_coverage_percentage
FROM multi_county_auctions
WHERE county_slug = 'brevard';
```

#### Attack 2: Parity Status Field Analysis
```sql
-- ATTACK: What are the actual parity status distributions?
SELECT 
    parity_status,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) as percentage_of_total,
    MIN(auction_date) as earliest_auction,
    MAX(auction_date) as latest_auction
FROM multi_county_auctions
WHERE county_slug = 'brevard'
  AND parity_status IS NOT NULL
GROUP BY parity_status
ORDER BY count DESC;
```

#### Attack 3: C Letter Calculation Verification  
```sql
-- ATTACK: Reproduce Letter C calculation independently
WITH recent_auctions AS (
    SELECT 
        id, 
        case_number, 
        parity_status, 
        auction_date,
        created_at
    FROM multi_county_auctions
    WHERE county_slug = 'brevard'
      AND auction_date >= CURRENT_DATE - INTERVAL '90 days'  -- Standard lookback
), parity_breakdown AS (
    SELECT 
        COUNT(*) as total_auctions,
        COUNT(CASE WHEN parity_status = 'clean' THEN 1 END) as clean_matches,
        COUNT(CASE WHEN parity_status IN ('clean', 'divergent') THEN 1 END) as any_matches,
        COUNT(CASE WHEN parity_status IS NULL THEN 1 END) as no_parity_data
    FROM recent_auctions
)
SELECT 
    total_auctions,
    clean_matches,
    any_matches,
    no_parity_data,
    ROUND(100.0 * clean_matches / NULLIF(total_auctions, 0), 2) as letter_c_percentage,
    ROUND(100.0 * any_matches / NULLIF(total_auctions, 0), 2) as letter_d_percentage,
    CASE 
        WHEN ROUND(100.0 * clean_matches / NULLIF(total_auctions, 0), 2) = 20.8 THEN 'MATCHES_REPORTED_C'
        ELSE 'DOES_NOT_MATCH_C'
    END as c_verification,
    CASE 
        WHEN ROUND(100.0 * any_matches / NULLIF(total_auctions, 0), 2) = 33.2 THEN 'MATCHES_REPORTED_D'
        ELSE 'DOES_NOT_MATCH_D'
    END as d_verification
FROM parity_breakdown;
```

#### Attack 4: PropertyOnion Litmus Independence
```sql
-- ATTACK: Is the litmus source truly independent?
SELECT 
    data_source,
    COUNT(*) as count,
    COUNT(CASE WHEN parity_status = 'clean' THEN 1 END) as clean_count,
    COUNT(CASE WHEN parity_status = 'divergent' THEN 1 END) as divergent_count,
    ROUND(100.0 * COUNT(CASE WHEN parity_status = 'clean' THEN 1 END) 
          / NULLIF(COUNT(*), 0), 2) as clean_percentage
FROM multi_county_auctions
WHERE county_slug = 'brevard'
  AND parity_status IS NOT NULL
GROUP BY data_source
ORDER BY count DESC;
```

#### Attack 5: Temporal Improvement Claims
```sql
-- ATTACK: Are claimed improvements real or measurement artifacts?
WITH daily_parity AS (
    SELECT 
        DATE(created_at) as measurement_date,
        COUNT(*) as daily_auctions,
        COUNT(CASE WHEN parity_status = 'clean' THEN 1 END) as daily_clean,
        COUNT(CASE WHEN parity_status IN ('clean', 'divergent') THEN 1 END) as daily_any,
        ROUND(100.0 * COUNT(CASE WHEN parity_status = 'clean' THEN 1 END) 
              / NULLIF(COUNT(*), 0), 2) as daily_c_percentage,
        ROUND(100.0 * COUNT(CASE WHEN parity_status IN ('clean', 'divergent') THEN 1 END) 
              / NULLIF(COUNT(*), 0), 2) as daily_d_percentage
    FROM multi_county_auctions
    WHERE county_slug = 'brevard'
      AND created_at >= CURRENT_DATE - INTERVAL '14 days'
      AND parity_status IS NOT NULL
    GROUP BY DATE(created_at)
)
SELECT 
    measurement_date,
    daily_auctions,
    daily_c_percentage,
    daily_d_percentage,
    LAG(daily_c_percentage) OVER (ORDER BY measurement_date) as prev_c_percentage,
    LAG(daily_d_percentage) OVER (ORDER BY measurement_date) as prev_d_percentage,
    daily_c_percentage - LAG(daily_c_percentage) OVER (ORDER BY measurement_date) as c_delta,
    daily_d_percentage - LAG(daily_d_percentage) OVER (ORDER BY measurement_date) as d_delta
FROM daily_parity
ORDER BY measurement_date DESC
LIMIT 10;
```

#### Attack 6: Cross-Validation Against Known Failures
```sql
-- ATTACK: Spot-check parity claims against courthouse calendar
SELECT 
    mca.case_number,
    mca.auction_date,
    mca.parity_status,
    mca.opening_bid,
    mca.data_source,
    -- Could join against brevard courthouse calendar if available
    CASE 
        WHEN mca.parity_status = 'clean' THEN 'CLAIMED_CLEAN'
        WHEN mca.parity_status = 'divergent' THEN 'ACKNOWLEDGED_DIVERGENT'
        ELSE 'NO_PARITY_STATUS'
    END as parity_claim
FROM multi_county_auctions mca
WHERE mca.county_slug = 'brevard'
  AND mca.auction_date >= CURRENT_DATE - INTERVAL '7 days'
  AND mca.parity_status IS NOT NULL
ORDER BY mca.auction_date DESC, mca.case_number
LIMIT 20;
```

## Refutation Strategy

### Refuter Mission
Attack claimed C/D improvements with focus on:
1. **Denominator manipulation:** Wrong auction universe counted
2. **Stale cache:** PropertyOnion litmus source not current  
3. **Circular logic:** Measuring our own parity assignments as "independent verification"
4. **Ghost matches:** Our system claims match but PropertyOnion doesn't have it
5. **Temporal artifacts:** Recent bulk updates affecting calculation baseline

### Survival Criteria for C/D Claims

```yaml
claim_survival_requirements:
  letter_c_improvement:
    evidence_needed: "SQL proof C percentage increased from 20.8% baseline"
    attack_resistance: "Must survive denominator, cache staleness, and circular logic attacks"
    minimum_threshold: "≥95% for gold standard certification"
    
  letter_d_improvement:
    evidence_needed: "SQL proof D percentage increased from 33.2% baseline"  
    attack_resistance: "Must survive ghost match and temporal artifact attacks"
    minimum_threshold: "≥95% for gold standard certification"
    
  relationship_consistency:
    logical_constraint: "D percentage ≥ C percentage (can't have more clean than total matches)"
    attack_vector: "If D < C, both claims invalid"
```

### Expected Refutation Outcomes

#### Scenario 1: Denominator Attack Success
```sql
-- Evidence: Wrong auction universe
INSERT INTO gold_standard_ultraloop_audit (
    dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived
) VALUES (
    $dispatch_id, 'native', 'brevard', 'C',
    'C letter improved from 20.8% via parity cleanup',
    jsonb_build_object(
        'attack_type', 'denominator_universe',
        'evidence', 'Measuring against all-time auctions instead of recent 90-day window',
        'sql_proof', '[SQL query results showing universe mismatch]',
        'refutation_strength', 'STRONG'
    ),
    false
);
```

#### Scenario 2: Claims Survive Attacks
```sql
-- Evidence: Improvements verified and attacks failed
INSERT INTO gold_standard_ultraloop_audit (
    dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived
) VALUES (
    $dispatch_id, 'native', 'brevard', 'C',
    'C letter improved from 20.8% to X% via parity cleanup',
    jsonb_build_object(
        'attack_attempts', ARRAY['denominator_universe', 'stale_cache', 'circular_logic'],
        'attacks_failed', true,
        'independent_verification', '[SQL evidence showing real improvement]',
        'improvement_magnitude', '[X - 20.8]%'
    ),
    true
);
```

## Integration Notes

### Phase 1 Execution (Brevard Sprint)
- This verifier runs during C/D ROOT CAUSE phase
- Must complete before J GENERATOR phase begins
- Refutation evidence collected for certification gate
- Failed claims block gold standard certification

### Success Metrics
1. **Independent calculation** reproduces claimed improvements
2. **Attacks fail** to find evidence contradicting claims
3. **Relationship preserved:** D ≥ C throughout improvement process
4. **Threshold achieved:** Both C and D reach ≥95% for gold standard