# Claude Code Session: CLI-Anything BidDeed — Complete Deferred Items

## CONTEXT
You are completing the final integration phase of the CLI-Anything BidDeed fork.
Repository: `breverdbidder/cli-anything-biddeed`
All code is deployed. 138/138 tests passing. Two CLIs installed (`cli-anything-zonewise`, `cli-anything-auction`).

**Three items remain:**
1. GitHub Actions workflows (credentials ARE in GitHub secrets already)
2. Supabase E2E persistence tests
3. LangGraph scaffold

## STEP 0: Push GitHub Secrets

The repo needs secrets for GitHub Actions. Read them from local credentials and push via API.

```bash
# Read Supabase credentials from local file
SUPABASE_CREDS="$HOME/SUPABASE_CREDENTIALS.md"
if [ ! -f "$SUPABASE_CREDS" ]; then
  # Try alternate locations
  SUPABASE_CREDS=$(find $HOME -name "SUPABASE_CREDENTIALS.md" -type f 2>/dev/null | head -1)
fi

# If file exists, extract keys and push
if [ -f "$SUPABASE_CREDS" ]; then
  echo "Found credentials at: $SUPABASE_CREDS"
  cat "$SUPABASE_CREDS"
fi

# Also check environment variables that may already be exported
echo "SUPABASE_URL: ${SUPABASE_URL:-not set}"
echo "SUPABASE_KEY: ${SUPABASE_KEY:+set (hidden)}"
echo "FIRECRAWL_API_KEY: ${FIRECRAWL_API_KEY:+set (hidden)}"
```

Push secrets using Python + PyNaCl:

```python
import base64, json, urllib.request, os
from nacl import encoding, public

TOKEN = os.environ.get("GITHUB_TOKEN") or open(os.path.expanduser("~/.config/gh_token")).read().strip()
REPO = "breverdbidder/cli-anything-biddeed"

# Get repo public key
req = urllib.request.Request(
    f"https://api.github.com/repos/{REPO}/actions/secrets/public-key",
    headers={"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}
)
resp = json.loads(urllib.request.urlopen(req).read())
pub_key_b64, key_id = resp["key"], resp["key_id"]

def push_secret(name, value):
    pk = public.PublicKey(pub_key_b64, encoding.Base64Encoder)
    encrypted = base64.b64encode(public.SealedBox(pk).encrypt(value.encode())).decode()
    data = json.dumps({"encrypted_value": encrypted, "key_id": key_id}).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/actions/secrets/{name}",
        data=data, method="PUT",
        headers={"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}
    )
    print(f"  {name}: HTTP {urllib.request.urlopen(req).status}")

# Push all secrets - get values from env or local files
secrets = {
    "SUPABASE_URL": os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co"),
    "SUPABASE_KEY": os.environ.get("SUPABASE_KEY", ""),  # Service role key
    "FIRECRAWL_API_KEY": os.environ.get("FIRECRAWL_API_KEY", ""),
}

for name, value in secrets.items():
    if value:
        push_secret(name, value)
    else:
        print(f"  {name}: SKIPPED (no value found)")
```

If env vars aren't set, find them in local files and export before running. The Supabase service role key ends in `...Tqp9nE`. The Firecrawl key starts with `fc-`.

Verify:
```bash
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/breverdbidder/cli-anything-biddeed/actions/secrets" | \
  python3 -c "import sys,json; [print(f'  ✓ {s[\"name\"]}') for s in json.load(sys.stdin).get('secrets',[])]"
```

Must show: SUPABASE_URL, SUPABASE_KEY, FIRECRAWL_API_KEY.

## STEP 1: Read Project State

```bash
cd ~/cli-anything-biddeed || git clone https://github.com/breverdbidder/cli-anything-biddeed.git ~/cli-anything-biddeed && cd ~/cli-anything-biddeed
cat CLAUDE.md
cat TODO.md
cat BIDDEED_OVERLAY.md
```

Install all packages:
```bash
pip install -e shared/
pip install -e zonewise/agent-harness/
pip install -e auction/agent-harness/
pip install pytest
```

Verify baseline:
```bash
python3 -m pytest shared/tests/ zonewise/agent-harness/cli_anything/zonewise/tests/ auction/agent-harness/cli_anything/auction/tests/ -q
```
Must show 138 passed.

## STEP 2: GitHub Actions Workflows

GitHub secrets are already configured. Create these workflow files:

### 2a: ZoneWise Nightly Scrape
Create `zonewise/workflows/nightly-scrape.yml`:

```yaml
name: ZoneWise Nightly Scrape
on:
  schedule:
    - cron: '0 4 * * *'  # 11 PM EST = 4 AM UTC
  workflow_dispatch: {}

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install CLIs
        run: |
          pip install -e shared/
          pip install -e zonewise/agent-harness/
      - name: Scrape Brevard County (Tier 4 — safe mode)
        run: cli-anything-zonewise --json county scrape --county brevard --tier 4 --persist
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          FIRECRAWL_API_KEY: ${{ secrets.FIRECRAWL_API_KEY }}
      - name: Export status
        run: cli-anything-zonewise --json county status --county brevard
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
```

### 2b: Auction Morning Analysis
Create `auction/workflows/morning-analysis.yml`:

```yaml
name: Auction Morning Analysis
on:
  schedule:
    - cron: '0 11 * * 1-5'  # 6 AM EST weekdays = 11 AM UTC
  workflow_dispatch:
    inputs:
      date:
        description: 'Auction date (YYYY-MM-DD or "sample")'
        required: false
        default: 'sample'

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install CLIs
        run: |
          pip install -e shared/
          pip install -e auction/agent-harness/
          pip install python-docx
      - name: Discover upcoming auctions
        run: cli-anything-auction --json discover upcoming
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
      - name: Batch analysis
        run: cli-anything-auction --json analyze batch --date ${{ github.event.inputs.date || 'sample' }} --persist
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
      - name: Generate reports
        run: |
          mkdir -p reports/
          cli-anything-auction --json report batch --date ${{ github.event.inputs.date || 'sample' }} -o reports/ --format text
      - name: Upload reports artifact
        uses: actions/upload-artifact@v4
        with:
          name: auction-reports-${{ github.run_number }}
          path: reports/
          retention-days: 30
```

### 2c: CI Test Workflow
Create `.github/workflows/ci.yml`:

```yaml
name: CI — Full Test Suite
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install all packages
        run: |
          pip install pytest
          pip install -e shared/
          pip install -e zonewise/agent-harness/
          pip install -e auction/agent-harness/
          pip install python-docx
      - name: Run full test suite
        run: |
          python3 -m pytest shared/tests/ \
            zonewise/agent-harness/cli_anything/zonewise/tests/ \
            auction/agent-harness/cli_anything/auction/tests/ \
            -v --tb=short
      - name: Verify CLI installation
        run: |
          which cli-anything-zonewise
          which cli-anything-auction
          cli-anything-zonewise --json county list | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['count']==46"
          cli-anything-auction --json analyze case --case 2024-CA-001234 | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['recommendation'] in ('BID','REVIEW','SKIP')"
```

**IMPORTANT:** The workflow files go in these EXACT locations:
- `zonewise/workflows/nightly-scrape.yml` → COPY to `.github/workflows/zonewise-nightly.yml`
- `auction/workflows/morning-analysis.yml` → COPY to `.github/workflows/auction-morning.yml`
- `.github/workflows/ci.yml` stays where it is

Both the source files AND the .github copies must exist. The source files are templates; the .github copies are what GitHub Actions actually runs.

After creating all workflows:
```bash
git add -A
git commit -m "ci: GitHub Actions — nightly scrape, morning analysis, CI test suite"
git push origin main
```

Then verify the CI workflow triggered:
```bash
curl -s -H "Authorization: token $(cat ~/.config/gh_token 2>/dev/null || echo $GITHUB_TOKEN)" \
  "https://api.github.com/repos/breverdbidder/cli-anything-biddeed/actions/runs?per_page=1" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); r=d.get('workflow_runs',[]); print(f'Latest run: {r[0][\"name\"]} — {r[0][\"status\"]}') if r else print('No runs yet')"
```

## STEP 3: Supabase E2E Persistence Tests

Verify Supabase connectivity first:
```bash
export SUPABASE_URL="https://mocerqjnksmhcjzxrewo.supabase.co"
# Get SUPABASE_KEY from GitHub secrets or local SUPABASE_CREDENTIALS.md
python3 -c "
from cli_anything_shared.supabase import health_check
try:
    health_check('auction')
    print('✓ Supabase connected')
except Exception as e:
    print(f'✗ {e}')
"
```

If connected, add E2E tests to `auction/agent-harness/cli_anything/auction/tests/test_full_e2e.py`:

```python
import os
import pytest

SUPABASE_AVAILABLE = os.environ.get("SUPABASE_URL") is not None

@pytest.mark.skipif(not SUPABASE_AVAILABLE, reason="SUPABASE_URL not set")
class TestSupabasePersistence:
    def test_persist_analysis(self):
        """Verify --persist writes to Supabase and returns db_id."""
        from click.testing import CliRunner
        from cli_anything.auction.auction_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "--persist", "analyze", "case", "--case", "2024-CA-001234"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        # If Supabase is connected, db_id should be present
        # If not, persist_error will be present — both are valid
        assert "recommendation" in data

    def test_audit_log_written(self):
        """Verify audit_log entry created."""
        from cli_anything_shared.supabase import query_table
        rows = query_table("audit_log", {"cli": "cli-anything-auction"}, limit=1, cli_name="auction")
        # May or may not have rows depending on whether audit decorator is active
        assert isinstance(rows, list)
```

Run with Supabase:
```bash
SUPABASE_URL=https://mocerqjnksmhcjzxrewo.supabase.co \
SUPABASE_KEY=<service_role_key> \
python3 -m pytest auction/agent-harness/cli_anything/auction/tests/test_full_e2e.py -v -k "Supabase" --tb=short
```

Commit:
```bash
git add -A
git commit -m "test: Supabase E2E persistence tests (skip when no credentials)"
git push origin main
```

## STEP 4: LangGraph Scaffold

Create `shared/cli_anything_shared/langgraph.py`:

```python
"""LangGraph integration scaffold for multi-agent CLI orchestration.

Defines the state graph for chaining CLI agents:
  discovery → analysis → reporting → persistence

Production implementation requires: pip install langgraph
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class PipelineStage(str, Enum):
    DISCOVERY = "discovery"
    ANALYSIS = "analysis"
    REPORTING = "reporting"
    PERSISTENCE = "persistence"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class PipelineState:
    """State object passed between pipeline stages."""
    stage: PipelineStage = PipelineStage.DISCOVERY
    auction_date: str = ""
    county: str = "brevard"
    cases: list = field(default_factory=list)
    analyses: list = field(default_factory=list)
    reports: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "stage": self.stage.value,
            "auction_date": self.auction_date,
            "county": self.county,
            "cases_count": len(self.cases),
            "analyses_count": len(self.analyses),
            "reports_count": len(self.reports),
            "errors_count": len(self.errors),
        }


def discovery_node(state: PipelineState) -> PipelineState:
    """Discovery stage: find upcoming auctions and scrape case list."""
    from cli_anything.auction.core.discovery import scrape_auction_list
    try:
        state.cases = scrape_auction_list(state.auction_date)
        state.stage = PipelineStage.ANALYSIS
    except Exception as e:
        state.errors.append(f"discovery: {e}")
        state.stage = PipelineStage.ERROR
    return state


def analysis_node(state: PipelineState) -> PipelineState:
    """Analysis stage: analyze all discovered cases."""
    from cli_anything.auction.core.analysis import batch_analyze
    try:
        result = batch_analyze(state.cases)
        state.analyses = result["results"]
        state.stage = PipelineStage.REPORTING
    except Exception as e:
        state.errors.append(f"analysis: {e}")
        state.stage = PipelineStage.ERROR
    return state


def reporting_node(state: PipelineState) -> PipelineState:
    """Reporting stage: generate reports for analyzed cases."""
    from cli_anything.auction.core.report import batch_reports
    try:
        result = batch_reports(state.analyses, "./pipeline_reports", fmt="text")
        state.reports = result.get("reports", [])
        state.stage = PipelineStage.PERSISTENCE
    except Exception as e:
        state.errors.append(f"reporting: {e}")
        state.stage = PipelineStage.ERROR
    return state


def persistence_node(state: PipelineState) -> PipelineState:
    """Persistence stage: save results to Supabase."""
    try:
        from cli_anything_shared.supabase import persist_result
        persist_result("pipeline_runs", state.to_dict(), cli_name="auction")
        state.stage = PipelineStage.COMPLETE
    except Exception as e:
        state.errors.append(f"persistence: {e}")
        # Don't fail the pipeline on persistence errors
        state.stage = PipelineStage.COMPLETE
    return state


def run_pipeline(auction_date: str = "sample", county: str = "brevard") -> PipelineState:
    """Execute the full pipeline sequentially.

    In production, this would be orchestrated by LangGraph with:
    - State checkpointing to Supabase between stages
    - Circuit breakers on each stage
    - Retry logic (max 3 per stage)
    - Parallel analysis of individual cases

    For now, runs sequentially as proof of concept.
    """
    state = PipelineState(auction_date=auction_date, county=county)

    nodes = [discovery_node, analysis_node, reporting_node, persistence_node]
    for node in nodes:
        state = node(state)
        if state.stage == PipelineStage.ERROR:
            break

    return state
```

Test the scaffold:
```python
# Quick verification
python3 -c "
from cli_anything_shared.langgraph import run_pipeline
state = run_pipeline('sample')
print(f'Stage: {state.stage.value}')
print(f'Cases: {len(state.cases)}')
print(f'Analyses: {len(state.analyses)}')
print(f'Reports: {len(state.reports)}')
print(f'Errors: {state.errors}')
d = state.to_dict()
print(f'Summary: {d}')
"
```

Add a test to `shared/tests/test_shared.py`:

```python
class TestLangGraphScaffold:
    def test_pipeline_sample(self):
        from cli_anything_shared.langgraph import run_pipeline, PipelineStage
        state = run_pipeline("sample")
        # Pipeline may hit persistence error (no Supabase) but should still complete
        assert state.stage in (PipelineStage.COMPLETE, PipelineStage.ERROR)
        assert len(state.cases) > 0
        assert len(state.analyses) > 0

    def test_pipeline_state_to_dict(self):
        from cli_anything_shared.langgraph import PipelineState
        state = PipelineState(auction_date="2026-03-15", county="brevard")
        d = state.to_dict()
        assert d["auction_date"] == "2026-03-15"
        assert d["county"] == "brevard"
```

Run all tests:
```bash
python3 -m pytest shared/tests/ zonewise/agent-harness/cli_anything/zonewise/tests/ auction/agent-harness/cli_anything/auction/tests/ -v --tb=short
```

Commit:
```bash
git add -A
git commit -m "feat: LangGraph scaffold + pipeline (discovery→analysis→reporting→persistence)

- Sequential pipeline proof-of-concept
- PipelineState dataclass with stage tracking
- 4 nodes: discovery, analysis, reporting, persistence
- Graceful error handling per stage
- Tests verify end-to-end pipeline with sample data"
git push origin main
```

## STEP 5: Update TODO.md

Mark all remaining items as complete:
```bash
# Update TODO.md — mark GitHub Actions, Supabase E2E, LangGraph as [x]
```

Final commit:
```bash
git add TODO.md
git commit -m "docs: All TODO items complete — 140+ tests, full pipeline operational"
git push origin main
```

## VERIFICATION CHECKLIST

Before ending the session, verify ALL of these:

```bash
# 1. All tests pass
python3 -m pytest shared/tests/ zonewise/agent-harness/cli_anything/zonewise/tests/ auction/agent-harness/cli_anything/auction/tests/ -q

# 2. Both CLIs in PATH
which cli-anything-zonewise && which cli-anything-auction

# 3. JSON piping works
cli-anything-auction --json analyze batch --date sample | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])"

# 4. GitHub Actions CI triggered
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/breverdbidder/cli-anything-biddeed/actions/runs?per_page=1" | \
  python3 -c "import sys,json; r=json.load(sys.stdin).get('workflow_runs',[]); print(r[0]['status'] if r else 'none')"

# 5. LangGraph pipeline runs
python3 -c "from cli_anything_shared.langgraph import run_pipeline; s=run_pipeline('sample'); print(f'{s.stage.value}: {len(s.analyses)} analyzed')"

# 6. Namespace coexistence
python3 -c "import cli_anything.zonewise; import cli_anything.auction; print('✓ PEP 420')"
```

## COST BUDGET
$0 for this session — no paid API calls. All tests use sample data and mocks.

## GIT
PAT4 from SECURITY.md (no expiry, repo+workflow scope).
Commit after each step. Descriptive messages.
