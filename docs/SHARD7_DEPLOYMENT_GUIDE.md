# SHARD-7 Gold Standard Deployment Guide

## Overview

SHARD-7 autonomous session targeting counties: **hillsborough, st_lucie, hernando, columbia, madison**

Built per GitHub issue #7543 mandate with 6-hour session budget and ship-to-main directive.

## County Status & Strategy

### Current Status (from issue briefing)
```
hillsborough (2/10): A✅ B❌ C❌(13.8%) D❌(35.8%) E❌(89.7%) F❌(2.2%) G❌ H✅ I❌ J❌(0.0%)
st_lucie (2/10): A✅ B❌ C❌(19.8%) D❌(93.6%) E❌(51.2%) F❌(0.7%) G❌ H✅ I❌ J❌(0.0%) 
hernando (1/10): A✅ B❌ C❌(16.8%) D❌(73.1%) E❌(71.7%) F❌(0.0%) G❌ H❌(526h) I❌ J❌(0.0%)
columbia (0/10): All letters FAIL (no data)
madison (0/10): All letters FAIL (no data)
```

### Execution Priority
1. **columbia/madison** (0/10): Letter A foundational work
2. **hernando** (1/10): Letter H freshness SLA fix
3. **All counties**: Letters B, F, J (highest leverage)

## Implementation Architecture

### Core Scripts

#### `scripts/shard7_gold_standard_improvements.py`
- Main autonomous session executor
- Implements all letter improvements A, B, F, H, J
- Evidence-before-claims verification protocol
- Ship-to-main automation
- 6-hour time budget management

#### `scripts/shard7_verification_protocol.py`  
- Post-improvement verification with SQL proofs
- Implements CLAUDE.md Evidence-Before-Claims protocol
- Provides [VERIFIED] status tags per honesty protocol
- Outputs structured verification results

#### `.github/workflows/shard7-gold-standard.yml`
- **WIRING MANDATE**: Schedules autonomous 24/7 operation
- Daily 8:00 UTC execution (part of 24/7 fleet)  
- Manual dispatch capability
- Parallel fleet coordination
- Artifact upload for verification results

#### `migrations/20260612_shard7_gold_standard_setup.sql`
- Database schema preparation
- SHARD-7 county initialization
- Verified outcomes tables
- Bid decisions table (Letter J)
- Indexes and functions

## Letter Improvement Strategy

### Letter A: Dual-Product Coverage (columbia/madison)
- FL GIO parcel ingestion via `scripts/ingest_county.py`
- Pipeline configuration for both auction lanes
- Creates foundational data for 0/10 counties

### Letter B: Verified Outcomes (all counties)
- Independent clerk source verification framework
- Separate tax_deed_outcomes / foreclosure_outcomes tables
- Data source independence per canon requirements

### Letter F: Tier1 Sold Amounts (all counties)
- Winning bid enrichment from verified sources
- `promote_tier1_from_outcomes()` function automation
- Hourly tier1 promotion cron job

### Letter H: Freshness SLA (hernando priority)
- Scraper schedule configuration
- SLA monitoring (≤48h requirement)
- Priority refresh for 526h aged data

### Letter J: Deal Thesis Pipeline (all counties)
- Shapira Formula components initialization
- bid_decisions table population
- ARV + max_bid + ml_score + triangle factors

## Database Schema Changes

### New Tables
```sql
-- Verified outcomes (independent sources)
public.tax_deed_outcomes
public.foreclosure_outcomes

-- Deal thesis pipeline
public.bid_decisions

-- Status tracking
public.gold_standard_county_status
public.county_conquest_status
```

### Key Functions
```sql
-- Letter F automation
public.promote_tier1_from_outcomes()

-- Verification protocol  
public.pencil_dod_evaluate_county(county_slug)
```

## Parallel Fleet Coordination

### SHARD-7 Boundaries
- **ONLY** work on assigned counties: hillsborough, st_lucie, hernando, columbia, madison
- **NO** cross-shard interference with other county work
- **Git pull --rebase** before every push to main
- **Small commits** scoped to single counties where possible

### Fleet Integration
- Part of 24/7 build cadence (8:00Z / 16:00Z / 00:00Z waves)
- Respects parallel session rules
- Checkpoints progress to Supabase
- Autonomous continuation across waves

## Verification Protocol

### Evidence-Before-Claims Implementation
Every improvement MUST be verified with SQL proof:

```sql
-- County evaluation (primary verification)
SELECT public.pencil_dod_evaluate_county('hillsborough');

-- Auction count verification
SELECT COUNT(*) FROM multi_county_auctions WHERE county = 'columbia';

-- Verified outcomes verification  
SELECT COUNT(*) FROM tax_deed_outcomes WHERE county_slug = 'hernando';

-- Tier1 promotion verification
SELECT COUNT(*) FROM multi_county_auctions WHERE county = 'st_lucie' AND tier1_verified = true;
```

### VERIFIED Status Tags
- All claims carry `[VERIFIED]` tags with database proof
- Wrong `VERIFIED` claims = 3× penalty per CLAUDE.md honesty protocol
- `UNTESTED` acceptable where immediate verification unavailable

## Execution Commands

### Manual Session Dispatch
```bash
# Full session (all counties, all letters)
python3 scripts/shard7_gold_standard_improvements.py

# Single county focus
python3 scripts/shard7_gold_standard_improvements.py --county columbia --letters A

# Verification only
python3 scripts/shard7_gold_standard_improvements.py --verify-only

# Custom time limit
python3 scripts/shard7_gold_standard_improvements.py --time-limit 3.0
```

### Verification Protocol
```bash
# Verify all SHARD-7 counties
python3 scripts/shard7_verification_protocol.py

# Single county verification with output
python3 scripts/shard7_verification_protocol.py --county hernando --output hernando_status.json
```

## Expected Outcomes

### Session Success Metrics
- **columbia/madison**: 0/10 → 1-2/10 (Letter A foundational)
- **hernando**: 1/10 → 2-3/10 (Letter H + additional improvements)
- **hillsborough/st_lucie**: 2/10 → 3-5/10 (Letter B, F, J improvements)

### Database Evidence
- Exact row counts in multi_county_auctions per county
- Verified outcomes in tax_deed_outcomes / foreclosure_outcomes
- Bid decisions initialized for deal thesis pipeline
- gold_standard_county_status updated with latest metrics

### Automation Wiring
- Daily 8:00 UTC autonomous sessions scheduled
- Verification artifacts uploaded to GitHub
- Fleet coordination logging
- Direct commits to main branch (no PR workflow)

## Troubleshooting

### Common Issues

#### Database Connection
```bash
# Test connectivity
python3 test_shard7_simple.py
```

#### Missing Environment
```bash
# Required secrets
SUPABASE_URL=https://mocerqjnksmhcjzxrewo.supabase.co
SUPABASE_KEY=<service_role_key>
```

#### Git Permissions
```bash
# Workflow needs proper git config
git config user.name "SHARD-7 Autonomous Agent"
git config user.email "shard7@biddeed.ai"
```

#### Migration Failures
```sql
-- Check migration applied
SELECT * FROM migration_log WHERE migration_name = '20260612_shard7_gold_standard_setup';

-- Manual table verification
SELECT table_name FROM information_schema.tables 
WHERE table_name IN ('tax_deed_outcomes', 'foreclosure_outcomes', 'bid_decisions');
```

## Compliance & Governance

### CLAUDE.md Adherence
- ✅ **Ship-to-main mandate**: Direct commits, no branches/PRs
- ✅ **Evidence-before-claims**: All improvements verified with SQL proof
- ✅ **Wiring mandate**: Code scheduled and executed, not just written
- ✅ **VERIFIED tags**: Database proof attached to all claims
- ✅ **Honesty protocol**: UNTESTED vs VERIFIED distinction maintained

### Autonomous Operation
- 6-hour session budget respected
- Work queue prioritized by county status
- Time limit monitoring with graceful cutoff
- Continuous verification protocol
- Fleet coordination compliance

### Quality Gates
- Database connectivity verified before execution
- Migration dependencies checked
- County assignment boundaries enforced
- Verification protocol mandatory
- Error handling with graceful degradation

---

**Deployment Status**: ✅ Ready for autonomous operation  
**Verification**: All components implement Evidence-Before-Claims protocol  
**Integration**: Wired for 24/7 fleet operation per issue mandate