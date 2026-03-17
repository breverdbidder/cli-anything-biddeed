---
name: project-tracker
description: Generate weekly project status reports covering budget vs actual, milestone tracking, and subcontractor performance
version: "1.0"
metadata:
  author: NextAutomation
---

# Project Tracker

An automated project reporting skill that generates comprehensive weekly status reports covering budget vs. actual spend, milestone tracking, and subcontractor performance — without touching a spreadsheet. This skill pulls data from multiple sources, normalizes it, identifies variances, scores contractor performance, and delivers investor-ready reports that would normally take a project manager 3-4 hours to compile manually.

## When to Use

- Generating weekly or biweekly project status reports for stakeholders
- Preparing LP/investor update packages with current project metrics
- Tracking subcontractor performance for retention and future selection
- Compiling budget variance reports for lender draw documentation
- Monitoring multiple projects across a development portfolio
- Creating executive dashboards for investment committee meetings

## Input Required

| Field | Required | Description |
|-------|----------|-------------|
| `project_data` | Yes | Budget, schedule, and scope baseline for the project |
| `financial_actuals` | Yes | Current period costs by category, vendor, and cost code |
| `schedule_status` | Yes | Activity completion percentages and actual dates |
| `contractor_data` | No | Sub contracts, change orders, RFIs, and payment history |
| `prior_reports` | No | Previous period reports for trend comparison |
| `reporting_period` | No | Date range for the report. Default: trailing 7 days |
| `audience` | No | LP, lender, internal, or executive. Default: internal |

## Process

### Step 1: Budget vs. Actual Compilation

Aggregate financial data and calculate variances at every level:

| Budget Level | Metrics Calculated | Variance Analysis |
|-------------|-------------------|-------------------|
| Total Project | Budget, committed, spent, forecast | $ and % variance from baseline |
| Division (CSI) | Hard costs, soft costs, contingency, financing | Per-division tracking |
| Cost Code | Individual line items (030 Concrete, 050 Steel, etc.) | Line-item granularity |
| Vendor/Sub | Per-contractor spend vs. contract value | Contract performance |
| Period | This week vs. last week vs. budget per period | Spend pacing |

Budget health indicators:

| Indicator | Formula | Healthy | Warning | Critical |
|-----------|---------|---------|---------|----------|
| Budget Variance | (Actual - Budget) / Budget | <3% | 3-8% | >8% |
| Committed vs. Budget | Total commitments / Total budget | <95% | 95-100% | >100% |
| Contingency Remaining | Contingency left / Original contingency | >60% | 30-60% | <30% |
| Cost Performance Index | Earned Value / Actual Cost | >0.95 | 0.85-0.95 | <0.85 |
| Change Order Rate | CO value / Original contract | <3% | 3-7% | >7% |

### Step 2: Milestone Progress Tracking

Map current status against project milestones:

| Milestone Category | Tracking Method | Status Classification |
|-------------------|----------------|----------------------|
| Permitting | Submission dates, review cycles, approval | On Track / Delayed / At Risk |
| Construction Phases | % complete vs. schedule | Ahead / On Track / Behind |
| Inspections | Pass/fail/resubmit tracking | Complete / Pending / Failed |
| Lender Milestones | Draw schedule, completion tests | Met / Approaching / Missed |
| Lease-up | Pre-leasing velocity, occupancy targets | Above / At / Below target |
| Closeout | Punch list, TCO, final inspections | On Track / Delayed |

Milestone dashboard format:

| Milestone | Planned Date | Forecast Date | Variance | Status | Notes |
|-----------|-------------|---------------|----------|--------|-------|
| Foundation Complete | 2025-10-15 | 2025-10-15 | 0 days | Complete | ✓ |
| Structural Topping | 2026-01-20 | 2026-01-28 | +8 days | Complete | Weather delay |
| MEP Rough Complete | 2026-03-15 | 2026-03-22 | +7 days | At Risk | HVAC crew issues |
| Drywall Complete | 2026-04-10 | 2026-04-20 | +10 days | Behind | Cascading from MEP |
| TCO | 2026-07-01 | 2026-07-15 | +14 days | At Risk | Dependent on recovery |
| Stabilization | 2026-12-01 | 2026-12-15 | +14 days | On Track | Pre-leasing strong |

### Step 3: Subcontractor Performance Scoring

Rate each subcontractor across multiple dimensions:

| Performance Dimension | Weight | Scoring Criteria | Score Range |
|----------------------|--------|-----------------|-------------|
| Schedule Compliance | 25% | On-time activity completion rate | 0-100 |
| Budget Compliance | 20% | Actual vs. contracted, CO frequency | 0-100 |
| Quality of Work | 20% | Inspection pass rate, punch list items | 0-100 |
| Safety Record | 15% | Incidents, violations, near-misses | 0-100 |
| Communication | 10% | RFI response time, meeting attendance | 0-100 |
| Staffing Reliability | 10% | Crew count vs. committed, consistency | 0-100 |

Performance tier classification:

| Tier | Score | Implication | Action |
|------|-------|-------------|--------|
| A - Excellent | 90-100 | Preferred for future projects | Recognize, fast-track payments |
| B - Good | 75-89 | Reliable performer | Standard management |
| C - Acceptable | 60-74 | Needs improvement | Performance improvement meeting |
| D - Below Standard | 40-59 | At risk of default | Formal warning, backup plan |
| F - Unacceptable | <40 | Contract jeopardized | Notice to cure, mobilize replacement |

Subcontractor scorecard format:

| Subcontractor | Trade | Contract | Spent | COs | Schedule | Quality | Safety | Overall |
|---------------|-------|----------|-------|-----|----------|---------|--------|---------|
| ABC Electric | Electrical | $1.2M | $680K | 2 ($45K) | 88 | 92 | 95 | 90 (A) |
| MidSouth HVAC | Mechanical | $1.8M | $1.1M | 4 ($120K) | 62 | 78 | 85 | 72 (C) |
| Premier Drywall | Drywall | $890K | $410K | 1 ($15K) | 85 | 88 | 90 | 87 (B) |

### Step 4: Change Order & RFI Analysis

Track and analyze change orders and information requests:

| CO/RFI Metric | Calculation | Benchmark |
|---------------|-------------|-----------|
| Total COs (Count) | Cumulative approved + pending | <15 per $10M in hard costs |
| Total COs (Value) | Sum of approved CO amounts | <5% of contract value |
| CO Trend | Weekly/monthly CO rate | Declining = healthy |
| Pending COs | Unresolved COs by age | Resolve within 14 days |
| RFI Count | Cumulative RFIs filed | Track by trade for patterns |
| RFI Response Time | Average days to respond | <5 business days |
| RFI-to-CO Conversion | % of RFIs that become COs | <15% is healthy |

### Step 5: Cash Flow & Draw Status

Track project cash position and lender draw compliance:

| Cash Flow Element | Current Period | Cumulative | Forecast |
|-------------------|---------------|------------|----------|
| Sources (Loan Draws) | Funds received this period | Total drawn to date | Remaining loan balance |
| Sources (Equity Calls) | Equity contributed | Total equity invested | Future calls needed |
| Uses (Hard Costs) | Period payments | Cumulative hard costs | Remaining hard costs |
| Uses (Soft Costs) | Period payments | Cumulative soft costs | Remaining soft costs |
| Uses (Interest Reserve) | Period interest | Cumulative interest | Reserve remaining |
| Net Position | Period surplus/deficit | Cumulative position | Projected at completion |

Draw schedule tracking:

| Draw # | Submitted | Amount | Status | Days to Fund | Issues |
|--------|-----------|--------|--------|-------------|--------|
| Draw 7 | 03/01 | $1,240,000 | Funded 03/10 | 9 days | None |
| Draw 8 | 03/15 | $1,180,000 | Under Review | Pending | Inspector scheduling |

### Step 6: Report Assembly & Distribution

Compile all analyses into audience-appropriate formats:

| Audience | Report Format | Detail Level | Frequency |
|----------|--------------|-------------|-----------|
| Internal Team | Full dashboard with action items | Maximum detail | Weekly |
| LP/Investors | Executive summary with financials | High-level + budget detail | Monthly |
| Lender | Draw package with compliance metrics | Budget + progress focused | Per draw |
| Executive/IC | Portfolio summary with exceptions | Exceptions only | Weekly |

## Output Format

The skill produces a Project Status Report containing:

1. **Executive Summary** - One-paragraph project health overview
2. **Budget Dashboard** - Budget vs. actual with variance analysis and CPI
3. **Milestone Tracker** - Visual timeline with status indicators
4. **Subcontractor Scorecards** - Performance ratings by trade
5. **Change Order Log** - Approved, pending, and trending analysis
6. **Cash Flow Statement** - Sources, uses, and draw schedule status
7. **Risk Register** - Updated risks with probability, impact, and mitigation
8. **Action Items** - Prioritized tasks with owners and deadlines
9. **Photo Documentation** - Progress photos with annotations (if provided)

## Methodology

This skill applies the **REPORT Framework**:

- **R**econcile financial data across all sources
- **E**valuate schedule performance against baseline
- **P**erformance-score all subcontractors objectively
- **O**utline change orders and their budget impact
- **R**isk assessment and mitigation tracking
- **T**rend analysis comparing period-over-period

Reports are designed to be decision-ready — every section ends with what action is needed, not just what happened.

## Advanced Configuration

| Parameter | Default | Options | Description |
|-----------|---------|---------|-------------|
| `report_format` | `internal` | internal, lp, lender, executive | Audience-specific formatting |
| `variance_threshold` | `5%` | 2-15% | Minimum variance to highlight |
| `sub_score_weights` | `balanced` | balanced, schedule_heavy, quality_heavy, custom | Performance scoring emphasis |
| `trend_periods` | `4` | 2-12 | Number of prior periods for trend analysis |
| `co_aging_alert` | `14_days` | 7, 14, 21, 30 days | Alert for unresolved change orders |
| `portfolio_mode` | `false` | true, false | Aggregate multiple projects into one report |

## Example

### Input
```
project_data:
  name: Nashville Midtown 42-Unit
  total_budget: $18,500,000
  start_date: 2025-06-01
  target_completion: 2026-08-01

financial_actuals:
  period: 2026-03-10 to 2026-03-16
  period_spend: $485,000
  cumulative_spend: $12,320,000

schedule_status:
  overall_completion: 62%
  scheduled_completion: 67%

reporting_period: 2026-03-10 to 2026-03-16
audience: lp
```

### Output
```
PROJECT STATUS REPORT — LP UPDATE
===================================
Nashville Midtown 42-Unit | Week of March 10-16, 2026

EXECUTIVE SUMMARY:
Project is 62% complete against a 67% scheduled target,
representing a 5% schedule variance primarily driven by
HVAC subcontractor staffing issues in Building A. Budget
is tracking at 103.8% of plan with $520K in approved change
orders. Contingency reserves remain adequate at 64%. Pre-
leasing interest is strong at 35% for Q3 2026 delivery.

BUDGET DASHBOARD:
                        Budget        Actual       Variance
Hard Costs:          $14,200,000   $9,850,000       —
Soft Costs:           $2,800,000   $1,920,000       —
Contingency:          $1,500,000    ($380,000)      —
Change Orders:                 —     $520,000       —
TOTAL:               $18,500,000  $12,320,000       —

Forecast at Completion: $19,180,000 (+3.7%)
Contingency Remaining: $960,000 (64% of original)
Cost Performance Index: 0.94

MILESTONE STATUS:
✓ Foundation Complete (10/15) — ON TIME
✓ Structural Complete (01/28) — 8 DAYS LATE
→ MEP Rough-in (03/15 target) — 7 DAYS BEHIND
  Drywall Complete (04/10 target) — 10 DAYS BEHIND (cascade)
  TCO (07/01 target) — AT RISK (+14 days)
  Stabilization (12/01 target) — ON TRACK

TOP SUBCONTRACTOR PERFORMANCE:
1. ABC Electric — 90/100 (A) — Excellent
2. Premier Drywall — 87/100 (B) — Good
3. Thompson Plumbing — 84/100 (B) — Good
4. MidSouth HVAC — 72/100 (C) — NEEDS IMPROVEMENT
   ↳ Chronic understaffing, 4 change orders ($120K)

CHANGE ORDERS THIS PERIOD:
- CO #12: Electrical panel upgrade (code change) — $28,000 (Approved)
- CO #13: Additional soil export (unforeseen) — $15,000 (Pending)

RISKS & MITIGATIONS:
1. [HIGH] HVAC schedule recovery — Demanding full crew by 03/17
2. [MED] Material escalation on finishes — Locking prices this week
3. [LOW] Pre-leasing pace — Currently ahead of pro forma

NEXT DRAW:
Draw #8: $1,180,000 submitted 03/15 — Under lender review
Expected funding: 03/24 (9 business days)
```

## Edge Cases & Best Practices

**Data Gaps**: When contractor invoices are late or incomplete, project the missing data based on historical patterns and clearly mark estimates. Update actuals when real data arrives and note the adjustment.

**Portfolio Reporting**: When tracking 3+ projects, generate individual project reports plus a portfolio-level executive summary that ranks projects by health score and highlights only exceptions requiring attention.

**Audience Adaptation**: LP reports should emphasize financial performance and timeline confidence. Lender reports should emphasize draw compliance and collateral protection. Internal reports should emphasize action items and accountability.

**Period-End Adjustments**: Monthly close often shifts numbers from weekly snapshots. Build in a reconciliation step at each month-end and note any significant adjustments from weekly to monthly figures.

## Integration

**Feeds into:** LP quarterly reports, lender draw packages, IC dashboards

**Receives from:** Cost Forecaster, Site Manager, accounting systems, schedule updates, contractor payment applications
