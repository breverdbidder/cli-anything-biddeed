---
globs:
  - "**/*"
description: "Ultraplan integration protocol — when to use /ultraplan vs headless execution"
alwaysApply: true
---

# ULTRAPLAN PROTOCOL

## Decision Gate — When to Use Ultraplan

Use `/ultraplan` for tasks with complexity > 6 that involve:
- Multi-file refactors (3+ files, cross-cutting changes)
- Architecture migrations (DB schema + API + frontend)
- Full feature implementations spanning multiple components
- OSINT pipeline builds (multiple adapters + correlation rules)
- Sprint-level work packages (e.g. "implement entire S2")

Use standard `claude -p` headless for:
- Bug fixes (single file or isolated)
- Config changes, secret rotations, DNS fixes
- Single-file implementations
- Workflow deployments
- Database migrations (schema only)
- Documentation updates

## Ultraplan Invocation

```
/ultraplan <full task description including acceptance criteria>
```

- Always include acceptance criteria in the ultraplan prompt
- Reference spec files: "per docs/plans/SPEC-NAME.md"
- Reference issue: "as described in issue #NNN"
- Ultraplan runs Opus 4.6 in CCR for up to 30 min
- Results land as a PR — review before merge

## Constraints

- `/ultraplan` does NOT work in headless mode (`claude -p`)
- Requires interactive CC session (tmux or direct terminal)
- Requires `/login` — OAuth must be active
- If Remote Control is active, it disconnects when ultraplan starts
- Works best with committed + pushed code (uses git remote snapshot)

## Native Status (verified 2026-04-07, CC 2.1.92)

- `/ultraplan` is a **native CC built-in** — no custom runner needed
- Custom `summit-ultraplan.yml` + `ultraplan-runner.py` retired (SUMMIT #392)
- Native implementation: 28 references in cli.js, full lifecycle phases
  (`plan_ready`, `needs_input`, `running`), CCR session URL tracking
- To dispatch ultraplan via GHA: use standard SUMMIT dispatch workflow
  with an interactive CC session, NOT the retired custom runner

## Post-Ultraplan

1. PR arrives from CCR execution
2. Review PR for Honesty Protocol compliance
3. Run Playwright verification if UI changes
4. Merge only after SHIP GATE criteria met
5. Update nexus_tasks with completion status
