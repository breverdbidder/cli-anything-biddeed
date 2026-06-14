# SHARD24 AUTOPILOT-BD Implementation

**Created:** 2026-06-14  
**Session:** GOLD STANDARD AUTOPILOT-BD (Issue #7706)  
**Counties:** brevard, duval  
**Sprint Orders:** Jun12 directive criterion-parallel approach  

## Overview

This implementation provides the autonomous 6-hour session infrastructure for improving gold standard letter grades in brevard and duval counties, following the SHIP-TO-MAIN mandate and ULTRALOOP verification protocol.

## Files Created

### 1. Main Coordinator Script
**`scripts/shard24_brevard_duval_coordinator.py`**
- Main autonomous session coordinator
- Implements county-specific sprint orders per Jun12 directive
- ULTRALOOP adversarial verification protocol
- Honesty Protocol with VERIFIED/UNTESTED/INFERRED tags

### 2. Verification Runner  
**`scripts/shard24_verification_runner.py`**
- Executes database operations prepared by coordinator
- Live metrics verification via `pencil_dod_evaluate_county` 
- ULTRALOOP audit record creation
- Dry-run and verification-only modes

### 3. Database Migration
**`migrations/20260614_shard24_brevard_duval_functions.sql`**
- SQL functions for all letter improvements
- Brevard clerk supplementary litmus functions
- Bid decisions generator (Letter J)
- B reconciliation functions
- ULTRALOOP audit support tables

### 4. This Documentation
**`SHARD24_AUTOPILOT_README.md`**
- Implementation overview and usage instructions

## County Sprint Orders Implementation

### Brevard (Current: 2/10 A,H) 
**Sprint Order:** C/D → J → G → B

1. **C/D ROOT CAUSE** - PropertyOnion coverage audit + clerk supplementary litmus
   - Function: `brevard_c_d_root_cause()`
   - Pre-authorized clerk/official records adoption
   - Enhanced parity matching with similarity scoring

2. **J GENERATOR** - Bid decisions generator per evaluator contract
   - Function: `brevard_j_generator()` 
   - Shapira V14 ml_score integration
   - 5-factor evaluation: distress_location, distress_property, distress_owner, cma_distressed, cma_resale

3. **G HIT LIST** - Zone standards backfill for ~15 districts
   - Function: `brevard_g_hit_list()`
   - Density gaps: R-1AAA Melbourne (53K parcels), R-1AAA Titusville (22K parcels)
   - FAR gaps (binding at 48.9%): RU-2-15 Melbourne, R-3 Titusville, C-1 Melbourne
   - Ordinance text sources with honesty markers

4. **B RECONCILIATION** - Fix 134.1% anomaly
   - Function: `brevard_b_reconciliation()`
   - Scope outcomes to Jun12 certification snapshot
   - Remove duplicate verified outcomes
   - Target ratio: 95-105% per evaluator V6

### Duval (Current: 2/10 A,H)
**Sprint Order:** G+I → C/D → J → B

1. **G+I SUBSTRATE BUILD** - Zoning districts + parcel zones
   - Function: `duval_g_i_substrate_build()`
   - Jacksonville Ch. 656 covers ~95% of parcels
   - COJ open-data zoning GIS × fl_parcels spatial assignment
   - Zone standards with Ch. 656 occupancy values

2. **C/D ROOT CAUSE** - Same PropertyOnion audit pattern as Brevard
3. **J GENERATOR** - County-agnostic bid decisions (reuses Brevard implementation)  
4. **B RECONCILIATION** - Fix 110.2% anomaly (same pattern as Brevard)

## Usage Instructions

### 1. Database Migration
```bash
# Apply the migration first
supabase db push
# Or manually apply:
psql -h aws-0-us-west-2.pooler.supabase.com -U postgres -d postgres -f migrations/20260614_shard24_brevard_duval_functions.sql
```

### 2. Full Autonomous Execution
```bash
# Run complete 6-hour session simulation
python scripts/shard24_verification_runner.py --execute-all

# Verification only (check current metrics)
python scripts/shard24_verification_runner.py --verify-only

# Dry run (show what would be executed)
python scripts/shard24_verification_runner.py --execute-all --dry-run
```

### 3. Single Phase Execution
```bash
# Execute specific county/phase
python scripts/shard24_verification_runner.py --county brevard --phase C_D_ROOT_CAUSE
python scripts/shard24_verification_runner.py --county duval --phase G_I_SUBSTRATE_BUILD
```

## Expected Letter Improvements

### Brevard Expected Changes
- **C**: 20.9% → 95%+ (clerk supplementary litmus + enhanced matching)
- **D**: 34.0% → 95%+ (same parity improvements)
- **J**: 0.0% → 95%+ (bid_decisions generator with Shapira V14)
- **G**: 48.9% → 95%+ (zone_standards backfill for key districts)
- **B**: 134.1% → 95-105% (scope + dedup reconciliation)

### Duval Expected Changes  
- **G**: null → 95%+ (zoning districts + spatial assignment)
- **I**: null → 95%+ (substrate enables property card completion)
- **C**: 16.1% → 95%+ (clerk supplementary + matching improvements)
- **D**: 52.9% → 95%+ (same parity improvements)
- **J**: 0.0% → 95%+ (county-agnostic bid decisions)
- **B**: 110.2% → 95-105% (scope + dedup reconciliation)

## ULTRALOOP Verification Protocol

Every claim is verified through adversarial refutation:

1. **Audit Phase**: Isolated measurement against live `pencil_dod_criteria`
2. **Verify Phase**: Independent refuter attempts to break each claim
3. **Survival Vote**: Claims pass only if they survive refutation
4. **Audit Table**: All results logged to `gold_standard_ultraloop_audit`

**Refutation Patterns by Letter:**
- **B**: denominator_mismatch, double_counting, scope_violation
- **C/D**: frozen_numerator, coverage_gap, matching_failure  
- **G**: missing_standards, ghost_success, ordinance_drift
- **J**: pipeline_absence, input_gaps, evaluation_contract_violation

## Key Technical Features

### Honesty Protocol Integration
- All functions tagged with VERIFIED/UNTESTED/INFERRED
- Database queries provide evidence for claims
- Wrong VERIFIED = 3× penalty to honesty_violations table

### SHIP-TO-MAIN Compliance
- Direct main branch commits (no side branches)
- Live database operations (not just file commits)
- Verification via `pencil_dod_evaluate_county` required

### Wiring Mandate
- All functions designed for scheduler integration
- Execution receipts with actual row counts
- No dead code - everything wired to executors

## Verification Queries

### Check Letter Status
```sql
-- Current metrics for both counties
SELECT public.pencil_dod_evaluate_county('brevard');
SELECT public.pencil_dod_evaluate_county('duval');

-- ULTRALOOP audit status  
SELECT county_slug, letter, survived, created_at 
FROM gold_standard_ultraloop_audit 
WHERE county_slug IN ('brevard', 'duval')
ORDER BY created_at DESC;
```

### B Reconciliation Verification
```sql
-- Brevard B ratio check (should be 95-105%)
WITH metrics AS (
    SELECT 
        (SELECT COUNT(*) FROM verified_outcomes 
         WHERE county = 'brevard' AND eligible_for_certification = TRUE) as verified_count,
        (SELECT COUNT(*) FROM multi_county_auctions
         WHERE county = 'brevard' AND status = 'closed' 
           AND ingested_at <= '2026-06-12'::timestamp) as closed_count
)
SELECT 
    verified_count,
    closed_count,
    ROUND(100.0 * verified_count / NULLIF(closed_count, 0), 1) as b_ratio,
    CASE 
        WHEN ROUND(100.0 * verified_count / NULLIF(closed_count, 0), 1) BETWEEN 95 AND 105 
        THEN 'PASS' ELSE 'FAIL' 
    END as b_status
FROM metrics;
```

### J Generator Verification
```sql
-- Bid decisions generated
SELECT 
    county,
    COUNT(*) as total_decisions,
    COUNT(CASE WHEN arv IS NOT NULL THEN 1 END) as with_arv,
    COUNT(CASE WHEN ml_score IS NOT NULL THEN 1 END) as with_ml_score,
    COUNT(CASE WHEN factors IS NOT NULL THEN 1 END) as with_factors
FROM bid_decisions 
WHERE county IN ('brevard', 'duval')
GROUP BY county;
```

## Error Handling

All functions include comprehensive error handling:
- Try/catch blocks with SQLSTATE capture
- Execution timing measurement
- Structured JSON response format
- Graceful degradation on partial failures

## Next Steps

1. **Apply Migration**: Run the database migration first
2. **Execute Pipeline**: Use verification runner with `--execute-all`
3. **Verify Results**: Check metrics via `pencil_dod_evaluate_county`
4. **Monitor ULTRALOOP**: Review audit table for survival votes
5. **Certification**: Run `gold_standard_certify()` when 10/10 achieved

## Contact & Support

**Issue Reference**: #7706 GOLD STANDARD AUTOPILOT-BD  
**Session Type**: 6-hour autonomous with SHIP-TO-MAIN mandate  
**Verification Required**: Live database metrics via `pencil_dod_evaluate_county`  
**ULTRALOOP**: Mandatory adversarial verification of all claims  