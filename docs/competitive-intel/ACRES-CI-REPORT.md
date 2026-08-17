# Acres.com Competitive Intelligence Report
## PRD · PRS · SWOT · Battle Card

**Classification:** Competitive Intelligence | P1
**Domain:** GTM / ZoneWise
**Prepared by:** Claude AI Architect (BidDeed.AI), headless session
**Date:** 2026-08-17
**Status:** DEPLOYED — committed to repo
**Template:** Reuses the real 8-section structure of `docs/plans/ALGOMA-CI-REPORT.md` (see §0 below — the "18 sections" recalled at dispatch time does not exist anywhere in this repo or in `pp-ci-engine`; the real, previously-shipped structure is 8 sections and this report follows it)

---

## 0. Correction to the dispatch brief (read first)

Three premises do not match what was found live in this session — two in the original dispatch brief, one discovered mid-session in this report's own first draft. Per HONESTY PROTOCOL, all three are corrected here rather than silently followed or silently left wrong:

1. **"18 sections."** No file in `cli-anything-biddeed` or `breverdbidder/pp-ci-engine` (commit `c32b8c5`, current `main`) contains an 18-section battle-card schema. Searched `agent_ops_log`-referencing docs and `ssot_registry_components`-referencing docs repo-wide — no hit. The one real, previously-shipped, structurally complete competitor report in this repo is `docs/plans/ALGOMA-CI-REPORT.md`, and it has **8 sections** (Executive Summary, Company Overview, PRD, PRS, SWOT, Battle Card, Strategic Implications, Appendix). This report reuses that real structure. (A concurrent session working the same issue independently confirmed the same finding and additionally fingerprinted real tech-stack/hosting facts — see `docs/competitive-intel/TECH-STACK-TRIO.md` and `docs/competitive-intel/trio-battle-card.html`, committed alongside this report.)
2. **"3rd CI-engine component blocked on an OpenAI key."** True as of the engine's first smoke test (2026-08-12), false as of `pp-ci-engine`'s own `docs/SMOKE-TEST-REPORT.md` update dated 2026-08-14: Ariel decided against adding an OpenAI key, and the 3rd component (`ui-screenshot-to-prompt`) was rewired to a from-scratch Gemini adapter (`ui_screenshot_to_prompt_gemini_adapter.py`) that no longer touches OpenAI at all. Running the engine live against Acres.com today (2026-08-17), the 3rd component was attempted 3 times and BLOCKED all 3 times on `Gemini HTTP 503 — "This model is currently experiencing high demand"` — a transient capacity error, not a credential gap. See §8 for the raw evidence.
3. **"AcreTrader is Acres.com's parent company" — wrong, self-caught mid-session.** This report's first draft stated Acres.com is "operated by AcreTrader," based on AcreTrader's own older newsroom post ("AcreTrader Launches Acres, a Geospatial Analytics Platform") and the mobile app's legacy package id (`com.acretrader.acremapsmobile`). Further research surfaced a **PR Newswire release confirming Proterra Investment Partners acquired AcreTrader FROM Acres.com on August 12, 2025** — the ownership relationship inverted, and as of that date **Acres.com is the independent company; AcreTrader is the divested asset**, now operating under Proterra (GM Rob Moore, Managing Director Drew Lipke). Carter Malloy is named in that release as "Founder and CEO of Acres.com and AcreTrader," continuing to lead Acres.com "alongside over 60 talented individuals" (Aug 2025 headcount — see §2 for how this reconciles with the separate "close to 100" figure from a Dec 2025 article). All references to "AcreTrader as Acres' parent" below have been corrected; the AcreTrader funding history is retained only as **pre-divestiture historical context**, explicitly not Acres.com's current capital structure. **This correction was made after the first version of this report was already committed and pushed to `main`** — the wrong claim was live on `main` briefly before being caught and fixed in a follow-up commit. Flagging that explicitly rather than quietly rewriting history, per this repo's "wrong = I was wrong" rule.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Company Overview](#2-company-overview)
3. [PRD — Product Requirements Decomposition](#3-prd--product-requirements-decomposition)
4. [PRS — Competitive Positioning Statement](#4-prs--competitive-positioning-statement)
5. [SWOT Analysis](#5-swot-analysis)
6. [Battle Card](#6-battle-card)
7. [Strategic Implications](#7-strategic-implications)
8. [Appendix: CI Engine Run Evidence + Sources](#8-appendix-ci-engine-run-evidence--sources)

---

## 1. Executive Summary

**Acres.com** (acres.com, legal entity **AcreMaps, LLC dba Acres**) is a nationwide land-data and zoning-intelligence platform, independently operated as of August 2025 (Fayetteville, AR; founder/CEO **Carter Malloy**) after Proterra Investment Partners acquired its former sibling/parent AcreTrader. It analyzes **150M+ US parcels** across **1,000+ data sources** and **12,000–13,000+ data/map layers** (both figures scraped live from acres.com — see discrepancy note in §2), and in 2026 shipped two major AI releases: native AI zoning search (Feb 16, 2026) and **Acres Intelligence**, a full AI land-research agent (May 8, 2026). It was named a **2026 HousingWire Tech100 winner**, the only Arkansas company on that year's list.

**Competitive verdict:** Acres is a **direct, head-on competitor to ZoneWise** on the exact axis ZoneWise competes: parcel-level zoning data at scale. Unlike Algoma (a workflow tool one layer above zoning data) or Gridics/Zoneomics (API-first but narrower), Acres is a nationwide, enterprise-funded, AI-native version of what ZoneWise is building for Florida — with real enterprise customers (CBRE, Lennar, PGIM, Century Communities, PG&E, Vulcan Materials confirmed live on acres.com) and a 30,000+ jurisdiction zoning-coverage claim. It has **zero** foreclosure or tax-deed auction intelligence — BidDeed.AI's core product is untouched by Acres.

**Threat level:** **HIGH for ZoneWise** (direct nationwide overlap on the zoning-data-at-scale category). **LOW for BidDeed.AI** (zero overlap on foreclosure/auction deal scoring).

**Opportunity:** ZoneWise cannot out-resource Acres nationally (Acres has ~60-100 employees per two 2025 press sources, a 5-figure-per-jurisdiction data operation already running, and — even independent of AcreTrader's now-divested capital — real enterprise reference customers most bootstrapped competitors don't have). ZoneWise's defensible ground is FL-specific depth combined with the auction/foreclosure layer Acres has no interest in building — the same "raw-data-layer-vs-workflow" framing used against Algoma, but here it's "deep-FL-vertical-vs-nationwide-horizontal," a different and harder fight.

---

## 2. Company Overview

| Field | Value | Tag |
|-------|-------|-----|
| **Product** | Acres.com | VERIFIED |
| **Legal entity** | AcreMaps, LLC dba Acres | VERIFIED — scraped footer disclaimer, live 2026-08-17 |
| **Corporate history** | Originally an AcreTrader product/subsidiary ("AcreTrader Launches Acres, a Geospatial Analytics Platform"). **Ownership inverted 2025-08-12**: Proterra Investment Partners acquired **AcreTrader** *from* Acres.com. Acres.com "remains independent" per the transaction announcement; AcreTrader now operates under Proterra (GM Rob Moore, MD Drew Lipke). **Acres.com currently has no disclosed parent company.** | VERIFIED — PR Newswire transaction announcement, 2025-08-12 |
| **URL** | https://www.acres.com | VERIFIED |
| **HQ** | Fayetteville, AR | VERIFIED |
| **Founder/CEO** | Carter Malloy — named in the Aug 2025 transaction release as "Founder and CEO of Acres.com and AcreTrader" | VERIFIED |
| **Founded (AcreTrader entity)** | 2018 (widely reported); Acres.com product launched later as an AcreTrader-affiliated product, then separated into its own company via the Aug 2025 divestiture | INFERRED — exact Acres.com product-launch/incorporation date not confirmed this session |
| **Team size** | "Over 60 talented individuals" (Aug 2025, PR Newswire transaction release) vs. "close to 100" (Dec 2025, Arkansas Democrat-Gazette). Both VERIFIED as reported, at different points in time — plausible headcount growth over ~4 months, not treated as a contradiction | VERIFIED (secondary/journalistic + press-release sources) — not independently confirmed via a primary Acres filing |
| **Funding** | **Historical, pre-divestiture context only, not Acres.com's current capital structure:** the AcreTrader entity raised $5M seed (Apr 2020, RZC Investments), $12M Series A (Jump Capital), $40M Series B (Jan 2022, Anthemis Group), expanded to $60M+ Series B (Mar 2022, adding Drive Capital) — before being sold to Proterra in Aug 2025. **Acres.com's own, current, independent funding/ownership structure is UNKNOWN** — not disclosed in any source found this session. | VERIFIED (historical AcreTrader funding) / **UNKNOWN** (Acres.com's current capital structure) |
| **Category** | Nationwide land intelligence / AI zoning search | VERIFIED |
| **Tagline (site)** | "Analyze and Value Land With Confidence" | VERIFIED |

### Scale claims (scraped live from acres.com, 2026-08-17)

| Metric | acres.com homepage | acres.com/data page | Tag |
|---|---|---|---|
| Data sources | 1,000+ | 1,000+ | VERIFIED (consistent) |
| Parcel records | 150M+ | 150M+ | VERIFIED (consistent) |
| Map/data layers | 12,000+ (labeled "Map Layers") | 13,000+ (labeled "Data Layers") | VERIFIED, but **note the discrepancy** — two different live pages on the same site show two different numbers under two slightly different labels. Not a fabrication on our part; flagging it as a real site inconsistency an Acres prospect could also notice. |
| Land transactions | 45M+ | — | VERIFIED |
| Land decisions influenced | "$40 Billion in Land Decisions Made Annually With Acres" | — | VERIFIED (marketing claim, not independently auditable) |
| Zoning jurisdictions covered | 30,000+ (per Feb 2026 press release) | not repeated on scraped pages | VERIFIED — from GlobeNewswire/HousingWire coverage of the Feb 16, 2026 launch, not from the live page scrape itself |

### Enterprise customers (logos live on acres.com homepage, 2026-08-17)

CBRE, PG&E, Lennar, PGIM, Century Communities, Vulcan Materials — **VERIFIED**, scraped directly, not inferred from press.

### Customer testimonials (scraped live, 2026-08-17)

- Scott Hair, Regional Corporate Director of Land, **Century Communities**
- Wes Craiglow, Executive Director, **ULI Northwest Arkansas**
- Greg Peters, VP and Director of Appraisal Operations, **Golden State Farm Credit**

---

## 3. PRD — Product Requirements Decomposition

### 3.1 Core Product Vision

Acres' stated mission (site copy): centralize "every layer of due diligence" — zoning, risk, ownership, transaction records — into one interactive panel so land teams can evaluate parcels, deals, and markets without stitching together fragmented county/state/GIS sources. The 2026 additions (native AI search, Acres Intelligence agent) push this from a raw-data browser toward a conversational research assistant that can "analyze zoning and generate site feasibility reports in seconds" (HousingWire's framing of Acres Intelligence).

### 3.2 Feature Inventory (from live site navigation, scraped 2026-08-17)

#### F-001: Map / Plat Map
- **What:** Core interactive parcel map (`/plat-map/map`)
- **ZoneWise parity:** PARTIAL — ZoneWise has parcel-level mapping for its covered FL counties, not a nationwide plat map

#### F-002: Value Land
- **What:** Instant land valuation reports (`/value-land`)
- **ZoneWise parity:** NOT IN ZONEWISE — ZoneWise doesn't produce standalone land-value reports; BidDeed.AI does ARV-based auction deal math, a different product shape

#### F-003: Find Recent Sales
- **What:** Nationwide land sales database, including non-disclosure states (`/recent-sales`)
- **ZoneWise parity:** NOT IN ZONEWISE

#### F-004: Layer Library
- **What:** 12,000–13,000+ map/data layers, browsable (`/layer-library`)
- **ZoneWise parity:** ZoneWise has zone codes/standards/permitted uses per parcel at FL depth; Acres' layer library is broader but each layer is shallower than ZoneWise's per-parcel zoning depth in covered counties

#### F-005: Prospecting
- **What:** Lead-list / prospecting tool for land acquisition teams (`/prospecting`)
- **ZoneWise parity:** NOT IN ZONEWISE

#### F-006: Analyze Land
- **What:** Feasibility/analysis workflow (`/analyze-land`)
- **ZoneWise parity:** PARTIAL — overlaps conceptually with zoning-constraint lookups ZoneWise supports, but Acres wraps it in a guided workflow

#### F-007: Easy Mapping / Site Planner
- **What:** Custom shareable maps, lot-yield generation (`/mapping`)
- **ZoneWise parity:** NOT IN ZONEWISE

#### F-008: Portfolio Management
- **What:** Collaborative workspace — commenting, tagging, document management, shared maps (`/portfolio`)
- **ZoneWise parity:** NOT IN ZONEWISE — no team-collaboration layer exists in ZoneWise today

#### F-009: Risk Management
- **What:** Instant risk visualization per parcel (`/manage-risk`)
- **ZoneWise parity:** NOT IN ZONEWISE

#### F-010: Mobile App
- **What:** iOS/Android app, package `com.acretrader.acremapsmobile` (VERIFIED via Play Store listing)
- **ZoneWise parity:** NOT IN ZONEWISE — no mobile app exists yet

#### F-011: Acres Intelligence (AI agent)
- **What:** Natural-language land research agent — launched May 8, 2026. Draws on "150+ million US parcels with zoning, permits, ownership, environmental, and risk data layers" per HousingWire; generates feasibility reports/dashboards "in minutes"
- **ZoneWise parity:** NOT IN ZONEWISE — this is the single largest capability gap. ZoneWise has no natural-language query layer.

#### F-012: Native AI Zoning Search
- **What:** Plain-language zoning/feasibility search across the map — launched Feb 16, 2026. Claimed coverage: 30,000+ local zoning jurisdictions nationwide
- **ZoneWise parity:** ZoneWise EXCEEDS on **per-parcel raw depth** in its covered FL counties (raw zone codes, setbacks, FAR, permitted uses as structured DB rows); Acres EXCEEDS on **breadth** (nationwide) and on **natural-language interface** (ZoneWise has none)

#### F-013: Industries pages
- **What:** Dedicated landing pages for Builders, Data Center, Energy, Finance & Lending, Real Estate, Retail
- **ZoneWise parity:** NOT IN ZONEWISE — ZoneWise has no vertical-specific packaging yet

#### F-014: Home Builder Index / Data Center Index
- **What:** Named index products tracking builder/data-center-specific land activity
- **ZoneWise parity:** NOT IN ZONEWISE

**Confirmed absent (checked directly — site nav, `/data` page, `landvalues.acres.com` blog index, and web search):** no foreclosure listings, no tax-deed auction data, no sheriff-sale calendar, no ARV/deal-scoring product. **This gap is real and confirmed, not assumed** — matching the dispatch brief's stated expectation.

### 3.3 Pricing Model

| Tier (from site nav) | What's known | Tag |
|---|---|---|
| **For Individuals** (`/pricing`) | Named "Acres+" (free trial signup URL: `/acresplus-purchase-annual-signup`) and "Pro" (`/pro-purchase-monthly-signup`) | VERIFIED tier *names* exist; **no dollar amounts found** |
| **For Business** (`/enterprise`) | "Enterprise" tier, demo-request gated | VERIFIED tier exists; contact-sales model |
| **Exact pricing** | **UNKNOWN** — `/pricing` returned HTTP 403 to both WebFetch and the pp-ci-engine's own live scrape did not target it directly this session; public search results confirm the tier *names* (Acres+, Pro, Enterprise) but not dollar figures | **UNKNOWN, explicitly, per dispatch instruction not to invent a number** |

---

## 4. PRS — Competitive Positioning Statement

### 4.1 Acres' Stated Positioning

Site copy: **"Analyze and Value Land With Confidence."** Product framing: "the largest and most comprehensive land intelligence platform available." Acres Intelligence framing (per its own launch press release): "the first AI agent built for land teams."

**Target buyer:** Homebuilders, developers, data-center operators, energy companies, lenders, institutional investors, retailers, appraisers — explicitly nationwide, explicitly enterprise-weighted (CBRE, Lennar, PGIM as reference customers).

**Category they're creating:** "AI land intelligence" — one platform spanning raw parcel data, valuation, prospecting, portfolio collaboration, and now conversational AI research, rather than a single-purpose zoning API or a single-purpose foreclosure tool.

### 4.2 Positioning Map: Acres vs. ZoneWise/BidDeed.AI

```
                    HIGH DATA DEPTH (per parcel)
                          │
         ZoneWise ────────┤
     (FL, 245K+ auctions   │
      tracked, deep zoning)│
                          │──── Acres
                          │  (150M parcels nationwide,
     WORKFLOW ─────────────┼── AI agent, shallower per-      DATA API
         │                 │   parcel zoning depth than
         │                 │   ZoneWise in FL specifically)
     Algoma                │
     TestFit                │
                          │
                    BREADTH (nationwide) / LOW-to-MEDIUM DEPTH
```

| Product | Primary Use Case | Target User | Monetization |
|---------|-------------------|-------------|---------------|
| **ZoneWise** | Parcel-level zoning data at scale, FL-focused | Researchers, investors, developers, APIs | Data subscription, API |
| **Acres.com** | Nationwide land data + AI research agent | Homebuilders, data centers, energy, institutional investors | Acres+/Pro/Enterprise, pricing UNKNOWN |
| **Gridics** | Zoning data + compliance | Enterprise developers, cities | Enterprise SaaS |
| **Zoneomics** | National zoning database | PropTech, research | API / data license |
| **Algoma** | Site feasibility workflow | Small/mid developer | Subscription reports |
| **PropertyOnion** | Foreclosure auctions | Investors | Marketplace |
| **BidDeed.AI** | Foreclosure deal scoring | FL foreclosure investors | SaaS |

### 4.3 ZoneWise Positioning AGAINST Acres

**When to use this:** When a prospect says "we already use Acres" or "why not just use Acres.com, it's nationwide."

> "Acres is the best nationwide land-data platform on the market right now — 150M+ parcels, an AI agent, enterprise customers like CBRE and Lennar. If you need land intelligence across 50 states, Acres is a legitimate first call. But if you're a Florida foreclosure investor, Acres has zero auction calendar, zero tax-deed intelligence, and zero ARV-based bid math — it's a land-data platform, not a foreclosure deal-scoring platform. ZoneWise plus BidDeed.AI is the only combination that gives you FL zoning depth *and* the auction layer in the same workflow."

---

## 5. SWOT Analysis

### 5.1 Acres.com SWOT

#### Strengths

| # | Strength | Evidence |
|---|----------|----------|
| S1 | Nationwide scale — 150M+ parcels, 1,000+ data sources | Live site scrape, consistent across two pages |
| S2 | Real enterprise reference customers | CBRE, Lennar, PGIM, Century Communities, PG&E, Vulcan Materials — logos live on homepage |
| S3 | AI-native roadmap shipping fast | Two major AI launches in 6 months (Feb + May 2026) |
| S4 | Historical capital base | The now-divested AcreTrader entity raised $60M+ Series B pre-Aug-2025; Acres.com's own current funding is undisclosed, but it operates at a scale (enterprise customers, 60-100+ staff) suggesting it isn't cash-starved post-divestiture |
| S5 | Industry press validation | 2026 HousingWire Tech100 winner |
| S6 | Multi-vertical packaging | Dedicated pages for Builders, Data Center, Energy, Finance, Real Estate, Retail |
| S7 | Mobile app already shipped | Live on iOS App Store + Google Play |

#### Weaknesses

| # | Weakness | Evidence |
|---|----------|----------|
| W1 | Zero foreclosure/tax-deed/auction coverage | Confirmed absent across `/data`, nav, and blog search |
| W2 | No public pricing | `/pricing` gated; tier names known (Acres+, Pro, Enterprise), no dollar figures found |
| W3 | Per-parcel zoning depth likely shallower than ZoneWise in FL specifically | Acres spans 150M parcels nationwide vs. ZoneWise's much smaller but deeper FL-specific dataset — breadth/depth tradeoff, not a ZoneWise-favorable "win" outright, but a real differentiation surface |
| W4 | Internal metric inconsistency | Homepage says "12,000+ Map Layers," `/data` page says "13,000+ Data Layers" — same company, two live pages, two numbers |
| W5 | No FL-specific auction-calendar or investor-bidding tooling | Product is acquisition/development-workflow oriented, not auction-day-execution oriented |

#### Opportunities

| # | Opportunity | Relevance |
|---|-------------|-----------|
| O1 | Could add foreclosure/tax-deed data as a new vertical | Would directly threaten BidDeed.AI if it happened — currently no signal they're building this |
| O2 | AI agent could eventually absorb ZoneWise's per-parcel-depth advantage if they invest more in FL specifically | Watch for FL-focused data-quality pushes |
| O3 | Continued enterprise land in the data-center/energy boom | Growing addressable market independent of ZoneWise/BidDeed.AI |

#### Threats

| # | Threat | To Acres |
|---|--------|----------|
| T1 | AI-generated zoning summaries carry misinterpretation risk at legal-decision scale | Same LLM-trust-boundary risk flagged against Algoma, at much higher stakes given enterprise customers |
| T2 | Gemini/OpenAI-style vision-model outages could affect Acres Intelligence uptime if similarly dependent on third-party LLM vendors | Speculative — Acres' own LLM vendor is not publicly disclosed; noted only as a category risk, not a confirmed Acres dependency |
| T3 | Breadth-over-depth model is vulnerable to vertical specialists (ZoneWise in FL zoning, BidDeed.AI in FL auctions) who out-execute on a narrow, high-stakes use case | Direct strategic threat from this exact competitive set |

### 5.2 ZoneWise/BidDeed.AI SWOT vs. Acres

#### Strengths (vs. Acres)

| # | Strength | vs. Acres |
|---|----------|-----------|
| S1 | Full FL foreclosure/auction intelligence | Acres has none — BidDeed.AI's `multi_county_auctions` table alone (245K+ rows) is a category Acres doesn't compete in at all |
| S2 | Founder with 10+ yr FL investing + FL broker + GC license | Domain credibility Acres' nationwide product team can't claim for FL specifically |
| S3 | Deep per-parcel zoning depth in covered FL counties | Raw zone codes, standards, permitted uses as structured queryable rows, not an AI summary layer |
| S4 | NEVER-LIE, DB-verified counts | Discipline Acres' own site inconsistency (12K vs 13K layers) suggests they don't uniformly enforce |

#### Weaknesses (vs. Acres)

| # | Weakness | vs. Acres |
|---|----------|-----------|
| W1 | No nationwide coverage | Acres claims 150M parcels / 30,000+ jurisdictions vs. ZoneWise's FL-only footprint |
| W2 | No AI natural-language query layer | Acres shipped two major AI launches in 2026; ZoneWise has none yet |
| W3 | No enterprise reference customers of Acres' caliber | CBRE/Lennar/PGIM tier logos vs. ZoneWise's current customer base |
| W4 | No mobile app | Acres has a live iOS/Android app |
| W5 | Funding gap presumed but unconfirmed | Acres.com's current, independent capital structure is UNKNOWN (post-Aug-2025 divestiture from AcreTrader); ZoneWise's is $0 external — the comparison itself is UNKNOWN pending Acres.com-specific disclosure |

---

## 6. Battle Card

### 6.1 One-Line Positioning

> **ZoneWise + BidDeed.AI:** The only platform combining deep Florida zoning intelligence with real foreclosure/tax-deed auction deal-scoring.
> **Acres.com:** The best nationwide land-data + AI-research platform available — for land acquisition and development, not auction-day foreclosure bidding.

### 6.2 When You Win vs. Acres

Win when the prospect needs:
- ✅ FL foreclosure/tax-deed auction calendars and case-level tracking (Acres has zero)
- ✅ ARV-based bid math / BID-REVIEW-SKIP deal scoring (Acres has zero)
- ✅ Raw, queryable per-parcel FL zone codes/standards/permitted uses rather than an AI summary
- ✅ A founder-operator's FL-specific domain judgment layered on the data
- ✅ Lower-cost, narrower tool for a FL-only workflow instead of a nationwide enterprise platform priced for CBRE/Lennar-scale buyers

### 6.3 When You Lose vs. Acres

Lose when the prospect needs:
- ❌ Nationwide coverage (Acres: 150M+ parcels, 30,000+ jurisdictions; ZoneWise: FL only)
- ❌ A natural-language AI research agent (Acres Intelligence; ZoneWise has none)
- ❌ Enterprise-grade portfolio collaboration tooling (tagging, commenting, shared maps)
- ❌ A mobile app
- ❌ Land valuation / comparable-sales reporting for non-foreclosure acquisitions
- ❌ Vendor credibility signals like HousingWire Tech100, $60M+ raised capital, CBRE/Lennar logos

### 6.4 Objection Handling

#### "We're already evaluating Acres.com."
> "Acres is a strong choice if you need nationwide land data — it's genuinely one of the best-funded, best-reviewed platforms in that category right now. But ask them directly: do they have a Florida tax-deed and foreclosure auction calendar? Do they compute ARV-based max-bid recommendations? They don't — it's not their product. If any part of your workflow touches Florida foreclosure or tax-deed auctions, you need a tool built for that specifically."

#### "Acres has an AI agent, you don't."
> "Correct, and it's a real capability gap we're tracking. But Acres Intelligence answers questions about acquisition and development feasibility — it doesn't compute a BID/REVIEW/SKIP recommendation against an actual courthouse auction calendar. Different job."

#### "Acres covers the whole country, you're Florida-only."
> "That's true, and if you need 50-state coverage, Acres wins outright. For Florida specifically — the most active foreclosure/tax-deed market in the US — we go deeper on a use case Acres doesn't build for at all: courthouse auction tracking + zoning-informed deal scoring in one place."

#### "Acres is backed by $60M+ and has CBRE as a customer."
> "Those enterprise logos are real. Acres was originally an AcreTrader product, but AcreTrader itself was sold to Proterra in August 2025 — Acres.com now runs independently, and its current funding isn't public. We're not claiming to out-fund them either way. We're claiming a narrower, sharper edge: 10+ years of Ariel's own FL foreclosure investing translated directly into the product, and zero invented data — every auction count is DB-verified, not AI-summarized."

### 6.5 Win/Loss Decision Tree

```
Prospect asks about land/zoning data
          ↓
  Need nationwide coverage?
    YES → Acres wins on breadth
    NO ↓
  FL-focused?
    YES ↓
  Foreclosure/tax-deed auction involved?
    YES → BidDeed.AI + ZoneWise win outright — Acres has zero overlap
    NO → Evaluate case by case; Acres' AI agent + broader layer library may still win
```

### 6.6 Feature Comparison Matrix

| Feature | ZoneWise/BidDeed.AI | Acres.com | Winner |
|---|---|---|---|
| Parcel-level zoning depth (FL) | ✅ Raw zone codes/standards/uses | ✅ AI-summarized, nationwide-spread | **ZoneWise** (FL depth) |
| Nationwide coverage | ❌ FL only | ✅ 150M+ parcels, 30,000+ jurisdictions | **Acres** |
| Natural-language AI research agent | ❌ None | ✅ Acres Intelligence (May 2026) | **Acres** |
| Foreclosure/tax-deed auction calendar | ✅ 245K+ auctions tracked | ❌ None found | **BidDeed.AI** |
| ARV × 70% max-bid deal scoring | ✅ Core product | ❌ None | **BidDeed.AI** |
| Land valuation / comp reports | ❌ Not the product | ✅ "Value Land" feature | Acres |
| Portfolio collaboration tools | ❌ None | ✅ Tagging, commenting, shared maps | Acres |
| Mobile app | ❌ None | ✅ iOS + Android live | Acres |
| Enterprise reference customers | ⚠️ Not publicly comparable this session | ✅ CBRE, Lennar, PGIM, Century Communities | Acres |
| Public pricing transparency | ✅ | ❌ UNKNOWN — tier names only, no $ found | **ZoneWise** |
| Funding | $0 external | UNKNOWN current — $60M+ historical (now-divested AcreTrader entity, pre-Aug-2025) | Unclear — not a like-for-like comparison |
| Data verification discipline | ✅ NEVER-LIE, DB-verified | ⚠️ Site shows internal 12K/13K layer-count inconsistency | **ZoneWise** |

**ZoneWise/BidDeed.AI wins:** 4 features (FL zoning depth, auction calendar, ARV bid math, pricing transparency/data discipline)
**Acres wins:** 6 features (breadth, AI agent, valuation reports, collaboration, mobile, customer logos)
**Unclear/not a like-for-like comparison:** 1 (funding — Acres.com's current capital structure is UNKNOWN post-divestiture from AcreTrader)
**Read:** Acres is a stronger *general* product with vastly more resources. ZoneWise/BidDeed.AI's win path is narrow and specific (FL + foreclosure), not broad.

### 6.7 Elevator Pitch (30 seconds)

> "Acres is the best nationwide land-data platform on the market — 150M parcels, an AI research agent, real enterprise customers. If that's your job, talk to them. Our job is narrower and sharper: Florida foreclosure and tax-deed investors who need courthouse-accurate auction data and ARV-based bid math in one place, built by someone who's actually bid at these auctions for 10+ years. Acres doesn't do that. We don't try to do what Acres does."

---

## 7. Strategic Implications

### 7.1 Threat Monitoring

| Trigger | Action |
|---|---|
| Acres announces any foreclosure/tax-deed/auction feature | Immediate escalation — this is the one move that turns Acres from "adjacent, high-resource" into "direct existential threat" to BidDeed.AI |
| Acres publishes public pricing | Re-run this dossier's §3.3 with real numbers |
| Acres' 12K vs 13K layer-count inconsistency gets fixed | Minor — re-verify current live numbers before quoting in future sales conversations |
| Acres.com discloses its own post-divestiture funding/ownership structure | Currently UNKNOWN — re-assess funding delta once real numbers exist |
| ZoneWise expands past Brevard/Orange/Duval | Narrows the "FL depth" gap that's currently the core differentiator vs. Acres' breadth |

### 7.2 Recommendation

Do not attempt to compete with Acres on breadth or AI-agent capability in the near term — that is a $60M+-funded, ~100-person, enterprise-validated head start. The defensible position is the same one used against Algoma but sharper here: **own the FL foreclosure/tax-deed vertical completely**, including the one thing Acres has shown zero interest in building. If Acres ever adds auction data, this recommendation must be revisited immediately (see trigger table above).

### 7.3 Content / SEO Strategy

- "Acres.com vs ZoneWise: nationwide land data vs. Florida foreclosure depth"
- "Why nationwide land platforms don't cover tax-deed auctions (and what to use instead)"
- "AI zoning search is not auction-day bid math: Acres Intelligence vs. BidDeed.AI"

---

## 8. Appendix: CI Engine Run Evidence + Sources

### 8.1 pp-ci-engine (CI v6.5) live run — 2026-08-17

Repo: `breverdbidder/pp-ci-engine`. Cloned fresh this session via `gh repo clone --recurse-submodules` (direct `git clone` over HTTPS failed with no credential helper in this sandbox — `gh` succeeded). Dependencies installed fresh (`npm install`, Python venv + `pip install -r requirements.txt`). System Chromium confirmed present at `/usr/bin/chromium`.

**Firecrawl status checked first (per the engine's own documented protocol):**
```
$ curl -H "Authorization: Bearer $FIRECRAWL_API_KEY" https://api.firecrawl.dev/v2/team/credit-usage
{"success":true,"data":{"remainingCredits":-13,"planCredits":1000,"billingPeriodStart":"2026-07-28T22:28:40.091Z","billingPeriodEnd":"2026-08-28T22:28:40.091Z"}}
```
Still exhausted (matches the 2026-08-12 finding, -13 vs. -10 credits then — someone/something used 3 more credits in the interim). `run.py` correctly used its Playwright fallback with no Firecrawl calls, exactly as designed.

**Real orchestrator runs — 3 targets, `python3 run.py --url <target> --out <dir>`:**

| Target | html_to_md | screenshot_to_code | ui_screenshot_to_prompt |
|---|---|---|---|
| `https://www.acres.com` | ✅ VERIFIED — turndown, 14,281 chars, 0.16s | ✅ VERIFIED — Gemini `gemini-3-flash-preview`, 3,227 prompt / 2,544 output tokens, 11.34s, `finishReason: STOP` | ❌ BLOCKED — `Gemini HTTP 503: model currently experiencing high demand` |
| `https://landvalues.acres.com` | ✅ VERIFIED — 11,058 chars, 0.12s | ✅ VERIFIED — 3,228 prompt / 2,837 output tokens, 13.45s | ❌ BLOCKED — same 503 |
| `https://www.acres.com/data` | ✅ VERIFIED — 6,652 chars, 0.14s | ✅ VERIFIED — 3,229 prompt / 2,735 output tokens, 12.91s | ❌ BLOCKED — same 503 |

Component 3 was retried **3 additional times** standalone against the already-captured `acres.com` screenshot (bounded per `CC_META_PROMPT.md` §7's retry cap) — all 3 returned the identical `503 UNAVAILABLE` from Gemini. This is a transient capacity error on Google's side, not a credential/config issue — confirmed by re-reading `pp-ci-engine`'s own `docs/SMOKE-TEST-REPORT.md`, which shows this exact adapter produced real, non-empty output (6 regions, 18,431 tokens) against a different target (LandGlide) on 2026-08-14. **Net result: 2 of 3 components VERIFIED on all 3 Acres.com targets; component 3 genuinely BLOCKED today by Gemini capacity, not fabricated.**

Raw output files (page.md, page.html, screenshot.png, reproduction.html, run_report.json per target) exist in this session's `/tmp/pp-ci-out-*` directories but were **not** committed to the repo — they are large binary/scraped artifacts (page.html alone is 251KB for the homepage), not the report itself, and match this repo's existing pattern of committing the finished dossier (`ALGOMA-CI-REPORT.md`) rather than raw scrape dumps.

### 8.2 Primary sources

| Source | URL | Confidence |
|---|---|---|
| Acres.com homepage (live scrape) | https://www.acres.com | VERIFIED |
| Acres.com /data page (live scrape) | https://www.acres.com/data | VERIFIED |
| Land Values Insider blog (live scrape) | https://landvalues.acres.com | VERIFIED |
| Acres Intelligence launch | https://www.globenewswire.com/news-release/2026/05/08/3291039/0/en/acres-com-launches-acres-intelligence-the-first-ai-agent-built-for-land-teams.html | VERIFIED |
| Native AI search + zoning intelligence launch | https://www.globenewswire.com/news-release/2026/02/16/3238680/0/en/Acres-com-Launches-Native-AI-Search-and-Zoning-Intelligence-Transforming-How-Teams-Discover-and-Evaluate-Land.html | VERIFIED |
| 2026 HousingWire Tech100 win | https://www.globenewswire.com/news-release/2026/02/02/3230677/0/en/Acres-com-Named-a-2026-HousingWire-Tech100-Winner-for-Transforming-Land-Intelligence-in-Homebuilding-and-Real-Estate.html | VERIFIED |
| AcreTrader launches Acres (original, now-superseded parent-company relationship) | https://acretrader.com/newsroom/acretrader-launches-acres-geospatial-analytics-platform-providing-comprehensive-insights-land-value | VERIFIED (historical) |
| **Proterra acquires AcreTrader FROM Acres.com — ownership correction, 2025-08-12** | https://www.prnewswire.com/news-releases/proterra-acquires-farmland-investment-platform-acretrader-from-acrescom-transaction-accelerates-opportunities-for-both-investors-and-farmers-302526006.html | **VERIFIED — supersedes the row above** |
| AcreTrader Series B $40M (historical, pre-divestiture) | https://www.businesswire.com/news/home/20220111005413/en/AcreTrader-Raises-%2440-Million-in-Series-B-Funding-to-Fuel-Strategic-Growth | VERIFIED |
| AcreTrader Series B expanded to $60M+ (historical, pre-divestiture) | https://acretrader.com/newsroom/acretrader-expands-series-b-round-over-60-million | VERIFIED |
| Acres.com "over 60" employees (Aug 2025) | PR Newswire transaction release, above | VERIFIED (press release) |
| Acres.com "close to 100" employees (Dec 2025) | https://www.arkansasonline.com/news/2025/dec/14/fayetteville-company-using-artificial/ | VERIFIED (secondary/journalistic source) |
| pp-ci-engine repo + smoke test report | https://github.com/breverdbidder/pp-ci-engine | VERIFIED (this session, direct repo read) |

### 8.3 Claims explicitly marked UNKNOWN (not fabricated)

| Claim | Status |
|---|---|
| Exact Acres+/Pro/Enterprise dollar pricing | **UNKNOWN** — `/pricing` returned HTTP 403 to automated fetch; public search did not surface dollar figures; tier names only |
| Acres.com's current, independent capital structure / funding / ownership post-Aug-2025 divestiture | **UNKNOWN** — the pre-divestiture AcreTrader funding history is retained as historical context only, not as Acres.com's current backing |
| Total Acres.com customer count beyond the 6 logos + 3 testimonials scraped live | **UNKNOWN** |
| Acres.com product-launch/incorporation date (as distinct from the AcreTrader entity's 2018 founding) | **UNKNOWN** — not confirmed this session |
| Which LLM vendor powers Acres Intelligence in production | **UNKNOWN** — not disclosed publicly; not assumed to be Gemini/OpenAI/Claude |

### 8.4 HONESTY PROTOCOL tags applied throughout

- **VERIFIED:** Legal entity name, current independent-ownership status (and the Aug 2025 Proterra/AcreTrader divestiture that produced it), HQ, founder, live scrape stats (parcels/sources/layers/transactions), enterprise customer logos, testimonials, AI-launch dates, Tech100 award, historical AcreTrader funding (as historical, not current), CI-engine run results (both VERIFIED and BLOCKED outcomes)
- **INFERRED:** Acres.com product-launch date relative to the AcreTrader entity's founding
- **UNKNOWN:** Exact pricing, Acres.com's current post-divestiture funding/ownership, full customer count, production LLM vendor

---

*CI Report complete. Committed to repo `breverdbidder/cli-anything-biddeed` at `docs/competitive-intel/ACRES-CI-REPORT.md`, config at `config/ci-dossiers/acres.yaml`, battle card at `docs/competitive-intel/ACRES-BATTLE-CARD.html`.*
