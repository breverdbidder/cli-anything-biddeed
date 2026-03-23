---
pattern: "*/SKILL.md"
---
# Harness SKILL.md Rules

- Every SKILL.md follows HARNESS.md 7-phase pipeline. No shortcuts
- Skill description must specify: trigger words, input format, output format
- Tool limit: 4-5 tools max per harness (Claude Architect principle)
- Dependencies: declared in requirements.txt or package.json at harness root
- AUTOLOOP: SKILL.md changes auto-tested via eval.json → score → keep/revert
- Max 50 iterations per AUTOLOOP run. Git commit on improve, reset on regress
- New agents: ALWAYS fork from existing harness, never from scratch
