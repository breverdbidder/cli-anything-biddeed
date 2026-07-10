---
name: market-trend-predictor
description: Monitor rent comps, days on market, and supply pipeline data to predict market direction and optimal timing windows
version: "1.0"
metadata:
  author: NextAutomation
---

# Market Trend Predictor

A market intelligence skill that continuously monitors rent comps, days on market, absorption rates, and supply pipeline data to predict where a market is heading 1-2 quarters ahead. Instead of relying on quarterly broker reports that are already stale by the time you read them, this skill synthesizes real-time signals into forward-looking predictions that drive buy/build/hold/sell decisions with confidence.

## When to Use

- Deciding whether to break ground or delay a development project
- Timing acquisitions to catch the bottom of a market cycle
- Evaluating hold vs. sell decisions for stabilized assets
- Underwriting rent growth assumptions for new deals
- Monitoring markets where you have active projects or pipeline
- Comparing multiple target markets for capital deployment priority

## Input Required

| Field | Required | Description |
|-------|----------|-------------|
| `target_market` | Yes | MSA, submarket, or specific neighborhood to analyze |
| `property_type` | Yes | Multifamily, office, retail, industrial, or mixed-use |
| `analysis_horizon` | Yes | Forward-looking period: 6mo, 12mo, 24mo |
| `current_portfolio` | No | Your existing assets in the market for context |
| `investment_thesis` | No | Development, value-add, core, or core-plus strategy |
| `benchmark_markets` | No | Comparison markets for relative analysis |

## Process

### Step 1: Rent Comp Trend Analysis

Track rental rate movements across the submarket:

| Metric | Measurement Method | Trend Signal |
|--------|-------------------|-------------|
| Effective Rent (Avg) | Trailing 3-mo weighted average | Primary demand indicator |
| Asking Rent vs. Effective | Concession gap analysis | Landlord confidence level |
| Rent Growth (MoM) | Month-over-month change | Momentum direction |
| Rent Growth (YoY) | Year-over-year change | Structural trend |
| Rent Growth Acceleration | Change in rate of change | Inflection detection |
| Rent-to-Income Ratio | Avg rent / Median household income | Affordability ceiling |
| Class A vs. B Spread | Premium gap trending | Flight to quality indicator |

Rent trend classification:

| Classification | MoM Trend | YoY Trend | Acceleration | Market Signal |
|---------------|-----------|-----------|-------------|---------------|
| Strong Growth | >0.5% | >5% | Positive | Aggressive build |
| Moderate Growth | 0.2-0.5% | 2-5% | Flat | Proceed with caution |
| Stagnant | 0-0.2% | 0-2% | Negative | Delay or value-engineer |
| Softening | Negative | Still positive | Negative | Hold/reassess pipeline |
| Declining | Negative | Negative | Negative | Exit or pause |

### Step 2: Days on Market & Absorption Tracking

Measure demand velocity and leasing momentum:

| Metric | Healthy Range | Warning Range | Critical Range |
|--------|--------------|---------------|----------------|
| Average DOM (Lease) | <30 days | 30-60 days | >60 days |
| Average DOM (Sale) | <90 days | 90-180 days | >180 days |
| Net Absorption (Monthly) | >0.5% of stock | 0-0.5% of stock | Negative |
| Absorption Trend (3-mo) | Accelerating | Flat | Decelerating |
| Pre-leasing Velocity | >50% at delivery | 25-50% at delivery | <25% at delivery |
| Lease Renewal Rate | >60% | 40-60% | <40% |

### Step 3: Supply Pipeline Intelligence

Monitor new construction and deliveries that will compete with your project:

| Pipeline Stage | Timeframe to Impact | Data Source | Risk Level |
|---------------|--------------------|-----------  |------------|
| Proposed/Entitled | 24-36 months | Planning departments | Low (many don't proceed) |
| Permitted | 18-24 months | Building departments | Medium |
| Under Construction | 6-18 months | Dodge/CoStar/field surveys | High |
| Delivering (next 6mo) | 0-6 months | Developer announcements | Immediate |
| Recently Delivered | Leasing up now | Listing sites | Active competition |

Supply-demand equilibrium score:

| Months of Supply | Market Condition | Action Guidance |
|-----------------|------------------|-----------------|
| <12 months | Undersupplied | Green light — build now |
| 12-18 months | Balanced | Proceed with differentiation |
| 18-24 months | Cautiously supplied | Delay or value-engineer |
| 24-36 months | Oversupplied | Hold — wait for absorption |
| >36 months | Significantly oversupplied | Exit or pivot asset type |

### Step 4: Leading Indicator Synthesis

Combine economic and demographic signals that predict market direction:

| Leading Indicator | Lead Time | Weight | Data Source |
|-------------------|-----------|--------|-------------|
| Building Permit Filings | 18-24 months | 15% | Census/local departments |
| Employment Announcements | 12-18 months | 20% | BLS/press releases |
| Migration Data (Net) | 6-12 months | 15% | USPS/Census/U-Haul index |
| Interest Rate Trajectory | 3-6 months | 15% | Fed futures/SOFR curve |
| Consumer Confidence | 3-6 months | 10% | Conference Board |
| Google Search Trends | 1-3 months | 10% | "apartments in [city]" |
| Local Policy Changes | Variable | 15% | City council/zoning changes |

### Step 5: Cycle Position Mapping

Determine where the market sits in the real estate cycle:

| Cycle Phase | Characteristics | Typical Duration | Strategy |
|-------------|----------------|------------------|----------|
| Recovery | Rising occupancy, flat rents, no new supply | 1-3 years | Buy aggressively |
| Expansion | Rising rents, new construction starts, strong demand | 2-4 years | Build and acquire |
| Hyper Supply | Deliveries exceed absorption, vacancy rising | 1-2 years | Sell or hold stabilized |
| Recession | Falling rents, negative absorption, distress | 1-2 years | Position for next recovery |

Transition signals between phases:

| Transition | Key Signal | Confirmation Signal |
|-----------|-----------|-------------------|
| Recovery → Expansion | Rent growth exceeds inflation | New construction starts accelerating |
| Expansion → Hyper Supply | Permits exceed 5-year avg by >40% | Absorption rate declining |
| Hyper Supply → Recession | Negative net absorption 2+ quarters | Concessions exceeding 2 months |
| Recession → Recovery | Permits drop >50% from peak | Occupancy stabilizes/ticks up |

### Step 6: Prediction & Confidence Scoring

Generate forward-looking projections with confidence intervals:

| Prediction Output | Method | Confidence Range |
|-------------------|--------|------------------|
| Rent Growth (next 12mo) | Regression + leading indicators | +/- 1.5% at 80% confidence |
| Vacancy Direction | Absorption vs. delivery modeling | Directional (up/down/flat) |
| Optimal Entry Timing | Cycle position + rate trajectory | Quarter-level precision |
| Comp Set Performance | Peer group benchmarking | Relative ranking |
| Risk Events | Scenario probability weighting | High/medium/low likelihood |

## Output Format

The skill produces a Market Trend Report containing:

1. **Market Pulse** - Current status snapshot with trend direction arrows
2. **Rent Forecast** - 6/12/24-month rent growth projections with ranges
3. **Supply-Demand Score** - Equilibrium assessment with months of supply
4. **Cycle Position Map** - Where the market sits and where it's heading
5. **Leading Indicator Dashboard** - Early warning signals with confidence
6. **Timing Recommendation** - Buy/build/hold/sell guidance with rationale
7. **Comp Market Comparison** - Relative ranking against benchmark markets
8. **Risk Calendar** - Upcoming events that could shift the market

## Methodology

This skill employs the **SIGNAL Framework**:

- **S**upply pipeline quantification
- **I**ncome and rent trajectory analysis
- **G**rowth indicators (jobs, population, permits)
- **N**et absorption and demand velocity
- **A**ffordability ceiling assessment
- **L**eading indicator synthesis

Each signal is scored on a -10 to +10 scale and combined with configurable weights to produce the composite Market Direction Score. Scores above +5 indicate strong tailwinds; -5 to +5 is neutral; below -5 signals headwinds.

## Advanced Configuration

| Parameter | Default | Options | Description |
|-----------|---------|---------|-------------|
| `data_freshness` | `30_days` | 7, 14, 30, 60, 90 days | Maximum age of data used in analysis |
| `prediction_model` | `ensemble` | regression, arima, ensemble, ml | Forecasting algorithm |
| `confidence_level` | `80%` | 70, 80, 90, 95% | Prediction interval width |
| `cycle_model` | `mueller` | mueller, pyhrr, custom | Real estate cycle framework |
| `comparison_depth` | `3_markets` | 1, 3, 5, 10 markets | Number of benchmark markets |
| `alert_sensitivity` | `medium` | low, medium, high | How quickly trend changes trigger alerts |

## Example

### Input
```
target_market: Nashville, TN - Midtown/Gulch
property_type: Multifamily
analysis_horizon: 12mo
investment_thesis: Development
benchmark_markets: Austin TX, Charlotte NC, Raleigh NC
```

### Output
```
MARKET TREND REPORT
====================

Market Pulse: CAUTIOUSLY OPTIMISTIC
Direction Score: +3.2/10 (Mild Tailwind)
Cycle Position: Late Expansion → approaching Hyper Supply

Rent Forecast (12-month):
- Effective Rent (current): $1,842/unit
- Projected (12mo): $1,895-$1,935/unit
- Growth Estimate: 2.9-5.0% (base: 3.8%)
- Confidence: 78%

Supply-Demand:
- Current Vacancy: 5.8% (up from 4.2% YoY)
- Net Absorption (trailing 12mo): 4,200 units
- Pipeline (delivering next 18mo): 6,800 units
- Months of Supply: 19.4 (CAUTIOUSLY SUPPLIED)

Key Signals:
[+] Job growth: +3.1% YoY (healthcare, tech)
[+] Net migration: +18,000 residents (trailing 12mo)
[+] Rent-to-income: 28.4% (room to grow)
[-] Pipeline: 6,800 units = 2.8% of existing stock
[-] Vacancy trending: +160bps YoY
[-] Concessions appearing in Class A (0.5-1.0 month)

vs. Benchmark Markets:
                Nashville   Austin    Charlotte   Raleigh
Direction Score:  +3.2       +1.8      +4.6        +5.1
Vacancy Trend:    Rising     Rising    Stable      Stable
Rent Growth:      3.8%       2.1%      4.2%        5.0%
Supply Risk:      Medium     High      Low         Low

TIMING RECOMMENDATION: PROCEED WITH CAUTION
- If breaking ground now: Target Class B+ product ($1,600-$1,900)
- Avoid Class A luxury — concession pressure ahead
- Deliver by Q2 2027 to beat the pipeline wave
- Consider Charlotte or Raleigh for better risk-adjusted entry
- Monitor: if vacancy hits 7.5%, pause and reassess
```

## Edge Cases & Best Practices

**New Submarket Formation**: When a previously undeveloped submarket is emerging (e.g., new transit stop), historical data is limited. Weight leading indicators (permits, infrastructure investment, employer commitments) heavily and use comparable submarket emergence patterns.

**Post-Pandemic Anomalies**: Remote work has permanently shifted some demand patterns. For markets with high tech/remote-worker migration, apply a structural demand adjustment rather than mean-reverting to pre-2020 trends.

**Supply Shock Events**: Natural disasters, sudden employer relocations, or policy changes (rent control, zoning overhaul) can invalidate trend extrapolations. Monitor risk event calendars and apply scenario-based adjustments.

**Micro vs. Macro Divergence**: A submarket can outperform a weak MSA or underperform a strong one. Always analyze at the submarket level, even when MSA-level data looks favorable.

## Integration

**Feeds into:** Property Profile Enricher (valuation context), Cost Forecaster (timing decisions), Project Tracker (market risk updates)

**Receives from:** MLS data feeds, CoStar/REIS, Census data, BLS employment data, permit databases
