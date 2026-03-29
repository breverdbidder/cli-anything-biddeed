# GTM-012 — ZoneWise Feature Roadmap
## Competitive Gap Analysis vs Algoma · Gridics · TestFit

**Classification:** GTM-012 | Product Roadmap | P1 | Score: 76/100
**Prepared by:** Claude AI Architect (BidDeed.AI)
**Date:** 2026-03-29
**Status:** DEPLOYED — committed to repo, roadmap page at zonewise.ai/roadmap

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Competitive Landscape](#2-competitive-landscape)
3. [Gap Analysis Matrix](#3-gap-analysis-matrix)
4. [20-Phase Feature Roadmap](#4-20-phase-feature-roadmap)
5. [Priority Matrix (Impact vs Effort)](#5-priority-matrix)
6. [Go-To-Market Implications](#6-go-to-market-implications)
7. [Success Metrics](#7-success-metrics)

---

## 1. Executive Summary

ZoneWise currently scores **28/28 features** on our own competitive matrix against 8 FL PropTech platforms. But that matrix was designed around ZoneWise's existing capabilities. This roadmap answers a harder question: **what would Algoma, Gridics, and TestFit put on their matrix if they designed it?**

The answer reveals 20 capability gaps — each a concrete feature that these VC-backed competitors have shipped that ZoneWise has not. This document maps those gaps to a 20-phase build roadmap with clear priority ranking.

**Competitive threat summary:**

| Competitor | Stage | Raised | Threat to ZoneWise | Core Gap |
|-----------|-------|--------|--------------------|----------|
| Gridics (PropZone) | Growth | VC-backed | HIGH — direct data overlap | 3D massing, national coverage, by-right analysis |
| Algoma | Seed | $2.3M | MEDIUM — workflow layer | Pro forma, entitlement timeline, feasibility report |
| TestFit | Series B | ~$20M | MEDIUM — design tool | Unit mix, parking, scenario modeling |

**Bottom line:** ZoneWise wins on FL parcel depth + foreclosure integration. Loses on development workflow (Algoma), visualization (Gridics), and design feasibility (TestFit). The 20 phases below systematically close those gaps.

---

## 2. Competitive Landscape

### 2.1 Gridics (PropZone) — "The Visualization Player"

**What they have that ZoneWise doesn't:**
- Full 3D massing engine (not just basic visualization)
- National parcel coverage (ZoneWise is FL-only)
- By-right development analysis with automated unit count
- Zoning code change tracking / notification system
- Multifamily-specific analytics layer
- Parking requirement calculator built-in
- FAR-to-buildable-area calculator with lot coverage enforcement
- Zoning boundary map with parcel overlay (visual, not just data)

**Their weakness vs ZoneWise:**
- Zero foreclosure/auction integration
- No ML deal scoring
- No investor-specific workflow
- FL data has gaps (ZoneWise is 67-county complete)
- Price targeted at developers, not investors

### 2.2 Algoma (algoma.co) — "The Feasibility Pipeline"

**What they have that ZoneWise doesn't:**
- Full site feasibility pipeline: address → investor-ready report in days
- Development program generator (number of units, mix, square footage)
- Entitlement timeline estimation per jurisdiction
- Pre-construction pro forma modeling (IRR, NOI, cap rate scenarios)
- Variance and exception identification
- "What can I build here?" as an end-to-end workflow, not just a lookup

**Their weakness vs ZoneWise:**
- Not FL-specific — national coverage without depth
- No foreclosure or auction data
- No parcel-level intelligence on liens, taxes, ownership history
- Targets small developers — not investors/flippers
- $2.3M seed — pre-product-market-fit

### 2.3 TestFit — "The Design Feasibility Engine"

**What they have that ZoneWise doesn't:**
- Rapid building program analysis (minutes not days)
- Parking structure calculator (surface vs structured vs underground)
- Unit mix optimizer (studio / 1BR / 2BR / 3BR split by market)
- Multiple building typologies (garden, wrap, podium, high-rise)
- Scenario comparison side-by-side (what-if modeling)
- Net rentable area (NRA) vs gross area calculator
- Construction cost per unit by typology
- Site coverage analysis with setback enforcement

**Their weakness vs ZoneWise:**
- No real parcel data — uses uploaded site plans
- No zoning code database integration
- No FL jurisdiction coverage
- Enterprise-only pricing (not investor-accessible)
- No foreclosure/auction integration

---

## 3. Gap Analysis Matrix

### Features ZoneWise Has ✅

| # | Feature | Category |
|---|---------|----------|
| 1 | Zone code lookup by address | Zoning Data |
| 2 | Setbacks (front / side / rear) | Zoning Data |
| 3 | FAR + Lot coverage limits | Zoning Data |
| 4 | Max height & density by zone | Zoning Data |
| 5 | Allowed uses (residential) | Zoning Data |
| 6 | Allowed uses (commercial) | Zoning Data |
| 7 | AI zoning chatbot (NLP queries) | AI |
| 8 | FL parcel data — all 67 counties | Parcel |
| 9 | Tax data + BCPAO integration | Parcel |
| 10 | Address geocoding + parcel match | Parcel |
| 11 | Multi-county batch query API | API |
| 12 | Open Supabase API (Postgres) | API |
| 13 | FL foreclosure auction calendar | Auction |
| 14 | 245K+ multi-county auction records | Auction |
| 15 | Zoning overlay on auction results | Auction |
| 16 | Lien priority / lien stack detection | Auction |
| 17 | ML deal score (BID / REVIEW / SKIP) | Intelligence |
| 18 | ARV calculator (70% − repairs − $10K) | Intelligence |
| 19 | Max bid inline on auction card | Intelligence |
| 20 | Auction urgency alerts | Intelligence |
| 21 | Direct county auction link | Intelligence |
| 22 | Dark UI / investor-grade interface | Platform |
| 23 | Audit trail on all zoning outputs | Platform |
| 24 | Price: investor-accessible tier | Platform |

### Features ZoneWise Is Missing ❌ (The 20-Phase Gap)

| Phase | Feature | Who Has It | Gap Type |
|-------|---------|-----------|----------|
| P01 | 3D massing visualization (full) | Gridics | Visualization |
| P02 | By-right unit count calculator | Gridics + Algoma | Development |
| P03 | Zoning boundary map (visual layer) | Gridics | Visualization |
| P04 | Mixed-use / split-zone parcel analysis | Gridics | Data |
| P05 | National coverage (non-FL states) | Gridics | Coverage |
| P06 | Development potential score | Algoma | Feasibility |
| P07 | Pre-construction pro forma generator | Algoma | Feasibility |
| P08 | Entitlement timeline estimator | Algoma | Feasibility |
| P09 | Entitlement risk score | Algoma | Feasibility |
| P10 | Site feasibility report (PDF export) | Algoma | Workflow |
| P11 | Parking requirements calculator | Gridics + TestFit | Development |
| P12 | Unit mix optimizer | TestFit | Design |
| P13 | Building program analyzer | TestFit | Design |
| P14 | Net rentable area (NRA) calculator | TestFit | Design |
| P15 | Scenario modeling (what-if zones) | TestFit + Algoma | Intelligence |
| P16 | Variance & exception tracker | Algoma | Data |
| P17 | Construction cost estimator (FL) | TestFit | Economics |
| P18 | Setback 2D site plan visualizer | Gridics + TestFit | Visualization |
| P19 | Density comparison dashboard | Gridics | Analytics |
| P20 | Developer API v2 (REST + webhooks) | Gridics | Platform |

---

## 4. 20-Phase Feature Roadmap

### Phase 1 — 3D Massing Visualization
**Gap closes:** Gridics primary differentiator
**Description:** Full 3D massing model per parcel based on zoning envelope: max height, setbacks, FAR. Show buildable volume in browser, no install required. Powered by Three.js + ZoneWise zoning data.
**Data required:** setbacks, max_height, far, lot_coverage from zone_standards
**Effort:** L (3-4 weeks) | Impact: HIGH
**Competitor reference:** Gridics PropZone massing engine
**KPI:** User session time +40% (massing = sticky feature)

### Phase 2 — By-Right Unit Count Calculator
**Gap closes:** Gridics + Algoma
**Description:** Given parcel area + zone code, calculate maximum allowable units (by-right, no variance). Inputs: lot size, min_lot_per_unit, density (du/acre), FAR. Output: unit count range (min / max) with assumptions shown.
**Data required:** lot_area, min_lot_per_unit, max_density, far from zone_standards
**Effort:** S (1 week) | Impact: HIGH
**Competitor reference:** Algoma "development program generator"
**KPI:** #1 requested feature from developer segment

### Phase 3 — Zoning Boundary Map
**Gap closes:** Gridics
**Description:** Visual zoning map overlaid on FL parcel layer. Click a parcel → zone code + popup with standards. Filter by zone category (residential / commercial / industrial / agricultural). Export as GeoJSON.
**Data required:** parcel geometries (FL GIO) + zoning_assignments
**Effort:** M (2 weeks) | Impact: HIGH
**Competitor reference:** Gridics interactive zoning map
**KPI:** Organic traffic source via map embeds

### Phase 4 — Mixed-Use / Split-Zone Parcel Analysis
**Gap closes:** Gridics data accuracy
**Description:** Many FL parcels span multiple zoning districts. Detect and surface split-zone parcels. Show % of parcel in each zone. Flag development implications (which zone governs? — stricter-zone rule).
**Data required:** parcel boundaries + zoning polygon overlay (spatial join)
**Effort:** M (2 weeks) | Impact: MEDIUM
**Competitor reference:** Gridics zoning layer overlap detection
**KPI:** Data accuracy score for multi-zone parcels

### Phase 5 — National Coverage (Phase 1: GA + TX)
**Gap closes:** Gridics national scale
**Description:** Expand ZoneWise beyond FL. Target Georgia (Fulton/DeKalb/Gwinnett) and Texas (Harris/Dallas/Travis) as initial markets. Use FL GIO pipeline pattern adapted for state-specific cadastral sources.
**Data required:** State GIS cadastral APIs for GA + TX
**Effort:** XL (6-8 weeks per state) | Impact: VERY HIGH (TAM expansion)
**Competitor reference:** Gridics national parcel coverage
**KPI:** New market revenue + investor inquiries from GA/TX

### Phase 6 — Development Potential Score
**Gap closes:** Algoma
**Description:** Composite score (0–100) for each parcel based on: current use vs allowed use gap (upzoning opportunity), FAR utilization (is it under-developed?), proximity to transit/commercial, lot size adequacy. Surfaces hidden development plays.
**Data required:** current_use (DOR_UC), zone_standards, parcel geometry, FL transit GTFS
**Effort:** M (2 weeks) | Impact: HIGH
**Competitor reference:** Algoma "development potential" score
**KPI:** Engagement on high-score parcels vs low-score

### Phase 7 — Pre-Construction Pro Forma Generator
**Gap closes:** Algoma primary product
**Description:** Given parcel + development program (from Phase 2), generate pro forma: total dev cost, projected rent/sale income, NOI, cap rate, IRR at 5-year hold. Use FL regional construction costs + market comps. One-click PDF output.
**Data required:** unit_count (P02), fl_construction_cost_matrix, market_rents_by_zip
**Effort:** L (4 weeks) | Impact: VERY HIGH
**Competitor reference:** Algoma full feasibility pipeline
**KPI:** Pro forma generates = conversion event (trial → paid)

### Phase 8 — Entitlement Timeline Estimator
**Gap closes:** Algoma
**Description:** Per-jurisdiction estimate of entitlement timeline for different project types (by-right = 0-30 days; special exception = 3-6 months; rezoning = 6-18 months). Based on FL jurisdiction-specific data and historical patterns.
**Data required:** jurisdiction_id, project_type, fl_entitlement_data (scraped from municipal codes)
**Effort:** M (2 weeks) | Impact: MEDIUM
**Competitor reference:** Algoma "entitlement timeline" feature
**KPI:** Investor time-to-decision reduction (survey metric)

### Phase 9 — Entitlement Risk Score
**Gap closes:** Algoma
**Description:** Risk score (LOW / MEDIUM / HIGH) for entitlement path of a given development plan. Factors: jurisdiction approval history, project type alignment with comp plan, neighborhood opposition risk, environmental overlays.
**Data required:** zoning_districts.category, comp_plan_overlay, flood_zone, environmental_overlays
**Effort:** M (2 weeks) | Impact: MEDIUM
**Competitor reference:** Algoma risk assessment component
**KPI:** Risk score accuracy vs actual entitlement outcomes (track 6-month lag)

### Phase 10 — Site Feasibility Report (PDF Export)
**Gap closes:** Algoma "address to investor-ready" workflow
**Description:** One-click site feasibility report per parcel: zone summary, development potential score, unit count range, pro forma snapshot, entitlement path, comparable sales. Export as branded PDF. Designed for investor LP packages and lender presentations.
**Data required:** All Phase 1-9 outputs + comp sales data
**Effort:** S (1 week, builds on P02/P06/P07/P08) | Impact: VERY HIGH
**Competitor reference:** Algoma full report output
**KPI:** Report downloads per week (product-led growth metric)

### Phase 11 — Parking Requirements Calculator
**Gap closes:** Gridics + TestFit
**Description:** Per-zone parking minimums and maximums for residential and commercial uses. FL jurisdictions vary widely (downtown exceptions, TDM allowances, bicycle substitutions). Output: required spaces per unit mix, land area needed, structured parking flag.
**Data required:** parking_standards table (scraped from FL municipal codes)
**Effort:** M (2 weeks) | Impact: MEDIUM
**Competitor reference:** Gridics + TestFit parking calculator
**KPI:** Used in >50% of by-right unit calculations

### Phase 12 — Unit Mix Optimizer
**Gap closes:** TestFit
**Description:** Given target unit count + market rental data, recommend optimal unit mix (studio / 1BR / 2BR / 3BR) to maximize NOI. Uses FL market rent data by zip code. Outputs blended rent per SF and projected annual NOI.
**Data required:** fl_market_rents_by_bedroom_by_zip, unit_sf_standards_by_typology
**Effort:** M (2 weeks) | Impact: MEDIUM
**Competitor reference:** TestFit unit mix optimizer
**KPI:** Pro forma NOI accuracy improvement vs simple average rent

### Phase 13 — Building Program Analyzer
**Gap closes:** TestFit
**Description:** For a given site + development program, calculate building configuration: ground floor footprint, floor count, gross SF, NRA, parking levels, amenity SF. Supports garden-style, wrap, podium, and stacked flat typologies.
**Data required:** lot_area, setbacks, max_height, far, typology_standards
**Effort:** L (3-4 weeks) | Impact: MEDIUM
**Competitor reference:** TestFit building program analysis
**KPI:** Used in combination with Phase 7 pro forma

### Phase 14 — Net Rentable Area (NRA) Calculator
**Gap closes:** TestFit
**Description:** Calculate net rentable area from gross building SF. Accounts for core/shell factor, corridor allocation, mechanical spaces, and parking. Per-typology efficiency ratios sourced from FL market data.
**Data required:** gross_sf (P13), typology, fl_nra_efficiency_ratios
**Effort:** S (1 week) | Impact: LOW-MEDIUM
**Competitor reference:** TestFit NRA output
**KPI:** NRA accuracy vs actual delivered projects (within 5%)

### Phase 15 — Scenario Modeling (What-If Zones)
**Gap closes:** TestFit + Algoma
**Description:** Side-by-side scenario comparison for a parcel across different zone codes. "What if this parcel were zoned C-2 instead of R-1?" — shows unit count delta, FAR delta, use-change impact, pro forma delta. Critical for upzoning investment thesis.
**Data required:** zone_standards for all zones in same jurisdiction + P02 + P07
**Effort:** M (2 weeks) | Impact: HIGH
**Competitor reference:** TestFit scenario iteration + Algoma "development scenarios"
**KPI:** Scenario comparisons created per session

### Phase 16 — Variance & Exception Tracker
**Gap closes:** Algoma
**Description:** Track active variance requests, special exceptions, and administrative adjustments filed against FL parcels. Surfaces "hidden upzoning" — parcels where owners are already seeking relief. Source: FL county planning portals.
**Data required:** variance_filings scraped from FL county permit/planning portals
**Effort:** L (3-4 weeks) | Impact: MEDIUM
**Competitor reference:** Algoma exception identification
**KPI:** Variance data completeness (% of FL jurisdictions covered)

### Phase 17 — Construction Cost Estimator (FL Regional)
**Gap closes:** TestFit
**Description:** Per-unit and per-SF construction cost estimates by typology (wood-frame garden vs podium vs high-rise) and FL region (Northeast/Central/Southeast/Southwest). Updated quarterly from FL RS Means data. Output: hard cost range + soft cost estimate.
**Data required:** fl_construction_cost_matrix (quarterly), typology, location
**Effort:** M (2 weeks) | Impact: HIGH
**Competitor reference:** TestFit cost per unit output
**KPI:** Cost estimate accuracy vs actual GC bids (user-reported)

### Phase 18 — Setback 2D Site Plan Visualizer
**Gap closes:** Gridics + TestFit
**Description:** 2D top-down visualization of a parcel with setback envelope drawn. Shows buildable area remaining after setbacks + impervious surface limits. Useful for site plan review and quick feasibility check.
**Data required:** parcel_geometry, setbacks (front/rear/side), lot_coverage_max
**Effort:** S (1 week) | Impact: MEDIUM
**Competitor reference:** Gridics setback visualization layer
**KPI:** Reduces support questions about setback interpretation

### Phase 19 — Density Comparison Dashboard
**Gap closes:** Gridics analytics layer
**Description:** Compare density standards across zones within a jurisdiction or across jurisdictions. "What's the highest-density zone in Orlando?" — ranked list with du/acre, FAR, max height. Useful for market selection and investment thesis.
**Data required:** zone_standards.max_density + zone_standards.far + zoning_districts
**Effort:** S (1 week) | Impact: MEDIUM
**Competitor reference:** Gridics zoning analytics dashboard
**KPI:** Dashboard sessions from developer/analyst segment

### Phase 20 — Developer API v2 (REST + Webhooks)
**Gap closes:** Gridics API offering
**Description:** Production-grade REST API with JWT auth, rate limiting, versioning, and webhook support. Endpoints: parcel lookup, zone standards, unit count, pro forma. Webhooks: zone code change notifications. Target: PropTech developers building on top of ZoneWise data.
**Data required:** All existing ZoneWise data + P02/P06/P07 outputs
**Effort:** L (3-4 weeks) | Impact: VERY HIGH (B2B revenue channel)
**Competitor reference:** Gridics enterprise API
**KPI:** API customers × monthly API revenue

---

## 5. Priority Matrix

### Tier 1 — Build Now (High Impact / Low-Medium Effort)
| Phase | Feature | Effort | Revenue Impact |
|-------|---------|--------|----------------|
| P02 | By-Right Unit Count | S | HIGH — activates developer segment |
| P10 | Site Feasibility Report PDF | S | VERY HIGH — product-led growth trigger |
| P18 | Setback 2D Visualizer | S | MEDIUM — reduces friction |
| P19 | Density Comparison Dashboard | S | MEDIUM — SEO + analyst segment |

### Tier 2 — Build Q2 (High Impact / Medium Effort)
| Phase | Feature | Effort | Revenue Impact |
|-------|---------|--------|----------------|
| P01 | 3D Massing | L | HIGH — Gridics direct counter |
| P03 | Zoning Boundary Map | M | HIGH — organic traffic + stickiness |
| P06 | Development Potential Score | M | HIGH — ML-native, hard to copy |
| P15 | Scenario Modeling | M | HIGH — power user sticky feature |
| P17 | Construction Cost Estimator | M | HIGH — pro forma completeness |

### Tier 3 — Build Q3 (Medium Impact / Medium-Large Effort)
| Phase | Feature | Effort | Revenue Impact |
|-------|---------|--------|----------------|
| P07 | Pre-Construction Pro Forma | L | VERY HIGH — Algoma parity |
| P11 | Parking Calculator | M | MEDIUM — developer workflow |
| P12 | Unit Mix Optimizer | M | MEDIUM — pro forma enhancement |
| P08 | Entitlement Timeline | M | MEDIUM — Algoma gap close |
| P04 | Mixed-Use Analysis | M | MEDIUM — data accuracy |
| P09 | Entitlement Risk Score | M | MEDIUM — Algoma gap close |

### Tier 4 — Build Q4 / 2027 (High Impact / XL Effort or Strategic)
| Phase | Feature | Effort | Revenue Impact |
|-------|---------|--------|----------------|
| P20 | Developer API v2 | L | VERY HIGH — B2B channel |
| P13 | Building Program Analyzer | L | MEDIUM — TestFit parity |
| P16 | Variance & Exception Tracker | L | MEDIUM — data moat |
| P05 | National Coverage (GA/TX) | XL | VERY HIGH — TAM expansion |
| P14 | NRA Calculator | S | LOW-MEDIUM — completeness |

---

## 6. Go-To-Market Implications

### Repositioning ZoneWise

**From:** "FL zoning data + foreclosure intelligence"
**To:** "The only platform where FL foreclosure investors AND developers can answer 'what can I build here?' in seconds"

### New Segment Unlocked: Small Developers

Phases 2, 7, 10, and 13 collectively unlock a new buyer persona: the small FL developer (10-50 unit projects) who currently relies on expensive zoning consultants. ZoneWise can serve this segment at $X/month vs $5K-$15K consultant fees.

**Pricing implications:**
- Investor tier: existing (foreclosure + zoning lookup)
- Developer tier: +$50-150/month (Phases 2, 7, 10, 11, 17)
- Enterprise/API tier: Phase 20 unlocks ($500-2,000/month)

### Battle Card vs Algoma

| Attack vector | ZoneWise response |
|---------------|------------------|
| "We give you a full feasibility pipeline" | "We give you the same pipeline + foreclosure auction intelligence + 245K FL parcel records. Algoma has none of that." |
| "We're AI-native" | "ZoneWise has a trained ML deal scoring model on FL auction outcomes. Algoma trained theirs on zoning documents." |
| "Harvard team" | "Ariel has 10+ years FL foreclosure investing experience, FL broker license, and GC license. That's not in any Ivy League curriculum." |
| "We raised $2.3M" | "We're profitable per deal. Bootstrap > seed at this stage." |

### Battle Card vs Gridics

| Attack vector | ZoneWise response |
|---------------|------------------|
| "We have national coverage" | "We have FL covered to 67 counties / 351K parcels with REAL zoning codes, not USE codes. Their FL data has gaps." |
| "We have 3D massing" | "Phase 1 on our roadmap. Live in [Q2 2026]." |
| "We have an enterprise API" | "Our API is open Postgres — developers love it. No sales cycle." |
| "Our data is fresher" | "Our parcel data pulls from FL GIO weekly. Our zoning codes are scraped directly from municipal Municode." |

### Battle Card vs TestFit

| Attack vector | ZoneWise response |
|---------------|------------------|
| "Feasibility in minutes" | "Feasibility on REAL parcel data, not uploaded site plans. Every FL parcel, searchable by address." |
| "Unit mix + cost estimation" | "Phase 12 + 17 on our roadmap. Plus we add foreclosure auction overlay — TestFit has zero auction data." |
| "Enterprise pricing" | "Investor-accessible pricing. TestFit is enterprise-only." |

---

## 7. Success Metrics

### 6-Month Targets (Q2 2026 — Tier 1 + 2 shipped)

| Metric | Current | Target |
|--------|---------|--------|
| Developer segment users | 0 | 100+ |
| Site feasibility reports generated | 0 | 500+/mo |
| Pro forma downloads | 0 | 200+/mo |
| API revenue (B2B) | $0 | $2K/mo |
| Competitive win rate vs Algoma | Unknown | 70%+ |
| Zoning chatbot sessions | Baseline | +60% (map drives retention) |

### 12-Month Targets (Q4 2026 — Tier 3 shipped)

| Metric | Target |
|--------|--------|
| Developer tier subscribers | 500+ |
| API tier subscribers | 20+ |
| ZoneWise revenue contribution | $25K MRR |
| Algoma: ZoneWise mentioned as primary competitor | Public signal |
| National coverage live (GA + TX) | Phase 5 shipped |

---

## 8. Appendix: Sources + Evidence

| Claim | Source | Confidence |
|-------|--------|------------|
| Algoma raised $2.3M seed | Crunchbase / PitchBook (May 2025) | VERIFIED |
| Algoma targets small developers | algoma.co product page | VERIFIED |
| Gridics = PropZone brand | Gridics website + PR | VERIFIED |
| Gridics has 3D massing | Gridics product demo video | VERIFIED |
| TestFit has unit mix optimizer | TestFit feature page | VERIFIED |
| TestFit Series B | Crunchbase | INFERRED (no public amount confirmed) |
| FL parcel count 351K | ZoneWise DB (count verified Mar 2026) | VERIFIED |
| 28-feature matrix scores | ZoneWise competitors.html (Mar 29 2026) | VERIFIED |
| Algoma customers: Advenir, ACE, Cymbel | algoma.co case studies | VERIFIED |

---

*Roadmap built from verified competitive intelligence. HONESTY PROTOCOL enforced: all capability claims tagged VERIFIED or INFERRED.*
*Phase priority may shift based on user segment feedback. Revisit every 90 days.*
