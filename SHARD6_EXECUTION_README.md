# SHARD-6 Gold Standard Execution Guide

**RUN 27**: highlands, escambia, nassau, calhoun, liberty  
**Dispatch**: 8ea6d509-c251-4e45-a5a5-65aac692cae6  
**Priority**: BREVARD SPRINT ORDER compliance

## Current Status (Per Issue Brief)

| County | Score | C (Clean) | D (Any) | E (Parcel) | Priority |
|--------|-------|-----------|---------|------------|----------|
| highlands | 2/10 | ❌ 31.5% | ❌ 97.5% | ❌ 50.2% | Medium |
| escambia | 1/10 | ❌ 20.5% | ❌ 59.0% | ❌ 87.1% | **HIGH** |
| nassau | 1/10 | ❌ 15.2% | ❌ 55.9% | ❌ 80.3% | High |
| calhoun | 0/10 | ❌ 0.0% | ❌ 0.0% | ❌ 0.0% | Skip (4 auctions) |
| liberty | 0/10 | ❌ null | ❌ null | ❌ null | Skip (0 auctions) |

## Execution Order

### 1. C/D Parity Improvements (Priority #1)
```bash
python3 scripts/shard6_cd_parity_improvements.py --all-counties
```

**Target Impact:**
- Normalize case numbers and addresses for better PropertyOnion matching
- Backfill missing auction dates from case number patterns  
- Expected improvement: +15-25% on C letters, +20-30% on D letters

### 2. E Parcel Linkage (Priority #2)  
```bash
python3 scripts/shard6_parcel_linkage_improvements.py --all-counties
```

**Target Impact:**
- Link auctions to parcel_id via address similarity (sample_properties)
- 70%+ similarity threshold with confidence scoring
- Expected improvement: +5-15% on E letters
- **High leverage**: Enables downstream J-letter deal thesis pipeline

### 3. Verification Protocol
```bash
python3 scripts/shard6_verification_protocol.py
```

**Verification Queries** (Evidence-Before-Claims):
```sql
-- Get actual metrics after improvements
SELECT public.pencil_dod_evaluate_county('escambia');
SELECT public.pencil_dod_evaluate_county('highlands'); 
SELECT public.pencil_dod_evaluate_county('nassau');

-- Verify parity improvements
SELECT county, parity_status, COUNT(*) 
FROM multi_county_auctions 
WHERE county IN ('escambia', 'highlands', 'nassau')
  AND parity_notes LIKE '%normalized%'
GROUP BY county, parity_status;

-- Verify parcel linkage improvements
SELECT county,
       COUNT(*) as total,
       COUNT(parcel_id) as linked,
       COUNT(CASE WHEN linkage_notes LIKE '%Address-linked%' THEN 1 END) as newly_linked,
       ROUND(COUNT(parcel_id) * 100.0 / COUNT(*), 1) as link_rate
FROM multi_county_auctions 
WHERE county IN ('escambia', 'highlands', 'nassau')
GROUP BY county;
```

## County-Specific Notes

### Escambia (Highest Priority)
- **Volume**: 6557 auctions (largest in shard)
- **E Status**: 87.1% (close to 95% threshold) 
- **Strategy**: Focus on C/D improvements, then push E over 95%
- **Expected outcome**: 3-4 letter improvement possible

### Highlands  
- **Volume**: 241 auctions
- **D Status**: 97.5% (already passing!)
- **E Gap**: 50.2% (biggest improvement opportunity)
- **Strategy**: Preserve D-pass, focus on E linkage

### Nassau
- **Volume**: 487 auctions  
- **Balanced gaps**: C=15.2%, D=55.9%, E=80.3%
- **Strategy**: Comprehensive C/D/E improvements

### Calhoun & Liberty
- **Status**: Minimal auction volume (4 and 0 respectively)
- **Decision**: Skip for this session, focus on high-value counties
- **Rationale**: ROI optimization per 6-hour session limit

## Implementation Details

### Address Normalization
```python
# Street type standardization
'STREET' -> 'ST', 'AVENUE' -> 'AVE', 'BOULEVARD' -> 'BLVD'

# Directional standardization  
'NORTH' -> 'N', 'SOUTH' -> 'S', 'EAST' -> 'E', 'WEST' -> 'W'

# Remove unit designators for matching
'LOT 5', 'UNIT 2A', 'APT 101' -> removed
```

### Case Number Normalization
```python
# Remove common prefixes
'CASE 2024-123' -> '2024-123'
'NO. 24-456' -> '24-456'

# Year standardization
'2024-123' -> '24-123' (consistent format)

# Alphanumeric only (keep hyphens)
'24-CA-123!' -> '24-CA-123'
```

### Parcel Linkage Strategy
- **Data source**: sample_properties table by co_no (DOR county number)
- **Matching**: Jaccard similarity on normalized addresses
- **Threshold**: 70% minimum, 85%+ = high confidence
- **Bonus scoring**: Exact house number matches get +0.2 score

## Expected Session Metrics

**Time Investment**: ~2-3 hours execution + verification  
**Counties Improved**: 3 (escambia, highlands, nassau)  
**Letter Improvements Expected**: 
- C letters: 2-3 counties improved
- D letters: 2-3 counties improved  
- E letters: 1-2 counties improved

**Gold Standard Advancement**:
- escambia: 1/10 → 3-4/10
- highlands: 2/10 → 3-4/10  
- nassau: 1/10 → 3-4/10

## Ship-to-Main Protocol

Per issue mandate: commit directly to main, no PR workflow.

```bash
# After execution and verification
git add scripts/shard6_*
git commit -m "feat: SHARD-6 RUN-27 gold standard improvements

- C/D parity improvements for escambia/highlands/nassau
- E parcel linkage enhancements 
- Verified metric improvements via pencil_dod_evaluate_county

VERIFIED improvements: [paste actual SQL results here]

Dispatch: 8ea6d509-c251-4e45-a5a5-65aac692cae6
🤖 Generated with Claude Code"

git push origin main
```

## Success Criteria

**PASS Criteria** (Evidence-before-claims):
1. At least 2 counties show measurable C/D improvement (>5%)
2. At least 1 county shows E improvement (>3%)  
3. SQL verification queries document actual changes
4. No regressions in currently passing letters

**FAIL Criteria**:
- Improvements are marginal (<2% change)
- Any currently passing letter regresses
- Script execution errors without recovery
- No documented SQL proof of improvements

## Integration Points

**Upstream Dependencies**: None (scripts are self-contained)
**Downstream Impact**: Improved E linkage feeds valuations_comps pipeline for J letters
**Parallel Coordination**: No conflicts expected (SHARD-6 counties only)
**Data Safety**: All operations are UPDATEs with audit trails, no DELETEs