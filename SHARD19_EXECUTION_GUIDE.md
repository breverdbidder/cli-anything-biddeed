# SHARD-19 GOLD STANDARD EXECUTION GUIDE

## Session Overview
- **Counties**: charlotte, citrus, broward
- **Current Status**: charlotte (3/10), citrus (3/10), broward (2/10)
- **Budget**: 6-hour autonomous session
- **Mandate**: Ship-to-main (no PRs)

## Scripts Created

### 1. `shard19_county_evaluation.py`
**Purpose**: Analyze current county metrics and identify priorities
```bash
python scripts/shard19_county_evaluation.py
```
- Queries `pencil_dod_evaluate_county()` for each target county
- Identifies failing criteria and priority order
- Generates analysis for session planning

### 2. `shard19_verified_outcomes.py` (Letter B - HIGHEST PRIORITY)
**Purpose**: Create independent verified outcomes from clerk sources
```bash
# Single county
python scripts/shard19_verified_outcomes.py --county charlotte

# All counties
python scripts/shard19_verified_outcomes.py --all-counties

# Dry run analysis
python scripts/shard19_verified_outcomes.py --all-counties --dry-run
```

**Impact**: 
- charlotte: B=null → ≥95% verified outcomes
- citrus: B=null → ≥95% verified outcomes  
- broward: B=null → ≥95% verified outcomes

**Sources**: RealForeclose.com + county clerk portals (independent from PropertyOnion)

### 3. `shard19_parcel_linkage.py` (Letter E - HIGH PRIORITY)
**Purpose**: Link parcel_id via county property appraiser ArcGIS
```bash
# Single county
python scripts/shard19_parcel_linkage.py --county charlotte --limit 100

# All counties  
python scripts/shard19_parcel_linkage.py --all-counties

# Dry run with custom limit
python scripts/shard19_parcel_linkage.py --all-counties --dry-run --limit 50
```

**Impact**:
- charlotte: 43.8% → ≥95% parcel linkage
- citrus: 95.3% (already passing, skipped)
- broward: 20.6% → ≥95% parcel linkage

**Method**: ArcGIS FeatureServer queries by address + owner name matching

### 4. `shard19_parity_improvements.py` (Letters C/D - MEDIUM PRIORITY)
**Purpose**: Improve parity matching with clerk supplementary litmus
```bash
# Single county
python scripts/shard19_parity_improvements.py --county broward

# All counties
python scripts/shard19_parity_improvements.py --all-counties

# Limited processing
python scripts/shard19_parity_improvements.py --all-counties --limit 100
```

**Impact**:
- charlotte: C=10.1%, D=97.4% → improved clean/any rates
- citrus: C=9.5%, D=75.3% → improved clean/any rates
- broward: C=19.4%, D=47.7% → improved clean/any rates

**Strategy**: Clerk/official-records supplementary litmus (pre-authorized per 2026-06-12 directive)

### 5. `shard19_gold_standard_executor.py` (MAIN ORCHESTRATOR)
**Purpose**: Execute complete autonomous session with time management
```bash
# Live execution (6-hour session)
python scripts/shard19_gold_standard_executor.py --execute

# Dry run analysis
python scripts/shard19_gold_standard_executor.py --dry-run
```

**Features**:
- 6-hour session time management
- Priority-ordered execution
- Automatic git commits per ship-to-main mandate
- Comprehensive session reporting
- Graceful timeout handling

## Execution Order (Automated by Orchestrator)

1. **Letter B**: Verified outcomes (all 3 counties)
2. **Letter E**: Parcel linkage (charlotte, broward priority)  
3. **Letters C/D**: Parity improvements (all 3 counties)
4. **Verification**: County metric evaluation
5. **Commit**: Ship directly to main branch

## Expected Improvements

### Before Session:
```
charlotte (3/10): A✓ H✓ | B❌ C❌ D❌ E❌ F❌ G❌ I❌ J❌
citrus (3/10):    A✓ H✓ E✓ | B❌ C❌ D❌ F❌ G❌ I❌ J❌  
broward (2/10):   A✓ H✓ | B❌ C❌ D❌ E❌ F❌ G❌ I❌ J❌
```

### After Session (Projected):
```
charlotte (6/10): A✓ B✓ C✓ D✓ E✓ H✓ | F❌ G❌ I❌ J❌
citrus (6/10):    A✓ B✓ C✓ D✓ E✓ H✓ | F❌ G❌ I❌ J❌
broward (5/10):   A✓ B✓ C✓ D✓ E✓ H✓ | F❌ G❌ I❌ J❌
```

## Verification Commands

After execution, verify improvements:
```sql
SELECT public.pencil_dod_evaluate_county('charlotte');
SELECT public.pencil_dod_evaluate_county('citrus'); 
SELECT public.pencil_dod_evaluate_county('broward');

-- Update scoreboard
SELECT public.gold_standard_loop();
SELECT public.gold_standard_certify();
```

## Ship-to-Main Protocol

Per issue mandate, all changes commit directly to main:
1. No PR creation
2. Autonomous execution
3. Direct main branch commits
4. Session reporting to issue

## Environment Requirements

Required environment variables:
- `SUPABASE_URL`: Database connection
- `SUPABASE_KEY`: Service role key for database access

Scripts handle missing environment gracefully with informative error messages.

## Session Monitoring

The executor provides real-time progress:
- Phase completion status
- Elapsed time tracking  
- Remaining session budget
- Success/failure reporting
- Automatic timeout handling

## Error Handling

Scripts implement defensive patterns:
- Timeout protection (6-hour ceiling)
- Network retry logic
- Database connection validation
- Graceful degradation on partial failures
- Comprehensive error logging

## Next Steps After Execution

1. Monitor letter metric improvements
2. Verify database changes via SQL
3. Check session report for any issues
4. Continue with remaining letters (F,G,I,J) in subsequent sessions
5. Aim for 10/10 certification per gold standard requirements