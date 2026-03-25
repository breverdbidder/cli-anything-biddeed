# PropZone vs ZoneWise — Feature Parity Comparison Spec

**Date:** 2026-03-25
**Author:** BidDeed.AI / Everest Capital USA
**Status:** ACTIVE — Gap closure in progress

---

## Overview

PropZone (Gridics) is the incumbent zoning data provider used by municipalities and real estate professionals in FL. This document maps every feature PropZone exposes against ZoneWise capabilities, identifies gaps, and defines build priorities for achieving parity-plus.

**Competitive hypothesis:** ZoneWise should match PropZone on data completeness, then win on ML predictions, AI chatbot, and 3D massing.

---

## API Architecture Comparison

| Layer | PropZone (Gridics) | ZoneWise |
|-------|-------------------|----------|
| Backend | Drupal 10 REST + GraphQL | Supabase + Python CLI |
| Auth | JWT publicToken (localStorage) + CSRF | Supabase anon/service keys |
| Tiles | CloudFront vector tiles (Mapbox GL) | BCPAO + Supabase |
| SSO | accounts.gridics.com | — |
| File Downloads | AWS API Gateway (auth-gated) | — |

---

## Feature Parity Matrix

| Feature | PropZone | ZoneWise | Gap | Priority |
|---------|----------|----------|-----|----------|
| Zone code | Yes | Yes | — | — |
| Zone sub-code | Yes | Partial | FILL | P1 |
| Zone type (residential/commercial/mixed) | Yes | Partial | FILL | P1 |
| Max height (ft) | Yes | Partial | FILL | P1 |
| Max stories | Yes | Partial | FILL | P1 |
| Setback — front | Yes | Partial | FILL | P1 |
| Setback — side | Yes | Partial | FILL | P1 |
| Setback — rear | Yes | Partial | FILL | P1 |
| Setback — water/riparian | Yes | No | BUILD | P1 |
| Setback — other | Yes | No | BUILD | P2 |
| FAR (Floor Area Ratio) | Yes | Yes | — | — |
| Lot coverage % | Yes | Yes | — | — |
| Residential density (units/acre) | Yes | Partial | FILL | P1 |
| Max dwelling units | Yes | Partial | FILL | P1 |
| Max lodging rooms | Yes | No | BUILD | P2 |
| Max office area (sqft) | Yes | No | BUILD | P2 |
| Max commercial area (sqft) | Yes | No | BUILD | P2 |
| Max built area (sqft) | Yes | No | BUILD | P2 |
| Max building footprint | Yes | Partial | FILL | P1 |
| Min open space % | Yes | Partial | FILL | P1 |
| Allowed uses — residential | Yes (detailed) | No | BUILD | P1 |
| Allowed uses — commercial | Yes (detailed) | No | BUILD | P1 |
| Allowed uses — lodging | Yes (detailed) | No | BUILD | P2 |
| Existing use classification | Yes | Partial | FILL | P2 |
| Tax assessed value | Yes | Via BCPAO | — | — |
| Tax year | Yes | Via BCPAO | — | — |
| Ownership name | Yes | Via BCPAO | — | — |
| Owner address | Yes | Via BCPAO | — | — |
| Lot size (sqft) | Yes | Yes | — | — |
| Year built | Yes | Via BCPAO | — | — |
| Parcel address | Yes | Yes | — | — |
| Lat/lng coordinates | Yes | Yes | — | — |
| Vector tile overlay | Yes | No | BUILD | P3 |
| Print/export to PDF | Yes | No | BUILD | P3 |
| File downloads (AWS gated) | Yes | No | — | P3 |
| **ZoneWise Advantages** | | | | |
| 3D massing model | No | **Yes** | ADVANTAGE | — |
| AI chatbot (zoning Q&A) | No | **Yes** | ADVANTAGE | — |
| ML predictions (deal score) | No | **Yes** | ADVANTAGE | — |
| Foreclosure overlay | No | **Yes** | ADVANTAGE | — |
| ARV calculator | No | **Yes** | ADVANTAGE | — |
| Audit trail / history | No | **Yes** | ADVANTAGE | — |
| Multi-county FL (67) | Partial | **Yes** | ADVANTAGE | — |
| API access for developers | Gated/paid | **Yes (Supabase)** | ADVANTAGE | — |

---

## Gap Closure Roadmap

### Phase 1: Data Completeness (P1 gaps)
*Target: Match PropZone on all critical zoning fields*

**Fields to fill from existing Brevard ordinance data:**
- `zone_subzone` — Parse from zoning district tables
- `zone_type` — Classify R/C/M/I from zone code prefix
- `max_height` — Source from municipal code PDFs (have 85% coverage)
- `max_stories` — Derive from max_height if not explicit
- `setback_front`, `setback_side`, `setback_rear` — Municipal code scraper
- `setback_water` — New: riparian setback from FL DEP data
- `residential_density` — Zoning ordinance table lookup
- `max_units` — Derived: density × lot_size_acres
- `max_building_footprint` — Derived: lot_size × lot_coverage
- `min_open_space` — Inverse of lot_coverage

**Allowed uses (P1 — highest value gap):**
PropZone shows a structured use matrix per zone. ZoneWise has no equivalent.
Build: `allowed_uses` JSONB column with `{residential: bool, commercial: bool, lodging: bool, uses: string[]}`.
Source from: municipal zoning ordinance use tables (Satellite Beach, Melbourne, Palm Bay).

### Phase 2: Secondary Fields (P2 gaps)
- `max_lodging_rooms`, `max_office_area`, `max_commercial_area`, `max_built_area`
- `setback_other` (e.g., garage setbacks)
- `existing_use` classification (improve BCPAO mapping)

### Phase 3: UX Parity (P3)
- Vector tile overlay (Mapbox GL integration)
- PDF export
- Shareable parcel deep-links

---

## Data Source Mapping

| PropZone Field | ZoneWise Source |
|----------------|-----------------|
| zone_code | zoning_assignments.zone_code |
| max_height | zoning_rules.max_height_ft |
| setbacks | zoning_rules.setback_* |
| FAR | zoning_rules.max_far |
| lot_coverage | zoning_rules.max_lot_coverage_pct |
| density | zoning_rules.max_density_units_per_acre |
| allowed_uses | NEW: allowed_uses JSONB (build) |
| tax records | BCPAO API (parcel enricher) |
| ownership | BCPAO API (parcel enricher) |

---

## Supabase Schema: propzone_intel

```sql
create table propzone_intel (
  id              uuid primary key default gen_random_uuid(),
  parcel_id       text not null unique,
  zone_code       text,
  zone_subzone    text,
  zone_type       text,
  max_height      numeric,
  max_stories     int,
  far             numeric,
  lot_coverage    numeric,
  residential_density numeric,
  max_units       int,
  setbacks        jsonb,  -- {front, side, rear, water}
  owner_name      text,
  address         text,
  lot_size_sqft   numeric,
  raw_data        jsonb,
  scraped_at      timestamptz default now(),
  created_at      timestamptz default now()
);

create index propzone_intel_parcel_id_idx on propzone_intel(parcel_id);
create index propzone_intel_zone_code_idx on propzone_intel(zone_code);
create index propzone_intel_scraped_at_idx on propzone_intel(scraped_at desc);
```

---

## CI Scraper Schedule

```yaml
# .github/workflows/propzone-scrape.yml
schedule:
  - cron: '0 8 * * *'   # 3 AM EST nightly

cities:
  - satellite-beach      # Primary — Ariel's market
  - melbourne            # Largest Brevard city
  - palm-bay             # High volume
  - cocoa
  - titusville

gap_threshold: 100       # Alert if gap_count > 100
alert: Telegram bot
storage: Supabase propzone_intel (merge-duplicates on parcel_id)
```

---

## Competitive Positioning

### Where ZoneWise Wins Today
1. **3D Massing** — Visual envelope model PropZone lacks entirely
2. **AI Chatbot** — Natural language zoning Q&A
3. **ML Deal Score** — Foreclosure → zoning → deal quality signal
4. **Multi-county FL** — PropZone is city-by-city; ZoneWise targets all 67 FL counties
5. **Developer API** — Supabase REST, no auth wall

### Where PropZone Wins Today (Gaps to Close)
1. **Allowed uses matrix** — Detailed R/C/L/I use classification
2. **Setback completeness** — Water/riparian setbacks
3. **Secondary dimensions** — Lodging rooms, office/commercial area caps
4. **Tile overlay UX** — Smooth map-click → instant zoning data

### Win Condition
ZoneWise achieves feature parity by Q2 2026, then differentiates on:
- ML-predicted development potential per parcel
- Foreclosure auction overlap (BidDeed.AI integration)
- Automated gap alerts for new municipal ordinances
- Mobile app (PropZone is desktop-only)
