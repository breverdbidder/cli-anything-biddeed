# ULTRALOOP Gold Standard Session Plan - Brevard & Duval

**Session Type:** Gold Standard Autopilot with ULTRALOOP Verification  
**Counties:** brevard, duval  
**Created:** 2026-06-12  
**Protocol:** ULTRALOOP SSOT per docs/ULTRALOOP-SSOT.md

## Executive Summary

This session establishes systematic adversarial audit infrastructure for Gold Standard county certification. The ULTRALOOP protocol addresses agentic laziness and self-preferential bias by moving audit orchestration out of the main context window - isolated subagents measure, independent refuters attack, claims certify only on survival.

## Current Metrics & Priorities

### Brevard County
- **Status:** A✓ H✓ | B 134.1% ANOMALY | C 20.8 | D 33.2 | E 78.6 | F 51.1 | G 48.9 | I 18.6 | J 0.0
- **Sprint Priority:** C/D (root cause) → J (generator) → G (hitlist) → B (reconciliation)
- **Critical Issue:** B=134.1% mathematical impossibility (auto-fail per ULTRALOOP)

### Duval County  
- **Status:** A✓ H✓ | B 110.2% ANOMALY | C 16.1 | D 52.9 | E 83.4 | F 63.3 | G null | I null | J 0.0
- **Sprint Priority:** G/I (null fix) → C/D (root cause) → J (generator) → B (reconciliation)
- **Critical Issue:** B=110.2% mathematical impossibility + G/I complete nulls

## ULTRALOOP Infrastructure Created

### 1. Audit Evidence Table
- **File:** `migrations/20260612_ultraloop_audit_table.sql`
- **Table:** `public.gold_standard_ultraloop_audit`
- **Purpose:** Store adversarial survival vote evidence per claim
- **Triggers:** Auto-fail anomaly ratios >100%, validate evidence requirements

### 2. Verification Workflows
Created in `.claude/workflows/`:

#### Brevard Workflows
- `ultraloop_brevard_b_refuter.md` - Auto-fail B=134.1% anomaly
- `ultraloop_brevard_cd_verifier.md` - Verify C/D parity improvements 
- `ultraloop_brevard_j_verifier.md` - Verify J=0.0%→≥95% generation

#### Duval Workflows  
- `ultraloop_duval_b_refuter.md` - Auto-fail B=110.2% anomaly
- `ultraloop_duval_gi_verifier.md` - Verify G/I null→value fixes

### 3. Certification Gate
- **File:** `.claude/ultraloop_certification_gate.sql`
- **Purpose:** Query audit table for certification eligibility
- **Rule:** ≥1 survived row per letter required, zero rows = gate fails closed

## Session Execution Flow

### Phase 1: Infrastructure Deployment
```yaml
tasks:
  - Run migrations/20260612_ultraloop_audit_table.sql
  - Verify audit table structure and triggers
  - Test certification gate queries
  - Initialize baseline evidence entries
duration: 15 minutes
success_criteria: "Table created, triggers working, sample data inserted"
```

### Phase 2: Brevard Sprint Execution 
```yaml
execution_order:
  phase_2a_cd_root_cause:
    target_letters: [C, D]
    workflow: ultraloop_brevard_cd_verifier.md
    current_metrics: "C=20.8%, D=33.2%" 
    attacks: [denominator_universe, stale_cache, circular_logic, ghost_matches]
    
  phase_2b_j_generator:
    target_letter: J
    workflow: ultraloop_brevard_j_verifier.md  
    current_metric: "J=0.0%"
    attacks: [incomplete_thesis, placeholder_values, ml_pipeline_failure]
    
  phase_2c_g_hitlist:
    target_letter: G
    workflow: "Create G verifier (density/FAR/parking coverage)"
    current_metric: "G=48.9%"
    attacks: [circular_measurement, weakest_dimension, backfill_artifacts]
    
  phase_2d_b_reconciliation:
    target_letter: B
    workflow: ultraloop_brevard_b_refuter.md
    current_metric: "B=134.1% ANOMALY"
    result: AUTO_FAIL (mathematical impossibility)

duration: 3-4 hours
success_criteria: "Audit rows inserted, claims survival determined"
```

### Phase 3: Duval Sprint Execution
```yaml
execution_order:
  phase_3a_gi_null_fix:
    target_letters: [G, I]
    workflow: ultraloop_duval_gi_verifier.md
    current_metrics: "G=null, I=null"
    attacks: [placeholder_data, cosmetic_fixes, infrastructure_missing]
    
  phase_3b_cd_root_cause:
    target_letters: [C, D] 
    workflow: "Adapt Brevard C/D verifier for Duval"
    current_metrics: "C=16.1%, D=52.9%"
    attacks: [same as Brevard C/D with Duval data]
    
  phase_3c_j_generator:
    target_letter: J
    workflow: "Adapt Brevard J verifier for Duval"
    current_metric: "J=0.0%"
    attacks: [same as Brevard J with Duval data]
    
  phase_3d_b_reconciliation:
    target_letter: B
    workflow: ultraloop_duval_b_refuter.md
    current_metric: "B=110.2% ANOMALY"  
    result: AUTO_FAIL (mathematical impossibility)

duration: 3-4 hours
success_criteria: "Audit rows inserted, claims survival determined"
```

### Phase 4: Certification Gate Evaluation
```yaml
tasks:
  - Run ultraloop_certification_gate.sql
  - Generate final certification report
  - Log evidence to session summary
  - Update gold_standard_county_status if eligible
duration: 30 minutes  
success_criteria: "Certification eligibility determined with SQL proof"
```

## Adversarial Attack Vectors by Letter

### Letter B (Auto-Fail Anomalies)
- **Mathematical impossibility** - ratios >100% definitionally impossible
- **Denominator error** - counting wrong auction universe
- **Double-counting** - same auction counted multiple times
- **Source contamination** - PropertyOnion data counted as "independent"

### Letter C/D (Parity Improvements)
- **Denominator manipulation** - wrong auction universe 
- **Stale cache** - PropertyOnion litmus source not current
- **Circular logic** - measuring own parity assignments
- **Ghost matches** - claimed match but source doesn't have it

### Letter G (Zoning Coverage) 
- **Circular measurement** - measuring own backfill as improvement
- **Weakest dimension rule** - minimum of density/FAR/parking sets bar
- **Infrastructure gaps** - zone_standards missing despite district population
- **Placeholder values** - default/placeholder data masquerading as real

### Letter I (Property Card Completeness)
- **Cosmetic fixes** - display changes without underlying data
- **Invalid coordinates** - outside county geographic bounds
- **Placeholder addresses** - UNKNOWN/TBD values counted as complete
- **Zero/null values** - suspicious assessed values

### Letter J (Shapira Deal Thesis)
- **Incomplete thesis** - partial rows counted as complete
- **Placeholder ML scores** - default values not computed scores  
- **Illogical CMA** - distressed entry > resale ARV (impossible)
- **Missing components** - distress triangle or CMA arms absent

## Expected Outcomes & Success Metrics

### Infrastructure Success
- [x] gold_standard_ultraloop_audit table created with triggers
- [x] Verification workflow templates created per county/letter
- [x] Certification gate query tested and functional
- [x] Evidence collection requirements documented

### Session Success Criteria
```yaml
minimum_requirements:
  audit_coverage: "≥1 audit attempt per failing letter per county"
  evidence_quality: "SQL queries executed, results pasted, attacks documented"
  survival_determination: "Each claim marked survived=true/false with evidence"
  certification_gate: "Final eligibility determined by gate query"

anomaly_handling:
  brevard_b: "134.1% auto-fail confirmed with mathematical proof"
  duval_b: "110.2% auto-fail confirmed with mathematical proof" 
  gate_impact: "Anomaly letters cannot be certified regardless of other work"

gold_standard_achievement:
  requirement: "All letters ≥95% AND survived adversarial attack"
  brevard_prognosis: "Blocked by B anomaly unless calculation fixed"
  duval_prognosis: "Blocked by B anomaly + G/I null status"
```

## Integration with Existing Systems

### Honesty Protocol V3 Compliance
- All claims carry VERIFIED/UNTESTED/INFERRED tags
- SQL proof required for VERIFIED claims
- Wrong VERIFIED = 3× penalty to honesty_violations table

### EG14 Enterprise Gate Compatibility
- ULTRALOOP supplements, never replaces, production gates
- Letter improvements must pass both ULTRALOOP survival and EG14 criteria
- Evidence preservation for downstream certification processes

### SHARD-11 Master Coordinator Integration
- ULTRALOOP audit results feed into shard11_master_coordinator.py
- Certification status updates gold_standard_county_status table
- Session evidence preserved for cross-session continuity

## Risk Mitigation

### High-Risk Scenarios
1. **Context Window Overflow:** Use workflow fan-out, not monolithic execution
2. **Token Budget Exhaustion:** Prioritize critical anomaly refutation first
3. **False Positive Certification:** Gate fails closed - no evidence = no certification
4. **Database Connection Issues:** Include fallback read-only verification mode

### Success Monitoring
- Monitor audit table row count growth during session
- Track survival rate - all refuted claims indicate systematic issues
- Verify SQL evidence actually contradicts claims (not just assertion)
- Ensure temporal consistency - gradual improvements more credible than sudden jumps

## Handoff Requirements

At session completion, this infrastructure will be available for future gold standard sessions:
- Reusable workflow templates per county/letter combination
- Production audit table with evidence history
- Tested certification gate queries
- Documentation of adversarial attack patterns

The ULTRALOOP protocol is now operationalized for systematic gold standard verification across the Florida county expansion program.