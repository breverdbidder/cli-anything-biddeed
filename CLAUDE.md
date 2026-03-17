# CLAUDE.md — BidDeed.AI / Everest Capital USA

## Who I Am
Ariel Shapira. Solo founder of BidDeed.AI and Everest Capital USA. 10+ years foreclosure investing in Brevard County, Florida. Licensed FL broker and general contractor. Building an AI-powered foreclosure auction intelligence platform. ADHD — I need systems that run themselves.

## My Stack
- **Repos:** github.com/breverdbidder/* (cli-anything-biddeed, zonewise-scraper-v4, biddeed-ai, biddeed-ai-ui, zonewise-web, cliproxy-gateway, tax-insurance-optimizer)
- **Database:** Supabase (mocerqjnksmhcjzxrewo.supabase.co) — multi_county_auctions (245K rows), activities, insights, daily_metrics
- **Compute:** Hetzner everest-dispatch (87.99.129.125) with CLIProxyAPI on 127.0.0.1:8317
- **AI:** Gemini Flash (FREE via CLIProxyAPI), DeepSeek V3.2 ($0.28/1M), Claude (Max plan, never API)
- **Deploy:** GitHub Actions + Cloudflare Pages + Render
- **Brand:** Navy #1E3A5F, Orange #F59E0B, Inter font, bg #020617

## Context Rules

When I mention an auction or property → query Supabase `multi_county_auctions` first
When I mention a case number → search `multi_county_auctions` by case_number field
When analyzing a deal → apply max bid formula: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)
When I ask about pipeline health → check `daily_metrics` and recent GitHub Action runs
When I mention a county → check if config exists in `counties/` before assuming anything
When something needs building → follow cli-anything HARNESS.md 7-phase pattern
When deploying code → push to GitHub, never local installs or Google Drive
When spending money → stop and confirm if >$10/session
When I context-switch mid-task → flag it: "📌 [previous task] is still open"
When I say "Summit" → execute immediately, no questions, no clarification

## How I Work
- Direct, no softening language. Facts and actions.
- Cost discipline: $10/session max. Batch operations. One attempt per approach.
- Zero HITL: try 3 alternatives before surfacing a blocker.
- Execute first, report results. Don't ask what to do.
- Push back with strong opinions when you disagree.
- Wrong = "I was wrong." Never invent numbers.

## Slash Commands
- `/auction-brief` — morning auction briefing from Supabase
- `/county-setup` — onboard a new Florida county
- `/deal-intel` — process foreclosure documents into structured data
- `/tldr` — end-of-session summary, updates memory.md
- `/transcript` — YouTube video analysis via Hetzner pipeline
- `/animated-ui` — Animated frontend builder for BidDeed.AI & ZoneWise.AI. 5-phase pipeline: Design System → 21st.dev components → Animation system → Assets → Build. Enforces house brand (navy #1E3A5F, orange #F59E0B, slate-950 #020617). Auto-deployed from breverdbidder/claude-skills-library to Hetzner /root/.claude/skills/

## Family Context (when relevant)
- Wife Mariam: runs Property360 real estate, Protection Partners insurance, contracting
- Son Michael (16): D1 competitive swimmer, Satellite Beach HS, keto diet, Shabbat observance
- Orthodox practices: Shabbat (no work Fri sunset–Sat havdalah), kosher, holidays

## Claude Code Session Hygiene (Mar 15, 2026)

### Mandatory Plugins
These plugins MUST be installed in every Claude Code environment:

1. **Context7** — Live API documentation. Fixes 6-12 month knowledge lag on Supabase, Cloudflare, LangGraph, Firecrawl, Mapbox APIs. Install: `/plugin` → Discover → context7. Zero cost.
2. **CC Status Line** — Context window monitor. Shows model, context %, session cost, git branch. Install: `npx cc-status-line@latest` before launching claude.
3. **cctop** — Claude Code sessions dashboard. Monitor all sessions from one TUI: status, context %, tokens, errors, git branch. Install: `curl -fsSL https://raw.githubusercontent.com/DeanLa/cctop/main/install.sh | bash`. Run `cctop` in separate terminal. Fork: breverdbidder/cctop.

### Context Window Rules
- **50% RULE:** Kill and restart session when context reaches ~50%. Claude degrades well before 100%.
- **NEVER /compact.** Worst of both worlds — loses working context but keeps stale/poisoned context. Always start fresh.
- **Sub-agents for heavy work.** Dispatch sub-agents (via Superpowers execute-plan) so main orchestrator context stays clean.
- **cli-anything harnesses:** Add context checkpoint between HARNESS.md phases. If context > 50% mid-pipeline, save state and restart.

### CC Status Line Config
```
Line 1: model | context% | session_cost | session_clock
Line 2: git_branch | git_worktree
```

---

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
