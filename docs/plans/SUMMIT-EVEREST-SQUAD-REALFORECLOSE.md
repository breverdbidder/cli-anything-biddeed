# SUMMIT: Everest Squad — RealForeclose Live Integration

**Date:** 2026-03-23
**Priority:** P0
**Owner:** Claude Code (autonomous)
**Repo:** breverdbidder/cli-anything-biddeed
**Path:** auction/agent-harness/cli_anything/auction/

---

## Objective

Replace SAMPLE_CASES in `core/discovery.py` with live RealForeclose data.
After this, `cli-anything-auction analyze batch --date 04/14/2024` processes ALL real cases for that date.

---

## Current State

```yaml
broken:
  discovery.py: Returns 5 hardcoded SAMPLE_CASES regardless of --date
  auction_cli.py: "--date sample" routes to SAMPLE_CASES
  analysis.py: estimate_arv() returns judgment * 1.3 (no BCPAO)

working:
  analysis.py: calculate_max_bid() formula correct
  analysis.py: recommend() thresholds correct (BID≥75%, REVIEW≥60%, SKIP<60%)
  report.py: DOCX generation works
  auction-morning.yml: GHA workflow runs daily, uploads artifacts
```

---

## Architecture

```
RealForeclose DAYLIST (public, no auth)
    │
    ▼
┌─────────────────────────────┐
│ 1. SCOUT: Discovery         │ GET brevard.realforeclose.com/index.cfm
│    ?zession=day_list        │   ?county=brevard&sale_type=fc
│    Parse HTML table         │   &sale_date=MM/DD/YYYY
│    Extract: case_number,    │
│    status, judgment, plaintiff│
└────────────┬────────────────┘
             │ List[CaseStub]
             ▼
┌─────────────────────────────┐
│ 2. SCOUT: Enrichment        │
│    AcclaimWeb → liens,      │ vaclmweb1.brevardclerk.us
│      plaintiff, defendant   │
│    BCPAO API → address,     │ bcpao.us/api/v1/search
│      parcel_id, value,      │
│      sqft, year_built,      │
│      bedrooms, bathrooms,   │
│      photo_url              │
└────────────┬────────────────┘
             │ List[EnrichedCase]
             ▼
┌─────────────────────────────┐
│ 3. ANALYST: ARV + Max Bid   │
│    ARV from BCPAO sales     │
│    history or value * 1.0   │
│    Max bid formula (exists) │
│    BID/REVIEW/SKIP (exists) │
└────────────┬────────────────┘
             │ List[AnalyzedCase]
             ▼
┌─────────────────────────────┐
│ 4. SCRIBE: Reports          │
│    Per-case DOCX (exists)   │
│    Batch summary table      │
│    Telegram notification    │
└─────────────────────────────┘
```

---

## Implementation Tasks

### Task 1: Replace discovery.py with RealForeclose DAYLIST scraper

```python
# Key endpoint (NO AUTH REQUIRED — public results page):
# https://brevard.realforeclose.com/index.cfm?zession=day_list&county=brevard&sale_type=fc&sale_date=04/14/2024

# Existing working code to port FROM:
# brevard-bidder-scraper/src/scrapers/historical_results_scraper.py
#   - scrape_realforeclose(date) function
#   - DayListParser HTML parser
#   - SSL workaround (verify=False)

# Port INTO:
# cli-anything-biddeed/auction/agent-harness/cli_anything/auction/core/discovery.py
```

**Requirements:**
- `scrape_auction_list(date)` → fetches live DAYLIST, returns list of case dicts
- `get_upcoming_auctions(date)` → returns count + metadata (no more "sample_data" status)
- Date format: accepts both `YYYY-MM-DD` and `MM/DD/YYYY`, normalizes internally
- Fallback: if RealForeclose 403/timeout, check Supabase `historical_auctions` table
- Keep SAMPLE_CASES as `--date sample` escape hatch for testing only

**HTML parsing pattern (from existing DayListParser):**
- Skip header tables (table_count < 2)
- Rows with 4+ cells: case_number, status, plaintiff/details, bid amount
- Parse `$xxx,xxx.xx` currency from cells
- Status detection: SOLD/CANCELLED/THIRD PARTY

---

### Task 2: BCPAO enrichment for each case

```python
# For each case_number from DAYLIST:
# 1. Search AcclaimWeb by case number → get defendant name, judgment amount, plaintiff
# 2. Extract property address from case details
# 3. Query BCPAO API: https://www.bcpao.us/api/v1/search?address={address}
#    Returns: parcel_id, just_value, sqft, year_built, bedrooms, bathrooms, photo_url
# 4. Get BCPAO sales history for ARV: https://www.bcpao.us/api/v1/search?acct={parcel_id}
#    Use recent comparable sales within 0.5 mile, same property type
```

**New file:** `core/enrichment.py`

```python
async def enrich_case(case_stub: dict) -> dict:
    """Add BCPAO property data and AcclaimWeb lien info to a case stub."""
    # 1. AcclaimWeb case lookup (existing pattern from acclaimweb_scraper.py)
    # 2. BCPAO property lookup
    # 3. BCPAO sales history for ARV
    # Returns enriched case dict with all fields needed for analysis
```

**Critical:** Use httpx async with SSL workaround. AcclaimWeb may 503 — retry 3x with backoff.

---

### Task 3: Improve ARV estimation in analysis.py

```python
# Current: estimate_arv() returns judgment * 1.3 (garbage)
# Replace with:
def estimate_arv(case_data: dict) -> float:
    """Estimate ARV from BCPAO data.
    
    Priority:
    1. BCPAO just_value (property appraiser assessed value)
    2. Recent comparable sales (if enrichment provided them)
    3. Judgment * 1.3 as absolute last resort
    """
```

---

### Task 4: Wire into auction_cli.py

```python
# Current: "--date sample" only
# Replace: "--date 04/14/2024" fetches live DAYLIST
# Keep: "--date sample" for testing

# CLI commands that must work:
# cli-anything-auction discover upcoming              → next auction date + count
# cli-anything-auction discover --date 04/14/2024     → cases for that date
# cli-anything-auction analyze batch --date 04/14/2024 → full analysis all cases
# cli-anything-auction report batch --date 04/14/2024 -o reports/ → DOCX reports
```

---

### Task 5: Update auction-morning.yml

```yaml
# Current: runs --date sample (fake data)
# Replace: discover next auction date, then analyze
# Pattern:
#   1. cli-anything-auction --json discover upcoming → get next_date
#   2. cli-anything-auction --json analyze batch --date $next_date
#   3. cli-anything-auction report batch --date $next_date -o reports/
#   4. Upload reports artifact
#   5. Telegram summary: "X cases analyzed: Y BID / Z REVIEW / W SKIP"
```

---

## Data Source Reference

```yaml
realforeclose_daylist:
  url: "https://brevard.realforeclose.com/index.cfm"
  params:
    zession: day_list
    county: brevard
    sale_type: fc          # fc=foreclosure, td=tax deed
    sale_date: "MM/DD/YYYY"
  auth: NONE (public results page)
  ssl: verify=False required
  rate_limit: 1 req/sec
  returns: HTML table with case_number, status, bid amounts

bcpao_api:
  url: "https://www.bcpao.us/api/v1/search"
  params: "?address={addr}" or "?acct={parcel_id}"
  auth: NONE
  rate_limit: 2 req/sec
  returns: JSON with property details, photos, sales history

acclaimweb:
  url: "https://vaclmweb1.brevardclerk.us/AcclaimWeb"
  note: May 503 intermittently — retry with backoff
  auth: NONE
  returns: Case details, liens, recorded documents
```

---

## Existing Code to Port

```yaml
from_repo: breverdbidder/brevard-bidder-scraper
files_to_reference:
  - src/scrapers/historical_results_scraper.py  # DayListParser, scrape_realforeclose()
  - src/scrapers/realforeclose_fetcher.py       # AuctionProperty dataclass, PlaintiffNormalizer
  - src/scrapers/bcpao_scraper.py               # BCPAO API query patterns
  - src/scrapers/acclaimweb_scraper.py           # AcclaimWeb case/lien search
  - src/scrapers/realforeclose_scraper.py        # PlaintiffNormalizer full mappings

into_repo: breverdbidder/cli-anything-biddeed
target_files:
  - auction/agent-harness/cli_anything/auction/core/discovery.py  # REPLACE
  - auction/agent-harness/cli_anything/auction/core/enrichment.py # NEW
  - auction/agent-harness/cli_anything/auction/core/analysis.py   # UPDATE estimate_arv
  - auction/agent-harness/cli_anything/auction/auction_cli.py     # UPDATE --date routing
  - .github/workflows/auction-morning.yml                         # UPDATE to use live data
```

---

## Validation

```yaml
test_command: "cli-anything-auction --json analyze batch --date 04/14/2024"
expected:
  - status != "sample_data"
  - total > 0 (real cases from RealForeclose)
  - each case has: case_number, address, judgment, arv, max_bid, recommendation
  - arv comes from BCPAO (not judgment * 1.3)
  - recommendations are BID/REVIEW/SKIP based on real ratios

smoke_test_dates:
  - "04/14/2024"  # Historical (should have results)
  - "03/19/2025"  # Recent past
  - "sample"      # Fallback still works
```

---

## Secrets Needed

```yaml
existing_and_sufficient:
  - SUPABASE_URL
  - SUPABASE_KEY
  - TELEGRAM_BOT_TOKEN
  - TELEGRAM_CHAT_ID

NOT_needed:
  - RF_EMAIL (DAYLIST is public, no auth)
  - RF_PASSWORD
```

---

## Success Criteria

```yaml
done_when:
  - "cli-anything-auction analyze batch --date 04/14/2024" returns real cases
  - No SAMPLE_CASES in output (unless --date sample)
  - ARV sourced from BCPAO, not judgment multiplier
  - auction-morning.yml processes real upcoming auctions
  - Telegram receives batch summary with real BID/REVIEW/SKIP counts
  - Reports artifact uploaded with real DOCX files
```
