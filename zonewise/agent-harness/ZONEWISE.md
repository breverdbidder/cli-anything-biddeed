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

## Output Format Contracts

Every command MUST return structured JSON matching these schemas. The eval suite enforces 25 binary assertions against these formats.

### County Scrape Output (T1)
Returns a JSON array. Each record MUST include:
- `parcel_id`: string matching Brevard format `##-##-##-##-#####.#-####.#`
- `zone_code`: non-null string, MUST start with a known Brevard prefix (`BU`, `GU`, `RS`, `RU`, `AU`, `IU`, `PUD`, `PIP`, `TU`, `SEU`, `RR`, `PA`, `MHPD`, `RVP`, `TR`)
- `zone_name`: non-null string describing the zoning category
- `county`: lowercase county name
- `zone_source`: provenance tag (`county_gis` | `fl_gio` | `use_code_crosswalk` | `firecrawl`)

### Spatial Join Output (T2)
Returns a JSON object:
- `total_parcels`: positive integer (Brevard ~351K)
- `matched_parcels`: positive integer
- `match_rate`: float, MUST be >= 0.95 (95% minimum)
- `unmatched_parcels`: array (may be empty)
- `processing_time_seconds`: numeric value in seconds
- `method`: string (e.g. `STRtree_bulk`)
- `county`: lowercase county name

### Municipal Conquest Output (T3)
Returns a JSON object:
- `municipality`: exact city name (e.g. `"Palm Bay"`)
- `gis_source`: URL string containing the municipal GIS endpoint
- `zone_source`: MUST NOT contain `"USE_CODE"` — always use native municipal zoning field
- `matched_parcels`: integer > 50000 for Palm Bay
- `zone_code`: string, city-native zone code
- `zone_description`: string, human-readable zone label
- All zoning records in `records[]` MUST have both `zone_code` and `zone_description`

### Supabase Persist Output (T4)
Returns a JSON object:
- `status_code`: 200 or 201
- `rows_affected`: integer matching input count
- `parcel_ids`: array of unique parcel ID strings
- `created_at`: ISO 8601 datetime string (e.g. `"2026-04-09T07:30:00Z"`)
- `county`: lowercase string matching source county

### Error Handling Output (T5)
On invalid input (e.g. non-existent county), return JSON (never a stack trace):
- `error`: human-readable message (no Python tracebacks)
- `error_code`: machine-readable code (e.g. `COUNTY_NOT_FOUND`)
- `exit_code`: non-zero integer (1 = failure, 2 = partial)
- No top-level field may be `null`

## Quality Gates

```yaml
gate_1: "Every output MUST be valid JSON — parseable without errors"
gate_2: "Every parcel_id MUST match county-specific format regex"
gate_3: "zone_source MUST reflect actual data provenance — never USE_CODE for municipal conquests"
gate_4: "Error states MUST return structured JSON with exit_code != 0"
gate_5: "Match rate for spatial joins MUST be >= 95% or flag as degraded"
```

## Guard Rails

```yaml
guard_rails:
  - "Do not output raw Python tracebacks — always wrap in structured JSON error"
  - "Do not use USE_CODE mapping when municipal GIS provides native zoning codes"
  - "Do not claim parcel counts without querying the actual data source"
```
