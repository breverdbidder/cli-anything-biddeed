# ULTRALOOP Brevard Letter J Verifier Workflow

**Mission:** Verify J=0.0% → ≥95% generation claims survive adversarial attack  
**County:** brevard  
**Letter:** J (Shapira Deal Thesis ≥95% of auctions)  
**Current Status:** J=0.0% (complete failure, generation claimed)

## Verification Protocol

### Letter J Definition (Critical - ⭐)
**Shapira Deal Thesis:** bid_decisions row carrying FULL thesis:
- **Distress Triangle:** distress_location + distress_property + distress_owner
- **Two-Arm CMA:** cma_distressed (entry basis) + cma_resale (ARV)  
- **ML Score:** Shapira ml_score
- **Max Bid:** Investment recommendation

**The Product:** equity = resale ARV − max_bid − repairs (spread between arms IS the product)

### SQL Attack Vectors

#### Attack 1: Baseline Verification (J=0.0% Confirmed)
```sql
-- ATTACK: Confirm starting baseline is truly 0.0%
SELECT 
    'brevard' as county,
    COUNT(*) as total_auctions,
    COUNT(bd.id) as with_bid_decisions,
    ROUND(100.0 * COUNT(bd.id) / NULLIF(COUNT(*), 0), 2) as j_percentage,
    CASE 
        WHEN ROUND(100.0 * COUNT(bd.id) / NULLIF(COUNT(*), 0), 2) = 0.0 
        THEN 'BASELINE_CONFIRMED'
        ELSE 'BASELINE_DISPUTED'
    END as baseline_status
FROM multi_county_auctions mca
LEFT JOIN bid_decisions bd ON mca.id = bd.auction_id
WHERE mca.county_slug = 'brevard'
  AND mca.auction_date >= CURRENT_DATE - INTERVAL '30 days';
```

#### Attack 2: Completeness Attack - Full Thesis Required
```sql
-- ATTACK: Are "generated" thesis rows actually complete per definition?
SELECT 
    bd.auction_id,
    mca.case_number,
    -- Distress Triangle completeness
    CASE WHEN bd.distress_location IS NOT NULL THEN 1 ELSE 0 END +
    CASE WHEN bd.distress_property IS NOT NULL THEN 1 ELSE 0 END +
    CASE WHEN bd.distress_owner IS NOT NULL THEN 1 ELSE 0 END as distress_triangle_completeness,
    
    -- Two-Arm CMA completeness  
    CASE WHEN bd.cma_distressed IS NOT NULL AND bd.cma_distressed > 0 THEN 1 ELSE 0 END as arm1_complete,
    CASE WHEN bd.cma_resale IS NOT NULL AND bd.cma_resale > 0 THEN 1 ELSE 0 END as arm2_complete,
    
    -- ML Score and Max Bid
    CASE WHEN bd.ml_score IS NOT NULL THEN 1 ELSE 0 END as ml_score_present,
    CASE WHEN bd.max_bid IS NOT NULL AND bd.max_bid > 0 THEN 1 ELSE 0 END as max_bid_present,
    
    -- Overall completeness (must be 7/7 for true thesis)
    (CASE WHEN bd.distress_location IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN bd.distress_property IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN bd.distress_owner IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN bd.cma_distressed IS NOT NULL AND bd.cma_distressed > 0 THEN 1 ELSE 0 END +
     CASE WHEN bd.cma_resale IS NOT NULL AND bd.cma_resale > 0 THEN 1 ELSE 0 END +
     CASE WHEN bd.ml_score IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN bd.max_bid IS NOT NULL AND bd.max_bid > 0 THEN 1 ELSE 0 END) as total_completeness_score
FROM bid_decisions bd
JOIN multi_county_auctions mca ON bd.auction_id = mca.id
WHERE mca.county_slug = 'brevard'
ORDER BY bd.created_at DESC
LIMIT 20;
```

#### Attack 3: CMA Two-Arm Validation
```sql
-- ATTACK: Are both CMA arms present and logical?
SELECT 
    bd.auction_id,
    mca.case_number,
    bd.cma_distressed as arm1_distressed_entry,
    bd.cma_resale as arm2_resale_arv,
    bd.max_bid,
    -- The spread between arms IS the product
    (bd.cma_resale - bd.cma_distressed) as cma_spread,
    -- Equity calculation per definition
    (bd.cma_resale - bd.max_bid - COALESCE(bd.repair_estimate, 0)) as calculated_equity,
    CASE 
        WHEN bd.cma_distressed IS NULL OR bd.cma_resale IS NULL 
        THEN 'INCOMPLETE_CMA'
        WHEN bd.cma_distressed >= bd.cma_resale 
        THEN 'ILLOGICAL_CMA_DISTRESSED_ABOVE_RESALE'
        WHEN bd.max_bid > bd.cma_resale 
        THEN 'ILLOGICAL_MAXBID_ABOVE_ARV'
        ELSE 'CMA_LOGICAL'
    END as cma_validation_status
FROM bid_decisions bd
JOIN multi_county_auctions mca ON bd.auction_id = mca.id
WHERE mca.county_slug = 'brevard'
  AND bd.cma_distressed IS NOT NULL
  AND bd.cma_resale IS NOT NULL
ORDER BY bd.created_at DESC;
```

#### Attack 4: ML Score Pipeline Verification
```sql
-- ATTACK: Are ML scores actually computed vs placeholder values?
SELECT 
    COUNT(*) as total_with_scores,
    COUNT(DISTINCT bd.ml_score) as unique_scores,
    MIN(bd.ml_score) as min_score,
    MAX(bd.ml_score) as max_score,
    AVG(bd.ml_score) as avg_score,
    STDDEV(bd.ml_score) as score_stddev,
    -- Attack: Check for placeholder/default values
    COUNT(CASE WHEN bd.ml_score = 0 THEN 1 END) as zero_scores,
    COUNT(CASE WHEN bd.ml_score = 0.5 THEN 1 END) as placeholder_scores,
    COUNT(CASE WHEN bd.ml_score IS NULL THEN 1 END) as null_scores,
    CASE 
        WHEN STDDEV(bd.ml_score) < 0.01 THEN 'SUSPICIOUSLY_UNIFORM'
        WHEN COUNT(CASE WHEN bd.ml_score = 0 THEN 1 END) > COUNT(*) * 0.5 THEN 'TOO_MANY_ZEROS'
        ELSE 'SCORES_APPEAR_COMPUTED'
    END as ml_pipeline_status
FROM bid_decisions bd
JOIN multi_county_auctions mca ON bd.auction_id = mca.id
WHERE mca.county_slug = 'brevard'
  AND bd.ml_score IS NOT NULL;
```

#### Attack 5: Generation Performance Claims
```sql
-- ATTACK: What percentage of auctions actually have complete thesis?
WITH brevard_auctions AS (
    SELECT mca.id, mca.case_number, mca.auction_date
    FROM multi_county_auctions mca
    WHERE mca.county_slug = 'brevard'
      AND mca.auction_date >= CURRENT_DATE - INTERVAL '30 days'
), complete_thesis AS (
    SELECT 
        ba.id,
        ba.case_number,
        bd.id as thesis_id,
        -- Full thesis validation per Letter J definition
        CASE WHEN 
            bd.distress_location IS NOT NULL AND
            bd.distress_property IS NOT NULL AND
            bd.distress_owner IS NOT NULL AND
            bd.cma_distressed IS NOT NULL AND bd.cma_distressed > 0 AND
            bd.cma_resale IS NOT NULL AND bd.cma_resale > 0 AND
            bd.cma_resale > bd.cma_distressed AND  -- Logical constraint
            bd.ml_score IS NOT NULL AND
            bd.max_bid IS NOT NULL AND bd.max_bid > 0
        THEN 1 ELSE 0 END as has_complete_thesis
    FROM brevard_auctions ba
    LEFT JOIN bid_decisions bd ON ba.id = bd.auction_id
)
SELECT 
    COUNT(*) as total_auctions,
    COUNT(CASE WHEN thesis_id IS NOT NULL THEN 1 END) as with_any_thesis,
    COUNT(CASE WHEN has_complete_thesis = 1 THEN 1 END) as with_complete_thesis,
    ROUND(100.0 * COUNT(CASE WHEN thesis_id IS NOT NULL THEN 1 END) 
          / NULLIF(COUNT(*), 0), 2) as any_thesis_percentage,
    ROUND(100.0 * COUNT(CASE WHEN has_complete_thesis = 1 THEN 1 END) 
          / NULLIF(COUNT(*), 0), 2) as complete_thesis_percentage,
    CASE 
        WHEN ROUND(100.0 * COUNT(CASE WHEN has_complete_thesis = 1 THEN 1 END) 
             / NULLIF(COUNT(*), 0), 2) >= 95.0 
        THEN 'GOLD_STANDARD_ACHIEVED'
        WHEN ROUND(100.0 * COUNT(CASE WHEN has_complete_thesis = 1 THEN 1 END) 
             / NULLIF(COUNT(*), 0), 2) > 0
        THEN 'PARTIAL_GENERATION'
        ELSE 'GENERATION_FAILED'
    END as letter_j_status
FROM complete_thesis;
```

#### Attack 6: Temporal Consistency
```sql
-- ATTACK: Was generation sudden (suspicious) or gradual (credible)?
SELECT 
    DATE(bd.created_at) as generation_date,
    COUNT(*) as daily_thesis_generated,
    COUNT(CASE WHEN bd.distress_location IS NOT NULL AND bd.distress_property IS NOT NULL 
               AND bd.distress_owner IS NOT NULL THEN 1 END) as with_complete_triangle,
    COUNT(CASE WHEN bd.cma_distressed > 0 AND bd.cma_resale > 0 
               AND bd.cma_resale > bd.cma_distressed THEN 1 END) as with_logical_cma,
    ROUND(AVG(bd.ml_score), 3) as avg_ml_score
FROM bid_decisions bd
JOIN multi_county_auctions mca ON bd.auction_id = mca.id
WHERE mca.county_slug = 'brevard'
  AND bd.created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(bd.created_at)
ORDER BY generation_date DESC;
```

## Refutation Strategy

### Critical Attack Vectors for J Generation Claims

1. **Incomplete Thesis Attack:** Count partial rows as complete
2. **Placeholder Values:** ML scores are defaults, not computed
3. **Illogical CMA:** Distressed entry > resale ARV (impossible)
4. **Missing Components:** Distress triangle incomplete
5. **Bulk Insert Artifacts:** Suspicious temporal generation pattern

### Survival Criteria

```yaml
j_generation_survival:
  minimum_threshold: "≥95% of auctions with COMPLETE thesis"
  definition_compliance: "All 7 components present and logical"
  
  components_required:
    distress_triangle: [distress_location, distress_property, distress_owner]
    two_arm_cma: [cma_distressed > 0, cma_resale > cma_distressed]
    ml_pipeline: [ml_score IS NOT NULL, not placeholder value]
    investment_rec: [max_bid > 0, max_bid < cma_resale]
  
  logical_constraints:
    cma_order: "cma_distressed < cma_resale (distressed entry < retail ARV)"
    max_bid_sensible: "max_bid < cma_resale (can't bid above ARV)"
    equity_positive: "cma_resale - max_bid - repairs > 0"
```

### Expected Outcomes

#### Scenario 1: Generation Claims Refuted
```sql
INSERT INTO gold_standard_ultraloop_audit (
    dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived
) VALUES (
    $dispatch_id, 'native', 'brevard', 'J',
    'J letter generated from 0.0% to X% via thesis pipeline',
    jsonb_build_object(
        'attack_type', 'incomplete_thesis',
        'evidence', 'Generated rows missing required components per Letter J definition',
        'incomplete_count', '[number of incomplete thesis rows]',
        'total_claimed', '[total claimed as generated]',
        'actual_complete_percentage', '[real percentage with full 7-component thesis]',
        'refutation_strength', 'STRONG'
    ),
    false
);
```

#### Scenario 2: Generation Verified and Survives
```sql
INSERT INTO gold_standard_ultraloop_audit (
    dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived
) VALUES (
    $dispatch_id, 'native', 'brevard', 'J',
    'J letter generated from 0.0% to X% via complete thesis pipeline',
    jsonb_build_object(
        'verification_queries', 6,
        'complete_thesis_confirmed', '[SQL evidence of 7-component completeness]',
        'logical_constraints_verified', true,
        'ml_pipeline_validated', '[evidence scores are computed not placeholder]',
        'generation_timeline', '[credible temporal pattern]',
        'final_percentage', '[X%]'
    ),
    true
);
```

## Integration with Brevard Sprint

### Phase 2 Execution (J GENERATOR)
- Runs after C/D ROOT CAUSE completion
- Must verify thesis generation pipeline functionality  
- Critical gate for Letter J certification
- Failure blocks gold standard achievement

### Success Definition
J generation succeeds if ≥95% of recent auctions carry complete 7-component thesis AND all attacks fail to refute the claim.