# CLAUDE.md — Project Status Tracker

> Harness: `cli-anything-biddeed/projecttracker/`
> Origin: Forked from NextAutomation Project Tracker v1.0
> Owner: Ariel Shapira — BidDeed.AI + ZoneWise.AI

## What This Is

**THE INVESTOR-READY PROJECT STATUS REPORT ENGINE.** After BidDeed.AI wins at auction, Forecaster budgets the rehab, Site Manager tracks progress — Project Tracker compiles everything into weekly status reports for internal use, LP/investors, lenders, and executive dashboards.

NOT for commercial 42-unit construction. This generates reports for $25K-$250K residential rehab projects in Brevard County.

## Pipeline

```
BUDGET → MILESTONE → SUBRATING → CHANGES → CASHFLOW → REPORT
```

| Stage | Status | What It Does |
|-------|--------|-------------|
| BUDGET | ✅ Working | Budget vs actual from rehab_spend_log, CPI, contingency tracking |
| MILESTONE | ✅ Working | Phase completion from sitemanager, schedule health |
| SUBRATING | ✅ Working | Weighted sub scoring (schedule/budget/quality/safety/comms/staffing) |
| CHANGES | ✅ Working | Change order tracking, aging analysis, trend detection |
| CASHFLOW | ✅ Working | Draw status, equity tracking, net position for hard money lenders |
| REPORT | ✅ Working | Composite health 0-100, audience-formatted, auto action items |

## Health Score Formula

```
project_health = budget_score(35%) + schedule_score(35%) + sub_avg(20%) + co_penalty(10%)
```

| Health | Score | Label |
|--------|-------|-------|
| Green | 80-100 | ON_TRACK |
| Yellow | 60-79 | NEEDS_ATTENTION |
| Orange | 40-59 | AT_RISK |
| Red | 0-39 | CRITICAL |

## Budget Health Indicators

| Indicator | Healthy | Warning | Critical |
|-----------|---------|---------|----------|
| Budget Variance | <3% | 3-8% | >8% |
| Committed Ratio | <95% | 95-100% | >100% |
| Contingency | >60% | 30-60% | <30% |
| CPI | >0.95 | 0.85-0.95 | <0.85 |
| CO Rate | <3% | 3-7% | >7% |

## Sub Performance Tiers

| Tier | Score | Action |
|------|-------|--------|
| A | 90-100 | Preferred, fast-track payments |
| B | 75-89 | Standard management |
| C | 60-74 | Performance improvement meeting |
| D | 40-59 | Formal warning, backup plan |
| F | <40 | Notice to cure, mobilize replacement |

## Supabase Tables

### project_status_reports
```sql
CREATE TABLE IF NOT EXISTS project_status_reports (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  report_date DATE NOT NULL,
  audience TEXT DEFAULT 'internal',
  project_health_score INT,
  health_label TEXT,
  budget_health TEXT,
  schedule_status TEXT,
  overall_pct NUMERIC,
  cpi NUMERIC,
  contingency_pct NUMERIC,
  co_count INT DEFAULT 0,
  co_approved_total NUMERIC DEFAULT 0,
  sub_avg_score NUMERIC DEFAULT 0,
  action_count INT DEFAULT 0,
  risk_count INT DEFAULT 0,
  report_json JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(project_id, report_date)
);
```

### project_change_orders
```sql
CREATE TABLE IF NOT EXISTS project_change_orders (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  co_number INT NOT NULL,
  amount NUMERIC NOT NULL,
  reason TEXT,
  status TEXT DEFAULT 'pending',
  trade TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### project_draws
```sql
CREATE TABLE IF NOT EXISTS project_draws (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  draw_number INT NOT NULL,
  amount NUMERIC NOT NULL,
  status TEXT DEFAULT 'submitted',
  submitted_date DATE,
  funded_date DATE,
  issues TEXT
);
```

### project_subcontractors
```sql
CREATE TABLE IF NOT EXISTS project_subcontractors (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  trade TEXT,
  contract_value NUMERIC DEFAULT 0,
  spent NUMERIC DEFAULT 0,
  co_count INT DEFAULT 0,
  co_value NUMERIC DEFAULT 0,
  schedule_score INT DEFAULT 75,
  budget_score INT DEFAULT 75,
  quality_score INT DEFAULT 75,
  safety_score INT DEFAULT 85,
  comms_score INT DEFAULT 70,
  staffing_score INT DEFAULT 70,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### project_equity_calls
```sql
CREATE TABLE IF NOT EXISTS project_equity_calls (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  amount NUMERIC NOT NULL,
  status TEXT DEFAULT 'received',
  call_date DATE,
  received_date DATE
);
```

## Audiences

| Audience | Focus | Depth | Frequency |
|----------|-------|-------|-----------|
| internal | Action items, accountability | Full detail | Weekly |
| lp | Financial performance, timeline | High-level + budget | Monthly |
| lender | Draw compliance, collateral | Budget + progress | Per draw |
| executive | Portfolio exceptions | Exceptions only | Weekly |

## Integration

| System | Direction | Data |
|--------|-----------|------|
| Forecaster | ← reads | rehab_projects, rehab_spend_log (budget + actuals) |
| SiteManager | ← reads | rehab_site_reports (phases, health, safety) |
| BidDeed.AI | ← reads | Won auction parcel IDs |
| ZoneWise.AI web | → feeds | Portfolio dashboard data |
| Supabase | ↔ persist | All project_* tables |
| AUTOLOOP | ← tested by | 25 binary assertions |

## Priority

1. Wire Supabase tables (5 tables)
2. --save persistence for reports
3. Integrate with existing forecaster + sitemanager data
4. Telegram critical alerts (<60 health)
