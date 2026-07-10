# SUMMIT DISPATCH: Firecrawl CLI Harness — Sprint 1 (Foundation)

**Dispatched:** March 16, 2026
**Target Repo:** breverdbidder/cli-anything-biddeed
**Branch:** main
**Priority:** HIGH
**Budget:** $0 (all CLI work, no paid API calls)

---

## CONTEXT

Read these files FIRST before writing any code:
1. `HARNESS.md` — 7-phase pipeline SOP
2. `BIDDEED_OVERLAY.md` — API/DB backend patterns
3. `firecrawl/FIRECRAWL_SPEC.md` — Full harness specification (just committed)
4. `docs/assessments/FIRECRAWL_CLI_ASSESSMENT.md` — Security assessment (just committed)
5. `zonewise/agent-harness/` — Reference implementation to follow same patterns

---

## SPRINT 1 TASKS (Foundation)

### Task 1: Scaffold directory structure
Create the following in `firecrawl/`:
```
firecrawl/
├── agent-harness/
│   ├── FIRECRAWL.md
│   ├── setup.py
│   └── cli_anything/
│       └── firecrawl/
│           ├── __init__.py
│           ├── __main__.py
│           ├── core/
│           │   ├── __init__.py
│           │   ├── scraper.py
│           │   ├── browser.py
│           │   └── batch.py
│           ├── utils/
│           │   ├── __init__.py
│           │   ├── firecrawl_backend.py
│           │   ├── output.py
│           │   └── supabase_persist.py
│           └── tests/
│               ├── __init__.py
│               ├── test_scrape.py
│               ├── test_search.py
│               ├── test_browser.py
│               └── test_batch.py
├── eval/
│   └── eval.json
├── workflows/
│   └── firecrawl-health.yml
└── agent.py
```

### Task 2: Implement firecrawl_backend.py
Follow the BIDDEED_OVERLAY.md backend pattern exactly:
- `find_firecrawl()` — verify CLI installed + API key set
- `health_check()` — run `firecrawl --status`
- `run_command(args, timeout)` — execute any firecrawl CLI command, return parsed JSON
- ALL subprocess calls MUST set `FIRECRAWL_NO_TELEMETRY=1` in env
- Pin version check: warn if not `firecrawl-cli@1.8.0`

### Task 3: Implement scraper.py (scrape + search + map + crawl)
```python
def scrape(url: str, format: str = "markdown", output_dir: str = ".firecrawl") -> dict
def search(query: str, scrape: bool = False, limit: int = 5) -> dict
def map_site(url: str) -> dict
def crawl(url: str, limit: int = 10) -> dict
```
Each function:
- Calls `firecrawl_backend.run_command()` with appropriate args
- Returns standardized JSON: `{status, command, url, content, file_path, credits_used, elapsed_ms, metadata}`
- Handles errors gracefully (timeout, network, auth failures)

### Task 4: Implement __main__.py CLI entry point
```bash
python -m cli_anything.firecrawl scrape <url> [--format markdown|json] [--json] [--persist]
python -m cli_anything.firecrawl search <query> [--scrape] [--limit N] [--json] [--persist]
python -m cli_anything.firecrawl crawl <url> [--limit N] [--json] [--persist]
python -m cli_anything.firecrawl map <url> [--json]
python -m cli_anything.firecrawl health
python -m cli_anything.firecrawl credits
```
Use argparse. Follow zonewise harness CLI patterns.

### Task 5: Write eval.json (FC-001 through FC-008)
Create `firecrawl/eval/eval.json` with the first 8 assertions from the spec:
- FC-001: health_check returns healthy
- FC-002: credits command returns numeric remaining
- FC-003: scrape example.com returns markdown content
- FC-004: scrape with --json returns valid JSON
- FC-005: scrape non-existent URL returns error status
- FC-006: search 'brevard county foreclosure' returns ≥1 result
- FC-007: search --scrape includes page content
- FC-008: search --limit 3 returns ≤3 results

### Task 6: Write tests (test_scrape.py, test_search.py)
Unit tests with mocked subprocess calls (don't burn Firecrawl credits in CI).
Test the command construction, JSON parsing, error handling.

### Task 7: Update repo metadata
- Add `firecrawl` to README.md active CLIs list
- Update TODO.md with Sprint 2 + Sprint 3 tasks
- Add `.firecrawl/` to root `.gitignore`

---

## RULES

1. **FIRECRAWL_NO_TELEMETRY=1** — hardcoded in ALL subprocess env dicts
2. **Pin firecrawl-cli@1.8.0** — never @latest in any script or workflow
3. **--json flag** on every command — machine-readable output mandatory
4. **No paid API calls** — all tests use mocked subprocess, no live Firecrawl calls
5. **Follow zonewise harness patterns** — same setup.py structure, same test patterns
6. **Single commit message format:** `feat(firecrawl): Sprint 1 — foundation scaffold + scrape/search core`
7. **Run tests before push** — all tests must pass locally

---

## DONE CRITERIA

- [ ] Directory structure matches spec exactly
- [ ] `firecrawl_backend.py` passes health check on Hetzner
- [ ] `scraper.py` has all 4 functions with standardized output
- [ ] `__main__.py` CLI responds to all 6 subcommands
- [ ] `eval.json` has 8 assertions (FC-001 through FC-008)
- [ ] All unit tests pass with mocked subprocess
- [ ] README.md updated, .gitignore updated, TODO.md updated
- [ ] Single clean commit pushed to main

---

## DO NOT

- Do NOT install firecrawl-cli during this sprint (tests are mocked)
- Do NOT make live API calls (zero credit burn)
- Do NOT create browser.py or batch.py implementations yet (Sprint 2)
- Do NOT create Supabase table yet (Sprint 3)
- Do NOT ask questions — if blocked, try 3 alternatives then report
