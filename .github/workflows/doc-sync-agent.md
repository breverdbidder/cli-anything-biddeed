---
engine: claude
on:
  push:
    branches: [main]
    paths:
      - "src/**"
      - "scripts/**"
      - "*.py"
      - "*.js"
      - "*.ts"
permissions:
  contents: read
  pull-requests: read
safe-outputs:
  create-pull-request:
    title-prefix: "[docs] "
    labels: [documentation, auto-generated]
    auto-merge: true
---

## Continuous Documentation Sync

When code changes are pushed, review and update documentation to stay in sync.

### What to check
- README.md accuracy vs current code
- CLAUDE.md directives match actual pipeline behavior
- SKILL.md files reflect current capabilities
- API docs match function signatures
- Inline code comments for complex logic

### Rules
- Only open a PR if changes are needed
- Keep changes minimal and focused
- Preserve existing formatting and style
- Never modify code files, only documentation
- If unsure about a change, skip it
