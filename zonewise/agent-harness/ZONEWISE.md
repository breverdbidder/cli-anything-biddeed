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

## Output Schemas

All outputs MUST be valid JSON. Every response — including errors — MUST be parseable JSON.

### Parcel Scrape Output (Array)
Each record in the array MUST contain:
- `parcel_id`: String matching Brevard format `##-##-##-##-#####.#-####.#` (e.g. `25-36-28-00-00001.0-0001.0`)
- `zone_code`: Non-null string using Brevard prefixes: BU, GU, RS, RU, AU, IU, PUD, PIP, TU, SEU, RR, PA, MHPD, RVP, TR
- `zone_name`: Non-null string (human-readable zone description)
- `category`: One of: residential, commercial, industrial, agricultural, general, planned
- `county`: Lowercase county name (e.g. `"brevard"`)

### Spatial Join Output (Object)
```json
{
  "total_parcels": 351247,        // integer > 0
  "matched_parcels": 340710,      // integer > 0
  "match_rate": 0.97,             // matched/total >= 0.95
  "unmatched_parcels": [],        // array (may be empty)
  "processing_time_seconds": 42.7 // numeric value
}
```

### Municipal Conquest Output (Object)
```json
{
  "municipality": "Palm Bay",                    // exact municipality name
  "gis_source": "https://gis.palmbayflorida.org/...", // must contain municipality GIS domain
  "zone_source": "municipal_gis",                // NEVER "USE_CODE" — use native zoning
  "matched_parcels": 78432,                      // integer (Palm Bay: >50000)
  "zone_code": "RS-1",                           // non-null
  "zone_description": "Single Family Residential" // non-null
}
```

### Supabase Persist Output (Object)
```json
{
  "status_code": 201,             // 200 or 201
  "rows_affected": 10,            // must match input count
  "parcel_ids": ["..."],          // unique array, no duplicates
  "created_at": "2026-04-10T07:30:00Z", // ISO 8601 timestamp
  "county": "brevard"             // lowercase string
}
```

### Error Output (Object)
On invalid input (e.g. non-existent county), return structured error — never raw tracebacks:
```json
{
  "error": "County 'Fakeland' not found in FL county registry.",
  "exit_code": 1,                 // non-zero (1 or 2)
  "county_requested": "Fakeland"  // no null top-level fields
}
```

## Guard Rails
- Do not fabricate parcel counts — query DB for exact numbers
- Do not use USE_CODE mapping when municipal GIS provides native zoning codes
