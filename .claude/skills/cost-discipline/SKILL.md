---
name: cost-discipline
description: Use to enforce session cost limits, prevent verbose output, avoid retry loops, and batch operations efficiently. Triggers on: $10 limit, token cost, session budget, cost cap, retry loop, verbose output, redundant search, spend tracking.
---

# Cost Discipline

## Role
Own session economics as measurable constraint enforcement, not aspirational frugality.

## Working Mode
Map -> Separate evidence from hypothesis -> Smallest intervention -> Validate.

## Focus Areas
1. Session budget cap -- $10/session hard limit, STOP and confirm before exceeding
2. Token efficiency -- prefer targeted reads over full file dumps
3. Batch operations -- group related API calls, never loop one-at-a-time
4. Retry discipline -- max 1 retry per approach, diagnose before retrying
5. Search efficiency -- targeted grep/glob before broad Agent searches
6. Output verbosity -- concise responses; skip preamble and trailing summaries
7. Tool selection -- use dedicated tools (Grep, Glob, Read) not Bash grep/find
8. Spend tracking -- report cumulative cost at natural session milestones

## Quality Gates
- verify: Session cost stays under $10 (track via token counts or CC cost meter)
- confirm: Each retry is preceded by diagnosis, not blind repetition
- check: Batch ops used when 3+ similar items need processing
- ensure: No full file reads when only a section is needed (use offset/limit)
- call_out: Flag if approaching $8 threshold (80% of cap)

## Output Format
Single status line at session milestones:
```
Cost check: $X.XX / $10.00 (XX%) — [current_task] — [items_remaining]
```

## Constraints
- STOP and confirm with user if next action will push session over $10
- Never retry a failed approach more than once without diagnosing root cause
- Never search with Agent tool if Grep/Glob can find it in 1-2 queries
- Never read entire files when offset/limit suffices
- $0 cost operations (file reads, git log) are always preferred over API calls

## Guard Rail
Do not initiate any action estimated to cost > $2 without confirming total session spend first.
