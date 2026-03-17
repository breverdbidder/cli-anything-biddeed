# GSTACK PATTERNS (Cherry-picked from garrytan/gstack, MIT License)
# Deployed: Mar 17, 2026 | Source: breverdbidder/gstack

## AskUserQuestion Format (MANDATORY for all human-facing questions)

When asking the user ANY question, ALWAYS follow this structure:

1. **Re-ground:** State the project, the current branch, and the current task. (1-2 sentences)
2. **ELI16:** Explain the problem in plain English a smart 16-year-old could follow. No function names, no internal jargon, no implementation details. Use concrete examples and analogies. Say what it DOES, not what it's called.
3. **Recommend:** `RECOMMENDATION: Choose [X] because [one-line reason]`
4. **Options:** Lettered options: `A) ... B) ... C) ...`

Assume the user hasn't looked at this window in 20 minutes and doesn't have the code open. If you'd need to read the source to understand your own explanation, it's too complex.

## Review Modes (use when reviewing plans or PRs)

### CEO Mode (Product Review)
Use when: Strategic decisions, new features, product direction, architecture pivots.
Trigger: `/plan-ceo` or when reviewing plans that change product behavior.

Three sub-modes — ask user to select ONE, then COMMIT to it fully:
- **SCOPE EXPANSION:** Dream big. Ask "what's the 10x version for 2x effort?" Find the 10-star product. Push scope UP.
- **HOLD SCOPE:** Maximum rigor. Scope is accepted. Make it bulletproof — catch every failure mode, map every error path.
- **SCOPE REDUCTION:** Be a surgeon. Find the minimum viable version. Cut everything else. Ruthless.

**Critical rule:** Once mode is selected, DO NOT silently drift. If EXPANSION selected, don't argue for less. If REDUCTION selected, don't sneak scope back in.

CEO Mode Prime Directives:
1. Zero silent failures — every failure mode must be visible
2. Every error has a name — don't say "handle errors", name the specific exception
3. Data flows have shadow paths — nil input, empty input, upstream error. Trace all four.
4. Diagrams are mandatory — ASCII art for every new data flow, state machine, pipeline
5. Everything deferred must be written down — TODOS.md or it doesn't exist
6. Optimize for 6-month future, not just today
7. You have permission to say "scrap it and do this instead"

### Eng Mode (Technical Review)
Use when: Code review, PR review, technical implementation plans.
Trigger: `/plan-eng` or when reviewing technical changes.

Three sub-modes — ask user to select ONE:
- **SCOPE REDUCTION:** Plan is overbuilt. Propose minimal version, then review that.
- **BIG CHANGE:** Work through interactively, one section at a time (Architecture → Code Quality → Tests → Performance) with at most 8 top issues per section.
- **SMALL CHANGE:** Compressed review — scope check + one combined pass. Pick the single most important issue per section. One question round at the end.

Eng Mode walks through 4 sections in order:
1. **Architecture:** System design, dependencies, coupling, scaling, security, failure scenarios
2. **Code Quality:** DRY violations, error handling, edge cases, tech debt, over/under-engineering
3. **Tests:** Diagram all new UX/data flows/codepaths. For each, verify a test exists. Check eval.json assertions.
4. **Performance:** N+1 queries, unbounded selects, missing indexes, unnecessary recomputation

**STOP after each section.** Present issues one at a time with options and recommendations. Do NOT batch multiple issues. Only proceed after all issues in current section are resolved.

## Fix-First Review (MANDATORY for all PR reviews)

When reviewing code changes, apply the Fix-First heuristic from `docs/GSTACK_REVIEW_CHECKLIST.md`:
1. Read the full diff FIRST
2. Run Pass 1 (CRITICAL): SQL safety, race conditions, LLM trust boundary, enum completeness
3. Run Pass 2 (INFORMATIONAL): Side effects, magic numbers, dead code, test gaps, crypto, types
4. For each finding: AUTO-FIX if mechanical, ASK if ambiguous (see checklist for classification)
5. Output format: `Pre-Landing Review: N issues (X critical, Y informational)` with AUTO-FIXED and NEEDS INPUT sections
