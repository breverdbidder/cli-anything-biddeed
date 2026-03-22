# CONTEXT-COMPRESSION-SPEC.md
# Spec: Convert CLAUDE.md files from prose → Mermaid/YAML
# Author: Claude AI Architect | Date: Mar 22, 2026
# Dispatched to: Claude Code via Summit

## Objective
Convert all CLAUDE.md files across 5 repos from verbose prose to Mermaid+YAML format.
Zero information loss. ~30% token reduction per file.

## Rule (PERMANENT)
```yaml
format_rules:
  mermaid: pipelines, workflows, state machines, decision trees, review flows
  yaml: configs, checklists, structured context, identity, rules, triggers
  prose: ONLY for 1-2 sentence section intros where no structure applies
  ascii: BANNED — token-expensive, LLM-unparseable
  convert_on_touch: when editing ANY doc, convert prose sections encountered
```

## Repos to Convert
```yaml
repos:
  - breverdbidder/cli-anything-biddeed    # PRIMARY — reference impl attached
  - breverdbidder/biddeed-ai
  - breverdbidder/biddeed-ai-ui
  - breverdbidder/zonewise-web
  - breverdbidder/zonewise-scraper-v4
also_apply_to:
  - SKILL.md files in any harness
  - docs/plans/*.md specs
  - HARNESS.md
  - PROJECT_STATE.json descriptions (where prose exists)
```

## Conversion Rules

### 1. Identity/Bio Blocks → YAML
```yaml
# BEFORE (prose):
# "Ariel Shapira. Solo founder of BidDeed.AI and Everest Capital USA.
#  10+ years foreclosure investing..."

# AFTER (yaml):
founder: Ariel Shapira
company: BidDeed.AI / Everest Capital USA
experience: 10+ yr foreclosure investing, Brevard County FL
```

### 2. Stack/Infra Lists → YAML
```yaml
# BEFORE (markdown bullets):
# - **Repos:** github.com/breverdbidder/*
# - **Database:** Supabase (url)

# AFTER (yaml):
repos: github.com/breverdbidder/*
db: { url: mocerqjnksmhcjzxrewo.supabase.co, key_tables: [...] }
```

### 3. Conditional Rules ("When X → Y") → YAML triggers
```yaml
# BEFORE (prose):
# "When I mention an auction → query Supabase first"

# AFTER (yaml):
triggers:
  auction_or_property: query Supabase multi_county_auctions first
  case_number: search by case_number field
```

### 4. Pipelines/Workflows → Mermaid flowchart
```
# BEFORE (prose):
# "Skills should hand off: Research → Summary → Content → Repurposing"

# AFTER (mermaid):
flowchart LR
  A[Research] --> B[Summary] --> C[Content] --> D[Repurposing]
```

### 5. Decision Trees → Mermaid flowchart TD
```
# BEFORE (prose):
# "Select one mode: SCOPE EXPANSION for 10x, HOLD for rigor, REDUCTION for minimal"

# AFTER (mermaid):
flowchart TD
  MODE{Select ONE} --> EXP[EXPANSION]
  MODE --> HOLD[HOLD SCOPE]
  MODE --> RED[REDUCTION]
```

### 6. Sequential Steps → Mermaid flowchart TD
```
# BEFORE (prose):
# "1. Read diff 2. Pass 1 critical 3. Pass 2 info 4. Auto-fix or ask"

# AFTER (mermaid):
flowchart TD
  A[Read diff] --> B[Pass 1 CRITICAL] --> C[Pass 2 INFO] --> D{Mechanical?}
  D -->|yes| E[AUTO-FIX]
  D -->|no| F[NEEDS INPUT]
```

### 7. Bullet-Point Principles → YAML list
```yaml
# BEFORE (markdown bullets):
# - Direct, no softening language
# - Cost discipline: $10/session max

# AFTER (yaml):
rules:
  - direct, no softening language
  - $10/session max, batch ops
```

## Execution Steps
```yaml
per_repo:
  1: git pull latest CLAUDE.md
  2: identify all prose sections
  3: convert using rules above
  4: validate no information lost (diff check)
  5: run token count before/after
  6: commit with message "refactor: CLAUDE.md → Mermaid+YAML (context compression)"
  7: push to main

verification:
  - zero information loss (manual diff)
  - token reduction ≥ 20%
  - all Mermaid blocks render correctly
  - all YAML blocks parse without errors
```

## Reference Implementation
See: cli-anything-biddeed CLAUDE-compressed.md (attached to this spec)
This is the canonical example — all other repos should follow this pattern.

## CEO Mode Directives Note
```yaml
change: "diagrams mandatory — ASCII art for every new data flow"
to: "diagrams mandatory — Mermaid for every new data flow"
reason: ASCII art is BANNED per CONTEXT COMPRESSION rule
```
