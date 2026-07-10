# CLAUDE.md — Cost Forecaster

> Harness: `cli-anything-biddeed/forecaster/`
> Origin: Forked from NextAutomation Cost Forecaster v1.0
> Owner: Ariel Shapira — BidDeed.AI + ZoneWise.AI

## What This Is

Rehab cost forecasting for Brevard County residential properties. NOT for $18M commercial construction — this handles $25K-$250K rehab/flip/rental budgets from foreclosure and tax deed acquisitions.

6-stage pipeline: BUDGET → VELOCITY → HISTORY → FORECAST → ALERTS → SCENARIOS

## Key Difference From Original Spec

The NextAutomation spec targets large commercial construction with lender draws, GMP contracts, and MEP coordination. We adapted it for:

- **Brevard rehab scale** — $25K-$250K budgets, 3 templates (light/medium/heavy)
- **BidDeed.AI integration** — ties into max bid formula, ARV, and auction pipeline
- **Brevard-specific costs** — hurricane roofing code, termite damage patterns, poly plumbing, Chinese drywall
- **ZoneWise.AI leads** — renovation ROI analysis for off-market acquisitions
- **Supabase historical data** — pattern matching against completed projects

## Pipeline

| Stage | Status | What It Does |
|-------|--------|-------------|
| BUDGET | ✅ Working | Template-based budget with BCPAO sqft lookup |
| VELOCITY | ✅ Working | Burn rate, acceleration, earned value (needs spend CSV) |
| HISTORY | ⚠️ Basic | Queries Supabase historical_auctions (needs repair cost data) |
| FORECAST | ✅ Working | Blended velocity + historical projection per category |
| ALERTS | ✅ Working | WATCH/WARNING/ALERT/CRITICAL severity with Brevard mitigations |
| SCENARIOS | ✅ Working | Best/base/worst with max bid recalculation |

## Key Files

- `agent.py` — Full 6-stage pipeline with CLI
- `eval/eval.json` — 25 binary assertions for AUTOLOOP
- `SKILL.md` — Docs and integration map
- `ORIGIN.md` — Original NextAutomation spec

## Supabase Tables

### `rehab_projects` (NEW — needs creation)
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
```

### `rehab_spend_log` (NEW — needs creation)
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
```

## Budget Templates

| Template | Range | Categories | Typical Use |
|----------|-------|-----------|------------|
| `light_rehab` | $15-40K | 9 categories | Cosmetic flip — paint, floors, fixtures |
| `medium_rehab` | $40-100K | 12 categories | Systems + cosmetic — add roof, HVAC, plumbing |
| `heavy_rehab` | $100-250K | 14 categories | Full gut — structural, everything |

## Brevard Cost Index

| Item | Cost | Notes |
|------|------|-------|
| Roof (shingle) | $5.50/sqft | Hurricane code premium +15% |
| HVAC (central) | $4,500/ton | Coastal humidity = oversized units |
| Interior paint | $2.50/sqft | |
| Flooring (LVP) | $6.00/sqft | Over existing tile saves demo |
| Kitchen reno | $12,000 base | Stock cabinets + granite |
| Bathroom reno | $6,000 base | Per bathroom |
| GC labor | $45/hr avg | Brevard market rate |

## Development Rules

1. All `print()` goes to `sys.stderr` — only `--json` output hits stdout
2. All `httpx.Client()` uses `headers=UA` with User-Agent
3. Historical data comes from Supabase, not invented
4. Confidence scores required per stage (0.0-1.0)
5. Brevard-specific mitigations in alerts, not generic advice

## Session Priorities

### P0 — Supabase Integration
1. Create `rehab_projects` and `rehab_spend_log` tables via Supabase REST
2. Add `--save` flag to persist forecast results to `rehab_projects`
3. Add `update-spend` subcommand to log expenses to `rehab_spend_log`
4. Wire `stage_history()` to actually query historical data with repair costs

### P1 — Enricher Integration
5. Accept enricher output as input — pull ARV, assessed value, owner info
6. Cross-reference BCPAO building data for sqft, year built, construction type
7. Auto-select template based on BCPAO condition/age data

### P2 — Report Generation
8. DOCX report output with budget vs actual charts
9. Weekly digest email/Telegram with active project alerts

### P3 — Advanced
10. Permit cost cross-reference (from enricher permits stage)
11. Material price tracking for lumber, concrete, steel in FL market

## CLI Quick Reference

```bash
# Basic forecast
python3 -m forecaster.agent forecast --budget 85000 --template medium_rehab --json

# With parcel (pulls sqft from BCPAO) and ARV
python3 -m forecaster.agent forecast --budget 85000 --parcel "25-37-22-00-00123.0-0000.00" --arv 280000 --json

# With spend log
python3 -m forecaster.agent forecast --budget 85000 --spend-csv spend.csv --start 2026-01-15 --weeks 12 --json

# Historical query
python3 -m forecaster.agent history --type medium_rehab --zip 32937 --last 20

# Status
python3 -m forecaster.agent status
```
