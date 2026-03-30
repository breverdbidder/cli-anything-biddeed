---
engine: claude
on:
  workflow_run:
    workflows: ["*"]
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
