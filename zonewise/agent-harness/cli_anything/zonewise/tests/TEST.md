# TEST.md — ZoneWise CLI Test Plan & Results

## Test Inventory Plan
- `test_core.py`: ~40 unit tests (scraper, parser, export, session)
- `test_full_e2e.py`: ~15 E2E tests (CLI subprocess, file I/O, pipeline)

## Unit Test Plan

### scraper.py
- `get_county_list()` returns 46 FL counties
- `get_county_list("TX")` returns empty
- `scrape_county()` validates county name
- `scrape_county()` with invalid county raises ValueError
- Tier 1 without API key returns error status
- Tier 4 returns manual_flag status
- `get_scrape_status()` returns unknown for uncached county

### parser.py
- `classify_zoning("RS-1")` → residential
- `classify_zoning("CG")` → commercial
- `classify_zoning("IL")` → industrial
- `classify_zoning("AG")` → agricultural
- `classify_zoning("MU-1")` → mixed_use
- `classify_zoning("ZZZ")` → other
- `parse_zoning_record()` structures raw input correctly
- `parse_zoning_from_markdown()` extracts codes from markdown
- `_parse_int()` handles various formats
- `_parse_setbacks()` returns structured dict

### export.py
- `to_json()` creates valid JSON file
- `to_csv()` creates valid CSV with headers
- `to_csv()` with empty data returns error
- `to_json()` creates parent directories

### session.py
- Session creates and loads from file
- Session records commands in history
- Session undo pops last entry
- Session status returns correct counts
- Session clear resets all state

## E2E Test Plan
- CLI `--help` returns 0
- CLI `--json county list` returns valid JSON with 46 counties
- CLI `county scrape --county brevard --tier 4` returns manual_flag
- CLI `session status` returns session info
- CLI subprocess via `_resolve_cli()`

---

## Test Results

(Appended after test execution)
