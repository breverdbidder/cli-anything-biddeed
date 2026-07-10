---
name: cost-forecaster
description: Analyze historical project data and current spend velocity to forecast costs and flag overruns before they impact margins
version: "1.0"
metadata:
  author: NextAutomation
---

# Cost Forecaster

A predictive cost analysis skill that reads historical project data and monitors current spend velocity to forecast total project costs and flag overruns before they wreck your margins. Instead of discovering budget blowouts at month-end reconciliation, this skill provides continuous forward-looking cost projections with early warning alerts, giving you weeks of lead time to course-correct.

## When to Use

- Monitoring active construction projects for budget compliance
- Evaluating mid-project cost-to-complete estimates
- Comparing actual spend against pro forma assumptions during development
- Identifying cost categories trending toward overruns
- Preparing for lender draw requests with current projections
- Assessing contractor performance against budgeted line items

## Input Required

| Field | Required | Description |
|-------|----------|-------------|
| `project_budget` | Yes | Original approved budget with line-item breakdown |
| `spend_to_date` | Yes | Actual costs incurred by category through current period |
| `project_timeline` | Yes | Start date, projected completion, current phase |
| `draw_schedule` | No | Lender draw history and upcoming milestones |
| `change_orders` | No | Approved and pending change orders with amounts |
| `historical_projects` | No | Past project data for pattern matching (improves accuracy) |
| `alert_threshold` | No | Percentage variance that triggers an alert. Default: 5% |

## Process

### Step 1: Spend Velocity Analysis

Calculate current burn rate and project forward:

| Metric | Calculation | Signal |
|--------|-------------|--------|
| Daily Burn Rate | Total spend ÷ Calendar days elapsed | Baseline velocity |
| Weekly Burn Rate | Rolling 4-week average spend | Short-term trend |
| Category Burn Rate | Per-category spend ÷ Category timeline | Granular velocity |
| Acceleration Factor | Current week rate ÷ 4-week average | Speeding up or slowing |
| Completion Velocity | % budget spent ÷ % timeline elapsed | Ahead/behind pace |
| Earned Value Ratio | Work completed value ÷ Actual cost | Efficiency indicator |

### Step 2: Historical Pattern Matching

Compare current project trajectory against similar completed projects:

| Pattern Factor | Comparison Method | Adjustment Applied |
|---------------|-------------------|-------------------|
| Project Type Match | Same asset class (multifamily, office, etc.) | Weight by similarity |
| Geographic Adjustment | Same MSA or region | Local cost index factor |
| Scale Normalization | Similar total budget range (+/- 30%) | Per-SF or per-unit basis |
| Timeline Stage | Same % complete milestone | Phase-specific patterns |
| Season Alignment | Same construction months | Weather/productivity factor |
| Market Conditions | Similar interest rate and material cost environment | Inflation adjustment |

Typical cost trajectory patterns by phase:

| Project Phase | % of Budget | Common Overrun Risk | Historical Variance |
|---------------|-------------|--------------------|--------------------|
| Pre-construction | 5-8% | Entitlement delays, design changes | +/- 15% |
| Foundation/Site | 10-15% | Soil conditions, weather | +/- 12% |
| Structural | 25-35% | Material price escalation, labor | +/- 8% |
| MEP Rough-in | 15-20% | Coordination conflicts, code changes | +/- 10% |
| Finishes | 15-20% | Selection upgrades, punch list scope | +/- 12% |
| Close-out | 3-5% | Punch list creep, warranty items | +/- 20% |

### Step 3: Category-Level Forecasting

Project remaining costs for each budget line item:

| Category | Forecast Method | Confidence Factors |
|----------|----------------|-------------------|
| Hard Costs - Labor | Velocity × remaining duration, adjusted for crew changes | Crew stability, weather forecast |
| Hard Costs - Materials | Committed POs + spot price forecast for uncommitted | % locked via contracts |
| Hard Costs - Subcontractors | Contract values + approved COs + pending CO estimate | Contract type (GMP vs. T&M) |
| Soft Costs - Architecture | Contract burn rate projection | Remaining deliverables count |
| Soft Costs - Legal | Historical pattern + known upcoming activity | Transaction phase |
| Soft Costs - Permits/Fees | Fixed schedule + escalation | Government processing timelines |
| Contingency | Remaining contingency - projected draws | Risk register items |
| Financing Costs | Rate × outstanding balance × remaining months | Rate lock status |

### Step 4: Overrun Detection & Severity Assessment

Flag categories exceeding thresholds with impact analysis:

| Severity Level | Threshold | Response Protocol | Timeline Impact |
|---------------|-----------|-------------------|----------------|
| Watch | 3-5% over pace | Monitor weekly, no action needed | Minimal |
| Warning | 5-10% over pace | Identify root cause, prepare mitigation | 1-2 week delay risk |
| Alert | 10-15% over pace | Immediate review, implement mitigation | 2-4 week delay risk |
| Critical | >15% over pace | Stop work evaluation, reforecast required | Major schedule impact |

For each flagged category, calculate:
- Projected overrun amount (dollars)
- Margin impact (basis points on project ROI)
- Contingency erosion rate
- Estimated date contingency is exhausted at current pace

### Step 5: Scenario Modeling

Generate three cost-to-complete scenarios:

| Scenario | Assumption | Use Case |
|----------|-----------|----------|
| Best Case | Current issues resolved, no new problems | LP optimistic reporting |
| Base Case | Current trajectory continues with historical adjustment | Primary planning number |
| Worst Case | Known risks materialize, contingency fully consumed | Stress test / lender scenario |

Each scenario includes:
- Total cost at completion
- Variance from original budget ($ and %)
- Impact on project IRR and equity multiple
- Contingency remaining at completion
- Cash flow timing changes

### Step 6: Mitigation Recommendations

Generate actionable cost reduction strategies ranked by impact:

| Strategy Type | Typical Savings | Implementation Speed | Risk Level |
|---------------|----------------|---------------------|------------|
| Value Engineering | 5-15% of affected category | 2-4 weeks | Low |
| Scope Reduction | 3-10% of total hard costs | 1-2 weeks | Medium |
| Procurement Rebid | 5-20% of specific trades | 4-8 weeks | Medium |
| Schedule Acceleration | Avoid escalation costs | Immediate | High |
| Phased Delivery | Defer non-critical scope | 1-2 weeks | Low |
| Contingency Reallocation | Redirect from low-risk categories | Immediate | Medium |

## Output Format

The skill produces a Cost Forecast Report containing:

1. **Executive Dashboard** - Budget vs. actual snapshot with forecast at completion
2. **Velocity Charts** - Burn rate trends by category with projections
3. **Overrun Alerts** - Flagged categories with severity, cause, and mitigation
4. **Scenario Comparison** - Best/base/worst case cost-to-complete
5. **Margin Impact Analysis** - How overruns affect project ROI and LP returns
6. **Contingency Status** - Remaining contingency and projected draw schedule
7. **Action Items** - Prioritized mitigation recommendations with dollar impact

## Methodology

This skill applies the **FORECAST Framework**:

- **F**requency analysis of spend patterns
- **O**utlier detection in cost categories
- **R**egression modeling against historical projects
- **E**arned value performance indexing
- **C**ontingency burn rate tracking
- **A**lert threshold monitoring
- **S**cenario stress testing
- **T**rend extrapolation with seasonal adjustment

Forecasts are updated with each new data input. Accuracy improves as the project progresses — typically within 3% at 50% completion and 1.5% at 75% completion.

## Advanced Configuration

| Parameter | Default | Options | Description |
|-----------|---------|---------|-------------|
| `forecast_model` | `blended` | velocity, historical, earned_value, blended | Primary forecasting method |
| `alert_threshold` | `5%` | 2-15% | Category overrun percentage that triggers alerts |
| `update_frequency` | `weekly` | daily, weekly, biweekly, monthly | How often to regenerate forecast |
| `historical_weight` | `30%` | 0-60% | How much historical project data influences forecast |
| `contingency_alert` | `50%` | 25-75% | Alert when contingency drops below this % remaining |
| `scenario_count` | `3` | 3, 5, 7 | Number of cost scenarios to generate |

## Example

### Input
```
project_budget:
  total: $18,500,000
  hard_costs: $14,200,000
  soft_costs: $2,800,000
  contingency: $1,500,000

spend_to_date:
  hard_costs: $7,850,000 (Month 8 of 14)
  soft_costs: $1,920,000
  contingency_used: $380,000

project_timeline:
  start: 2025-06-01
  projected_completion: 2026-08-01
  current_phase: Structural (70% complete)

change_orders:
  approved: $420,000 (3 COs)
  pending: $185,000 (2 COs)
```

### Output
```
COST FORECAST REPORT
====================

Budget vs. Actual (Month 8 of 14):
- Budget to Date: $9,700,000
- Actual to Date: $10,150,000 (including $380K contingency)
- Variance: +$450,000 (4.6%)

Spend Velocity:
- Budgeted Monthly Burn: $1,321,000
- Actual Monthly Burn (4-wk avg): $1,485,000
- Acceleration Factor: 1.12x (TRENDING UP)
- Earned Value Ratio: 0.94 (spending 6% more than earning)

OVERRUN ALERTS:
[WARNING] Structural Steel: +8.2% over pace
  - Root Cause: Steel price escalation (+12% since bid)
  - Projected Overrun: $340,000
  - Margin Impact: -45 bps on project IRR
  - Mitigation: Lock remaining steel orders NOW

[WATCH] Electrical Rough-in: +4.1% over pace
  - Root Cause: Design coordination RFIs
  - Projected Overrun: $95,000
  - Action: Monitor next 2 weeks

Forecast at Completion:
                    Best Case    Base Case    Worst Case
Total Cost:         $19,020,000  $19,480,000  $20,250,000
vs. Budget:         +$520,000    +$980,000    +$1,750,000
Variance:           +2.8%        +5.3%        +9.5%
Contingency Left:   $980,000     $520,000     ($250,000)
Project IRR Impact: -25 bps      -65 bps      -140 bps

PRIORITY ACTIONS:
1. Lock steel POs for remaining phases ($340K savings potential)
2. Resolve 4 open MEP coordination RFIs this week
3. Request GC updated cost-to-complete by Friday
4. Review pending COs ($185K) — approve or reject by EOM
5. Schedule VE session for interior finishes (Phase starts Month 10)
```

## Edge Cases & Best Practices

**Early Stage Projects**: Before 30% completion, historical pattern matching provides more reliable forecasts than velocity analysis. Weight historical data heavier and apply wider confidence intervals.

**Change Order Heavy Projects**: When approved COs exceed 5% of original budget, reset the baseline budget and recalculate all velocity metrics against the revised number. Otherwise alerts become meaningless.

**Multi-Phase Developments**: For projects delivered in phases, run separate forecasts for each phase but aggregate for total portfolio view. Phase 1 actuals should inform Phase 2+ forecasts.

**GMP Contracts**: When working under a GMP, track the contractor's contingency separately from owner contingency. GMP savings sharing provisions affect final cost significantly.

## Integration

**Feeds into:** Project Tracker, Site Manager, Deal Structure Optimizer

**Receives from:** Property Profile Enricher, contractor invoices, lender draw data, accounting system exports
