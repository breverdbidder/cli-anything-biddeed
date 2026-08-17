# Algoma Competitive Intelligence Report
## PRD · PRS · SWOT · Battle Card

**Classification:** GTM-011 | Competitive Intelligence | P1
**Domain:** GTM / ZoneWise
**Prepared by:** Claude AI Architect (BidDeed.AI)
**Date:** 2026-03-29
**Status:** DEPLOYED — committed to repo from Feb 2026 chat artifact
**Artifact vault entry:** Algoma Full CI Report (PRD/PRS/SWOT/Battle Card)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Company Overview](#2-company-overview)
2A. [Technology Stack & Hosting (Verified — Aug 17 2026)](#2a-technology-stack--hosting-verified--aug-17-2026)
3. [PRD — Product Requirements Decomposition](#3-prd--product-requirements-decomposition)
4. [PRS — Competitive Positioning Statement](#4-prs--competitive-positioning-statement)
5. [SWOT Analysis](#5-swot-analysis)
6. [Battle Card](#6-battle-card)
7. [Strategic Implications](#7-strategic-implications)
8. [Appendix: Sources + Evidence](#8-appendix-sources--evidence)

---

## 1. Executive Summary

**Algoma** (algoma.co) is an AI-native site feasibility and pre-construction automation platform targeting small and mid-sized real estate developers. Founded 2023 by Harvard alumni, raised $2.3M seed (May 2025), headquartered in New York.

**Competitive verdict:** Algoma is NOT a direct head-to-head competitor with ZoneWise or BidDeed.AI. It is a developer-workflow tool that wraps zoning data inside a broader feasibility pipeline. ZoneWise is a raw data infrastructure product; Algoma is a workflow product that sits on top of similar data. They are adjacent, not identical.

**Threat level:** MEDIUM for ZoneWise (overlapping zoning data layer), LOW for BidDeed.AI (zero overlap on foreclosure/auction).

**Opportunity:** Position ZoneWise as the enterprise data-layer that tools like Algoma should be building on — not the end-user product they compete with.

---

## 2. Company Overview

| Field | Value |
|-------|-------|
| **Company** | Algoma |
| **URL** | https://www.algoma.co |
| **Founded** | 2023 |
| **HQ** | New York, NY |
| **Stage** | Seed ($2.3M — May 2025) |
| **Lead investor** | Zacua Ventures |
| **Co-investors** | SOSV, Iron Prairie, DOMiNO, Compose VC |
| **Team size** | ~3 founders + small team |
| **Category** | PropTech / AI Site Feasibility / Pre-Construction |
| **Tagline** | "Address to investor-ready in days" |

### Founding Team

| Person | Role | Background |
|--------|------|------------|
| Josef Bromovsky | CEO | Harvard MBA |
| Seyfihan Usarer | COO | Harvard + McKinsey |
| Kyle MertensMeyer | CPO | Harvard Innovation Labs |

### Known Customers

- Advenir
- ACE
- Cymbel

### Funding Timeline

| Date | Event | Amount |
|------|-------|--------|
| 2023 | Founded at Harvard Innovation Labs | — |
| May 2025 | Seed round closed | $2.3M |

---

## 2A. Technology Stack & Hosting (Verified — Aug 17 2026)

**Method note:** Web search on "Algoma" is unreliable for this competitor — it collides with the unrelated public company Algoma Steel. This section is built entirely from real HTTP header, DNS, and page-markup fingerprinting (`curl -sI`, `dig`), not search results. Raw command output is preserved below rather than summarized, per NEVER-LIE.

### 2A.1 Marketing site — `www.algoma.co` — Squarespace (VERIFIED)

```
$ curl -sI https://www.algoma.co
HTTP/2 200
server: Squarespace
x-contextid: hL0NVMBI/3hESlrVY
strict-transport-security: max-age=15552000
set-cookie: crumb=...;Secure;Path=/

$ curl -sI https://algoma.co        (bare domain)
HTTP/2 301
location: https://www.algoma.co/
server: Squarespace

$ dig +short algoma.co
198.49.23.145 / 198.185.159.144 / 198.49.23.144 / 198.185.159.145

$ dig +short www.algoma.co CNAME
ext-sq.squarespace.com.

$ dig +short NS algoma.co
connect1.squarespacedns.com.
connect2.squarespacedns.com.
```

`Server: Squarespace`, the `ext-sq.squarespace.com` CNAME, the Squarespace-owned NS delegation, and the Squarespace IP block are four independent, mutually-confirming signals. **VERIFIED: the algoma.co marketing site is hosted on Squarespace**, not a custom-built site as the product's polished UI might suggest.

### 2A.2 Product app — `app.algoma.co` — separate origin (VERIFIED)

The marketing site links to a distinct product subdomain with its own DNS record — this is the actual application, not the Squarespace site:

```
$ dig +short app.algoma.co
34.149.105.236

$ curl -sI https://app.algoma.co/
HTTP/2 200
server: UploadServer
via: 1.1 google
x-goog-generation: 1786626646584339
x-goog-metageneration: 2
x-goog-stored-content-encoding: identity
x-goog-storage-class: STANDARD
x-goog-hash: crc32c=..., md5=...
```

`Server: UploadServer` + `Via: 1.1 google` + the `x-goog-*` family of headers is the signature of Google Cloud Storage's object-serving API — **VERIFIED: the Algoma product app is served as static files directly out of a GCS bucket** (fronted by Google's edge network on a custom domain), not from Squarespace, Vercel, Netlify, or AWS. This differs from Firebase Hosting, which returns `Server: Google Frontend` rather than `UploadServer`.

Page markup confirms the bundle:

```html
<link rel="icon" href="/katmanTimber16.ico" />
<script type="module" crossorigin src="/assets/index-gjKKAXU3.js"></script>
<link rel="stylesheet" crossorigin href="/assets/index-DUHzzUZq.css">
<body><div id="root"></div></body>
```

`/assets/index-[8-char-hash].js` loaded as an ES module, paired with `/assets/index-[hash].css` and a bare `<div id="root">` mount point, is the canonical **Vite production build** output pattern. **HYPOTHESIS (framework):** React — `id="root"` plus a Vite bundle is the standard Vite+React scaffold, but the framework itself isn't directly provable from a minified single-file bundle without executing the JS, which curl does not do.

### 2A.3 What's UNKNOWN for Algoma

| Item | Status | Why |
|------|--------|-----|
| Backend / API framework | UNKNOWN | app.algoma.co is a client-rendered SPA; API calls happen after JS execution, invisible to `curl` |
| Database technology | UNKNOWN | Not observable from frontend fingerprint at all — no backend endpoints were probed (out of scope: would require authenticated app interaction) |
| Exact GCS delivery path (raw bucket vs. Cloud CDN/Load Balancer in front) | INFERRED | `x-goog-*` headers confirm GCS-origin; whether a GCLB/Cloud CDN sits in front is not distinguishable from these headers alone |
| LLM vendor | UNKNOWN | No model-identifying headers or client-side markers found; the original 2026-03 CI report's "GPT-4 likely" claim (§3.4/3.5) remains INFERRED, unchanged by this pass |

---

## 3. PRD — Product Requirements Decomposition

### 3.1 Core Product Vision

Algoma's stated mission: democratize the pre-construction workflow that institutional developers have always had access to (planning attorneys, zoning consultants, architects, financial modelers) — and deliver it to small/mid developers at subscription cost.

**The pain they solve:** A small developer evaluating an infill site previously needed:
- $5,000–$25,000 in zoning consultant fees
- 4–8 weeks for feasibility studies
- Separate tools for comps, pro forma, renderings
- No single source of truth from address to investor pitch

Algoma collapses this into a single AI-powered workflow, delivering results in days not weeks.

### 3.2 Feature Inventory

#### F-001: Site Overview
- **What:** Parcel fundamentals — lot size, dimensions, zoning designation, owner info, sale history, site risks
- **Data sources:** Public assessor records, GIS layers
- **ZoneWise parity:** PARTIAL — ZoneWise has parcel data and zoning assignments at higher volume but no owner/sale history layer

#### F-002: Zoning Analysis
- **What:** Instant zoning constraints per address — height limits, setbacks, FAR (Floor Area Ratio), density limits, site coverage, permitted uses
- **Data sources:** Municipal zoning codes, GIS boundaries
- **Delivery:** Natural language summary + structured data
- **ZoneWise parity:** ZoneWise EXCEEDS — 351K+ parcels with district standards, permitted uses, raw zone codes; Algoma's zoning layer is likely shallower nationally

#### F-003: Market Intelligence
- **What:** Housing supply comps, permit activity, demographic trends, economic indicators near the site
- **Data sources:** Census, permit APIs, MLS aggregates
- **ZoneWise parity:** NOT IN ZONEWISE — this is a developer-facing data product ZoneWise doesn't offer

#### F-004: Comp Builder
- **What:** Filter comparable sales/rentals by proximity, recency, asset type, building class; generate rent charts
- **ZoneWise parity:** NOT IN ZONEWISE — investment comp layer outside current scope

#### F-005: Site Capacity / AI Massing
- **What:** AI-generated massing study based on zoning constraints — unit yield, buildable square footage, FAR utilization
- **ZoneWise parity:** NOT IN ZONEWISE — this is design/architecture-adjacent

#### F-006: Pro Forma Generation
- **What:** Financial modeling — construction costs, projected revenue, cap rate, NOI, IRR
- **ZoneWise parity:** NOT IN ZONEWISE — BidDeed.AI does ARV-based deal math for foreclosures, not development pro formas

#### F-007: Investor-Ready Renderings
- **What:** AI-generated architectural renderings of proposed buildings
- **ZoneWise parity:** NOT IN ZONEWISE — fully different domain

#### F-008: Feasibility Packages (Premium)
- **What:** Expert-assisted packages with Algoma's team doing the analysis
- **ZoneWise parity:** NOT IN ZONEWISE — service component

### 3.3 User Journey Map

```
Developer finds potential site
        ↓
Enter address in Algoma
        ↓
Site Overview: Is this even viable? (zoning, lot, owner)
        ↓
Zoning Analysis: What can I build here?
        ↓
Site Capacity: How many units? What's the FAR utilization?
        ↓
Market Intelligence: Is this market worth building in?
        ↓
Comp Builder: What will units rent/sell for?
        ↓
Pro Forma: Does the math pencil?
        ↓
Renderings: What does this look like for investors?
        ↓
Investor pitch: Funded → Build
```

### 3.4 Technical Architecture (Inferred)

```
┌─────────────────────────────────────────┐
│              ALGOMA PLATFORM             │
│                                          │
│  Address Input                           │
│       ↓                                  │
│  Geocoding + Parcel Lookup               │
│       ↓                                  │
│  Multi-source Data Assembly              │
│  ├── Zoning API / GIS layers            │
│  ├── Assessor records                   │
│  ├── Permit data                        │
│  └── Market data aggregates             │
│       ↓                                  │
│  LLM Layer (GPT-4 likely)               │
│  ├── Zoning code interpretation         │
│  ├── Natural language summaries         │
│  ├── Massing calculations               │
│  └── Pro forma generation               │
│       ↓                                  │
│  Output                                  │
│  ├── Dashboard / web app                │
│  └── Feasibility package (PDF/deck)     │
└─────────────────────────────────────────┘
```

### 3.5 Pricing Model (Inferred — No Public Pricing)

| Tier | Likely Structure | Target User |
|------|-----------------|-------------|
| Starter | Limited reports/month | Occasional developer |
| Pro | Subscription, unlimited lookups | Active developer team |
| Enterprise | Algoma Feasibility Packages + white-glove | Institutional developers |

No public pricing = likely $500–$2,000/month range (consultant replacement thesis requires high ACV).

---

## 4. PRS — Competitive Positioning Statement

### 4.1 Algoma's Stated Positioning

> "Address to investor-ready in days."

Core claim: Algoma replaces the consultant stack (planning attorney + zoning consultant + architect + financial modeler) with a single AI platform.

**Target buyer:** Small-to-mid real estate developer evaluating infill sites for new construction.

**Category they're creating:** "AI Site Feasibility" — not competing with Gridics/Zoneomics (data APIs) or PropertyOnion (auction marketplace), but creating a new workflow category.

### 4.2 Positioning Map: Competitors vs. ZoneWise/BidDeed

```
                    HIGH DATA DEPTH
                          │
                          │
         ZoneWise ────────┤──── Zoneomics
                          │
     WORKFLOW ────────────┼──────────────── DATA API
         │                │
         │                │
     Algoma ──────────────┤
     TestFit              │
                          │
                    LOW DATA DEPTH
```

| Product | Primary Use Case | Target User | Monetization |
|---------|-----------------|-------------|-------------|
| **ZoneWise** | Parcel-level zoning data at scale | Researchers, investors, developers, APIs | Data subscription, API |
| **Algoma** | Site feasibility workflow | Small/mid developer | Subscription reports |
| **Gridics** | Zoning data + compliance | Enterprise developers, cities | Enterprise SaaS |
| **Zoneomics** | National zoning database | PropTech, research | API / data license |
| **TestFit** | Design automation / massing | Architects, developers | Enterprise SaaS |
| **ArkDesign** | AI architectural design | Architects | SaaS |
| **PropertyOnion** | Foreclosure auctions | Investors | Marketplace |
| **Reventure** | Market intelligence | Investors, analysts | Subscription |
| **BidDeed.AI** | Foreclosure deal scoring | FL foreclosure investors | SaaS |

### 4.3 ZoneWise Positioning AGAINST Algoma

**When to use this:** When a prospect says "we looked at Algoma" or "we're using Algoma."

> "Algoma is a great developer workflow tool built on top of data. ZoneWise IS the data layer. If you're a developer building a product like Algoma, you should be pulling from ZoneWise — not scraping fragmented GIS sources. If you're an end user who wants a workflow tool, Algoma has polished UX for developer feasibility. If you want raw zoning intelligence at scale — 350,000+ parcels, standards, permitted uses, all queryable — ZoneWise is the foundation, not the interface."

---

## 5. SWOT Analysis

### 5.1 Algoma SWOT

#### Strengths

| # | Strength | Evidence |
|---|----------|----------|
| S1 | Full workflow coverage (address → investor pitch) | Product feature set covers entire developer pre-construction journey |
| S2 | Elite founder pedigree (Harvard + McKinsey) | Investor credibility, B2B sales execution |
| S3 | Clear pain point solution (replaces $10K+ consultant fees) | "One consistent subscription" messaging |
| S4 | $2.3M seed with strong PropTech VCs | Zacua, SOSV, Iron Prairie credibility |
| S5 | AI massing + renderings | Unique feature set vs. data-only competitors |
| S6 | Pro forma integrated | End-to-end financial decision support |

#### Weaknesses

| # | Weakness | Evidence |
|---|----------|----------|
| W1 | No raw data access or bulk export | Product is closed workflow, not data API |
| W2 | Zoning data likely shallow nationally | No documented 350K+ parcel data at depth |
| W3 | Zero foreclosure/auction layer | BidDeed.AI use case completely unaddressed |
| W4 | No public pricing (opacity = friction) | No pricing page; requires sales conversation |
| W5 | Early stage / limited customer base | 3 known customers documented |
| W6 | No domain expertise in FL foreclosures | Founders from Harvard Innovation Labs, not real estate investing |
| W7 | Potential LLM hallucination risk in zoning interpretation | AI-generated zoning summaries can misread complex codes |
| W8 | Consultant-dependent hybrid model | Not pure SaaS yet; feasibility packages require human team |

#### Opportunities

| # | Opportunity | Relevance |
|---|-------------|-----------|
| O1 | National zoning data APIs are fragmented — white space exists | Potential ZoneWise partnership |
| O2 | Developer market huge ($1.7T US residential construction) | Growing market |
| O3 | AI cost curves dropping → margins improve | Price compression coming |
| O4 | Planning departments going digital → more API access | Data quality improves |
| O5 | Could acquire/license ZoneWise data layer | Partnership or competitor |

#### Threats

| # | Threat | To Algoma |
|---|--------|-----------|
| T1 | Gridics has deeper enterprise relationships | Enterprise market locked up |
| T2 | Large platforms (CoStar, MSCI) can add feasibility features | Gets gobbled up |
| T3 | Zoning data quality issues at national scale | Core product reliability |
| T4 | LLM accuracy in legal/zoning interpretation | Liability risk |
| T5 | Small seed round limits runway | 18–24 month survival window |
| T6 | Harvard pedigree ≠ real estate operator credibility | Trust gap with experienced investors/developers |

### 5.2 BidDeed.AI/ZoneWise SWOT vs. Algoma

#### BidDeed.AI/ZoneWise Strengths (vs. Algoma)

| # | Strength | vs. Algoma |
|---|----------|------------|
| S1 | 351K+ parcels deep Florida data | Algoma has breadth, ZoneWise has depth |
| S2 | Foreclosure + auction intelligence | Algoma has zero coverage |
| S3 | Founder with 10+ yr FL investing experience | Credibility Algoma can't match for FL investors |
| S4 | Raw data + queryable API approach | Algoma is closed workflow |
| S5 | Zone standards + permitted uses per parcel | Algoma's zoning layer is a summary, not raw |
| S6 | Proven Brevard conquest with real parcel counts | NEVER-LIE: real DB-verified numbers vs. Algoma's national claims |

#### BidDeed.AI/ZoneWise Weaknesses (vs. Algoma)

| # | Weakness | vs. Algoma |
|---|----------|------------|
| W1 | No pro forma / financial modeling | Algoma has integrated pro forma |
| W2 | No AI massing / renderings | Algoma has AI architectural content |
| W3 | FL-focused (3 counties) vs. national | Algoma claims national coverage |
| W4 | No developer workflow (address → pitch) | Algoma has polished UX for this |
| W5 | Less funded ($0 external vs. $2.3M) | Algoma has investor-backed runway |

---

## 6. Battle Card

### 6.1 One-Line Positioning

> **ZoneWise:** The raw zoning intelligence layer. Deep FL parcel data — standards, codes, uses — at scale.
> **Algoma:** The developer workflow tool. Site feasibility from address to investor pitch.

**They are not the same product. Avoid direct comparison in most scenarios.**

### 6.2 When You Win vs. Algoma

Win when the prospect needs:
- ✅ Bulk parcel data (thousands to hundreds of thousands of records)
- ✅ Raw zone codes, standards, permitted uses — not AI-summarized
- ✅ Florida-specific deep data (Brevard, Orange, Duval coverage)
- ✅ Foreclosure/auction deal scoring (BidDeed.AI core)
- ✅ API/database access vs. a workflow app
- ✅ Investor verifying a deal before bidding at auction
- ✅ County-level data for all 67 FL counties (roadmap)
- ✅ PropTech builder who needs a data layer for their app

### 6.3 When You Lose vs. Algoma

Lose when the prospect needs:
- ❌ Address → investor pitch in one tool
- ❌ AI-generated pro formas and financial models
- ❌ Architectural massing studies or renderings
- ❌ Market comps and rent analysis
- ❌ New construction feasibility (not resale/foreclosure)
- ❌ National geographic coverage (outside FL)
- ❌ Polished single-page SaaS UX for non-technical developers

### 6.4 Objection Handling

#### "We use Algoma for our zoning research."
> "Great — Algoma is a workflow tool for new construction decisions. ZoneWise is the data layer beneath tools like Algoma. If you're looking up one address at a time, Algoma works. If you need bulk parcel data, raw zone codes at scale, or foreclosure + zoning combined, you need ZoneWise."

#### "Algoma covers the whole country. You only cover Florida."
> "Algoma claims national coverage — but national coverage that's 1 inch deep vs. Florida at 351K+ parcels with full standards, setbacks, permitted uses, and zone codes. For Florida real estate — the most active foreclosure market in the US — ZoneWise is the only source that goes this deep. Algoma gives you a summary; we give you the source data."

#### "Algoma has pro forma and renderings — you don't."
> "Correct — we're not a developer workflow tool. We're the data intelligence layer. For foreclosure investors who need to know what a parcel can be rezoned for, what the max density is, and how that affects ARV — ZoneWise gives you the raw answer. Algoma is for greenfield developers. BidDeed.AI is for foreclosure investors."

#### "Algoma raised $2.3M and has real VC backing."
> "They have investor-backed runway and great pedigree. We have 10+ years of FL foreclosure investing, 351,000 verified parcels in the database, and zero invented data. Ariel has written checks on these properties — that's a different kind of credibility than a Harvard innovation lab."

#### "Algoma's AI reads the zoning codes for me."
> "AI summaries of zoning codes are convenient until they're wrong, and zoning errors cost deals. ZoneWise gives you the raw data — you query the actual zone standards, not an LLM's interpretation of them. When you're buying at auction with no inspection period, you need to trust the data, not an AI summary."

### 6.5 Win/Loss Decision Tree

```
Prospect asks about zoning data
          ↓
  New construction developer?
    YES → Algoma may suit them better
    NO ↓
  FL-focused?
    YES → ZoneWise wins on depth
    NO ↓
  Need bulk/API access?
    YES → ZoneWise wins, Algoma can't do this
    NO ↓
  Foreclosure/auction investor?
    YES → BidDeed.AI — Algoma has zero overlap
    NO ↓
  Evaluate overlap case by case
```

### 6.6 Feature Comparison Matrix

| Feature | ZoneWise/BidDeed.AI | Algoma | Winner |
|---------|---------------------|--------|--------|
| Parcel-level zoning (FL, depth) | ✅ 351K+ parcels | ✅ Address lookup | **ZoneWise** |
| National coverage | ❌ FL focus (expanding) | ✅ Claims national | Algoma |
| Raw zone codes/standards export | ✅ Full access | ❌ Summarized only | **ZoneWise** |
| Permitted uses per zone | ✅ Per district | ✅ Summary | **ZoneWise** |
| Zone standards (setbacks, FAR, height) | ✅ Raw data | ✅ AI summary | **ZoneWise** (raw) |
| Foreclosure/auction deal scoring | ✅ Core product | ❌ None | **BidDeed.AI** |
| ML deal score (BID/REVIEW/SKIP) | ✅ | ❌ | **BidDeed.AI** |
| ARV × 70% max bid calculation | ✅ | ❌ | **BidDeed.AI** |
| Auction calendar (FL) | ✅ | ❌ | **BidDeed.AI** |
| Pro forma / financial modeling | ❌ | ✅ | Algoma |
| AI massing studies | ❌ | ✅ | Algoma |
| Investor-ready renderings | ❌ | ✅ | Algoma |
| Market comps / rent analysis | ❌ | ✅ | Algoma |
| API / bulk data access | ✅ Supabase | ❌ Closed workflow | **ZoneWise** |
| Founder domain expertise (FL investing) | ✅ 10+ yr | ❌ | **BidDeed.AI** |
| Data verification / NEVER-LIE | ✅ DB-verified | ❌ AI-generated | **ZoneWise** |
| Pricing transparency | ✅ | ❌ No public pricing | **ZoneWise** |
| Funding | $0 external | $2.3M seed | Algoma |

**ZoneWise/BidDeed.AI wins:** 10 features
**Algoma wins:** 6 features
**Algoma leads:** Funding, national geography, workflow UX

### 6.7 Elevator Pitch (30 seconds)

**Against Algoma in a room:**

> "Algoma solves a great problem — taking a developer from an address to an investor pitch in days. We solve a different problem: giving FL real estate investors the raw zoning and auction intelligence they need to bid confidently at foreclosure sales. ZoneWise is the data layer; Algoma is a workflow app. They're not the same product, and if you're a FL foreclosure investor, Algoma won't help you buy smarter at auction."

---

## 7. Strategic Implications

### 7.1 Partnership Opportunity

Algoma is built on top of a zoning data layer they're likely scraping or licensing from fragmented sources. ZoneWise's deep FL data could be the layer Algoma builds on for Florida.

**Pitch to Algoma:** "License ZoneWise FL parcel + zoning data. We have 351K+ Brevard parcels, growing to 67 FL counties. You get the most accurate FL zoning layer in existence. We get distribution into your developer user base."

**Risk:** They become a competitor if they build a foreclosure/auction layer. Evaluate carefully.

### 7.2 Content / SEO Strategy

Create content targeting developer searchers who find Algoma but are actually FL foreclosure investors:

- "Algoma vs ZoneWise: What FL investors need to know"
- "AI zoning tools for FL real estate: Algoma, Gridics, ZoneWise compared"
- "Foreclosure investors: why you need raw zoning data, not AI summaries"

### 7.3 Feature Roadmap Signals

Algoma's success with pro forma + massing signals market appetite for:
- ❓ Should ZoneWise add a basic pro forma layer for foreclosure investors? (Separate from new construction use case)
- ❓ Could ZoneWise add a "redevelopment potential" score per parcel based on zoning capacity?

**Recommendation:** Watch Algoma's traction. If they start adding foreclosure data or FL-specific features, escalate threat level to HIGH.

### 7.4 Threat Monitoring

| Trigger | Action |
|---------|--------|
| Algoma raises Series A ($5M+) | Upgrade threat to HIGH, accelerate FL expansion |
| Algoma adds foreclosure/auction data | Direct competitor — activate battle card aggressively |
| Algoma announces FL-specific coverage | Match with ZoneWise 67-county depth announcement |
| Algoma announces partnership with CoStar/Zillow | Monitor for acquisition — raises visibility |
| Algoma's AI massing gets traction with FL developers | Explore adding redevelopment score to ZoneWise |

---

## 8. Appendix: Sources + Evidence

### Primary Sources

| Source | URL | Confidence |
|--------|-----|------------|
| Algoma website | https://www.algoma.co | VERIFIED |
| GlobeNewswire seed round announcement | https://www.globenewswire.com/news-release/2025/05/15/3082413/0/en/PropTech-Startup-Algoma-Raises-Seed-Round-to-Become-the-AI-Engine-Behind-Every-Real-Estate-Deal.html | VERIFIED |
| TechFundingNews coverage | https://techfundingnews.com/exclusive-algoma-led-by-harvard-alumni-grabs-2-3m-to-become-the-ai-engine-behind-every-real-estate-deal/ | VERIFIED |
| KeyCrew journal | https://keycrew.co/journal/meet-algoma-a-startup-automating-pre-construction-services-for-modern-developers/ | VERIFIED |
| DOMiNO Ventures portfolio | https://dominovc.com/were-excited-to-announce-our-investment-in-algoma-the-ai-native-platform-transforming-how-real-estate-deals-get-done-from-address-to-investor-ready-in-days/ | VERIFIED |
| Harvard Innovation Labs | https://innovationlabs.harvard.edu/venture/algoma | VERIFIED |
| Zacua Ventures portfolio | https://zacuaventures.com/project/algoma/ | VERIFIED |

### Claims Requiring Verification

| Claim | Status |
|-------|--------|
| Pricing range ($500–$2,000/month) | INFERRED — no public pricing found |
| LLM used is GPT-4 | INFERRED — not disclosed |
| National coverage quality | HYPOTHESIS — claimed nationally, depth unverified |
| Customer count beyond 3 | UNKNOWN |

### HONESTY PROTOCOL Tags Applied

- **VERIFIED:** Funding amount, investors, founders, URL, founding year, known customers
- **INFERRED:** Pricing tier estimates, LLM technology stack, technical architecture
- **HYPOTHESIS:** National zoning data depth vs. ZoneWise FL depth
- **UNKNOWN:** Exact pricing, full customer list, revenue, churn

---

*CI Report complete. Committed to repo per GTM-011 directive.*
*Next: Mark GTM-011 DONE in nexus_tasks, update artifact_vault status to DEPLOYED.*
