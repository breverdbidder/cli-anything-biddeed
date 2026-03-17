You are working on the Cost Forecaster agent in /opt/biddeed/cli-anything-biddeed/forecaster/

Read forecaster/CLAUDE.md FIRST. It is your root directive.

## SESSION GOAL

Create Supabase tables, add persistence (--save), add spend logging (update-spend), and wire historical data query. 4 phases, 4 commits.

## PHASE 1: CREATE SUPABASE TABLES

Create two tables using the Supabase REST API. Use these env vars:
- SUPABASE_URL (already set)
- SUPABASE_KEY (service role, already set)

### Table 1: rehab_projects
```sql
CREATE TABLE IF NOT EXISTS rehab_projects (
  id BIGSERIAL PRIMARY KEY,
  parcel_id TEXT,
  project_name TEXT,
  template TEXT,
  total_budget NUMERIC,
  total_spent NUMERIC DEFAULT 0,
  total_forecast NUMERIC,
  variance_pct FLOAT,
  status TEXT DEFAULT 'ACTIVE',
  start_date DATE,
  projected_weeks INT,
  arv NUMERIC,
  alerts_json JSONB,
  scenarios_json JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rp_parcel ON rehab_projects(parcel_id);
CREATE INDEX IF NOT EXISTS idx_rp_status ON rehab_projects(status);
```

### Table 2: rehab_spend_log
```sql
CREATE TABLE IF NOT EXISTS rehab_spend_log (
  id BIGSERIAL PRIMARY KEY,
  project_id BIGINT REFERENCES rehab_projects(id),
  parcel_id TEXT,
  category TEXT NOT NULL,
  amount NUMERIC NOT NULL,
  description TEXT,
  vendor TEXT,
  receipt_url TEXT,
  spend_date DATE DEFAULT CURRENT_DATE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rsl_project ON rehab_spend_log(project_id);
CREATE INDEX IF NOT EXISTS idx_rsl_parcel ON rehab_spend_log(parcel_id);
```

You can create these via `curl` to the Supabase SQL endpoint, or by adding a migration script. If `exec_sql` RPC is not available, create a `migrations/create_forecaster_tables.sql` file and document it for manual execution.

Verify: Query the tables to confirm they exist.

COMMIT: `git add -A && git commit -m "feat(forecaster): Supabase tables rehab_projects + rehab_spend_log" && git push origin main`

## PHASE 2: ADD --save FLAG

In `agent.py`, modify the `forecast` subcommand:

1. Add `--save` flag to argparse
2. When `--save` is passed, after running the pipeline, upsert the result to `rehab_projects`:
   - Map: parcel_id, template, total_budget, total_spent (from velocity), total_forecast, variance_pct, arv
   - Store alerts as alerts_json, scenarios as scenarios_json
   - Set status = 'ACTIVE'
3. Use the existing `supabase_upsert()` function

Verify: `python3 -m forecaster.agent forecast --budget 85000 --template medium_rehab --save --json 2>/dev/null | python3 -c "import json,sys; json.load(sys.stdin); print('Valid JSON')"` — then query Supabase to confirm row exists.

COMMIT: `git add -A && git commit -m "feat(forecaster): --save flag persists forecast to Supabase" && git push origin main`

## PHASE 3: ADD update-spend SUBCOMMAND

Add a new `update-spend` subcommand to `agent.py`:

```
python3 -m forecaster.agent update-spend --parcel "25-37-22-00-00123.0-0000.00" --category kitchen --amount 4500 --vendor "Home Depot" --description "Cabinets delivery"
```

1. Add argparse subcommand with: --parcel (required), --category (required), --amount (required), --vendor, --description, --date
2. Insert into `rehab_spend_log` via Supabase REST
3. After inserting, query total spent for this parcel and print summary
4. Validate category against known template categories — warn if unknown but still insert

Verify: Insert a test spend entry, then query to confirm.

COMMIT: `git add -A && git commit -m "feat(forecaster): update-spend subcommand for expense tracking" && git push origin main`

## PHASE 4: WIRE HISTORICAL QUERY + SMOKE TEST

In `stage_history()`, improve the Supabase query:

1. Query `rehab_projects` (not just historical_auctions) for completed projects — filter by `status = 'COMPLETED'` or similar
2. Also query `historical_auctions` for repair_estimate data as fallback
3. Calculate actual avg_final_cost, avg_overrun_pct, avg_timeline_weeks from real data
4. If no data exists yet, fall back to the Brevard pattern defaults already in the code

Then run full smoke test:
1. `python3 -m forecaster.agent forecast --budget 85000 --template medium_rehab --arv 280000 --json 2>/dev/null > forecaster/eval_outputs/smoke_test.json`
2. Validate JSON
3. `python3 -m forecaster.agent status 2>&1`
4. Run eval if available: `python3 scripts/eval_runner.py --eval-file forecaster/eval/eval.json --outputs-dir forecaster/eval_outputs/ || true`

COMMIT: `git add -A && git commit -m "feat(forecaster): historical query + smoke test $(date +%Y%m%d)" && git push origin main`

## RULES

- You are autonomous. The human is not available. Never ask questions.
- ONE commit per phase. Push after each commit. 4 total commits expected.
- All print() goes to sys.stderr. Only --json output hits stdout. This is ALREADY correct in agent.py — do NOT break it.
- All httpx.Client() uses headers=UA. This is ALREADY correct — do NOT break it.
- If Supabase exec_sql is unavailable, create the SQL as a migration file and move on.
- If context window reaches 50%, stop and push what you have. Do not /compact.
- Do NOT refactor the entire file. Make targeted additions only.
- Do NOT add new dependencies beyond httpx (already installed).
- Do NOT touch eval.json.
- Total session budget: under $5. Be efficient.
