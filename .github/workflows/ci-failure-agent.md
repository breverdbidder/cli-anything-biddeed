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

When a CI workflow fails, diagnose the root cause and create an issue with the proposed fix.

### Process
1. Read the failed workflow logs
2. Identify the root cause (test failure, dependency issue, build error, timeout, flaky test)
3. Create an issue with:
   - Summary of what failed
   - Root cause analysis
   - Proposed fix (with code snippets if applicable)
   - Link to the failed run

### Rules
- Don't create issues for known flaky tests (check if similar issue exists)
- Include the exact error message
- If the fix is obvious (typo, missing dep), include the exact fix
- If complex, describe the investigation path
- Never propose fixes you're not confident about
