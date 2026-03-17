# cli-anything-firecrawl — Harness Spec

**Parent:** [HARNESS.md](../HARNESS.md) + [BIDDEED_OVERLAY.md](../BIDDEED_OVERLAY.md)
**Date:** March 16, 2026
**Status:** SPEC (Ready for PLAN → HANDOFF to Claude Code)
**Assessment:** ADOPT (87.7/100) — see `docs/assessments/FIRECRAWL_CLI_ASSESSMENT.md`

---

## 1. Purpose

Wrap `firecrawl-cli` as a cli-anything harness so LangGraph agents and Claude Code can:
- Scrape URLs to file-based markdown/JSON (no context pollution)
- Run cloud browser sessions for JS-heavy municipal GIS portals
- Search+scrape web in one composable step
- Batch parallel queries for bulk data extraction

This harness **wraps an existing CLI** (unlike zonewise/auction which wrap APIs directly). Pattern: thin orchestration layer around `firecrawl-cli` commands.

---

## 2. Phase 1 — Codebase Analysis (Upstream CLI)

### 2.1 Backend Engine
- `firecrawl-cli` npm package (Node.js 18+)
- Hosted API at `api.firecrawl.dev` (Fire-engine proprietary proxy layer)
- Auth: `FIRECRAWL_API_KEY` env var or `~/.firecrawl/config.json`

### 2.2 Command-to-Action Mapping
| Firecrawl Command | Agent Action | Output |
|-------------------|-------------|--------|
| `firecrawl scrape <url>` | Extract single page | `.firecrawl/<name>.md` or `.json` |
| `firecrawl search "query" --scrape` | Search + extract top results | `.firecrawl/search-*.json` |
| `firecrawl crawl <url>` | Bulk site extraction | `.firecrawl/<domain>/` tree |
| `firecrawl map <url>` | Discover all URLs on site | JSON list of URLs |
| `firecrawl browser launch-session` | Start cloud browser | Session ID + live view URL |
| `firecrawl browser execute "cmd"` | Interact with page | Command result |
| `firecrawl agent "prompt"` | AI-driven extraction | Structured results |
| `firecrawl download <url>` | Map + scrape entire site | `.firecrawl/<domain>/` nested dirs |

### 2.3 Data Model
- Output: Files in `.firecrawl/` directory (markdown, JSON, structured)
- State: Session IDs for browser sessions (ephemeral, TTL-based)
- Config: `~/.firecrawl/config.json` (API key, defaults)

### 2.4 Existing CLI
The CLI IS the tool. Our harness wraps it, not replaces it.

---

## 3. Phase 2 — CLI Architecture Design

### 3.1 Interaction Model
**Subcommand CLI** (one-shot operations for pipeline composability)

```
cli-anything-firecrawl scrape <url> [--format markdown|json] [--json] [--persist]
cli-anything-firecrawl search <query> [--scrape] [--limit N] [--json] [--persist]
cli-anything-firecrawl crawl <url> [--limit N] [--json] [--persist]
cli-anything-firecrawl map <url> [--json]
cli-anything-firecrawl browser-scrape <url> [--actions "click @e5, scroll"] [--json] [--persist]
cli-anything-firecrawl batch <file.jsonl> [--parallel N] [--json] [--persist]
cli-anything-firecrawl health
cli-anything-firecrawl credits
```

### 3.2 Command Groups
| Group | Commands | Description |
|-------|----------|-------------|
| **Extract** | `scrape`, `search`, `crawl`, `map` | Core data extraction |
| **Browser** | `browser-scrape` | Cloud browser session + scrape (one-shot) |
| **Batch** | `batch` | Parallel execution from JSONL manifest |
| **Admin** | `health`, `credits` | Status checks |

### 3.3 State Model

**Stateless by default** — each command is independent, outputs JSON to stdout.

**`--persist` flag** — writes results to Supabase:
```sql
-- Table: firecrawl_results
CREATE TABLE firecrawl_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    url TEXT NOT NULL,
    command TEXT NOT NULL,        -- scrape|search|crawl|map|browser-scrape
    format TEXT DEFAULT 'markdown',
    content TEXT,                 -- extracted content
    metadata JSONB,              -- credits used, response time, etc.
    source_cli TEXT DEFAULT 'firecrawl',
    pipeline TEXT,               -- 'zonewise'|'auction'|'biddeed'|null
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.4 Output Format
```json
{
  "status": "success",
  "command": "scrape",
  "url": "https://gis.palmbayflorida.org/...",
  "format": "markdown",
  "content": "# Palm Bay Zoning Map\n...",
  "file_path": ".firecrawl/palmbayflorida-zoning.md",
  "credits_used": 1,
  "elapsed_ms": 2340,
  "metadata": {
    "title": "Palm Bay GIS Portal",
    "source_url": "https://gis.palmbayflorida.org/...",
    "scraped_at": "2026-03-16T14:30:00Z"
  }
}
```

---

## 4. Phase 3 — Implementation

### 4.1 Directory Structure
```
firecrawl/
├── agent-harness/
│   ├── FIRECRAWL.md           # Harness-specific docs
│   ├── setup.py               # pip install -e .
│   └── cli_anything/
│       └── firecrawl/
│           ├── __init__.py
│           ├── __main__.py     # Entry point
│           ├── core/
│           │   ├── scraper.py      # scrape, search, crawl, map
│           │   ├── browser.py      # browser-scrape (cloud browser orchestration)
│           │   └── batch.py        # parallel batch execution
│           ├── utils/
│           │   ├── firecrawl_backend.py  # CLI invocation wrapper
│           │   ├── output.py             # JSON/file output handling
│           │   └── supabase_persist.py   # --persist flag handler
│           └── tests/
│               ├── test_scrape.py
│               ├── test_search.py
│               ├── test_browser.py
│               └── test_batch.py
├── eval/
│   └── eval.json              # 25 binary assertions for AUTOLOOP
├── workflows/
│   └── firecrawl-health.yml   # GHA: daily credit check + connectivity
└── agent.py                   # LangGraph agent node wrapper
```

### 4.2 Backend Module (`firecrawl_backend.py`)

```python
"""Backend wrapper for firecrawl-cli. Follows BIDDEED_OVERLAY.md pattern."""
import os
import shutil
import subprocess
import json

def find_firecrawl():
    """Verify firecrawl-cli is installed and authenticated."""
    path = shutil.which("firecrawl")
    if not path:
        raise RuntimeError(
            "firecrawl-cli not installed. Install with:\n"
            "  npm install -g firecrawl-cli@1.8.0\n"
            "  firecrawl login --api-key $FIRECRAWL_API_KEY"
        )
    key = os.environ.get("FIRECRAWL_API_KEY")
    if not key:
        raise RuntimeError(
            "FIRECRAWL_API_KEY not set. Export it:\n"
            "  export FIRECRAWL_API_KEY=fc-YOUR-KEY"
        )
    return path

def health_check():
    """Verify CLI connectivity and credits."""
    path = find_firecrawl()
    result = subprocess.run(
        [path, "--status"],
        capture_output=True, text=True, timeout=10,
        env={**os.environ, "FIRECRAWL_NO_TELEMETRY": "1"}
    )
    if result.returncode != 0:
        raise RuntimeError(f"Firecrawl health check failed: {result.stderr}")
    return {"status": "healthy", "output": result.stdout.strip()}

def run_command(args: list[str], timeout: int = 120) -> dict:
    """Execute a firecrawl CLI command, return parsed JSON."""
    path = find_firecrawl()
    env = {**os.environ, "FIRECRAWL_NO_TELEMETRY": "1"}
    
    # Ensure --json flag for machine-readable output
    if "--json" not in args:
        args.append("--json")
    
    result = subprocess.run(
        [path] + args,
        capture_output=True, text=True, timeout=timeout, env=env
    )
    
    if result.returncode != 0:
        return {"status": "error", "error": result.stderr.strip(), "exit_code": result.returncode}
    
    try:
        return {"status": "success", **json.loads(result.stdout)}
    except json.JSONDecodeError:
        return {"status": "success", "raw_output": result.stdout.strip()}
```

### 4.3 Browser-Scrape (One-Shot Cloud Browser)

```python
"""Orchestrates cloud browser session lifecycle for single-page JS extraction."""

def browser_scrape(url: str, actions: list[str] = None, timeout: int = 60) -> dict:
    """
    Launch browser → navigate → optional actions → scrape → close.
    One-shot pattern: no persistent sessions.
    """
    from .firecrawl_backend import run_command
    
    # 1. Launch session
    session = run_command(["browser", "launch-session", "--ttl", str(timeout)])
    if session.get("status") != "success":
        return session
    
    try:
        # 2. Navigate
        run_command(["browser", "execute", f"open {url}"])
        
        # 3. Optional actions (click, scroll, wait)
        for action in (actions or []):
            run_command(["browser", "execute", action])
        
        # 4. Scrape
        result = run_command(["browser", "execute", "scrape"])
        
        return result
    finally:
        # 5. Always close session
        run_command(["browser", "close"])
```

---

## 5. Phase 4 — Testing (eval.json)

### 25 Binary Assertions for AUTOLOOP

```json
{
  "harness": "firecrawl",
  "version": "1.0.0",
  "assertions": [
    {"id": "FC-001", "test": "health_check returns healthy", "type": "L1"},
    {"id": "FC-002", "test": "credits command returns numeric remaining", "type": "L1"},
    {"id": "FC-003", "test": "scrape https://example.com returns markdown content", "type": "L2"},
    {"id": "FC-004", "test": "scrape with --json flag returns valid JSON", "type": "L1"},
    {"id": "FC-005", "test": "scrape non-existent URL returns error status", "type": "L2"},
    {"id": "FC-006", "test": "search 'brevard county foreclosure' returns ≥1 result", "type": "L2"},
    {"id": "FC-007", "test": "search --scrape includes page content in results", "type": "L2"},
    {"id": "FC-008", "test": "search --limit 3 returns ≤3 results", "type": "L2"},
    {"id": "FC-009", "test": "map https://www.bcpao.us returns ≥5 URLs", "type": "L2"},
    {"id": "FC-010", "test": "crawl with --limit 2 returns exactly 2 pages", "type": "L2"},
    {"id": "FC-011", "test": "browser-scrape https://example.com returns content", "type": "L2"},
    {"id": "FC-012", "test": "browser session closes cleanly after scrape", "type": "L1"},
    {"id": "FC-013", "test": "FIRECRAWL_NO_TELEMETRY=1 is set in all subprocess calls", "type": "L1"},
    {"id": "FC-014", "test": "missing API key raises RuntimeError with instructions", "type": "L1"},
    {"id": "FC-015", "test": "missing CLI binary raises RuntimeError with install cmd", "type": "L1"},
    {"id": "FC-016", "test": "--persist flag writes to Supabase firecrawl_results table", "type": "L2"},
    {"id": "FC-017", "test": "persisted record contains url, command, content, metadata", "type": "L2"},
    {"id": "FC-018", "test": "batch command processes 3-item JSONL file", "type": "L2"},
    {"id": "FC-019", "test": "batch parallel execution completes faster than sequential", "type": "L2"},
    {"id": "FC-020", "test": "output file_path matches .firecrawl/ directory convention", "type": "L1"},
    {"id": "FC-021", "test": "scrape bcpao.us property page extracts owner name", "type": "L2"},
    {"id": "FC-022", "test": "scrape palmbayflorida.org GIS returns zoning data", "type": "L2"},
    {"id": "FC-023", "test": "timeout on slow scrape returns error, not hang", "type": "L1"},
    {"id": "FC-024", "test": "credits_used field present in all successful responses", "type": "L2"},
    {"id": "FC-025", "test": "agent.py node returns LangGraph-compatible state dict", "type": "L1"}
  ]
}
```

---

## 6. Phase 5 — Deployment

### 6.1 GitHub Actions Setup
```yaml
# In any workflow that uses firecrawl harness:
- name: Install Firecrawl CLI
  run: |
    npm install -g firecrawl-cli@1.8.0
    export FIRECRAWL_NO_TELEMETRY=1
    firecrawl login --api-key ${{ secrets.FIRECRAWL_API_KEY }}
```

### 6.2 Hetzner (everest-dispatch) Setup
```bash
# One-time setup on 87.99.129.125
npm install -g firecrawl-cli@1.8.0
echo 'export FIRECRAWL_NO_TELEMETRY=1' >> /etc/environment
firecrawl login --api-key $FIRECRAWL_API_KEY
```

### 6.3 Integration Points
| Consumer | Pattern | Trigger |
|----------|---------|---------|
| ZoneWise Scraper V4 | `browser-scrape` for municipal GIS portals | Municipal conquest pipeline |
| Auction CLI | `search --scrape` for competitive intel | Weekly auction prep |
| Reports CLI | `scrape` for property listing enrichment | On-demand report generation |
| AUTOLOOP | `eval.json` assertions | Nightly 2AM EST via GHA |

---

## 7. Phase 6 — LangGraph Agent Node

```python
# agent.py — LangGraph node for firecrawl harness
from typing import TypedDict

class FirecrawlState(TypedDict):
    urls: list[str]
    query: str | None
    results: list[dict]
    errors: list[str]
    credits_used: int

def firecrawl_node(state: FirecrawlState) -> FirecrawlState:
    """LangGraph node: scrape URLs or search query, return results."""
    from agent_harness.cli_anything.firecrawl.core.scraper import scrape, search
    
    results = []
    errors = []
    credits = 0
    
    if state.get("query"):
        r = search(state["query"], scrape=True, limit=5)
        if r["status"] == "success":
            results.append(r)
            credits += r.get("credits_used", 0)
        else:
            errors.append(r.get("error", "Unknown search error"))
    
    for url in state.get("urls", []):
        r = scrape(url)
        if r["status"] == "success":
            results.append(r)
            credits += r.get("credits_used", 0)
        else:
            errors.append(f"{url}: {r.get('error', 'Unknown error')}")
    
    return {
        **state,
        "results": state.get("results", []) + results,
        "errors": state.get("errors", []) + errors,
        "credits_used": state.get("credits_used", 0) + credits
    }
```

---

## 8. Phase 7 — Iteration Plan

### Sprint 1 (Week 1): Foundation
- [ ] Create `firecrawl/` directory in cli-anything-biddeed
- [ ] Implement `firecrawl_backend.py` with health check
- [ ] Implement `scrape` and `search` commands
- [ ] Write FC-001 through FC-008 tests
- [ ] Push to GitHub

### Sprint 2 (Week 2): Browser + Batch
- [ ] Implement `browser-scrape` one-shot pattern
- [ ] Implement `batch` parallel execution
- [ ] Write FC-009 through FC-019 tests
- [ ] Test against Palm Bay GIS portal (POC)

### Sprint 3 (Week 3): Integration + Deploy
- [ ] Implement `--persist` Supabase writer
- [ ] Create `agent.py` LangGraph node
- [ ] Wire into ZoneWise municipal conquest pipeline
- [ ] Write FC-020 through FC-025 tests
- [ ] Deploy to Hetzner
- [ ] Add to AUTOLOOP nightly eval

### Success Criteria
- All 25 eval assertions passing
- Palm Bay GIS portal scraped successfully via cloud browser
- ZoneWise municipal conquest pipeline uses firecrawl harness for ≥1 city
- Credits usage stays within Hobby plan (3,000/month)

---

*Spec stored: `firecrawl/FIRECRAWL_SPEC.md` in cli-anything-biddeed repo*
*Companion: `docs/assessments/FIRECRAWL_CLI_ASSESSMENT.md`*
*Next: PLAN → HANDOFF to Claude Code for Sprint 1 implementation*
