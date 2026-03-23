---
engine: claude
on:
  pull_request:
    types: [opened, synchronize]
permissions:
  contents: read
  pull-requests: read
safe-outputs:
  add-labels:
    allowed:
      - auto-merge-low
      - auto-merge-medium
      - needs-human-review
  add-comment:
    max: 1
---

## PR Risk Classification Gate

Classify PRs by risk level and apply merge strategy.

### Risk Tiers
- LOW (auto-merge): Only docs, deps (patch), style, comments, tests, CI config
- MEDIUM (merge after CI): Non-critical code changes, refactors, non-domain logic
- HIGH (human review): Domain logic (auction/zoning/scraping), security, DB schema, auth, secrets, API contracts

### Process
1. Review changed files and diff
2. Classify risk tier
3. Apply label: auto-merge-low, auto-merge-medium, or needs-human-review
4. Comment with 1-line risk explanation

### Rules
- When in doubt, classify higher (MEDIUM over LOW, HIGH over MEDIUM)
- Any change to .env, secrets, auth, or DB migrations = always HIGH
- Changes to CLAUDE.md or .claude/rules/ = MEDIUM minimum
