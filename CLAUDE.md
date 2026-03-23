# CLAUDE.md — BidDeed.AI / Everest Capital USA

## Identity
```yaml
founder: Ariel Shapira
company: BidDeed.AI / Everest Capital USA
experience: 10+ yr foreclosure investing, Brevard County FL
licenses: FL broker, general contractor
style: direct, no softening, facts+actions
adhd: systems must self-run
```

## Stack
```yaml
repos: github.com/breverdbidder/*
  active: [cli-anything-biddeed, zonewise-scraper-v4, biddeed-ai, biddeed-ai-ui, zonewise-web, cliproxy-gateway, tax-insurance-optimizer]
db: Supabase mocerqjnksmhcjzxrewo.supabase.co
  tables: [multi_county_auctions(245K), activities, insights, daily_metrics]
compute: Hetzner 87.99.129.125 (CLIProxyAPI 127.0.0.1:8317)
ai:
  free: Gemini Flash (CLIProxyAPI) — DEAD, keys expired
  cheap: DeepSeek V3.2 ($0.28/1M)
  primary: Claude (Max plan, never API)
deploy: [GitHub Actions, Cloudflare Pages, Render]
brand: { primary: "#1E3A5F", accent: "#F59E0B", font: Inter, bg: "#020617" }
```

## 3-Layer CLAUDE.md Hierarchy (Claude Architect Standard)
```yaml
layer_1_user: ~/.claude/CLAUDE.md  # personal prefs, not version-controlled
layer_2_project: ./CLAUDE.md       # THIS FILE — team rules, architecture, triggers
layer_3_path_rules: .claude/rules/ # pattern-matched, loaded ONLY when editing matching files
  deployed: [harness(*/SKILL.md), evals(*/eval/**), scripts(scripts/**), youtube(youtube/**)]
  principle: lean context window — rules load only when relevant
  enforcement: hooks for 100% reliability (finance/security), prompts for style/tone
```


## Context Rules
```yaml
triggers:
  auction_or_property: query Supabase multi_county_auctions first
  case_number: search multi_county_auctions.case_number
  deal_analysis: apply (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)
  pipeline_health: check daily_metrics + recent GHA runs
  county_mention: verify counties/ config exists before assuming
  build_request: follow cli-anything HARNESS.md 7-phase
  deploy: push to GitHub, never local/GDrive
  spend_over_10: STOP and confirm
  context_switch: flag "📌 [previous task] still open"
  summit: execute immediately, zero questions
```

## Work Principles
```yaml
rules:
  - execute first, report results
  - $10/session max, batch ops, one attempt per approach
  - zero HITL: 3 alternatives before surfacing blocker
  - push back with strong opinions when disagreeing
  - wrong = "I was wrong", never invent numbers
```

## Slash Commands
```yaml
commands:
  /auction-brief: morning auction briefing from Supabase
  /county-setup: onboard new FL county
  /deal-intel: process foreclosure docs → structured data
  /tldr: end-of-session summary, update memory.md
  /transcript: YouTube video analysis via Hetzner pipeline
  /animated-ui: >
    5-phase: Design System → 21st.dev → Animation → Assets → Build.
    Enforces house brand. Auto-deployed from claude-skills-library to Hetzner.
```

## Family
```yaml
wife: Mariam (Property360 real estate, Protection Partners insurance, contracting)
son: Michael (16, D1 swimmer, Satellite Beach HS, keto diet, Shabbat)
observance: Orthodox (Shabbat Fri sunset–Sat havdalah, kosher, holidays)
```

## Session Hygiene (Mar 15, 2026)

### Mandatory Plugins
```yaml
plugins:
  context7: { purpose: live API docs, install: "/plugin → context7", cost: $0 }
  cc-status-line: { purpose: context monitor, install: "npx cc-status-line@latest" }
  cctop: { purpose: sessions dashboard, install: "curl -fsSL https://raw.githubusercontent.com/DeanLa/cctop/main/install.sh | bash", fork: breverdbidder/cctop }
```

### Context Window Rules
```yaml
rules:
  50pct_rule: kill+restart at ~50% context
  never_compact: loses working context, keeps stale — always fresh start
  sub_agents: dispatch via Superpowers for heavy work
  harness_checkpoint: save state + restart if >50% mid-pipeline
cc_status_line:
  line1: "model | context% | session_cost | session_clock"
  line2: "git_branch | git_worktree"
```

---

# GSTACK PATTERNS
```yaml
source: garrytan/gstack (MIT)
deployed: Mar 17, 2026
fork: breverdbidder/gstack
```

## AskUserQuestion Format (MANDATORY)
```yaml
format:
  1_reground: project + branch + current task (1-2 sentences)
  2_eli16: plain English a 16yo follows, no jargon, concrete examples
  3_recommend: "RECOMMENDATION: Choose [X] because [reason]"
  4_options: "A) ... B) ... C) ..."
assumption: user hasn't looked in 20 min, no code open
```

## Review Modes

```mermaid
flowchart TD
  START{Review Type?} -->|strategic/product| CEO["/plan-ceo"]
  START -->|technical/PR| ENG["/plan-eng"]

  CEO --> CEO_MODE{Select ONE mode}
  CEO_MODE --> EXP["SCOPE EXPANSION<br/>10x version for 2x effort"]
  CEO_MODE --> HOLD["HOLD SCOPE<br/>Max rigor, bulletproof"]
  CEO_MODE --> RED_C["SCOPE REDUCTION<br/>Minimum viable, cut rest"]

  ENG --> ENG_MODE{Select ONE mode}
  ENG_MODE --> RED_E["SCOPE REDUCTION<br/>Propose minimal, review that"]
  ENG_MODE --> BIG["BIG CHANGE<br/>Interactive, 4 sections, ≤8 issues each"]
  ENG_MODE --> SMALL["SMALL CHANGE<br/>Compressed, 1 issue/section"]
```

### CEO Mode Directives
```yaml
directives:
  - zero silent failures — every failure mode visible
  - every error has a name — specific exception, not "handle errors"
  - data flows have shadow paths — nil, empty, upstream error
  - diagrams mandatory — Mermaid for every new data flow
  - deferred = written in TODOS.md or doesn't exist
  - optimize for 6-month future
  - permission to say "scrap it and do this instead"
critical: once mode selected, NEVER drift to another
```

### Eng Mode Sections
```mermaid
flowchart LR
  A[1. Architecture] --> B[2. Code Quality]
  B --> C[3. Tests]
  C --> D[4. Performance]
```
```yaml
eng_sections:
  architecture: [system design, dependencies, coupling, scaling, security, failure scenarios]
  code_quality: [DRY, error handling, edge cases, tech debt, over/under-engineering]
  tests: [diagram UX/data/code flows, verify test exists, check eval.json]
  performance: [N+1 queries, unbounded selects, missing indexes, recomputation]
rule: STOP after each section, present issues one-at-a-time, resolve before next
```

## Fix-First Review (MANDATORY)
```mermaid
flowchart TD
  READ[1. Read full diff] --> P1[2. Pass 1 CRITICAL<br/>SQL safety, race conditions,<br/>LLM trust boundary, enum completeness]
  P1 --> P2[3. Pass 2 INFORMATIONAL<br/>Side effects, magic numbers,<br/>dead code, test gaps, crypto, types]
  P2 --> FIX{Mechanical?}
  FIX -->|yes| AUTO[AUTO-FIX]
  FIX -->|no| ASK[NEEDS INPUT]
  AUTO --> OUT["Pre-Landing Review: N issues<br/>(X critical, Y informational)"]
  ASK --> OUT
```

## visual-explainer Skill
```yaml
source: ~/.claude/skills/visual-explainer/plugins/visual-explainer/SKILL.md
output: ~/.agent/diagrams/ (open in browser)
commands: [/diff-review, /plan-review, /project-recap, /generate-web-diagram, /generate-slides, /fact-check]
brand: templates/biddeed-brand-preset.html
auto_trigger: "table 4+ rows OR 3+ columns → HTML, never ASCII"
```

## gh-aw Integration (Mar 23, 2026)

### Active Agentic Workflows
- `doc-sync-agent.md` — Auto-updates docs on code push (auto-merge)
- `issue-triage-agent.md` — Labels new issues P0-P3 + type
- `ci-failure-agent.md` — Diagnoses CI failures, opens fix issues
- `pr-gate-agent.md` — Classifies PR risk: LOW/MEDIUM/HIGH
- `dep-guardian-agent.md` — Weekly dependency updates (Monday 3AM EST)
- `changelog-agent.md` — Auto-changelog on release

### Merge Strategy
- LOW risk: auto-merge (docs, deps patch, style, tests)
- MEDIUM risk: merge after CI green
- HIGH risk: needs-human-review label → Ariel reviews

### Engine
All workflows use `engine: claude` with ANTHROPIC_API_KEY secret.
