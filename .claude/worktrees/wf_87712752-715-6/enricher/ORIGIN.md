---
name: property-profile-enricher
description: Aggregate comps, liens, tax records, owner info, permits, and valuations into a single enriched property profile
version: "1.0"
metadata:
  author: NextAutomation
---

# Property Profile Enricher

An automated due diligence skill that pulls data from multiple public and proprietary sources to build a complete property profile in a single pass. Instead of manually searching county records, comp databases, and permit portals one at a time, this skill aggregates owner information, liens, encumbrances, tax assessments, permit history, comparable sales, and current valuations into a structured, decision-ready report.

## When to Use

- Enriching a target property before making initial contact with the owner
- Building acquisition pipeline profiles for off-market deal sourcing
- Validating broker-provided information against public records
- Screening properties for hidden liens or encumbrances before LOI
- Compiling due diligence packets for investment committee review
- Batch-enriching property lists from skip-tracing or driving-for-dollars campaigns

## Input Required

| Field | Required | Description |
|-------|----------|-------------|
| `property_address` | Yes | Full street address including city, state, and zip |
| `parcel_id` | No | APN or parcel number if known (speeds lookup) |
| `property_type` | Yes | Residential, multifamily, commercial, industrial, land |
| `enrichment_depth` | No | Quick (owner + tax + comps), standard (+ liens + permits), deep (+ valuations + history). Default: standard |
| `comp_radius` | No | Search radius for comparable sales in miles. Default: 1.0 |
| `comp_timeframe` | No | How far back to pull comps. Default: 12 months |

## Process

### Step 1: Owner & Ownership Research

Identify current ownership structure and acquisition history:

| Data Point | Source Priority | Validation Method |
|------------|----------------|-------------------|
| Current Owner Name | County assessor → Title company | Cross-reference tax rolls |
| Ownership Type | Secretary of State / County | Entity vs. individual verification |
| Acquisition Date | Deed records | Most recent grant deed |
| Purchase Price | Transfer tax / Deed | Calculate from doc stamps if not disclosed |
| Mailing Address | Tax rolls | Skip-trace if different from property address |
| Entity Structure | SOS filings | Identify managing members / principals |
| Ownership Duration | Deed chain | Flag if >10 years (potential motivation) |

### Step 2: Tax & Assessment Analysis

Evaluate tax status and assessment trajectory:

| Metric | Calculation | Red Flag Threshold |
|--------|-------------|-------------------|
| Current Assessed Value | County assessor | >30% below market = opportunity |
| Tax Rate (Effective) | Annual tax / Assessed value | Above 2.5% = high carry cost |
| Tax Delinquency | Payment status check | Any delinquency = distress signal |
| Assessment Trend (3yr) | YoY change in assessed value | Declining = potential issue |
| Special Assessments | District overlay check | Active assessments = hidden cost |
| Exemptions Applied | Homestead / Veteran / Other | Loss of exemption = seller motivation |
| Tax Lien Status | County records | Active liens = high-priority target |

### Step 3: Lien & Encumbrance Stacking

Build complete picture of existing claims against the property:

| Lien Type | Source | Priority | Impact Assessment |
|-----------|--------|----------|-------------------|
| Mortgage(s) | County recorder | 1st/2nd position | Calculate LTV and equity position |
| Mechanic's Liens | County recorder | Super-priority in some states | Active = construction disputes |
| Tax Liens | County treasurer | Superior to mortgages | Federal vs. state vs. local |
| HOA Liens | Association records | Varies by state | Assess total exposure |
| Judgment Liens | Court records | General lien | Owner financial distress indicator |
| UCC Filings | SOS database | Equipment/inventory | Business property encumbrances |
| Lis Pendens | Court records | Pending litigation | Active lawsuits affecting title |

### Step 4: Permit & Improvement History

Trace all permitted work and identify unpermitted modifications:

| Permit Category | Data Extracted | Analysis Applied |
|-----------------|---------------|------------------|
| Building Permits | Date, scope, cost, status | Open permits = liability |
| Renovation Permits | Scope of work, contractor | Recent work = updated condition |
| Demolition Permits | Date, scope | Site readiness assessment |
| Electrical/Plumbing | Specialty permits | Infrastructure condition indicator |
| Certificate of Occupancy | Issuance date, conditions | Compliance verification |
| Code Violations | Active/resolved, severity | Outstanding = negotiation leverage |
| Zoning Variances | Granted exceptions | Existing entitlements = value add |

### Step 5: Comparable Sales Analysis

Pull and analyze recent transactions for market positioning:

| Comp Filter | Default Setting | Adjustable Range |
|-------------|----------------|------------------|
| Radius | 1.0 mile | 0.25 - 5.0 miles |
| Timeframe | 12 months | 3 - 36 months |
| Property Type Match | Same type | Expand to similar |
| Size Range | +/- 20% of subject | +/- 10-50% |
| Condition Match | Similar | All conditions |
| Minimum Comps | 5 | 3 - 15 |

For each comp, extract:
- Sale price and price per SF/unit
- Days on market
- Condition adjustments
- Seller concessions
- Financing terms (cash vs. financed)

### Step 6: Valuation Synthesis

Combine all data into actionable valuation ranges:

| Valuation Approach | Method | Weight by Property Type |
|-------------------|--------|------------------------|
| Sales Comparison | Adjusted comp average | 40% residential, 20% commercial |
| Income Approach | Cap rate × NOI | 20% residential, 50% commercial |
| Cost Approach | Land + replacement cost - depreciation | 20% all types |
| Assessed Value Ratio | Market/assessed ratio from comps | 10% all types |
| Distress Discount | Adjustment for motivation signals | 10% if signals present |

## Output Format

The skill produces a Property Enrichment Report containing:

1. **Owner Profile** - Name, entity structure, contact info, ownership duration
2. **Financial Position** - Estimated equity, loan balances, tax status
3. **Lien Stack** - Complete encumbrance summary with priority positions
4. **Permit Timeline** - All permitted activity with open/closed status
5. **Comp Analysis** - 5-10 comparable sales with adjustment grid
6. **Valuation Range** - Low/mid/high estimates with methodology breakdown
7. **Motivation Score** - 0-100 seller motivation indicator based on distress signals
8. **Action Recommendation** - Contact strategy based on owner profile and motivation

## Methodology

This skill employs the **ENRICH Framework**:

- **E**ntity and ownership resolution
- **N**otice and lien discovery
- **R**ecord aggregation from multiple sources
- **I**mprovement and permit tracing
- **C**omparable transaction analysis
- **H**olistic valuation synthesis

Each data source is cross-validated against at least one other source. Confidence scores are assigned to each data point based on source reliability and recency.

## Advanced Configuration

| Parameter | Default | Options | Description |
|-----------|---------|---------|-------------|
| `source_priority` | `public_first` | public_first, paid_first, hybrid | Data source preference order |
| `comp_adjustment` | `automatic` | automatic, manual, none | How comps are adjusted to subject |
| `lien_depth` | `standard` | quick, standard, deep | How far back to search lien records |
| `valuation_model` | `blended` | blended, income, comp, cost | Primary valuation approach |
| `batch_mode` | `false` | true, false | Enable for enriching multiple properties |
| `output_format` | `report` | report, json, csv | Output structure preference |

## Example

### Input
```
property_address: 4521 Riverside Dr, Los Angeles, CA 90039
property_type: Multifamily
enrichment_depth: deep
comp_radius: 1.5
comp_timeframe: 12
```

### Output
```
PROPERTY ENRICHMENT REPORT
===========================

Owner Profile:
- Entity: Riverside Holdings LLC (CA LLC, formed 2008)
- Principal: James T. Morrison
- Acquired: 06/2009 for $1,850,000
- Mailing: 1200 Wilshire Blvd #400, Los Angeles, CA 90017
- Ownership Duration: 16.8 years (LONG HOLD)

Financial Position:
- Estimated Current Value: $4,200,000 - $4,650,000
- Mortgage Balance (est.): $920,000 (original $1,480,000, 2009)
- Estimated Equity: $3,280,000 - $3,730,000 (78% equity)
- Tax Assessment: $2,340,000 (Prop 13 protected)
- Annual Tax: $28,600 (effective rate 1.22%)
- Tax Status: CURRENT (no delinquency)

Lien Stack:
- 1st Mortgage: ~$920K (Wells Fargo, 2009 origination)
- No mechanic's liens
- No tax liens
- No judgment liens
- CLEAN TITLE

Permit History:
- 2012: Roof replacement ($45,000) - CLOSED
- 2018: Seismic retrofit ($180,000) - CLOSED
- 2023: Plumbing repair ($12,000) - CLOSED
- No open permits, no code violations

Comparable Sales (8 comps, 1.5mi, 12mo):
- Median: $385/SF | $210,000/unit
- Range: $340-$425/SF
- Average DOM: 42 days
- Subject estimate: $4,410,000 ($392/SF)

Motivation Score: 35/100 (LOW-MODERATE)
- Long hold duration (+15 pts)
- Clean financial position (-20 pts)
- No distress signals (-15 pts)
- Prop 13 basis lock (+10 pts)
- Owner age unknown (neutral)

Recommendation: WARM APPROACH
- Lead with 1031 exchange benefits (long hold, massive basis)
- Emphasize tax-deferred wealth preservation
- Do not lead with price — owner is not distressed
```

## Edge Cases & Best Practices

**Trusts & LLCs**: When ownership is in a trust or multi-layer LLC, trace through to the actual decision-maker. Multiple entity layers often indicate sophisticated owners — adjust your outreach accordingly.

**Recently Transferred**: Properties transferred within 6 months should be flagged as unlikely acquisition targets. The exception is estate transfers, which may indicate motivated sellers.

**Data Conflicts**: When county records and third-party data disagree, default to county records and note the discrepancy. Discrepancies themselves can indicate unreported transfers or recording delays.

**Batch Processing**: When enriching 50+ properties, run in batch mode with quick depth first, then selectively upgrade promising targets to deep enrichment.

## Integration

**Feeds into:** Cost Forecaster, Market Trend Predictor, Deal Structure Optimizer

**Receives from:** Skip-tracing outputs, driving-for-dollars lists, MLS data feeds, acquisition screening pipelines
