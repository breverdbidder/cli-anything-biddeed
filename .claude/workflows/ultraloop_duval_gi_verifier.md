# ULTRALOOP Duval G/I Letters Verifier Workflow

**Mission:** Verify G/I null→value fixes survive adversarial attack  
**County:** duval  
**Letters:** G (Zoning Gold Standard ≥95%), I (Property Card Render-Complete ≥95%)  
**Current Status:** G=null, I=null (both completely missing, fix claimed)

## Verification Protocol

### Letter Definitions
- **G (Zoning Gold Standard):** Minimum of density/FAR/parking-per-1000 coverage ≥95% of applicable parcels  
- **I (Property Card Render-Complete ⭐):** Address + geo + value + zoning code ≥95% of cards
- **Null Status:** Complete absence of data/functionality (worse than 0%)

### SQL Attack Vectors

#### Attack 1: Null Status Baseline Confirmation
```sql
-- ATTACK: Confirm G and I are truly null (not zero, but missing)
WITH duval_baseline AS (
    SELECT 
        mca.id as auction_id,
        mca.case_number,
        mca.parcel_id,
        -- Letter G components
        zd.density_max,
        zs.far_max,
        zs.parking_per_1000,
        CASE WHEN zd.density_max IS NOT NULL OR zs.far_max IS NOT NULL 
             OR zs.parking_per_1000 IS NOT NULL THEN 1 ELSE 0 END as has_any_zoning,
        
        -- Letter I components  
        mca.property_address,
        mca.latitude,
        mca.longitude,
        mca.assessed_value,
        mca.zoning_code,
        CASE WHEN mca.property_address IS NOT NULL AND mca.latitude IS NOT NULL 
             AND mca.longitude IS NOT NULL AND mca.assessed_value IS NOT NULL 
             AND mca.zoning_code IS NOT NULL THEN 1 ELSE 0 END as card_complete
    FROM multi_county_auctions mca
    LEFT JOIN zoning_assignments za ON mca.parcel_id = za.parcel_id
    LEFT JOIN zoning_districts zd ON za.zone_code = zd.code
    LEFT JOIN zone_standards zs ON zd.id = zs.district_id
    WHERE mca.county_slug = 'duval'
      AND mca.auction_date >= CURRENT_DATE - INTERVAL '30 days'
)
SELECT 
    'duval' as county,
    COUNT(*) as total_auctions,
    -- Letter G analysis
    COUNT(CASE WHEN has_any_zoning = 1 THEN 1 END) as with_any_zoning,
    ROUND(100.0 * COUNT(CASE WHEN has_any_zoning = 1 THEN 1 END) 
          / NULLIF(COUNT(*), 0), 2) as g_baseline_percentage,
    
    -- Letter I analysis
    COUNT(CASE WHEN card_complete = 1 THEN 1 END) as complete_cards,
    ROUND(100.0 * COUNT(CASE WHEN card_complete = 1 THEN 1 END) 
          / NULLIF(COUNT(*), 0), 2) as i_baseline_percentage,
    
    -- Null confirmation
    CASE 
        WHEN COUNT(CASE WHEN has_any_zoning = 1 THEN 1 END) = 0 THEN 'G_NULL_CONFIRMED'
        ELSE 'G_NOT_NULL'
    END as g_null_status,
    CASE 
        WHEN COUNT(CASE WHEN card_complete = 1 THEN 1 END) = 0 THEN 'I_NULL_CONFIRMED'  
        ELSE 'I_NOT_NULL'
    END as i_null_status
FROM duval_baseline;
```

#### Attack 2: Zoning Infrastructure Verification (Letter G)
```sql
-- ATTACK: Are zoning fixes real data or cosmetic placeholders?
SELECT 
    -- Infrastructure table counts
    (SELECT COUNT(*) FROM jurisdictions WHERE county = 'Duval') as duval_jurisdictions,
    (SELECT COUNT(*) FROM zoning_districts WHERE jurisdiction_id IN 
        (SELECT id FROM jurisdictions WHERE county = 'Duval')) as duval_zoning_districts,
    (SELECT COUNT(*) FROM zone_standards WHERE district_id IN 
        (SELECT zd.id FROM zoning_districts zd 
         JOIN jurisdictions j ON zd.jurisdiction_id = j.id 
         WHERE j.county = 'Duval')) as duval_zone_standards,
    
    -- Sample actual data quality
    (SELECT COUNT(CASE WHEN density_max IS NOT NULL AND density_max > 0 THEN 1 END)
     FROM zone_standards zs
     JOIN zoning_districts zd ON zs.district_id = zd.id  
     JOIN jurisdictions j ON zd.jurisdiction_id = j.id
     WHERE j.county = 'Duval') as standards_with_density,
    
    (SELECT COUNT(CASE WHEN far_max IS NOT NULL AND far_max > 0 THEN 1 END)
     FROM zone_standards zs
     JOIN zoning_districts zd ON zs.district_id = zd.id
     JOIN jurisdictions j ON zd.jurisdiction_id = j.id  
     WHERE j.county = 'Duval') as standards_with_far,
     
    (SELECT COUNT(CASE WHEN parking_per_1000 IS NOT NULL AND parking_per_1000 > 0 THEN 1 END)
     FROM zone_standards zs
     JOIN zoning_districts zd ON zs.district_id = zd.id
     JOIN jurisdictions j ON zd.jurisdiction_id = j.id
     WHERE j.county = 'Duval') as standards_with_parking;
```

#### Attack 3: Property Card Infrastructure (Letter I)  
```sql
-- ATTACK: Are property card components actually populated?
WITH duval_card_analysis AS (
    SELECT 
        mca.id,
        mca.case_number,
        -- Card component analysis
        CASE WHEN mca.property_address IS NOT NULL AND LENGTH(TRIM(mca.property_address)) > 0 
             THEN 1 ELSE 0 END as has_address,
        CASE WHEN mca.latitude IS NOT NULL AND mca.longitude IS NOT NULL 
             AND ABS(mca.latitude) > 0.001 AND ABS(mca.longitude) > 0.001  
             THEN 1 ELSE 0 END as has_geo,
        CASE WHEN mca.assessed_value IS NOT NULL AND mca.assessed_value > 0 
             THEN 1 ELSE 0 END as has_value,  
        CASE WHEN mca.zoning_code IS NOT NULL AND LENGTH(TRIM(mca.zoning_code)) > 0
             THEN 1 ELSE 0 END as has_zoning,
        -- Overall completeness per I definition
        CASE WHEN mca.property_address IS NOT NULL AND LENGTH(TRIM(mca.property_address)) > 0
             AND mca.latitude IS NOT NULL AND mca.longitude IS NOT NULL
             AND ABS(mca.latitude) > 0.001 AND ABS(mca.longitude) > 0.001
             AND mca.assessed_value IS NOT NULL AND mca.assessed_value > 0
             AND mca.zoning_code IS NOT NULL AND LENGTH(TRIM(mca.zoning_code)) > 0
             THEN 1 ELSE 0 END as card_render_complete
    FROM multi_county_auctions mca
    WHERE mca.county_slug = 'duval'
      AND mca.auction_date >= CURRENT_DATE - INTERVAL '30 days'
)
SELECT 
    COUNT(*) as total_duval_auctions,
    -- Component-wise analysis
    SUM(has_address) as with_address,
    SUM(has_geo) as with_geo,
    SUM(has_value) as with_value, 
    SUM(has_zoning) as with_zoning,
    SUM(card_render_complete) as fully_complete_cards,
    
    -- Percentages
    ROUND(100.0 * SUM(has_address) / COUNT(*), 2) as address_percentage,
    ROUND(100.0 * SUM(has_geo) / COUNT(*), 2) as geo_percentage,
    ROUND(100.0 * SUM(has_value) / COUNT(*), 2) as value_percentage,
    ROUND(100.0 * SUM(has_zoning) / COUNT(*), 2) as zoning_percentage,
    ROUND(100.0 * SUM(card_render_complete) / COUNT(*), 2) as letter_i_percentage,
    
    -- Weakest component (bottleneck per G definition)
    LEAST(
        ROUND(100.0 * SUM(has_address) / COUNT(*), 2),
        ROUND(100.0 * SUM(has_geo) / COUNT(*), 2),
        ROUND(100.0 * SUM(has_value) / COUNT(*), 2),
        ROUND(100.0 * SUM(has_zoning) / COUNT(*), 2)
    ) as bottleneck_percentage
FROM duval_card_analysis;
```

#### Attack 4: Placeholder Data Detection
```sql
-- ATTACK: Are fixes real data or placeholder/default values?
SELECT 
    'Duval Placeholder Analysis' as analysis_type,
    -- Common placeholder patterns
    COUNT(CASE WHEN zoning_code = 'UNKNOWN' OR zoning_code = 'TBD' 
               OR zoning_code = 'PENDING' THEN 1 END) as placeholder_zoning_codes,
    COUNT(CASE WHEN property_address ILIKE '%UNKNOWN%' 
               OR property_address ILIKE '%TBD%' THEN 1 END) as placeholder_addresses,
    COUNT(CASE WHEN assessed_value = 0 OR assessed_value = 1 THEN 1 END) as suspicious_values,
    
    -- Coordinate validity for Duval County (rough bounds)
    COUNT(CASE WHEN latitude < 30.0 OR latitude > 30.7 
               OR longitude > -81.0 OR longitude < -82.0 THEN 1 END) as invalid_coordinates,
    
    -- Sample suspicious entries
    array_agg(CASE WHEN zoning_code = 'UNKNOWN' THEN case_number END) 
        FILTER (WHERE zoning_code = 'UNKNOWN') as unknown_zoning_samples
FROM multi_county_auctions
WHERE county_slug = 'duval'
  AND auction_date >= CURRENT_DATE - INTERVAL '7 days'
LIMIT 1;
```

#### Attack 5: Fix Temporality Analysis  
```sql
-- ATTACK: Were null→value fixes sudden (suspicious) or gradual (credible)?
WITH daily_completeness AS (
    SELECT 
        DATE(created_at) as fix_date,
        COUNT(*) as daily_auctions,
        
        -- G letter progress  
        COUNT(CASE WHEN zoning_code IS NOT NULL THEN 1 END) as daily_with_zoning,
        ROUND(100.0 * COUNT(CASE WHEN zoning_code IS NOT NULL THEN 1 END) 
              / NULLIF(COUNT(*), 0), 2) as daily_g_proxy,
        
        -- I letter progress
        COUNT(CASE WHEN property_address IS NOT NULL AND latitude IS NOT NULL 
                   AND longitude IS NOT NULL AND assessed_value IS NOT NULL 
                   AND zoning_code IS NOT NULL THEN 1 END) as daily_complete_cards,
        ROUND(100.0 * COUNT(CASE WHEN property_address IS NOT NULL AND latitude IS NOT NULL 
                                 AND longitude IS NOT NULL AND assessed_value IS NOT NULL 
                                 AND zoning_code IS NOT NULL THEN 1 END) 
              / NULLIF(COUNT(*), 0), 2) as daily_i_percentage
    FROM multi_county_auctions
    WHERE county_slug = 'duval'
      AND created_at >= CURRENT_DATE - INTERVAL '14 days'
    GROUP BY DATE(created_at)
)
SELECT 
    fix_date,
    daily_auctions,
    daily_g_proxy,
    daily_i_percentage,
    LAG(daily_g_proxy) OVER (ORDER BY fix_date) as prev_g_proxy,
    LAG(daily_i_percentage) OVER (ORDER BY fix_date) as prev_i_percentage,
    daily_g_proxy - LAG(daily_g_proxy) OVER (ORDER BY fix_date) as g_daily_delta,
    daily_i_percentage - LAG(daily_i_percentage) OVER (ORDER BY fix_date) as i_daily_delta,
    CASE 
        WHEN daily_g_proxy - LAG(daily_g_proxy) OVER (ORDER BY fix_date) > 50 
        THEN 'SUSPICIOUS_G_JUMP'
        ELSE 'CREDIBLE_G_PROGRESS'
    END as g_pattern_analysis,
    CASE 
        WHEN daily_i_percentage - LAG(daily_i_percentage) OVER (ORDER BY fix_date) > 50
        THEN 'SUSPICIOUS_I_JUMP' 
        ELSE 'CREDIBLE_I_PROGRESS'
    END as i_pattern_analysis
FROM daily_completeness
ORDER BY fix_date DESC;
```

#### Attack 6: Cross-County Consistency
```sql
-- ATTACK: Are Duval fixes consistent with established patterns in other counties?
SELECT 
    county_slug,
    COUNT(*) as auctions,
    ROUND(AVG(CASE WHEN zoning_code IS NOT NULL THEN 100.0 ELSE 0 END), 2) as avg_zoning_coverage,
    ROUND(AVG(CASE WHEN property_address IS NOT NULL AND latitude IS NOT NULL 
                   AND longitude IS NOT NULL AND assessed_value IS NOT NULL 
                   THEN 100.0 ELSE 0 END), 2) as avg_card_completeness,
    CASE 
        WHEN county_slug = 'duval' THEN 'TARGET_COUNTY'
        WHEN county_slug IN ('brevard', 'orange', 'hillsborough') THEN 'BENCHMARK_COUNTY' 
        ELSE 'OTHER_COUNTY'
    END as county_category
FROM multi_county_auctions
WHERE county_slug IN ('duval', 'brevard', 'orange', 'hillsborough', 'pinellas')
  AND auction_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY county_slug
ORDER BY avg_card_completeness DESC;
```

## Refutation Strategy

### Critical Attack Vectors for G/I Null Fixes

1. **Placeholder Data:** "Fixed" with default/placeholder values  
2. **Cosmetic Fixes:** Display layer changes without underlying data
3. **Bulk Insert Artifacts:** Suspicious temporal patterns
4. **Infrastructure Missing:** Tables populated but standards/relationships absent
5. **Cross-County Inconsistency:** Results don't match established county patterns

### Survival Criteria

```yaml
gi_null_fixes_survival:
  letter_g_requirements:
    infrastructure: "Jurisdictions, zoning_districts, zone_standards populated"
    data_quality: "Real density/FAR/parking values, not placeholders"  
    coverage: "≥95% of applicable parcels"
    minimum_dimension: "Weakest of density/FAR/parking sets the bar"
    
  letter_i_requirements:
    components: [address, latitude, longitude, assessed_value, zoning_code]
    completeness: "≥95% of auctions with ALL 4 components"
    data_validity: "Coordinates within Duval bounds, non-zero values"
    render_capability: "Card actually renders with all components"
    
  temporal_credibility:
    pattern: "Gradual improvement over time, not sudden jumps"  
    consistency: "Matches established county fix patterns"
```

### Expected Outcomes

#### Scenario 1: Null Fixes Refuted (Cosmetic/Placeholder)
```sql
INSERT INTO gold_standard_ultraloop_audit (
    dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived
) VALUES (
    $dispatch_id, 'native', 'duval', 'G',
    'G letter fixed from null to X% via zoning infrastructure',
    jsonb_build_object(
        'attack_type', 'placeholder_data',
        'evidence', 'Zoning codes populated with placeholder values UNKNOWN/TBD',
        'placeholder_count', '[count of placeholder entries]',
        'infrastructure_gaps', '[missing zone_standards or jurisdictions]',
        'refutation_strength', 'STRONG'
    ),
    false
);

INSERT INTO gold_standard_ultraloop_audit (
    dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived
) VALUES (
    $dispatch_id, 'native', 'duval', 'I', 
    'I letter fixed from null to Y% via property card completion',
    jsonb_build_object(
        'attack_type', 'cosmetic_fix',
        'evidence', 'Cards display placeholder data, do not actually render complete',
        'invalid_coordinates', '[count outside Duval bounds]',
        'zero_values', '[count of suspicious assessed values]',
        'refutation_strength', 'STRONG'
    ),
    false
);
```

#### Scenario 2: Null Fixes Verified and Survive
```sql
INSERT INTO gold_standard_ultraloop_audit (
    dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived  
) VALUES (
    $dispatch_id, 'native', 'duval', 'G',
    'G letter fixed from null to X% via complete zoning infrastructure',
    jsonb_build_object(
        'verification_queries', 6,
        'infrastructure_confirmed', '[jurisdictions + districts + standards counts]',
        'data_quality_verified', '[real density/FAR/parking values confirmed]',
        'temporal_pattern', 'gradual credible improvement',
        'final_percentage', '[X%]'
    ),
    true
);
```

## Integration with Duval Sprint

### Phase 1 Execution (G/I NULL FIX)  
- Highest priority in Duval sprint order
- Must complete before C/D improvements
- Critical foundation for all downstream letters
- Null status is worse than low percentages - complete infrastructure gap

### Success Definition
G/I null fixes succeed if complete infrastructure is populated with real data (not placeholders) AND ≥95% coverage achieved AND temporal patterns are credible.