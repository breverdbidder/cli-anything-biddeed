# SHARD-12 Manual Execution Guide

## Context
Due to GitHub App workflow permissions, the SHARD-12 scripts must be executed manually or via existing workflow dispatch.

## Priority Order (Chain Break Fix)

### 1. Duval Harvest→Outcomes Mapper (CRITICAL)
**Problem**: 37 court-format Duval cases harvested but ZERO foreclosure_outcomes rows
**Solution**: Map staging tables to foreclosure_outcomes

```bash
# Manual execution
python scripts/shard12_duval_harvest_outcomes_mapper.py

# Expected output: 
# - Processes duval_clerk_grantor_recordings_staging
# - Processes duval_tax_deed_recordings_staging  
# - Maps case_number + winning_bid → foreclosure_outcomes
# - Data sources: acclaim_ct:DUVAL-FC-V1, acclaim_ct:DUVAL-TD-V1
```

### 2. Multi-County AcclaimWeb Port
**Problem**: Only Brevard has AcclaimWeb integration
**Solution**: Port to marion, clay, pasco counties

```bash
# Auto-discover endpoints and scrape previous month
python scripts/shard12_acclaim_port_multi_county.py

# Specific year/month
python scripts/shard12_acclaim_port_multi_county.py 2024 12
```

## Verification Commands

### Check Duval Chain Break Status
```python
python -c "
import psycopg2, os
conn = psycopg2.connect(
    host='aws-0-us-west-2.pooler.supabase.com', port=5432,
    database='postgres', user='postgres.mocerqjnksmhcjzxrewo', 
    password=os.environ.get('SUPABASE_DB_PASSWORD', 'BiKvLwWTdS0PwulM')
)
with conn.cursor() as cur:
    cur.execute('SELECT public.pencil_dod_evaluate_county(%s)', ('duval',))
    print('DUVAL METRICS:', cur.fetchone()[0])
conn.close()
"
```

### Check SHARD-12 Counties
```python
python -c "
import psycopg2, os
conn = psycopg2.connect(
    host='aws-0-us-west-2.pooler.supabase.com', port=5432,
    database='postgres', user='postgres.mocerqjnksmhcjzxrewo',
    password=os.environ.get('SUPABASE_DB_PASSWORD', 'BiKvLwWTdS0PwulM')
)
counties = ['marion', 'clay', 'pasco', 'glades']
for county in counties:
    with conn.cursor() as cur:
        cur.execute('SELECT public.pencil_dod_evaluate_county(%s)', (county,))
        print(f'{county.upper()}: {cur.fetchone()[0]}')
conn.close()
"
```

## Wiring to Existing Workflows

Since new workflows can't be created, wire to existing dispatch systems:

### Option 1: Manual Dispatch via Existing Workflows
- Use `claude-code-direct.yml` to execute scripts
- Use `continuous-executor.yml` for scheduling

### Option 2: Add to Existing Cron Jobs
- Integrate with existing scraper schedules  
- Add to daily verification sweeps

## Expected Outcomes

### Duval Chain Break Fix
- B metric: 74.5% → 85%+ (more verified outcomes)
- F metric: 46.8% → 60%+ (tier1 amounts from winning_bid)

### SHARD-12 Counties  
- New verified outcomes from AcclaimWeb discovery
- Improved B+F metrics across marion/clay/pasco
- Foundation for full gold standard achievement

## Monitoring

After execution, monitor:
1. `public.foreclosure_outcomes` row count increases
2. County evaluation metrics via `pencil_dod_evaluate_county()`
3. Gold standard scoreboard improvements
4. Tier1 promote hourly picking up new amounts