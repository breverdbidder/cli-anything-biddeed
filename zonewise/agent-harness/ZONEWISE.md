# ZONEWISE.md — Project-Specific Analysis & SOP

## Architecture Summary

ZoneWise is a multi-county zoning data scraper that collects, parses, and structures
zoning ordinance data from Florida county websites. Unlike GUI targets, ZoneWise
operates as a data pipeline: scrape HTML → parse zoning codes → structure JSON → persist to Supabase.

```
┌────────────────────────────────────────────────┐
│              County Websites (67 FL)            │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐    │
│  │ Brevard  │ │  Miami   │ │  Orange      │    │
│  │ County   │ │  -Dade   │ │  County      │ …  │
│  └────┬─────┘ └────┬─────┘ └────┬─────────┘    │
└───────┼────────────┼────────────┼───────────────┘
        │            │            │
   ┌────┴────────────┴────────────┴────────┐
   │         Tiered Scraping Pipeline       │
   │  Tier1: Firecrawl → Markdown           │
   │  Tier2: Gemini Flash → Structured JSON │
   │  Tier3: Claude Sonnet → Complex Zoning │
   │  Tier4: Manual Flag                    │
   └────────────────────┬──────────────────┘
                        │
   ┌────────────────────┴──────────────────┐
   │         cli-anything-zonewise          │
   │  Click CLI + REPL + --json output      │
   │  --persist → Supabase                  │
   └────────────────────────────────────────┘
```

## Backend Strategy: HTTP API Client

ZoneWise has no local GUI software. The "backends" are:

1. **Firecrawl** — Web scraping API ($83/mo). Converts county websites to clean markdown.
2. **Gemini Flash** — Google's free-tier LLM. Parses markdown into structured JSON zoning records.
3. **Claude Sonnet** — Complex zoning interpretation (Free on Max plan).
4. **Supabase** — Persistence layer for all zoning data.

## Data Model

### County Record
```json
{
  "county": "brevard",
  "state": "FL",
  "last_scraped": "2026-03-11T04:00:00Z",
  "parcels_total": 1247,
  "status": "complete"
}
```

### Zoning Record
```json
{
  "county": "brevard",
  "zone_code": "RS-1",
  "zone_name": "Single Family Residential",
  "category": "residential",
  "min_lot_size_sqft": 7500,
  "max_height_ft": 35,
  "setbacks": {"front": 25, "rear": 20, "side": 7.5},
  "allowed_uses": ["single_family", "home_office"],
  "source_url": "https://..."
}
```

## Command Map

| Agent Action | CLI Command |
|-------------|-------------|
| Scrape a county | `county scrape --county brevard` |
| List counties | `county list --state FL` |
| Check scrape status | `county status --county brevard` |
| Look up single parcel | `parcel lookup --address "123 Main St"` |
| Batch parcel lookup | `parcel batch --input parcels.csv` |
| Export to Supabase | `export supabase --county brevard` |
| Export CSV | `export csv --county brevard -o data.csv` |
