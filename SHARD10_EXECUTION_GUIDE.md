# SHARD-10 Gold Standard Execution Guide

## Overview

This guide documents the complete autonomous execution framework for SHARD-10 counties in the Gold Standard campaign.

**Target Counties:** manatee, alachua, martin, franklin, union  
**Current Status:** 5/50 letters passing (10.0%)  
**Session Goal:** Maximize improvements within 6-hour autonomous window  

## County Status Summary

```
manatee  (2/10): A✅ H✅ | B❌ C❌(14.5%) D❌(35.2%) E❌(91.4%) F❌(9.4%) G❌ I❌ J❌(0.0%)
alachua  (1/10): A✅      | B❌ C❌(10.9%) D❌(50.3%) E❌(77.4%) F❌(0.0%) G❌ H❌(343h) I❌ J❌(0.0%)
martin   (1/10): A✅      | B❌ C❌(11.4%) D❌(72.3%) E❌(34.8%) F❌(0.0%) G❌ H❌(222.9h) I❌ J❌(0.0%)
franklin (0/10): ALL FAIL | No data ingested  
union    (0/10): ALL FAIL | No data ingested
```

## Execution Scripts

### 1. Main Orchestrator
- **File:** `execute_shard10_session.py`
- **Purpose:** Complete 6-hour autonomous session
- **Usage:** `python execute_shard10_session.py`
- **Features:** Baseline evaluation, phase execution, verification, reporting

### 2. County Bootstrap
- **File:** `scripts/shard10_county_bootstrap.py`  
- **Purpose:** Setup baseline data for franklin and union
- **Target:** 0/10 → 5-7/10 per county
- **Operations:** FL GIO ingestion, pipeline configuration, initial evaluation

### 3. Parcel Linkage
- **File:** `scripts/shard10_parcel_linkage.py`
- **Purpose:** Improve Letter E (parcel linkage ≥95%)
- **Priority Target:** manatee 91.4% → 95%+ (highest leverage)
- **Operations:** Address matching, county appraiser API integration

### 4. Freshness Fix  
- **File:** `scripts/shard10_freshness_fix.py`
- **Purpose:** Improve Letter H (freshness ≤48h)
- **Targets:** alachua (343h stale), martin (222h stale)  
- **Operations:** Pipeline reconfiguration, scraper reactivation

### 5. Analysis & Verification
- **File:** `analyze_shard10_status.py`
- **Purpose:** Comprehensive status analysis and priority identification
- **File:** `test_shard10_connection.py` 
- **Purpose:** Database connectivity verification

## Prioritized Execution Strategy

### Phase 1: County Bootstrap (90-120 min)
**Target:** franklin, union counties  
**Expected Impact:** 0/10 → 5-7/10 per county  
**Operations:**
- FL GIO parcel ingestion via `ingest_county.py`
- Pipeline.counties configuration setup
- Baseline Gold Standard evaluation

### Phase 2: High-Impact Improvements (45 min)  
**Target:** manatee parcel linkage (Letter E)  
**Expected Impact:** 91.4% → 95%+ = +1 letter passing  
**Operations:**
- Property appraiser API integration
- Address-based parcel matching
- Batch parcel_id updates

### Phase 3: Freshness Optimization (30 min)
**Target:** alachua, martin (Letter H)  
**Expected Impact:** +2 letters passing  
**Operations:**
- Pipeline configuration updates
- Scraper scheduling activation
- Connectivity verification

### Phase 4: Verification (15 min)
**Operations:**
- Final Gold Standard evaluation all counties
- Session report generation
- Commit all changes to main

## Expected Outcomes

### Baseline → Final Projection
- **franklin:** 0/10 → 6/10 (+6 letters)
- **union:** 0/10 → 6/10 (+6 letters) 
- **manatee:** 2/10 → 3/10 (+1 letter - Letter E)
- **alachua:** 1/10 → 2/10 (+1 letter - Letter H)
- **martin:** 1/10 → 2/10 (+1 letter - Letter H)

**Total Improvement:** 5/50 → 19/50 letters (+14 letters, +28%)

## Database Schema Dependencies

### Required Tables
- `multi_county_auctions` - Auction records with parcel_id linkage
- `sample_properties` - FL GIO parcel data by CO_NO
- `fl_counties` - County metadata and CO_NO mapping
- `counties` (pipeline) - Scraper configuration
- `tax_deed_outcomes` / `foreclosure_outcomes` - Verified outcomes (Letter B)

### Key Functions
- `public.pencil_dod_evaluate_county(county_slug)` - Gold Standard evaluation
- `public.gold_standard_loop()` - System-wide scoring
- `public.gold_standard_certify()` - Certification process

## County-Specific Configurations

### Franklin County (CO_NO=29)
```yaml
appraiser_url: "To be discovered via endpoint scanning"
forecast_platform: "manual_queue" 
tax_deed_platform: "manual_queue"
priority: 3 (new county)
```

### Union County (CO_NO=73)  
```yaml
appraiser_url: "To be discovered via endpoint scanning"
forecast_platform: "manual_queue"
tax_deed_platform: "manual_queue" 
priority: 3 (new county)
```

### Manatee County (CO_NO=51)
```yaml
parcel_linkage_current: 91.4%
parcel_linkage_target: 95%+
gap_auctions: ~290 unlinked auctions
strategy: "Address matching via sample_properties"
```

### Alachua County (CO_NO=11)
```yaml
staleness: 343 hours (≫48h SLA)
last_activity: "To be verified"
fix_strategy: "Pipeline reactivation + scheduling"
```

### Martin County (CO_NO=53) 
```yaml
staleness: 222 hours (≫48h SLA)
parcel_linkage: 34.8% (secondary improvement opportunity)
fix_strategy: "Pipeline reactivation + parcel matching"
```

## Execution Commands

### Full Autonomous Session
```bash
python execute_shard10_session.py
```

### Dry Run (Planning)
```bash  
python execute_shard10_session.py --dry-run
```

### Specific Phase Only
```bash
python execute_shard10_session.py --phase-only 1  # County bootstrap
python execute_shard10_session.py --phase-only 2  # Parcel linkage  
python execute_shard10_session.py --phase-only 3  # Freshness fix
python execute_shard10_session.py --phase-only 4  # Verification
```

### Individual Components
```bash
# County bootstrap
python scripts/shard10_county_bootstrap.py --county franklin
python scripts/shard10_county_bootstrap.py --county union

# Parcel linkage
python scripts/shard10_parcel_linkage.py --county manatee

# Freshness fix
python scripts/shard10_freshness_fix.py --all-stale

# Analysis
python analyze_shard10_status.py
```

## Environment Requirements

### Required Environment Variables
```bash
SUPABASE_URL="https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY="<service-role-key>"
# Optional: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

### Required Python Packages
```bash
pip install httpx requests
```

## Success Criteria

### Minimum Success (50% of goal)
- **franklin:** 0/10 → 4/10 
- **union:** 0/10 → 4/10
- **Total:** 5/50 → 12/50 (+7 letters)

### Target Success (100% of goal)  
- **franklin:** 0/10 → 6/10
- **union:** 0/10 → 6/10
- **manatee:** 2/10 → 3/10 (Letter E)
- **alachua:** 1/10 → 2/10 (Letter H)
- **martin:** 1/10 → 2/10 (Letter H)
- **Total:** 5/50 → 19/50 (+14 letters)

### Stretch Success (150% of goal)
- Additional parcel linkage improvements
- Additional pipeline optimizations
- **Total:** 5/50 → 25/50 (+20 letters)

## Verification Protocol

### Real-Time Verification
Each script includes `pencil_dod_evaluate_county()` calls for immediate feedback.

### Final Verification
The session executor runs comprehensive verification:
1. All counties evaluated via Gold Standard RPC
2. Before/after comparison generated  
3. Session report with detailed improvements
4. Database state verification

### Evidence Requirements (NEVER-LIE Protocol)
All metrics must be VERIFIED with actual database queries:
- Exact parcel counts (not estimates)
- Precise linkage percentages 
- Actual staleness hours
- Verified improvement deltas

## Ship-to-Main Integration

All code committed directly to main branch per ship-to-main mandate:
- No feature branches for autonomous sessions
- Direct commits with proper attribution
- Immediate deployment and verification
- No human review loop required for gold standard work

## Troubleshooting

### Common Issues
1. **Database timeouts:** Increase timeout to 60s for heavy queries
2. **Parcel matching failures:** Check address standardization
3. **Pipeline config errors:** Verify counties table permissions  
4. **Staleness not improving:** Check scraper endpoint connectivity

### Recovery Actions
- All scripts include error handling and rollback capabilities
- Session can be resumed from any phase
- Individual county failures do not block other counties
- Comprehensive logging for post-session analysis

## Monitoring and Alerts

### Success Indicators
- Letter count increases after each phase
- Database metrics reflect actual improvements
- No timeout or connectivity errors
- Session completes within 6-hour budget

### Alert Conditions  
- More than 2 consecutive script failures
- Zero improvement after Phase 1
- Database connectivity issues
- Session exceeding time budget

---

**Last Updated:** 2026-06-11  
**Session Type:** Autonomous 6-hour Gold Standard improvements  
**Execution Authority:** Ship-to-main mandate with zero human intervention**