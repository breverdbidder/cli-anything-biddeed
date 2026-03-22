# Competitor Diff Report: PropertyOnion vs BidDeed.AI AuctionCalendar

**Generated:** 2026-03-22 07:11 UTC
**Competitor URL:** https://propertyonion.com/property_search/Brevard?view_type=calendar
**BidDeed.AI Component:** components/competitor-lens/AuctionCalendar.jsx
**BrandGuard Score:** PASS 100/100

---

## TL;DR

PropertyOnion's auction calendar shows *when* auctions happen. BidDeed.AI's version
shows *which* ones to attend — and why.

---

## Feature Comparison

| Feature | PropertyOnion | BidDeed.AI AuctionCalendar | Delta |
|---------|--------------|---------------------------|-------|
| **Calendar grid view** | ✅ Month/week calendar | ✅ Full calendar grid | Parity |
| **List view toggle** | ✅ Toggle available | ✅ Calendar + list toggle | Parity |
| **County filter** | ✅ All 67 FL counties | ✅ All 67 FL counties | Parity |
| **Sale type color-coding** | ✅ Foreclosure vs tax deed | ✅ Extended: MTG/TD/HOA/REO | BidDeed+ |
| **Property count per day** | ✅ Shows count per date | ✅ Shows count per date | Parity |
| **ML Deal Score** | ❌ No scoring | ✅ BID/REVIEW/SKIP per property | **BidDeed+** |
| **Max bid calculation** | ❌ No calculation | ✅ ARV formula inline | **BidDeed+** |
| **Lien priority warnings** | ❌ No lien data | ✅ HOA/senior mortgage flags | **BidDeed+** |
| **ZoneWise zoning overlay** | ❌ Not available | ✅ Zoning data per parcel | **BidDeed+** |
| **County auction platform link** | ❌ No direct link | ✅ Direct RealForeclose link | **BidDeed+** |
| **BID/REVIEW/SKIP badges** | ❌ No action signal | ✅ Per-property action badge | **BidDeed+** |
| **Interactive map** | ❌ Not on calendar | ❌ Not on calendar (Sprint 4) | Deferred |
| **Email alerts** | ✅ Daily digest | ❌ Not yet (Sprint 4) | Competitor+ |
| **Save properties** | ✅ Watchlist | ❌ Not yet (Sprint 4) | Competitor+ |
| **Mobile responsive** | ✅ Full responsive | ✅ Tailwind responsive | Parity |
| **Dark theme** | ❌ Light only | ✅ Dark bg-[#020617] | **BidDeed+** |
| **Data source** | Live public records | ✅ Supabase multi_county_auctions | Parity |

---

## UX Pattern Analysis

### Navigation Flow
**PropertyOnion:**
```
Search bar → County dropdown → View type toggle → Calendar grid → Click date → Property list modal
```
**BidDeed.AI:**
```
County selector → Month/week toggle → Calendar grid → Click date → Inline property drawer (ML scores visible)
```
**Delta:** BidDeed.AI surfaces deal quality BEFORE the click. No wasted clicks on SKIP properties.

### Calendar Grid Pattern
**PropertyOnion:** Date cells show property count badge. Click opens a modal list.
**BidDeed.AI:** Date cells show count + top deal score badge (e.g., "3 props · BID 82").
Color intensity maps to deal quality — brighter = better.

**BidDeed.AI improvement:** Users can visually scan the calendar for high-opportunity days
without opening any individual property.

### Property Card (within day modal)
**PropertyOnion fields:** Address · Status badge · Opening bid · Sale type
**BidDeed.AI fields:** Address · ML score (BID/REVIEW/SKIP) · Opening bid · Max bid · Lien warning · Sale type · County auction link

**BidDeed.AI improvement:** 4 additional intelligence fields that directly drive buy/skip decisions.

---

## Brand Comparison

| Brand Element | PropertyOnion | BidDeed.AI |
|--------------|--------------|-----------|
| Background | White (#FFFFFF) | Slate-950 (#020617) |
| Primary color | Orange (#F97316) | Navy (#1E3A5F) |
| Accent | Green (#16a34a) | Orange (#F59E0B) |
| Font | System font | Inter |
| Status badges | Green/yellow/red (generic) | BID/REVIEW/SKIP (action-oriented) |
| Dark mode | Not available | Native dark-first |

---

## Competitive Advantages Delivered

1. **ML scoring replaces guessing** — PropertyOnion makes all listings look equal. BidDeed.AI
   surfaces the 20% worth attending from the 80% to skip.

2. **Max bid shown inline** — No more back-of-napkin math at the auction. ARV × 70% - Repairs
   - $10K - MIN($25K,15%×ARV) is calculated per property.

3. **Lien stack awareness** — HOA foreclosures let senior mortgages survive. PropertyOnion
   shows nothing. BidDeed.AI flags this before you waste $5K in deposit money.

4. **County auction link** — One click to RealForeclose. PropertyOnion links to their own
   detail page, adding a navigation step.

5. **Dark professional UI** — Signals platform maturity vs PropertyOnion's generic light theme.

---

## Feature Gaps (PropertyOnion has, BidDeed.AI needs)

| Gap | Priority | Sprint |
|-----|----------|--------|
| Email alerts for new listings | HIGH | Sprint 4 |
| Save/watchlist properties | HIGH | Sprint 4 |
| Sharing/export of calendar view | MEDIUM | Sprint 4 |
| Public-facing county page URLs | MEDIUM | Sprint 4 |

---

## Reusable Patterns Extracted

| Pattern | Extracted To | Reuse Count |
|---------|-------------|-------------|
| `auction-calendar-grid` | ux_pattern_library | 1 |
| `county-multi-select` | ux_pattern_library | 1 |
| `sale-type-color-coding` | ux_pattern_library | 1 |
| `calendar-list-view-toggle` | ux_pattern_library | 1 |

---

*Report generated by CompetitorLens Agent #14 · BidDeed.AI DesignWise Squad*
