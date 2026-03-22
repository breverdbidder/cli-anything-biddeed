# Competitor Diff Report: Foreclosure.com vs BidDeed.AI PropertySearchGrid

**Generated:** 2026-03-22 07:11 UTC
**Competitor URL:** https://www.foreclosure.com/listing/search-results/?stateCode=FL
**BidDeed.AI Component:** components/competitor-lens/PropertySearchGrid.jsx
**BrandGuard Score:** PASS 100/100

---

## TL;DR

Foreclosure.com shows a list of properties with stage badges. BidDeed.AI shows
*which ones to bid on* with ML scores, max bid calculations, and lien risk flags —
all powered by our Supabase intelligence layer.

---

## Feature Comparison

| Feature | Foreclosure.com | BidDeed.AI PropertySearchGrid | Delta |
|---------|-----------------|-------------------------------|-------|
| **Multi-filter search** | ✅ Location/type/price/stage | ✅ County/stage/price/score/lien | Parity+ |
| **Property cards with photos** | ✅ Photo + price + beds/baths | ✅ Cards (no photo — data-first) | Foreclosure+ |
| **Price display** | ✅ Asking/listing price | ✅ Opening bid | Parity |
| **Stage badges** | ✅ Pre-Fore/Auction/REO | ✅ Sale type + BID/REVIEW/SKIP | **BidDeed+** |
| **Sort options** | ✅ Price/newest/relevant | ✅ + Deal Score sort | **BidDeed+** |
| **Grid/list toggle** | ✅ Grid/list/map | ✅ Grid/list | Competitor+ (map) |
| **Export/CSV** | ✅ Export button | ✅ Export CSV with ML data | Parity+ |
| **Email alerts** | ✅ Per-search alerts | ❌ Not yet (Sprint 4) | Competitor+ |
| **Save search** | ✅ Save search feature | ❌ Not yet (Sprint 4) | Competitor+ |
| **Interactive map** | ✅ Google Maps cluster | ❌ Not yet (Sprint 4) | Competitor+ |
| **ML Deal Score** | ❌ No scoring | ✅ BID/REVIEW/SKIP + numeric | **BidDeed+** |
| **Max bid calculation** | ❌ No formula | ✅ ARV×70%-Repairs-$10K-Margin | **BidDeed+** |
| **Lien status indicator** | ❌ No lien data | ✅ Clean/Risky/Unknown badge | **BidDeed+** |
| **County auction link** | ❌ Stays on their site | ✅ Direct RealForeclose link | **BidDeed+** |
| **ARV estimate display** | ❌ No ARV data | ✅ ARV shown per property | **BidDeed+** |
| **Auction date prominence** | ❌ Buried in detail | ✅ Shown on card with urgency | **BidDeed+** |
| **Days-until-auction badge** | ❌ Not shown | ✅ "3d left" with orange alert | **BidDeed+** |
| **Deal score filter** | ❌ Not available | ✅ Min score slider in sidebar | **BidDeed+** |
| **Dark UI** | ❌ White background | ✅ Dark-first #020617 | **BidDeed+** |
| **Auth required** | ✅ Feature gating | ❌ Open data (Supabase RLS) | Different model |

---

## UX Pattern Analysis

### Filter Architecture
**Foreclosure.com:**
```
Location bar (hero) → Type dropdown → [Search] → Sidebar: price/beds/baths/stage
```
**BidDeed.AI:**
```
Sidebar: County / Stage / Price / Min Score / Lien Status → Live filter on Supabase data
```
**Delta:** BidDeed.AI adds 2 intelligence-layer filters (Deal Score, Lien Status) that
Foreclosure.com cannot offer because they have no ML layer.

### Property Card Design
**Foreclosure.com fields:** Photo · Address · Price · Beds/Baths/Sqft · Stage badge · Days on market
**BidDeed.AI fields:**
- BID/REVIEW/SKIP badge + ML score
- Opening bid + Max bid (ARV formula)
- ARV estimate + Repairs estimate
- Auction date with days-until urgency badge
- Lien status (Clean/Risky/Unknown)
- Stage badge (secondary)
- Plaintiff name
- County auction platform link

**BidDeed.AI improvement:** Every field drives a specific investment decision. Foreclosure.com's
beds/baths/sqft are relevant to retail buyers, not foreclosure investors.

### Sort Options
**Foreclosure.com:** Newest · Price H-L · Price L-H · Relevance
**BidDeed.AI:** Newest · Price H-L · Price L-H · Deal Score: Best First · Auction Date: Soonest

**"Deal Score: Best First"** is a sort option no competitor can offer without an ML layer.

### Status Badge System
**Foreclosure.com:** Red=Pre-Foreclosure, Yellow=Auction, Blue=Bank-Owned (passive stage info)
**BidDeed.AI:** BID (emerald) / REVIEW (amber) / SKIP (red) = **action-oriented signals**

The shift from "what stage is this?" to "what should I do?" is the core UX differentiation.

---

## Brand Comparison

| Brand Element | Foreclosure.com | BidDeed.AI |
|--------------|-----------------|-----------|
| Background | White (#FFFFFF) | Slate-950 (#020617) |
| Primary | Red (#CC0000) | Navy (#1E3A5F) |
| CTA color | Red | Orange (#F59E0B) |
| Font | System/generic | Inter |
| Badge system | Stage labels (passive) | Action signals (active) |
| Dark mode | Not available | Native |
| Density | Low (marketing-heavy) | High (data-dense) |

---

## Competitive Advantages Delivered

1. **BID/REVIEW/SKIP replaces browsing** — Foreclosure.com users must open every property.
   BidDeed.AI users see the action signal on the card. SKIP = don't open.

2. **Max bid shown on card** — Investors know their number before clicking in. Foreclosure.com
   shows asking price only.

3. **Lien status filter** — Filter OUT risky properties before browsing. Foreclosure.com has
   no lien awareness at any level.

4. **Deal Score sort** — "Show me the best deals first" is the #1 investor need. Foreclosure.com
   cannot offer this without ML infrastructure.

5. **Auction urgency badge** — "3d left" in orange on the card creates urgency. Foreclosure.com
   buries auction dates in detail views.

6. **Direct county platform link** — Investor workflow ends at RealForeclose, not our site.
   We send them where they need to go. Foreclosure.com keeps them on their platform.

---

## Feature Gaps (Foreclosure.com has, BidDeed.AI needs)

| Gap | Priority | Sprint |
|-----|----------|--------|
| Property photos | MEDIUM | Sprint 4 (integrate image API) |
| Interactive map view | HIGH | Sprint 4 (Mapbox GL) |
| Email alerts per search | HIGH | Sprint 4 |
| Save/watchlist search | HIGH | Sprint 4 |
| Beds/baths filter | LOW | Sprint 4 (low investor relevance) |

---

## Reusable Patterns Extracted

| Pattern | Extracted To | Reuse Count |
|---------|-------------|-------------|
| `multi-filter-search` | ux_pattern_library | 1 |
| `property-card-grid` | ux_pattern_library | 1 |
| `status-badge-system` | ux_pattern_library | 2 (also from PropertyOnion) |
| `save-track-export` | ux_pattern_library | 2 (also from PropertyOnion) |
| `results-toolbar` | ux_pattern_library | 1 |
| `map-cluster-view` | ux_pattern_library | 1 |

---

*Report generated by CompetitorLens Agent #14 · BidDeed.AI DesignWise Squad*
