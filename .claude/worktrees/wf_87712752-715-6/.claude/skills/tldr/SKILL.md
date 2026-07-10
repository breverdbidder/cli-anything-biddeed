---
name: tldr
description: End-of-session summary. Captures decisions, discoveries, next actions, and blockers. Saves to the most relevant folder. Updates memory.md. Run at the end of any Claude Code session.
---

# TLDR — Session Summary

Summarize this session: what was decided, what was built, what broke, what's next.

Save to the most relevant location:
- Architecture decisions → `docs/decisions/`
- Bug fixes → commit message is enough, skip file
- New feature → `docs/plans/` or update existing spec
- Research/analysis → `reports/`
- General session → `docs/sessions/`

Format:

```markdown
# Session: [date] — [one-line summary]

## Decisions
- [each decision with reasoning]

## Built / Changed
- [files created or modified, with purpose]

## Discovered
- [things learned, patterns found, gotchas hit]

## Blockers
- [anything unresolved, with severity]

## Next Actions
- [ ] [specific actionable task]
- [ ] [specific actionable task]
```

Then append a one-liner to `memory.md` under Session Log:
```
- [date]: [one-line summary of what happened and key outcome]
```

If any preference or pattern was learned (e.g., "user prefers X approach"), add it to memory.md under My Preferences.
