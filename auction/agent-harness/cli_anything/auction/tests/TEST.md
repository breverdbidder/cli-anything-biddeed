# TEST.md — Auction CLI Test Plan & Results

## Test Inventory
- `test_core.py`: ~45 unit tests (analysis, discovery, title_search, report, export)
- `test_full_e2e.py`: ~20 E2E tests (CliRunner + subprocess)

## Unit Test Plan

### analysis.py (CORE BUSINESS LOGIC)
- Max bid formula: standard, low ARV, high ARV, zero repairs, negative result
- Bid ratio calculation: standard, zero judgment, above 1.0
- Recommendations: BID/REVIEW/SKIP thresholds, boundary cases
- Full case analysis with and without overrides
- Batch analysis

### discovery.py
- Upcoming auctions
- Scrape auction list
- Get case details (found / not found)

### title_search.py
- Search liens
- Lien priority sorting
- Senior mortgage detection (safe / risk / no liens)

### report.py
- Text report generation
- File output (text, JSON)
- Batch report generation

### export.py
- JSON export
- CSV export

## E2E Test Plan
- All CLI commands via CliRunner
- Subprocess tests via _resolve_cli()
- Report file verification

---

## Test Results

(Appended after execution)
