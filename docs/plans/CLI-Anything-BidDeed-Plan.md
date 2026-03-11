# CLI-Anything BidDeed: Implementation Plan
## Claude Code Handoff — March 11, 2026

**Spec:** CLI-Anything-BidDeed-Spec.md (APPROVED)
**Repo:** breverdbidder/cli-anything-biddeed (to be created)
**Upstream:** HKUDS/CLI-Anything

---

## SESSION STRUCTURE

This plan is divided into **4 sessions** designed for Claude Code's 7-hour autonomous window. Each session has clear entry/exit criteria and a verification checklist.

---

## SESSION 1: Fork + Foundation + Shared Utilities
**Estimated: 2-3 hours**

### Step 1.1: Fork & Clone
```bash
# Fork HKUDS/CLI-Anything → breverdbidder/cli-anything-biddeed via GitHub API
# Clone locally
gh repo fork HKUDS/CLI-Anything --clone --org breverdbidder --fork-name cli-anything-biddeed
cd cli-anything-biddeed
```

**Verify:**
- [ ] Repo exists at github.com/breverdbidder/cli-anything-biddeed
- [ ] All upstream files intact (HARNESS.md, cli-anything-plugin/, all harnesses)
- [ ] Git remote `upstream` points to HKUDS/CLI-Anything

### Step 1.2: Create BIDDEED_OVERLAY.md
Location: `/BIDDEED_OVERLAY.md` (root of repo, sibling to HARNESS.md)

**Content must cover:**

1. **Scope Statement** — This overlay extends HARNESS.md for API/DB backend targets. HARNESS.md remains the base SOP. This overlay adds patterns for:
   - Cloud API backends (no local GUI software)
   - Supabase as persistence layer
   - GitHub Actions as scheduling layer
   - LLM cost tracking per invocation
   - Audit logging

2. **Backend Pattern: API/DB Targets**
   - Instead of `utils/<software>_backend.py` wrapping a local executable, our backends wrap HTTP APIs and database connections
   - Pattern: `find_<service>()` checks for API key in env/config, raises RuntimeError with setup instructions
   - All backends must have a `health_check()` method that verifies connectivity
   - Example backends: `supabase_backend.py`, `firecrawl_backend.py`, `bcpao_backend.py`

3. **Hybrid State Model**
   - Default: JSON stdout (stateless, composable)
   - `--persist` flag: write results to Supabase table + return row ID in JSON
   - `--from-db` flag: read input from Supabase instead of stdin/args
   - Session state stored in `~/.config/cli-anything/<software>/session.json`

4. **Cost Tracking Protocol**
   - Every LLM invocation wrapped in cost tracker
   - Budget enforcement: `--budget <usd>` flag (default $1.00 per command)
   - Logs to Supabase `daily_quota_usage` table
   - Fields: cli_name, command, model, tokens_in, tokens_out, cost_usd, timestamp

5. **Audit Logging Protocol**
   - Every command invocation logged to Supabase `audit_log` table
   - Fields: cli, command, args_hash, timestamp, duration_ms, cost_usd, result_summary, user
   - Decorator pattern: `@audit_logged` on every Click command

6. **GitHub Actions Template**
   - Each CLI ships a workflow template in `<software>/workflows/`
   - Template includes: pip install, config from secrets, run command, error notification
   - Cron scheduling for nightly jobs

7. **Testing Extensions**
   - Unit tests: mock all external APIs (Supabase, Firecrawl, BCPAO, etc.)
   - E2E tests: require real API keys (skip gracefully if missing, unlike HARNESS.md's hard-fail)
   - Reason for deviation: GUI software is free to install; API keys have cost implications
   - Integration tests: verify piped workflows between CLIs

**Verify:**
- [ ] BIDDEED_OVERLAY.md exists and covers all 7 sections
- [ ] References HARNESS.md as base (not duplicating it)

### Step 1.3: Create Shared Utilities
Location: `/shared/cli_anything_shared/`

**Files to create:**

#### `shared/cli_anything_shared/__init__.py`
```python
"""Shared utilities for BidDeed CLI-Anything tools."""
__version__ = "1.0.0"
```

#### `shared/cli_anything_shared/supabase.py`
- `get_client()` — returns Supabase client from env `SUPABASE_URL` + `SUPABASE_KEY`
- `persist_result(table, data)` — insert row, return ID
- `read_result(table, id)` — fetch row by ID
- `health_check()` — verify connection, return bool
- Error handling: clear messages if env vars missing

#### `shared/cli_anything_shared/cost.py`
- `CostTracker` class with context manager interface
- Tracks: model, tokens_in, tokens_out, cost_usd
- `enforce_budget(budget_usd)` — raises BudgetExceeded if over
- `log_to_supabase(session_id)` — persists to daily_quota_usage
- Pricing table for: Claude Sonnet 4.5, Gemini 2.5 Flash, DeepSeek V3.2

#### `shared/cli_anything_shared/audit.py`
- `@audit_logged` decorator for Click commands
- Captures: cli name, full command string, duration, result summary
- Writes to Supabase `audit_log` table
- Graceful failure: if Supabase unavailable, log to stderr and continue

#### `shared/cli_anything_shared/config.py`
- `load_config(cli_name)` — loads from `~/.config/cli-anything/<cli_name>/config.json`
- `save_config(cli_name, key, value)` — updates config file
- `get_config(cli_name, key, env_var=None)` — tries env var first, then config file
- Used by all backends for API key management

#### `shared/setup.py`
```python
from setuptools import setup, find_packages
setup(
    name="cli-anything-shared",
    version="1.0.0",
    packages=find_packages(),
    install_requires=["supabase>=2.0.0", "click>=8.0.0"],
    python_requires=">=3.10",
)
```

**Verify:**
- [ ] `pip install -e shared/` succeeds
- [ ] `python -c "from cli_anything_shared.supabase import get_client"` imports clean
- [ ] All 4 modules have docstrings and type hints
- [ ] Unit tests pass for config loading (no external deps needed)

### Step 1.4: Update README
Location: `/README.md`

Add a "BidDeed Fork" section at the top explaining:
- This is a fork of HKUDS/CLI-Anything
- Extended for API/DB backend targets (foreclosure auctions, zoning data)
- See BIDDEED_OVERLAY.md for stack-specific patterns
- Two CLIs: cli-anything-zonewise, cli-anything-auction

**Session 1 Exit Criteria:**
- [ ] Fork repo live on GitHub
- [ ] BIDDEED_OVERLAY.md complete
- [ ] shared/ package installable
- [ ] README updated
- [ ] All changes committed and pushed

---

## SESSION 2: ZoneWise CLI (7-Phase Pipeline)
**Estimated: 4-5 hours**

### Reference: Existing ZoneWise Codebase
- Repo: breverdbidder/zonewise-scraper-v4
- Pipeline: Firecrawl (Tier1) → Gemini Flash (Tier2) → Claude Sonnet (Tier3)
- Data: 67 FL counties, Modal.com parallel scraping
- Output: Supabase tables

### Phase 1: Codebase Analysis
- Read zonewise-scraper-v4 source
- Map current pipeline stages to CLI commands
- Identify: data model (county zoning records), input/output formats, external dependencies
- Document in ZONEWISE.md

### Phase 2: CLI Architecture Design
Use the command tree from the spec:

```
cli-anything-zonewise
├── county
│   ├── scrape     --county <name> [--tier 1|2|3] [--persist]
│   ├── list       [--state FL]
│   └── status     --county <name>
├── parcel
│   ├── lookup     --address <addr> | --parcel <id>
│   ├── batch      --input <file.csv>
│   └── report     --parcel <id> --format json|csv
├── export
│   ├── supabase   --county <name> [--table <name>]
│   ├── csv        --county <name> -o <file>
│   └── json       --county <name> -o <file>
├── config
│   ├── set        <key> <value>
│   └── get        [key]
├── session
│   ├── status
│   ├── history
│   └── undo
└── (bare)         → REPL mode
```

State model:
- Session JSON: current county, last scrape timestamp, parcels cached
- Config: API keys (Firecrawl, Gemini, Supabase), default county, tier preferences

### Phase 3: Implementation
Directory: `zonewise/agent-harness/cli_anything/zonewise/`

**Core modules:**

`core/scraper.py`:
- `scrape_county(county, tier=1)` — runs the tiered scraping pipeline
- `get_county_list(state="FL")` — returns available counties
- `get_scrape_status(county)` — last run info from Supabase

`core/parser.py`:
- `parse_zoning_code(raw_html, county)` — extracts structured zoning from HTML
- `classify_zoning(code)` — residential/commercial/industrial/mixed
- `extract_setbacks(zoning_doc)` — parses setback requirements

`core/export.py`:
- `to_json(data, output_path)` — structured JSON output
- `to_csv(data, output_path)` — CSV export
- `to_supabase(data, table)` — Supabase insert/upsert

`core/session.py`:
- Copy session pattern from libreoffice harness
- Adapt for county/parcel state instead of document state

**Backend modules:**

`utils/firecrawl_backend.py`:
- `find_firecrawl()` — checks FIRECRAWL_API_KEY env var
- `scrape_url(url)` — returns markdown
- `health_check()` — pings Firecrawl API

`utils/supabase_backend.py`:
- Wraps shared/supabase.py with zonewise-specific queries
- `get_county_data(county)`, `upsert_parcels(county, data)`

`utils/repl_skin.py`:
- Copy from cli-anything-plugin/repl_skin.py (per HARNESS.md)

**CLI entry point:** `zonewise_cli.py`
- Click group with `invoke_without_command=True` → REPL
- `--json` flag on all commands
- `--persist` flag for Supabase writes
- `@audit_logged` decorator on all commands

### Phase 4: Test Planning (TEST.md)
Write TEST.md BEFORE any test code:
- Unit test plan: scraper (mocked HTTP), parser (sample HTML), export (temp files)
- E2E test plan: real Firecrawl scrape of 1 county (if API key available)
- Workflow scenarios: full county scrape → parse → export pipeline

### Phase 5: Test Implementation
- `test_core.py`: Unit tests with mocked responses (~40-60 tests)
- `test_full_e2e.py`: E2E tests with real APIs (~15-25 tests)
- CLI subprocess tests via `_resolve_cli("cli-anything-zonewise")`

### Phase 6: Document Results
- Run `pytest -v --tb=no`
- Append results to TEST.md

### Phase 7: Publish
```bash
cd zonewise/agent-harness
pip install -e .
which cli-anything-zonewise
cli-anything-zonewise --help
cli-anything-zonewise --json county list
```

**Session 2 Exit Criteria:**
- [ ] All 7 phases complete
- [ ] `cli-anything-zonewise` in PATH
- [ ] `cli-anything-zonewise --json county list` returns valid JSON
- [ ] All tests pass (100% unit, E2E may skip if no API keys)
- [ ] REPL mode works
- [ ] ZONEWISE.md complete
- [ ] TEST.md has plan + results
- [ ] Changes committed and pushed

---

## SESSION 3: Auction CLI (7-Phase Pipeline)
**Estimated: 5-6 hours**

### Reference: Existing Auction Codebase
- Legacy: breverdbidder/brevard-bidder-scraper (V13.4.0)
- Data sources: RealForeclose, BCPAO, AcclaimWeb, RealTDM
- Analysis: Max bid formula, lien priority, bid/judgment ratios
- Output: DOCX reports, Supabase tables

### Phase 1: Codebase Analysis
- Read brevard-bidder-scraper source
- Map the 12-stage pipeline to CLI commands
- Document in AUCTION.md
- Key backends: RealForeclose (auction lists), BCPAO (property data), AcclaimWeb (liens)

### Phase 2: CLI Architecture Design
Use the command tree from the spec:

```
cli-anything-auction
├── discover
│   ├── upcoming   [--date <YYYY-MM-DD>]
│   ├── scrape     --date <YYYY-MM-DD> [--persist]
│   └── status
├── analyze
│   ├── case       --case <number> [--persist]
│   ├── batch      --date <YYYY-MM-DD> [--persist]
│   ├── liens      --case <number>
│   └── arv        --case <number>
├── recommend
│   ├── bid        --date <YYYY-MM-DD> [--min-ratio 0.75]
│   ├── review     --date <YYYY-MM-DD>
│   └── summary    --date <YYYY-MM-DD>
├── report
│   ├── generate   --case <number> --format docx|pdf
│   ├── batch      --date <YYYY-MM-DD> -o <dir>
│   └── dashboard  --date <YYYY-MM-DD> --format html
├── export
│   ├── supabase   --date <YYYY-MM-DD>
│   └── csv        --date <YYYY-MM-DD> -o <file>
├── config / session (same pattern as zonewise)
└── (bare)         → REPL mode
```

### Phase 3: Implementation

**Core modules:**

`core/discovery.py`:
- `get_upcoming_auctions(date=None)` — scrapes RealForeclose calendar
- `scrape_auction_list(date)` — gets all cases for a date
- `get_case_details(case_number)` — full case metadata

`core/title_search.py`:
- `search_liens(case_number)` — AcclaimWeb lien search
- `get_lien_priority(liens)` — determines priority order
- `detect_senior_mortgage(liens, plaintiff)` — HOA foreclosure detection

`core/analysis.py`:
- `calculate_arv(parcel_id)` — automated ARV from comps
- `estimate_repairs(property_data)` — repair cost estimate
- `calculate_max_bid(arv, repairs)` — formula: (ARV×70%)-Repairs-$10K-MIN($25K,15%ARV)
- `recommend(case_data)` — returns BID/REVIEW/SKIP with ratio

`core/report.py`:
- `generate_report(case_data, format="docx")` — single case report
- `generate_batch(cases, output_dir)` — batch reports
- Uses python-docx (our established tooling, not LibreOffice headless)

`core/export.py`:
- Same pattern as zonewise (JSON, CSV, Supabase)

**Backend modules:**

`utils/bcpao_backend.py`:
- `find_bcpao()` — verifies API endpoint accessible
- `get_property(parcel_id)` — property details + photo URL
- `search_by_address(address)` — parcel lookup

`utils/acclaimweb_backend.py`:
- `find_acclaimweb()` — verifies endpoint
- `search_by_name(name)` — party name search
- `get_document(doc_id)` — document details

`utils/realforeclose_backend.py`:
- `find_realforeclose()` — verifies endpoint
- `get_calendar(county="brevard")` — auction calendar
- `get_auction_list(date)` — cases for date

### Phases 4-7: Same pattern as ZoneWise
- TEST.md plan → test_core.py + test_full_e2e.py → document results → publish

**Session 3 Exit Criteria:**
- [ ] All 7 phases complete
- [ ] `cli-anything-auction` in PATH
- [ ] `cli-anything-auction --json discover upcoming` returns valid JSON
- [ ] `cli-anything-auction --json analyze case --case <test-case>` returns BID/REVIEW/SKIP
- [ ] DOCX report generation works
- [ ] All tests pass
- [ ] REPL mode works
- [ ] AUCTION.md + TEST.md complete
- [ ] Changes committed and pushed

---

## SESSION 4: Integration + Deployment
**Estimated: 3-4 hours**

### Step 4.1: Piped Workflow Verification
```bash
# Test: zonewise → auction pipe
cli-anything-zonewise --json parcel lookup --address "123 Ocean Ave, Satellite Beach" \
  | cli-anything-auction --json analyze --stdin

# Test: auction batch → report batch
cli-anything-auction --json recommend bid --date 2026-03-15 \
  | cli-anything-auction report batch --stdin -o ./reports/
```

### Step 4.2: GitHub Actions Workflows

`zonewise/workflows/nightly-scrape.yml`:
- Cron: 11 PM EST daily
- Installs cli-anything-zonewise + cli-anything-shared
- Runs: `cli-anything-zonewise --json county scrape --county brevard --persist`
- Secrets: SUPABASE_URL, SUPABASE_KEY, FIRECRAWL_API_KEY

`auction/workflows/morning-analysis.yml`:
- Cron: 6 AM EST on auction days (configurable)
- Installs cli-anything-auction + cli-anything-shared
- Runs: discover → analyze batch → report batch → persist
- Secrets: SUPABASE_URL, SUPABASE_KEY

### Step 4.3: Supabase Verification
- Verify `--persist` writes to correct tables
- Verify `--from-db` reads back correctly
- Verify `audit_log` entries created for all commands
- Verify `daily_quota_usage` tracks costs

### Step 4.4: LangGraph Integration (Scaffold Only)
- Create `shared/cli_anything_shared/langgraph.py`
- Define state graph: discovery → analysis → reporting
- Checkpoint/resume via Supabase
- **Full implementation deferred to Session 5** — scaffold the interface now

### Step 4.5: End-to-End Integration Test
```bash
# Full pipeline: scrape → analyze → report → persist → verify DB
./integration_test.sh
```

**Session 4 Exit Criteria:**
- [ ] Piped workflow works between CLIs
- [ ] GitHub Actions workflows committed (not yet activated)
- [ ] Supabase persistence verified
- [ ] Audit logging verified
- [ ] Integration test passes
- [ ] All changes committed, pushed, PR created if needed
- [ ] Final README.md updated with usage examples

---

## GITHUB PAT & SECRETS

Use: PAT4 from SECURITY.md (no expiry, repo+workflow scope)
Supabase: URL=mocerqjnksmhcjzxrewo.supabase.co (keys from SUPABASE_CREDENTIALS.md)

---

## COST BUDGET

| Session | Estimated API Cost | Notes |
|---------|-------------------|-------|
| Session 1 | $0 | No external APIs, pure code |
| Session 2 | $2-3 | Firecrawl E2E tests (1 county) |
| Session 3 | $1-2 | Minimal API calls for test mocks |
| Session 4 | $2-3 | Integration testing |
| **Total** | **$5-8** | Well under $10/session limit |

---

## DEPENDENCY VERSIONS

```
click>=8.0.0
prompt-toolkit>=3.0.0
supabase>=2.0.0
python-docx>=1.1.0
httpx>=0.25.0
pytest>=7.0.0
```

---

## CRITICAL REMINDERS FOR CLAUDE CODE

1. **Read HARNESS.md FIRST** before every session — it's the SOP
2. **Read BIDDEED_OVERLAY.md** for our stack-specific patterns
3. **PEP 420 namespace**: `cli_anything/` has NO `__init__.py`
4. **Test before push**: `pytest -v` must pass before any git push
5. **`_resolve_cli()`**: all subprocess tests use this pattern, never hardcode paths
6. **`--json` on EVERYTHING**: every command must support JSON output
7. **REPL is default**: bare command with no subcommand enters REPL
8. **Copy repl_skin.py**: from cli-anything-plugin/ into each CLI's utils/
9. **Cost discipline**: no retry loops, no verbose dumps, one attempt per approach
10. **Commit frequently**: descriptive messages, push after each phase
