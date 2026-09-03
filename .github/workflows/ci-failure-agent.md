---
engine: claude
on:
  # 2026-09-03 (#19767): narrowed from workflows: ["*"], found during a sweep
  # for other wildcard workflow_run triggers contributing to a run-storm
  # (see sentinel-v2.yml / task-lifecycle.yml for the primary fix + evidence).
  # This workflow is currently `disabled_manually` (gh api workflows/250146872
  # -> state: disabled_manually) so it was not a live contributor to the
  # measured storm, but the wildcard is the same latent landmine and would
  # reproduce the fan-out the moment someone re-enables it. Scoped to the
  # build/gate/deploy/security surface plus the SUMMIT dispatch workflows —
  # narrower than "every workflow" but still covers the CI-shaped failures
  # this agent exists to diagnose. This list is INFERRED from workflow names
  # (ci.yml, security-scan.yml, rls-gate.yml, eg14-gate.yml,
  # playwright-verify.yml, brandguard-pr-check.yml, qa-visual-regression.yml,
  # weekly-designmd-drift.yml) rather than verified against a canonical "this
  # is CI" definition — review before re-enabling if the intent was broader.
  workflow_run:
    workflows:
      - "CI — Full Test Suite"
      - "AgentShield — Weekly Security Scan"
      - "RLS Gate (scheduled + on migration push)"
      - "EG14 Gate (parameterized)"
      - "Playwright Verify — Hetzner SSH (generic)"
      - "BrandGuard PR Check"
      - "qa-visual-regression"
      - "Weekly DesignMD Drift Check"
      - "CC Runner — GHA-only (no Hetzner)"
      - "Gemini Runner — T2/T3 grunt lane (no Hetzner, no Claude Code)"
      - "SUMMIT: Task from Issue"
    types: [completed]
    branches: [main]
permissions:
  contents: read
  issues: read
  actions: read
safe-outputs:
  create-issue:
    title-prefix: "[ci-fix] "
    labels: [ci-failure, auto-diagnosed]
    close-older-issues: true
---

## CI Failure Analyzer

When a CI workflow fails, diagnose the root cause and create or update an issue.

### IGNORE LIST — Do NOT create issues for these workflows (use `noop` output):
- Everest Sentinel
- Everest Sentinel V2
- Sprint Parallel Executor (24/6)
- Any workflow whose name starts with "SHIP-" (e.g. ship-paperclip-*)
- Issue Triage Agent
- Ci Failure Agent
- Daily Auto-Fixer
- Hetzner Watchdog
- SUMMIT Verifier — 30min Loop
- Continuous Executor (Every 2 Hours)
- Morning Executor (6 AM EST — Sun-Thu, Sat)

### DEDUP — Before creating an issue:
1. Search open issues with label `ci-failure` for the exact workflow name.
2. If an open issue already exists for this workflow → add a comment to it with the new failure run URL and DO NOT create a new issue (use `noop` output for the create-issue action).
3. If the most recent failure for this workflow was less than **1 hour ago** → use `noop` (cooldown, no new issue).

### SEVERITY TIERS:
- Check how many consecutive failures this workflow has had (look at the last 5 runs).
- **3+ consecutive failures** → label `P1`, add `[P1]` to issue title.
- **First failure** → label `P2`, apply a **6-hour cooldown** (if existing P2 issue opened < 6h ago → comment instead of new issue).
- A single transient failure is likely noise — prefer `noop` unless the error is clearly actionable.

### Process
1. Check if workflow name is in the IGNORE LIST → if yes, output `noop`.
2. Check dedup (open issues for this workflow) and cooldown → if triggered, add comment + `noop`.
3. Check consecutive failure count to assign severity.
4. Read the failed workflow logs.
5. Identify the root cause (test failure, dependency issue, build error, timeout, flaky test).
6. Create an issue with:
   - Summary of what failed
   - Root cause analysis
   - Proposed fix (with code snippets if applicable)
   - Link to the failed run
   - Consecutive failure count
   - Severity label (P1 or P2)

### Rules
- NEVER create duplicate issues for the same workflow — always check first.
- Don't create issues for expected/infrastructure noise workflows (see IGNORE LIST).
- Include the exact error message.
- If the fix is obvious (typo, missing dep), include the exact fix.
- If complex, describe the investigation path.
- Never propose fixes you're not confident about.
- Prefer `noop` over creating noise — a missed issue is better than 9 duplicate issues.
