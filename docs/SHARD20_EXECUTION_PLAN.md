# SHARD-20 GOLD STANDARD EXECUTION PLAN

**Session:** Autopilot Run 20  
**Date:** 2026-06-13  
**Counties:** charlotte, citrus, broward  
**Budget:** 6-hour autonomous session  
**Mandate:** SHIP-TO-MAIN (direct commits, no branches)

## Current Baseline (Verified from Issue #7653)

### charlotte (3/10)
- **A**: ✅ PASS (fc=249, td=7857)
- **B**: ❌ FAIL (null verified outcomes, 945 closed_sold)  
- **C**: ❌ FAIL 10.1% (821 matched_clean of 8106)
- **D**: ✅ PASS 97.4% (7899 matched_any of 8106)
- **E**: ❌ FAIL 43.8% (3547 parcel_linked of 8106)
- **F**: ❌ FAIL 2.1% (20 tier1_sold, 945 closed_sold)
- **G**: ❌ FAIL (null density/far/pk1000)
- **H**: ✅ PASS 26.0h (last_seen within SLA)
- **I**: ❌ FAIL (null zoned_complete_parcels, 1423 field_complete_parcels)
- **J**: ❌ FAIL 0.0% (0 deal_complete of 8106)

### citrus (3/10)
- **A**: ✅ PASS (fc=1666, td=3846)
- **B**: ❌ FAIL (null verified outcomes, 1308 closed_sold)
- **C**: ❌ FAIL 9.5% (523 matched_clean of 5512)
- **D**: ❌ FAIL 75.3% (4152 matched_any of 5512) 
- **E**: ✅ PASS 95.3% (5253 parcel_linked of 5512)
- **F**: ❌ FAIL 6.1% (80 tier1_sold, 1308 closed_sold)
- **G**: ❌ FAIL (null density/far/pk1000)
- **H**: ✅ PASS 13.6h (last_seen within SLA)
- **I**: ❌ FAIL (null zoned_complete_parcels, 1473 field_complete_parcels)
- **J**: ❌ FAIL 0.0% (0 deal_complete of 5512)

### broward (2/10)
- **A**: ✅ PASS (fc=19801, td=10308)
- **B**: ❌ FAIL (null verified outcomes, 12198 closed_sold)
- **C**: ❌ FAIL 19.4% (5836 matched_clean of 30109)
- **D**: ❌ FAIL 47.7% (14364 matched_any of 30109)
- **E**: ❌ FAIL 20.6% (6205 parcel_linked of 30109)
- **F**: ❌ FAIL 2.5% (300 tier1_sold, 12198 closed_sold)
- **G**: ❌ FAIL (null density/far/pk1000)
- **H**: ✅ PASS 0.2h (last_seen within SLA)
- **I**: ❌ FAIL (null zoned_complete_parcels, 737 field_complete_parcels)
- **J**: ❌ FAIL 0.0% (0 deal_complete of 30109)

## CRITERION-PARALLEL STRATEGY

Target highest-leverage letters across all counties rather than serialized county completion.

### Priority Order (Issue-Authorized)

#### 1. **J GENERATOR** (HIGHEST LEVERAGE)
- **Impact**: 0% → 95% × 3 counties = 285 total points
- **Script**: `scripts/shard20_j_generator.py` 
- **Infrastructure**: `migrations/20260613_shard20_bid_decisions.sql`
- **Contract**: bid_decisions with arv + max_bid + ml_score + factors[5 keys]
- **Shapira Formula**: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)
- **Dependencies**: Shapira V14 model, gen_valuations_comps_batch

#### 2. **C/D ROOT CAUSE** (COVERAGE AUDIT)
- **Impact**: Fix PropertyOnion vs clerk/official-records coverage gap
- **Script**: `scripts/shard20_cd_parity_analysis.py`
- **Issue**: C metrics low (9.5-19.4%) while D varies (47.7-97.4%)
- **Authorization**: Pre-authorized clerk/official-records supplementary litmus
- **Pattern**: Numerators frozen while denominator grew 33%

#### 3. **B RECONCILIATION** (ANOMALY RESOLUTION)
- **Impact**: Fix verified_outcomes > closed_sold anomaly
- **Script**: `scripts/shard20_b_reconciliation.py`
- **Issue**: charlotte B would be 135.8% (verified=8547 > closed_sold=6373)
- **Canon**: B passes only at 95-105%, anomalous ratios FAIL
- **Root**: Likely outcomes beyond scoped set or double-counting

## DATABASE INFRASTRUCTURE

### Migration Status
- ✅ `20260613_shard20_bid_decisions.sql` - Prepared for J letter pipeline
- ✅ Tables: bid_decisions with validation triggers
- ✅ Views: v_bid_decisions_j_metrics, shard20_j_verification function
- ✅ Indexes: Performance-optimized for case_number, county_slug, factors

### Schema Requirements
```sql
-- Critical J evaluator contract
SELECT 
  case_number,
  arv,              -- NOT NULL
  max_bid,          -- NOT NULL
  ml_score,         -- NOT NULL
  factors           -- JSONB with 5 required keys
FROM bid_decisions 
WHERE validate_bid_decisions_factors(factors) = true;
```

### Required Factor Keys (J Letter)
1. `distress_location` - Location desirability score
2. `distress_property` - Property condition score  
3. `distress_owner` - Owner distress indicators
4. `cma_distressed` - Distressed comparables analysis
5. `cma_resale` - Retail resale comparables analysis

## EXECUTION ORCHESTRATION

### Main Script
```bash
python scripts/shard20_gold_standard_autopilot.py
```

### Individual Priorities
```bash  
python scripts/shard20_gold_standard_autopilot.py --priority J_GENERATOR
python scripts/shard20_gold_standard_autopilot.py --priority CD_ANALYSIS  
python scripts/shard20_gold_standard_autopilot.py --priority B_RECONCILIATION
```

### Verification Only
```bash
python scripts/shard20_gold_standard_autopilot.py --verification-only
```

## ULTRALOOP VERIFICATION PROTOCOL

### Audit Requirements
1. **Fan-out verification**: One subagent per failing letter per county
2. **Adversarial survival vote**: Independent refuter for every claim
3. **SQL evidence**: All metrics VERIFIED with live DB queries
4. **Loop-until-done**: Fix verification against live gold_standard_county_status

### Verification Functions
```sql
-- Per-county evaluation
SELECT public.pencil_dod_evaluate_county('charlotte');
SELECT public.pencil_dod_evaluate_county('citrus');
SELECT public.pencil_dod_evaluate_county('broward');

-- SHARD-20 J verification with evidence
SELECT * FROM shard20_j_verification('charlotte');
```

### Success Criteria
- **J Letter**: ≥95% auctions with complete bid_decisions per contract
- **C Letter**: ≥95% parity_status='matched_clean'
- **D Letter**: ≥95% matched_clean OR matched_divergent
- **B Letter**: 95-105% verified_outcomes rate (anomalies resolved)

## HONESTY PROTOCOL COMPLIANCE

### Verification Tags (MANDATORY)
- **VERIFIED**: Proof attached (SQL query result, test execution)
- **UNTESTED**: Not tested yet (zero penalty, always acceptable)
- **INFERRED**: Guessing from context (must include evidence)

### Never-Lie Rules
- ❌ Never claim metric improvement without fresh SQL verification
- ❌ Never mark tasks complete without execution receipt
- ❌ Wrong VERIFIED = 3× penalty to honesty_violations table
- ✅ "I was wrong" when incorrect, never rationalize

## SHIP-TO-MAIN PROTOCOL

### Commit Requirements  
- Direct commits to main branch (no side branches)
- Frequent commits with descriptive messages
- Co-author attribution to breverdbidder
- Migration files applied to live Supabase

### Wiring Mandate
- All scrapers/pipelines MUST be scheduled for execution
- Code not SCHEDULED = dead code (scores zero)
- Every script must execute at least once during session
- Report actual row counts written to tables

## SESSION BUDGET

- **Total**: 6 hours autonomous execution
- **Close-out**: Begin at ~5.5h elapsed
- **Verification**: Mandatory before session end
- **Evidence**: Paste before/after JSON from pencil_dod_evaluate_county

## DEPENDENCY CHAINS

### J Letter Pipeline
1. Execute `20260613_shard20_bid_decisions.sql` migration
2. Run `shard20_j_generator.py` to populate bid_decisions  
3. Verify via `shard20_j_verification()` function
4. Confirm pencil_dod_evaluate_county J metrics move

### C/D Parity Fixes
1. Run `shard20_cd_parity_analysis.py` to audit coverage
2. Implement clerk/official-records supplementary litmus
3. Backfill matched cases via authorized sources
4. Verify C/D metrics approach ≥95% threshold

### B Reconciliation  
1. Run `shard20_b_reconciliation.py` to identify anomaly
2. Scope verified_outcomes to snapshot set 
3. Resolve double-counting or denominator mismatches
4. Verify B metrics fall within 95-105% normal range

---

**SHIP GATE**: Before any completion claim, paste SQL verification evidence showing actual metric movement in live database. Code-only commits without execution = WIP, never SHIPPED.