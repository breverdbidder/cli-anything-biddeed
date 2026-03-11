# BIDDEED_OVERLAY.md — Stack-Specific Extensions to HARNESS.md

**Base SOP:** [HARNESS.md](./HARNESS.md) — Read it first. This overlay EXTENDS, never replaces.

**Scope:** Patterns for API/DB backend targets (no local GUI software). Applies to all BidDeed CLIs.

---

## 1. Backend Pattern: API/DB Targets

HARNESS.md defines `utils/<software>_backend.py` wrapping local executables. For our stack, backends wrap HTTP APIs and database connections instead.

### Pattern
```python
# utils/<service>_backend.py
import os
import shutil

def find_<service>():
    """Verify <service> access. Returns API key or connection string."""
    key = os.environ.get("<SERVICE>_API_KEY")
    if not key:
        key = get_config("<cli_name>", "<service>_api_key")
    if key:
        return key
    raise RuntimeError(
        "<Service> not configured. Set it with:\n"
        "  export <SERVICE>_API_KEY=xxx\n"
        "  # or: cli-anything-<name> config set <service>_api_key xxx"
    )

def health_check():
    """Verify connectivity. Returns True or raises."""
    key = find_<service>()
    # ping endpoint
    return True
```

### Our Backends
| Backend | Service | Auth Method | Health Check |
|---------|---------|-------------|-------------|
| `supabase_backend.py` | Supabase DB | SUPABASE_URL + SUPABASE_KEY | `select 1` query |
| `firecrawl_backend.py` | Firecrawl API | FIRECRAWL_API_KEY | `/v0/health` ping |
| `bcpao_backend.py` | Brevard County Property Appraiser | None (public) | HTTP 200 on base URL |
| `acclaimweb_backend.py` | Brevard Clerk of Courts | None (public) | HTTP 200 on search page |
| `realforeclose_backend.py` | RealForeclose auction site | None (public) | HTTP 200 on calendar |

---

## 2. Hybrid State Model

### Default: JSON stdout (stateless, composable)
Every command outputs structured JSON to stdout when `--json` flag is set. This enables Unix piping between CLIs.

### `--persist` flag: Supabase durability
When `--persist` is passed, results are ALSO written to Supabase. The JSON output includes the row ID:
```json
{"result": "...", "db_id": "row_abc123", "table": "auction_analysis"}
```

### `--from-db` flag: Read from Supabase
Instead of processing from scratch, reads previous results from Supabase:
```bash
cli-anything-auction report generate --from-db --case 2024-CA-001234 --format docx
```

### Session State
Stored in `~/.config/cli-anything/<cli_name>/session.json`:
```json
{
  "current_county": "brevard",
  "last_command": "analyze case --case 2024-CA-001234",
  "history": [],
  "undo_stack": []
}
```

---

## 3. Cost Tracking Protocol

Every LLM invocation wrapped in cost tracker:

```python
from cli_anything_shared.cost import CostTracker

with CostTracker(budget=1.00, cli="auction", command="analyze") as tracker:
    result = llm.invoke(prompt)
    tracker.log(model="claude-sonnet-4.5", tokens_in=500, tokens_out=200)
```

### Budget Enforcement
- Default: $1.00 per command invocation
- Override: `--budget <usd>` flag
- Exceeding budget raises `BudgetExceeded` error (command aborts gracefully)
- Logged to Supabase `daily_quota_usage` table

---

## 4. Audit Logging Protocol

Decorator pattern on every Click command:

```python
from cli_anything_shared.audit import audit_logged

@cli.command()
@audit_logged
def analyze(case, persist):
    ...
```

Logs to Supabase `audit_log`:
```json
{
  "cli": "cli-anything-auction",
  "command": "analyze case --case 2024-CA-001234",
  "timestamp": "2026-03-11T14:30:00Z",
  "duration_ms": 4200,
  "cost_usd": 0.03,
  "result_summary": "BID (ratio: 0.82)",
  "user": "github-actions"
}
```

Graceful failure: if Supabase unavailable, logs to stderr and continues.

---

## 5. GitHub Actions Templates

Each CLI ships a workflow template in `<software>/workflows/`:

```yaml
name: <CLI> Nightly Run
on:
  schedule:
    - cron: '0 4 * * *'  # 11 PM EST
  workflow_dispatch: {}
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: |
          pip install -e shared/
          pip install -e <software>/agent-harness/
      - run: cli-anything-<software> --json <default-command> --persist
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
```

---

## 6. Testing Extensions

### Deviation from HARNESS.md
HARNESS.md mandates hard-fail when backends are missing ("No graceful degradation"). For API/DB backends, we modify this:

- **Unit tests**: Mock all external APIs. No API keys needed. MUST always pass.
- **E2E tests**: Require real API keys. Skip gracefully if missing with clear message.
- **Reason**: GUI software is free to install (`apt install gimp`). API keys have cost implications.
- **Integration tests**: Verify piped workflows between CLIs. Require both CLIs installed.

### Skip Pattern for E2E
```python
import pytest
import os

SUPABASE_AVAILABLE = os.environ.get("SUPABASE_URL") is not None

@pytest.mark.skipif(not SUPABASE_AVAILABLE, reason="SUPABASE_URL not set")
def test_persist_to_supabase():
    ...
```

---

## 7. Upstream Contribution Path

By keeping `cli_anything.*` namespace and HARNESS.md untouched:

1. **Short-term**: Our overlay patterns (API backends, cost tracking) proposed as official templates
2. **Medium-term**: `cli-anything-zonewise` and `cli-anything-auction` demonstrate non-GUI use cases
3. **Long-term**: CLI-Anything marketplace listing as real-estate/fintech vertical tools
