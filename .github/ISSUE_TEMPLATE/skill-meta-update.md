---
name: Skill Meta Update
about: Auto-dispatched brief that appends skill-audit learnings into CC_META_PROMPT.md
title: "[skill-meta-updater] Auto-learn from skill-audit"
labels: ["automation", "skill-meta-updater"]
---

Operating contract: CC_META_PROMPT.md. Read it first.
READ ALL COMMENTS ON THIS ISSUE BEFORE STARTING.

/loop
/goal Close the skill self-improvement loop for this run: read the latest
docs/skill-audits/skill-audit-*.md file, extract its scarred rules, friction
patterns, and dispatch failures, and append them as compact one-line entries
to the `## AUTO-LEARNINGS` section of CC_META_PROMPT.md so the next dispatch
inherits them.

## Context / live numbers to re-derive
- List `docs/skill-audits/` and confirm which file is actually the latest by
  filename date — more than one audit may have landed in the same push, do
  not assume the file that triggered this run is the newest.

## Required behavior
1. Read the latest `docs/skill-audits/skill-audit-*.md` file in full.
2. Extract `scarred_rules[]`, `friction_patterns[]`, `dispatch_failures[]`
   (or the closest equivalent sections if the audit's field names differ —
   note the mapping if so).
3. For each extracted item, write one entry on its own line:
   `[YYYY-MM-DD] PATTERN: <one line, max 120 chars>` — use today's UTC date
   and the audit's own content. Do not invent findings that aren't in the audit.
4. Append the entries below the
   `## AUTO-LEARNINGS (do not hand-edit below this line)` marker in
   CC_META_PROMPT.md, below its `<!-- skill-meta-updater: last updated ... -->`
   comment. Do NOT modify anything above the marker line.
5. Update the `<!-- skill-meta-updater: last updated ... -->` comment to today's
   UTC date.
6. Enforce a hard cap of 20 entries total under the marker — if appending would
   exceed 20, drop the oldest (top) entries first (FIFO).
7. Commit with message: `chore(meta): auto-learn from skill-audit <date>`

## Order of work
inspect docs/skill-audits/ -> read latest audit -> dry-run the diff to
CC_META_PROMPT.md -> apply -> commit -> log to agent_ops_log -> prove

## Explicit non-goals
- Do NOT modify anything above the `## AUTO-LEARNINGS` marker in CC_META_PROMPT.md
- Do NOT summarize or compress existing CC_META_PROMPT.md content
- Do NOT create new Supabase tables
- Do NOT process more than the single latest skill-audit file this run

## Definition of Done
- [ ] Latest `docs/skill-audits/skill-audit-*.md` read and quoted
- [ ] CC_META_PROMPT.md AUTO-LEARNINGS section has new entries appended, capped at 20
- [ ] Commit `chore(meta): auto-learn from skill-audit <date>` pushed to main
- [ ] `public.agent_ops_log` row inserted: task='skill-meta-updater', status reflects outcome
- [ ] Negative test: confirm content above the AUTO-LEARNINGS marker is byte-identical to before the run

## Protocol
Honesty Protocol V3. Report VERIFIED | PARTIAL | BLOCKED | UNTESTED per
CC_META_PROMPT.md section 6. Log the `agent_ops_log` row per section 6.
