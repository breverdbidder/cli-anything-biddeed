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

## Output Format Specifications

All outputs MUST be valid JSON. Every response uses one of the schemas below.

### Parcel Scrape Output (array)
```json
[
  {
    "parcel_id": "##-##-##-##-#####.#-####.#",
    "zone_code": "BU-1",
    "zone_name": "General Commercial",
    "category": "commercial",
    "county": "brevard",
    "zone_source": "county_gis"
  }
]
```
- `parcel_id`: Brevard format `##-##-##-##-#####.#-####.#` (regex: `^\d{2}-\d{2}-\d{2}-\d{2}-\d{5}\.\d-\d{4}\.\d$`)
- `zone_code`: Must start with known prefix: BU, GU, RS, RU, AU, IU, PUD, PIP, TU, SEU, RR, PA, MHPD, RVP, TR
- `zone_name`: Human-readable, never null
- `zone_source`: One of `county_gis | fl_gio | use_code_crosswalk | municipal_gis | firecrawl`

### Spatial Join Output (object)
```json
{
  "total_parcels": 351247,
  "matched_parcels": 340710,
  "match_rate": 0.97,
  "unmatched_parcels": [],
  "processing_time_seconds": 42.7,
  "method": "STRtree_bulk",
  "county": "brevard"
}
```
- `total_parcels`: Integer > 0
- `matched_parcels`: Integer > 0
- Match rate (`matched_parcels / total_parcels`) must be >= 0.95
- `unmatched_parcels`: Always an array (empty if none)
- `processing_time_seconds`: Numeric value

### Municipal Conquest Output (object)
```json
{
  "municipality": "Palm Bay",
  "gis_source": "https://gis.palmbayflorida.org/arcgis/rest/services/Zoning/MapServer/0",
  "zone_source": "municipal_gis",
  "matched_parcels": 78432,
  "total_parcels": 80215,
  "match_rate": 0.978,
  "zone_code": "RS-1",
  "zone_description": "Single Family Residential"
}
```
- `municipality`: Exact city name (e.g., "Palm Bay")
- `gis_source`: Full URL to the ArcGIS MapServer endpoint used
- `zone_source`: NEVER "USE_CODE" — must use city's native zoning field
- `matched_parcels`: Must be > 50000 for Palm Bay
- Both `zone_code` and `zone_description` required on every record

### Supabase Persist Output (object)
```json
{
  "status_code": 201,
  "rows_affected": 10,
  "parcel_ids": ["25-37-28-00-00012.0-0001.0"],
  "created_at": "2026-04-08T07:35:00+00:00",
  "county": "brevard",
  "table": "zoning_assignments"
}
```
- `status_code`: 200 or 201
- `rows_affected`: Must match input count exactly
- `parcel_ids`: Array of unique IDs (no duplicates)
- `created_at`: ISO 8601 datetime
- `county`: Lowercase string

### Error Output (object)
```json
{
  "error": "County 'Fakeland' not found in Florida county registry.",
  "error_code": "COUNTY_NOT_FOUND",
  "exit_code": 1,
  "county_requested": "Fakeland"
}
```
- `error`: Human-readable message (no Python tracebacks)
- `exit_code`: Non-zero (1 or 2)
- No null top-level fields
- Always valid JSON even in error state

## Guard Rails

- Do not output raw Python tracebacks — always wrap errors in structured JSON
- Do not use USE_CODE mapping when municipal GIS data is available
- Do not claim parcel counts without DB query proof (NEVER-LIE)
