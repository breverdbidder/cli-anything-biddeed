---
name: zonewise-scraper
description: Use when parsing or scraping Brevard County parcel data from BCPAO (bcpao.us), validating property records, querying FL GIO cadastral API, or working with zoning assignments. Triggers on: BCPAO, parcel scrape, zoning assignment, FL GIO, DOR_UC crosswalk, co_no, parcel_id, zonewise data ingestion.
---

# ZoneWise Scraper

## Role
Own parcel data extraction as evidence-driven coverage, not aspirational claims.

## Working Mode
Map -> Separate evidence from hypothesis -> Smallest intervention -> Validate with DB counts.

## Focus Areas
1. BCPAO HTTP scraping -- public API, no auth, rate-limit aware (max 5 req/s)
2. FL GIO cadastral API -- paginated, 2000 features/request, CO_NO parameter
3. DOR_UC crosswalk -- maps use codes to zone categories (see `scripts/ingest_county.py`)
4. Supabase persistence -- `zoning_assignments` table, parcel_id as primary key
5. Zone source tracking -- `fl_gio | county_gis | use_code_crosswalk | firecrawl`
6. Schema validation -- parcel_id, zone_code, zone_source, county, co_no, ingested_at
7. Dedup on upsert -- conflict on parcel_id + county, update zone_code if newer source
8. Error handling -- log failed parcels to failed_parcels table, never silently skip

## Quality Gates
- verify: Output schema matches `{parcel_id, zone_code, zone_source, county, co_no}`
- confirm: Count of ingested rows matches FL GIO `total_count` for that co_no
- check: No NULL zone_codes in output (fallback to DOR_UC if county GIS unavailable)
- ensure: `zone_source` field is populated on every row
- call_out: Report any parcels where co_no doesn't match expected county mapping

## Output Format
```json
{
  "county": "brevard",
  "co_no": 15,
  "total_parcels": 245000,
  "ingested": 244987,
  "failed": 13,
  "zone_sources": {"fl_gio": 180000, "county_gis": 64987},
  "sample": [{"parcel_id": "2423456", "zone_code": "RU-1-11", "zone_source": "county_gis"}]
}
```

## Constraints
- NEVER report percentages without running `SELECT COUNT(*) FROM zoning_assignments WHERE county=X` first
- NEVER declare ingestion "done" without verifying DB count matches FL GIO total_count
- Rate limit: max 5 concurrent requests to BCPAO, 2000 features/page for FL GIO
- Use `scripts/ingest_county.py` as canonical ingestion script -- do not create alternatives
- Zone codes must use official county format (e.g., RU-1-11 not "residential")

## Guard Rail
Do not report parcel counts or conquest percentages without querying the database first.
