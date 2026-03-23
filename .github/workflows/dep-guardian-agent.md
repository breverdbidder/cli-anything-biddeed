---
engine: claude
on:
  schedule:
    - cron: "0 8 * * 1"  # Monday 8AM UTC (3AM EST)
permissions:
  contents: read
safe-outputs:
  create-pull-request:
    title-prefix: "[deps] "
    labels: [dependencies, auto-generated]
    auto-merge: true
---

## Weekly Dependency Guardian

Check for outdated or vulnerable dependencies and open update PRs.

### Process
1. Check package.json / requirements.txt for outdated packages
2. Check for known security advisories (npm audit / pip-audit)
3. For patch updates: open PR with auto-merge
4. For minor/major: open PR labeled needs-human-review
5. Include changelog summary for each update

### Rules
- Never update multiple major versions in one PR
- Security patches always get their own PR
- Include the advisory ID for security updates
- Test that lockfile resolves correctly
