# DESIGNWISE-S1-DISPATCH.md
# Sprint 1 Completion — Claude Code Dispatch Instructions
# Date: 2026-03-21 | Version: 1.2.0
# Target: 100% S1 completion with verification
# Rule: NEVER-LIE. Verify every step. Wrong = "I was wrong".

---

## CONTEXT LOAD (DO THIS FIRST)

```bash
# 1. Read these files in order
cat CLAUDE.md
cat docs/plans/DESIGNWISE-SPEC.md
cat docs/plans/DESIGNWISE-PLAN.md
ls -la designwise/agent-harness/cli_anything/designwise/core/
ls -la designwise/tests/
```

## EXISTING STATE (VERIFIED 2026-03-21)

### Files that EXIST (19 files):
- `designwise/agent-harness/cli_anything/__init__.py` ✅
- `designwise/agent-harness/cli_anything/designwise/__init__.py` ✅
- `designwise/agent-harness/cli_anything/designwise/core/__init__.py` ✅
- `designwise/agent-harness/cli_anything/designwise/core/stitch_agent.py` ✅ (785 lines, V1.2.0)
- `designwise/agent-harness/cli_anything/designwise/core/brandguard_agent.py` ✅ (479 lines — HTTP logic only, NO Playwright)
- `designwise/agent-harness/cli_anything/designwise/core/commander.py` ✅ (423 lines — async dispatch, NO LangGraph)
- `designwise/agent-harness/cli_anything/designwise/core/codewise_agent.py` ✅ (480 lines — S2 item, exists early)
- `designwise/agent-harness/cli_anything/designwise/utils/__init__.py` ✅
- `designwise/tests/__init__.py` ✅
- `designwise/tests/test_stitch_quota.py` ✅ (patch tests)
- `designwise/tests/test_brand_drift.py` ✅ (patch tests)
- `designwise/tests/test_prototype.py` ✅ (patch tests)
- `designwise/tests/test_parallel_dispatch.py` ✅ (patch tests)

### Files that are MISSING (S1 blockers):
- ❌ `designwise/agent-harness/setup.py`
- ❌ `designwise/agent-harness/cli_anything/designwise/designwise_cli.py`
- ❌ `designwise/agent-harness/cli_anything/designwise/utils/supabase_client.py`
- ❌ `designwise/agent-harness/cli_anything/designwise/utils/brand_tokens.py`
- ❌ `designwise/agent-harness/cli_anything/designwise/utils/vercel_api.py`
- ❌ 9 remaining agent files (deploywise, qawise, analytics, support, iterate, seo, a11y, competitor, content)
- ❌ `designwise/eval/eval.json`
- ❌ `designwise/eval/eval_runner.py`
- ❌ `.github/workflows/autoloop-designwise.yml`
- ❌ `.github/workflows/brandguard-pr-check.yml`
- ❌ `designwise/tests/test_cli.py`
- ❌ `designwise/tests/test_brandguard_full.py`
- ❌ `designwise/tests/test_commander_full.py`
- ❌ `designwise/tests/test_utils.py`

### Supabase tables MISSING (all 11):
design_tasks, brand_violations, visual_baselines, page_analytics, conversion_funnel, support_tickets, ab_tests, deploy_log, competitor_snapshots, seo_audits, stitch_usage

### GHA Workflows that EXIST:
- ✅ designwise-notify.yml
- ✅ summit-designwise-bugfix.yml
- ✅ summit-designwise-patch.yml
- ✅ summit-designwise-s1-complete.yml
- ✅ summit-designwise-s1.yml

---

## EXECUTION PLAN — 9 STEPS

### STEP 1: Shared Utils (S1.1) — 3 files

**File: `designwise/agent-harness/cli_anything/designwise/utils/supabase_client.py`**
- Import httpx, os
- Class `DesignWiseDB` with `__init__(self, url=None, key=None)` reading from env vars `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`
- Methods for ALL 11 tables:
  - `insert(table, data)` → POST to /rest/v1/{table}
  - `query(table, params)` → GET from /rest/v1/{table}
  - `update(table, match, data)` → PATCH to /rest/v1/{table}
  - `upsert(table, data)` → POST with Prefer: resolution=merge-duplicates
  - `delete(table, match)` → DELETE from /rest/v1/{table}
- Table-specific helpers:
  - `log_task(task_type, agent_id, input_spec)` → insert design_tasks
  - `log_violation(scan_id, page_url, violation_type, expected, actual, severity)` → insert brand_violations
  - `log_deploy(commit_sha, branch, tier, status, checks)` → insert deploy_log
  - `get_quota_usage(month_start)` → query stitch_usage
- Headers: apikey + Authorization + Content-Type + Prefer
- All methods async with httpx.AsyncClient
- Error handling: return `{"error": str}` on failure, never raise

**File: `designwise/agent-harness/cli_anything/designwise/utils/brand_tokens.py`**
- Function `parse_design_md(path="DESIGN.md")` → returns dict:
  ```python
  {
      "colors": {"primary": "#1E3A5F", "accent": "#F59E0B", "background": "#020617", ...},
      "banned_colors": [...],
      "fonts": {"heading": "Inter", "body": "Inter", "mono": "JetBrains Mono"},
      "font_size_min": 11,
      "spacing": {...},
      "contrast_min": {"body": 4.5, "large": 3.0},
  }
  ```
- Function `check_color(hex_value, tokens)` → returns (valid, violation_detail)
- Function `check_font(font_family, tokens)` → returns (valid, violation_detail)
- Function `check_contrast(fg_hex, bg_hex, min_ratio=4.5)` → returns (passes, actual_ratio)
- Function `hex_to_rgb(hex_str)` → tuple
- Function `relative_luminance(rgb)` → float
- Function `contrast_ratio(lum1, lum2)` → float
- House brand constants hardcoded as fallback if DESIGN.md not found:
  - Navy: #1E3A5F, Orange: #F59E0B, Slate bg: #020617, Font: Inter

**File: `designwise/agent-harness/cli_anything/designwise/utils/vercel_api.py`**
- Class `VercelClient` with `__init__(self, token=None, project_id=None)`
- Env vars: `VERCEL_TOKEN`, `VERCEL_PROJECT_ID` (default: prj_EaXgEO6WDoSpCeLhuCemtbPr6e8E)
- Methods:
  - `list_deployments(limit=10)` → GET /v6/deployments
  - `get_deployment(deploy_id)` → GET /v13/deployments/{id}
  - `create_deployment(branch, git_sha)` → POST /v13/deployments
  - `get_preview_url(deploy_id)` → extract URL from deployment
  - `promote_to_production(deploy_id)` → POST /v13/deployments/{id}/promote (placeholder)
  - `rollback(deploy_id)` → revert commit approach
  - `check_status(deploy_id)` → poll deployment status
- Base URL: https://api.vercel.com
- Auth: Bearer token header
- All async httpx

**Commit after Step 1:** `feat(designwise): S1.1 — shared utils (supabase_client, brand_tokens, vercel_api)`

---

### STEP 2: CLI Entry Point + setup.py (S1.1)

**File: `designwise/agent-harness/cli_anything/designwise/designwise_cli.py`**
```python
"""DesignWise Squad — CLI Entry Point. 13 AI agents for ZoneWise.AI UI lifecycle."""
import argparse
import sys
import json

def main():
    parser = argparse.ArgumentParser(description="DesignWise Squad CLI")
    subparsers = parser.add_subparsers(dest="agent", help="Agent to invoke")
    
    # 13 subcommands — each imports its agent module
    agents = {
        "commander": ("Commander — LangGraph orchestrator", "core.commander"),
        "stitch": ("StitchWise — Stitch 2.0 MCP wrapper", "core.stitch_agent"),
        "brandguard": ("BrandGuard — Design system enforcer", "core.brandguard_agent"),
        "code": ("CodeWise — Stitch → Next.js converter", "core.codewise_agent"),
        "deploy": ("DeployWise — 3-tier deployment gatekeeper", "core.deploywise_agent"),
        "qa": ("QAWise — Visual regression + E2E", "core.qawise_agent"),
        "analytics": ("AnalyticsWise — PostHog + funnel tracking", "core.analytics_agent"),
        "support": ("SupportWise — Ticket classifier", "core.support_agent"),
        "iterate": ("IterateWise — A/B test self-improvement", "core.iterate_agent"),
        "seo": ("SEOWise — SEO automation", "core.seo_agent"),
        "a11y": ("AccessibilityWise — WCAG 2.1 AA", "core.a11y_agent"),
        "competitor": ("CompetitorWise — Weekly competitor monitor", "core.competitor_agent"),
        "content": ("ContentWise — Content generation", "core.content_agent"),
    }
    for name, (help_text, _) in agents.items():
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--json", action="store_true", help="JSON output")
        # Each agent adds its own args via add_agent_args() if it exists
    
    args, remaining = parser.parse_known_args()
    if not args.agent:
        parser.print_help()
        sys.exit(1)
    
    # Dynamic import and dispatch
    module_path = agents[args.agent][1]
    # Import and call main() on the agent module
```

- Must handle all 13 agents
- Must pass --json flag through
- Must pass remaining args through to agent
- Must have `if __name__ == "__main__": main()`

**File: `designwise/agent-harness/setup.py`**
```python
from setuptools import setup, find_packages
setup(
    name="cli-anything-designwise",
    version="1.2.0",
    packages=find_packages(),
    entry_points={"console_scripts": ["cli-anything-designwise=cli_anything.designwise.designwise_cli:main"]},
    install_requires=["httpx>=0.24", "click>=8.0"],
    extras_require={
        "full": ["playwright", "axe-core-python", "langgraph"],
    },
    python_requires=">=3.10",
)
```

**Commit:** `feat(designwise): S1.1 — CLI scaffold (13 subcommands) + setup.py`

---

### STEP 3: 9 Remaining Agent Implementations (S1.1)

Create in `designwise/agent-harness/cli_anything/designwise/core/`:

Each agent MUST follow this pattern:
- Class with descriptive docstring from SPEC §2
- `__init__` with config params
- Core methods with real logic skeletons (not empty pass)
- `async def run(self, **kwargs) -> dict` main entry
- `def main()` CLI entry with argparse
- Minimum 150 lines with proper error handling
- JSON-serializable output
- Uses shared utils (supabase_client, brand_tokens, vercel_api)

**Agents to create (in order):**

1. `deploywise_agent.py` — SPEC Agent 05
   - Methods: deploy_to_lab(), create_pr_preview(), check_all_gates(), promote_to_production(), run_smoke_test(), auto_rollback()
   - Uses vercel_api.py
   - 3-tier pipeline: lab → preview (BrandGuard+QA+A11y+SEO gates) → production
   - Post-deploy smoke test within 60s
   - Auto-rollback on smoke failure

2. `qawise_agent.py` — SPEC Agent 06
   - Methods: capture_screenshots(url, viewports), diff_against_baseline(route), run_e2e_flow(), run_lighthouse_ci()
   - Viewports: 1280px (desktop), 768px (tablet), 375px (mobile)
   - Pixelmatch diff threshold: 1%
   - E2E flow: Landing → Heatmap → Parcel → Gate → Signup → App → Chat → Map
   - Lighthouse targets: Performance ≥80, Accessibility ≥90, SEO ≥80
   - Stores baselines in Supabase visual_baselines table

3. `analytics_agent.py` — SPEC Agent 07
   - Methods: aggregate_daily(), generate_funnel_report(), check_conversion_alerts(), generate_weekly_digest()
   - PostHog API client (self-hosted on Hetzner port 8100)
   - Funnel steps: heatmap_view → parcel_click → gate_shown → signup_start → signup_complete → trial_start → paid
   - Alert: any step drops >15% vs 7-day average → Telegram
   - Writes to: page_analytics, conversion_funnel tables

4. `support_agent.py` — SPEC Agent 08
   - Methods: classify_ticket(message), auto_respond(ticket_id), create_github_issue(ticket_id), escalate_to_telegram(ticket_id)
   - Classification categories: ui_bug, feature_request, data_question, billing, general
   - ui_bug → GitHub Issue + ETA response
   - billing → Telegram escalation (HITL required)
   - general → Claude Sonnet auto-response
   - Writes to: support_tickets table

5. `iterate_agent.py` — SPEC Agent 09
   - Methods: identify_lowest_performers(), generate_hypothesis(page_route), request_variants(screen_name, count), configure_ab_test(test_name), measure_significance(test_id), promote_winner(test_id), update_design_md(pattern)
   - Karpathy self-improvement loop
   - Traffic split: 33/33/34 for 3 variants
   - Chi-squared test, 95% confidence for significance
   - Winning variant → default, losers → archive
   - All experiments deploy to LAB first
   - Writes to: ab_tests table

6. `seo_agent.py` — SPEC Agent 10
   - Methods: scan_meta_tags(url), generate_sitemap(routes), add_structured_data(), run_lighthouse_seo(), check_core_web_vitals(), monitor_google_index()
   - Meta: title ≤60 chars, description ≤160 chars, og:image, twitter:card
   - Schema.org: WebApplication, Organization, Product
   - Core Web Vitals: LCP <2.5s, FID <100ms, CLS <0.1
   - Writes to: seo_audits table

7. `a11y_agent.py` — SPEC Agent 11
   - Methods: run_axe_scan(url), test_keyboard_nav(url), audit_aria_labels(url), check_color_independence(url), check_motion_preferences(url)
   - axe-core via Playwright
   - WCAG 2.1 AA: all 50 success criteria
   - Tab order, focus visible, no keyboard traps
   - ARIA on all interactive elements, map controls, modals
   - Target score: ≥90
   - Writes to: brand_violations with a11y-specific violation types

8. `competitor_agent.py` — SPEC Agent 12
   - Methods: capture_homepage(competitor), diff_dom(competitor), extract_pricing(competitor), detect_new_routes(competitor), analyze_tech_stack(competitor), generate_weekly_digest()
   - Targets: propertyonion.com, reventure.app, dono.ai, gridics.com, testfit.io
   - Screenshot + DOM hash comparison week over week
   - Wappalyzer-style header analysis for tech stack
   - Writes to: competitor_snapshots table

9. `content_agent.py` — SPEC Agent 13
   - Methods: generate_landing_copy(section), generate_blog_post(topic), generate_case_study(persona), generate_email_sequence(sequence_type), generate_social_post(platform), validate_with_brandguard(content), validate_with_seo(content)
   - All copy reviewed by BrandGuard for tone
   - All claims backed by real Supabase data
   - NEVER mention competitors by name
   - Blog posts pass through SEOWise before publish

**Commit:** `feat(designwise): S1.1 — 9 agent implementations (13 total squad complete)`

---

### STEP 4: Supabase Schema (S1.4)

Create ALL 11 tables. Use the Supabase Management API or direct PostgreSQL.

**Method: Use Supabase SQL endpoint**
```bash
# Try the pg endpoint via supabase-js or direct SQL
# Connection string: postgresql://postgres.[ref]:[password]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
# Ref: mocerqjnksmhcjzxrewo
```

If direct SQL doesn't work, use the REST API to verify tables exist, and create a migration file that documents what needs to be run manually.

**Tables (from SPEC §4):**
1. design_tasks (with figma_url TEXT column)
2. brand_violations
3. visual_baselines
4. page_analytics (with UNIQUE on route+date)
5. conversion_funnel (with UNIQUE on date+step)
6. support_tickets
7. ab_tests
8. deploy_log
9. competitor_snapshots (with UNIQUE on competitor+scan_date)
10. seo_audits (with UNIQUE on route+scan_date)
11. stitch_usage (with UNIQUE on date+mode+screen_name)

**RLS Policies:**
- All tables: service_role full access
- page_analytics, conversion_funnel: read-only for authenticated
- support_tickets: users can read/write their own

**Verification:** Query each table with curl and confirm 200 status.

**Commit:** `feat(designwise): S1.4 — Supabase 11 tables + RLS + migration`

---

### STEP 5: BrandGuard PR Check Workflow (S1.2)

**File: `.github/workflows/brandguard-pr-check.yml`**
```yaml
name: "BrandGuard PR Check"
on:
  pull_request:
    branches: [main]
    paths:
      - 'app/**'
      - 'components/**'
      - 'styles/**'
      - '*.css'
      - '*.tsx'
      - '*.ts'

jobs:
  brandguard:
    name: "Brand Compliance Scan"
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: |
          pip install httpx playwright
          playwright install chromium
      - name: Run BrandGuard
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_KEY }}
        run: |
          cd designwise/agent-harness
          python -m cli_anything.designwise.core.brandguard_agent \
            --url "${{ github.event.pull_request.head.repo.html_url }}" \
            --json > /tmp/brandguard_report.json
          # Check for critical violations
          python -c "
          import json
          with open('/tmp/brandguard_report.json') as f:
              report = json.load(f)
          violations = report.get('violations', [])
          critical = [v for v in violations if v.get('severity') == 'critical']
          if critical:
              print(f'❌ {len(critical)} critical violations found')
              for v in critical:
                  print(f'  - {v[\"violation_type\"]}: {v[\"actual\"]} (expected: {v[\"expected\"]})')
              exit(1)
          print(f'✅ BrandGuard passed ({len(violations)} minor issues)')
          "
      - name: Comment on PR
        if: always()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = JSON.parse(fs.readFileSync('/tmp/brandguard_report.json', 'utf8'));
            const violations = report.violations || [];
            const body = violations.length === 0
              ? '✅ **BrandGuard:** All checks passed!'
              : `⚠️ **BrandGuard:** ${violations.length} violations found\n\n${violations.map(v => \`- \${v.violation_type}: \${v.actual} (expected: \${v.expected})\`).join('\n')}`;
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body
            });
```

**Commit:** `ci(designwise): S1.2 — brandguard-pr-check.yml`

---

### STEP 6: Eval Framework (S1.6)

**File: `designwise/eval/eval.json`**
Copy EXACTLY from SPEC §5 — 25 binary assertions. No modifications.

**File: `designwise/eval/eval_runner.py`**
- Follow the pattern from `scripts/eval_runner.py` (read it first)
- Load eval.json
- For each assertion: invoke the relevant agent CLI with --json
- Parse output, check assertion
- Report: passed/failed/total with per-agent breakdown
- Output JSON summary

**File: `.github/workflows/autoloop-designwise.yml`**
```yaml
name: "AutoLoop: DesignWise Eval"
on:
  schedule:
    - cron: '0 8 * * *'  # 3AM EST = 8AM UTC
  workflow_dispatch: {}

jobs:
  eval:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install deps
        run: pip install httpx playwright && playwright install chromium
      - name: Run eval
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_KEY }}
        run: python designwise/eval/eval_runner.py --json > eval_results.json
      - name: Report
        run: |
          python -c "
          import json
          with open('eval_results.json') as f:
              r = json.load(f)
          print(f'Score: {r[\"passed\"]}/{r[\"total\"]}')
          if r['passed'] < r['total']:
              for f in r.get('failures', []):
                  print(f'  ❌ {f[\"id\"]}: {f[\"test\"]}')
          "
```

**Commit:** `feat(designwise): S1.6 — eval framework (25 assertions + autoloop cron)`

---

### STEP 7: Tests (S1.2 + S1.3)

**File: `designwise/tests/test_cli.py`** — 15 tests
- Test each of 13 subcommands responds to --help
- Test --json flag produces valid JSON on 2 agents
- Test unknown subcommand prints help

**File: `designwise/tests/test_brandguard_full.py`** — 20 tests
- Test hex color validation (valid, invalid, banned)
- Test font family check (Inter pass, Arial fail)
- Test contrast ratio calculation (known pairs)
- Test WCAG AA threshold (4.5:1 body, 3:1 large)
- Test link checker (mock 200, mock 404)
- Test nav consistency (same component on 2 pages)
- Test font size minimum (11px pass, 10px fail)
- Test full scan output format (JSON structure)
- Test violation severity classification
- Test Supabase insert format

**File: `designwise/tests/test_commander_full.py`** — 10 tests
- Test task classification (new_screen → stitch, fix_bug → brandguard, etc.)
- Test state transitions (RECEIVE → CLASSIFY → DISPATCH → MONITOR → COMPLETE)
- Test quota enforcement (dispatch blocked when quota exceeded)
- Test parallel dispatch mode
- Test Telegram notification format
- Test design_tasks Supabase insert format

**File: `designwise/tests/test_utils.py`** — 10 tests
- Test DesignWiseDB.insert() builds correct POST request
- Test DesignWiseDB.query() builds correct GET params
- Test brand_tokens.parse_design_md() returns correct structure
- Test brand_tokens.check_contrast() with known color pairs
- Test brand_tokens.hex_to_rgb() conversion
- Test VercelClient headers include Bearer token
- Test VercelClient.list_deployments() URL construction
- Test error handling on network failure

**Commit:** `test(designwise): S1 — 55 tests (cli, brandguard, commander, utils)`

---

### STEP 8: Git Push

```bash
git config user.email "ci@biddeed.ai"
git config user.name "BidDeed-CI"
git remote set-url origin "https://x-access-token:${GH_PAT}@github.com/breverdbidder/cli-anything-biddeed.git"

# Commit after EACH step above — never batch
# Push after all commits
git push origin main
```

---

### STEP 9: Verification + Telegram

Before sending Telegram, VERIFY:

```bash
# 1. Count all files in designwise/
find designwise/ -type f -name "*.py" | wc -l
# Expected: 25+ Python files

# 2. Count all test files
find designwise/tests/ -type f -name "test_*.py" | wc -l
# Expected: 8+ test files

# 3. Verify CLI entry point
python designwise/agent-harness/cli_anything/designwise/designwise_cli.py --help
# Expected: 13 subcommands listed

# 4. Verify setup.py
cat designwise/agent-harness/setup.py | grep "cli-anything-designwise"
# Expected: package name found

# 5. Count agent files
ls designwise/agent-harness/cli_anything/designwise/core/*_agent.py | wc -l
# Expected: 13 agent files

# 6. Verify eval.json
python -c "import json; d=json.load(open('designwise/eval/eval.json')); print(f'{len(d[\"assertions\"])} assertions')"
# Expected: 25 assertions

# 7. Verify workflows
ls .github/workflows/*designwise* | wc -l
# Expected: 7+ workflow files

# 8. Verify Supabase tables (if created)
for TABLE in design_tasks brand_violations visual_baselines page_analytics conversion_funnel support_tickets ab_tests deploy_log competitor_snapshots seo_audits stitch_usage; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "apikey: ${SUPABASE_SERVICE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
    "${SUPABASE_URL}/rest/v1/${TABLE}?select=count&limit=0")
  echo "$TABLE: $STATUS"
done
```

**Only send Telegram AFTER all 8 verifications pass.**

Telegram message format:
```
✅ DESIGNWISE SPRINT 1 — 100% COMPLETE

📦 S1.1 Scaffold:
• designwise_cli.py (13 subcommands)
• setup.py (pip installable)
• 3 shared utils
• 13 agents total (4 existing + 9 new)

🛡️ S1.2 BrandGuard:
• brandguard-pr-check.yml deployed
• 20 dedicated tests

🎖️ S1.3 Commander:
• Task classification + dispatch
• Quota enforcement active

🗄️ S1.4 Supabase:
• 11/11 tables: [STATUS]

📊 S1.6 Eval:
• eval.json (25 assertions)
• autoloop-designwise.yml (nightly 3AM EST)

🧪 Tests: [TOTAL] across 8 test files
📁 Files: [TOTAL] Python files in designwise/
```

---

## FAILURE HANDLING

If ANY step fails:
1. Log the error
2. Try ONE alternative approach
3. If still fails: commit what you have, note the failure
4. Send Telegram with partial status:
```
⚠️ DESIGNWISE S1 — PARTIAL (X/9 steps complete)
❌ Failed: [step] — [error]
✅ Completed: [list]
🔧 Next: [what needs manual fix]
```

NEVER claim 100% if verification fails. Trust is earned by showing proof.
