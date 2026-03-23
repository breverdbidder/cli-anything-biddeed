---
engine: claude
on:
  issues:
    types: [opened, reopened]
permissions:
  contents: read
  issues: read
safe-outputs:
  add-labels:
    allowed:
      - bug
      - feature
      - question
      - documentation
      - P0-critical
      - P1-high
      - P2-medium
      - P3-low
  add-comment:
    max: 1
---

## Issue Triage Agent

Analyze new issues and apply appropriate labels.

### Label Rules
- P0-critical: Security vulnerabilities, data loss, production down
- P1-high: Broken core functionality, blocking workflows
- P2-medium: Non-blocking bugs, performance issues
- P3-low: Nice-to-haves, cosmetic issues
- bug/feature/question/documentation: Type classification

### Process
1. Read the issue title and body
2. Check for duplicates in recent issues
3. Apply priority label (P0-P3)
4. Apply type label (bug/feature/question/documentation)
5. Add a brief comment explaining the triage decision

### Rules
- Be concise in comments (2-3 sentences max)
- If unclear, label as P2-medium and question
- Never close issues automatically
- For P0-critical, also mention @breverdbidder in comment
