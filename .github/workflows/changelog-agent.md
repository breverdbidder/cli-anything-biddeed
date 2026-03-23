---
engine: claude
on:
  release:
    types: [published]
permissions:
  contents: read
safe-outputs:
  create-pull-request:
    title-prefix: "[changelog] "
    labels: [changelog, auto-generated]
    auto-merge: true
---

## Release Changelog Generator

Generate changelog entries from commits since the last release.

### Process
1. Get commits between current and previous release tag
2. Categorize: Features, Fixes, Docs, Refactors, CI/Ops
3. Write concise changelog entry
4. Update CHANGELOG.md (prepend new entry)
5. Open PR with the update

### Style
- Use conventional commit prefixes
- Link to PRs where available
- Keep entries to one line each
- Group by category
