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
