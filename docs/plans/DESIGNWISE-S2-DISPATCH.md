# DESIGNWISE-S2-DISPATCH.md
# Sprint 2: Stitch + Build — Claude Code Dispatch
# Date: 2026-03-22 | Version: 1.2.0

---

## CONTEXT LOAD (DO THIS FIRST)

```bash
cat CLAUDE.md
cat docs/plans/DESIGNWISE-SPEC.md | head -300
cat docs/plans/DESIGNWISE-PLAN.md | grep -A 100 "SPRINT 2"
ls -la designwise/agent-harness/cli_anything/designwise/core/
```

## EXISTING STATE (VERIFIED 2026-03-22)

### S1 COMPLETE — DO NOT RECREATE:
- 13 agents in designwise/agent-harness/cli_anything/designwise/core/
- CLI + setup.py + 3 utils
- 55+ tests in designwise/tests/
- eval.json + autoloop + brandguard-pr-check.yml
- 11 Supabase tables (design_tasks, brand_violations, visual_baselines, page_analytics, conversion_funnel, support_tickets, ab_tests, deploy_log, competitor_snapshots, seo_audits, stitch_usage)

### S2 AGENTS THAT EXIST BUT NEED REAL IMPLEMENTATION:
- stitch_agent.py (785 lines, V1.2.0 — MCP stubs, needs real MCP client wrapper)
- codewise_agent.py (480 lines — needs real HTML→Next.js converter)
- deploywise_agent.py (S1 stub — needs full 3-tier pipeline)

---

## EXECUTION PLAN — 7 STEPS

### STEP 1: StitchWise MCP Client Wrapper (S2.1)

Create `designwise/agent-harness/cli_anything/designwise/utils/stitch_mcp.py`:

This is the REAL MCP client that replaces the stubs in stitch_agent.py.

- Class `StitchMCPClient` wrapping subprocess communication with `npx @google/stitch-sdk serve`
- Methods matching the 3 canonical MCP tools:
  - `build_sitemaps(project_id, routes)` → dict[route, html]
  - `get_screen_code(project_id, screen_name)` → HTML+CSS string
  - `get_screen_image(project_id, screen_name)` → base64 PNG
- JSON-RPC communication over stdio (MCP protocol)
- Connection lifecycle: start(), call(), close()
- Error handling: retry 3x, fallback to cached HTML if MCP server unavailable
- Cache layer: save last successful response per screen to /tmp/stitch_cache/
- Subprocess management: spawn `npx @google/stitch-sdk serve` on first call, reuse
- Also support fallback: `npx stitchmcp` (community wrapper) if official SDK fails

Update `stitch_agent.py`:
- Replace `_call_stitch_mcp()` stub to use real `StitchMCPClient`
- Keep all existing logic (quota, batch, prototype, intent prompts, etc.)
- Just swap the transport layer

**Commit:** `feat(designwise): S2.1 — StitchWise MCP client wrapper (real MCP transport)`

### STEP 2: CodeWise Real Implementation (S2.2)

Update `designwise/agent-harness/cli_anything/designwise/core/codewise_agent.py`:

The existing file is a stub. Replace with real Stitch→Next.js converter:

- Method `convert_screen(screen_name, html_css, design_md_path)`:
  - Parse HTML from Stitch output
  - Extract Tailwind classes
  - Map hardcoded hex colors → CSS variable references from DESIGN.md
  - Replace HTML elements with shadcn/ui components where possible
  - Wrap in proper Next.js page component (.tsx)
  - Add TypeScript types
  - Return: { tsx_code, route, component_name, imports }

- Method `convert_all_screens(screens_dict)`:
  - Iterate all screens from StitchWise batch output
  - Route mapping: landing-hero→/, heatmap→/heatmap, app→/app, etc.
  - Generate index file with all exports
  - Return: { files: [{path, content}], routes: {} }

- Method `create_feature_branch(screen_name)`:
  - git checkout -b feat/designwise-{screen_name}
  - Write files to correct Next.js paths
  - Run ESLint + TypeScript checks
  - git add + commit
  - Create PR via GitHub API

- Direct Stitch MCP pipeline (Amendment 4):
  - Primary: Connect to Stitch MCP → generate React directly
  - Fallback: HTML export → conversion pipeline (above)

- Uses `brand_tokens.py` util for DESIGN.md parsing
- Uses `stitch_mcp.py` for MCP communication

**Commit:** `feat(designwise): S2.2 — CodeWise real Stitch→Next.js converter`

### STEP 3: DeployWise Full Implementation (S2.3)

Update `designwise/agent-harness/cli_anything/designwise/core/deploywise_agent.py`:

Full 3-tier deployment gatekeeper:

- Method `deploy_to_lab(branch_name)`:
  - Push to `lab` branch on zonewise-web
  - Vercel auto-deploys to lab.zonewise.ai
  - Return: { deploy_url, deploy_id }

- Method `create_pr_preview(feature_branch, target="main")`:
  - Create PR via GitHub API
  - Vercel auto-generates preview URL
  - Return: { pr_url, pr_number, preview_url }

- Method `check_all_gates(pr_number)`:
  - Poll GitHub API for required status checks:
    - brandguard-pr-check ✅/❌
    - qa-visual-regression ✅/❌
    - a11y-check ✅/❌
    - seo-check ✅/❌
  - Return: { all_passed: bool, results: {} }

- Method `promote_to_production(pr_number)`:
  - Merge PR via GitHub API (only if all gates passed)
  - Vercel auto-deploys main to production
  - Return: { merge_sha, deploy_url }

- Method `run_smoke_test(url)`:
  - Hit 5 critical URLs within 60 seconds of deploy
  - Check: 200 status, page loads, no console errors
  - Return: { passed: bool, results: [] }

- Method `auto_rollback(commit_sha)`:
  - git revert HEAD → force push
  - Telegram alert
  - Log to deploy_log table

- Uses `vercel_api.py` util
- All deploys logged to Supabase deploy_log table

**Commit:** `feat(designwise): S2.3 — DeployWise 3-tier deploy pipeline`

### STEP 4: QAWise Visual Regression Workflow (S2.3 support)

Create `.github/workflows/qa-visual-regression.yml`:
- Trigger: on pull_request targeting main
- Steps: checkout → setup → install playwright → capture screenshots → diff vs baseline
- Required check: blocks merge if diff > 1%
- Stores baselines in Supabase visual_baselines table

**Commit:** `ci(designwise): S2.3 — qa-visual-regression.yml PR check`

### STEP 5: New Tests for S2

Add to `designwise/tests/`:

- `test_stitch_mcp.py` — 10 tests:
  - MCP client initialization
  - build_sitemaps returns dict
  - get_screen_code returns HTML
  - get_screen_image returns base64
  - Retry on connection failure
  - Cache hit/miss
  - Fallback to community wrapper

- `test_codewise_full.py` — 10 tests:
  - HTML parsing extracts elements
  - Color replacement hex→CSS var
  - TypeScript output validates
  - Route mapping correctness
  - shadcn/ui component substitution
  - Feature branch creation
  - ESLint pass on output

- `test_deploywise_full.py` — 10 tests:
  - Lab deploy creates correct branch
  - PR creation returns URL
  - Gate checking polls correctly
  - Promotion only when all gates pass
  - Smoke test hits correct URLs
  - Rollback reverts commit
  - deploy_log Supabase insert format

**Commit:** `test(designwise): S2 — 30 new tests (MCP, CodeWise, DeployWise)`

### STEP 6: Update PLAN.md Checklist

Mark S2 items as complete. Update TODO.md if present.

**Commit:** `docs(designwise): S2 checklist updated`

### STEP 7: Git Push + Telegram

```bash
git config user.email "ci@biddeed.ai"
git config user.name "BidDeed-CI"
```

Commit after EACH step. Push after all commits.

Verification before Telegram:
```bash
# Count files
find designwise/ -name "*.py" | wc -l  # Expected: 35+
find designwise/tests/ -name "test_*.py" | wc -l  # Expected: 11+

# Verify new files exist
ls designwise/agent-harness/cli_anything/designwise/utils/stitch_mcp.py
ls .github/workflows/qa-visual-regression.yml

# Check test count
grep -r "def test_" designwise/tests/ | wc -l  # Expected: 85+
```

Telegram:
```
✅ DESIGNWISE SPRINT 2 COMPLETE

🎨 S2.1: StitchWise MCP client wrapper (real transport)
⚙️ S2.2: CodeWise Stitch→Next.js converter
🚀 S2.3: DeployWise 3-tier pipeline (lab→preview→prod)
🔍 QA: qa-visual-regression.yml PR check
🧪 Tests: 30+ new (85+ total)

Sprint 3 ready.
```

---

## WHAT S2 DOES NOT INCLUDE (deferred):
- S2.4 Core Pages — This is zonewise-web repo work, needs separate Summit dispatch
- Actual Stitch screen generation — requires Google Cloud auth (PRE-FLIGHT)
- lab.zonewise.ai setup — needs Vercel branch deploy config

## FAILURE HANDLING
If any step fails: commit what you have, note failure, send partial Telegram.
NEVER claim 100% if verification fails.
