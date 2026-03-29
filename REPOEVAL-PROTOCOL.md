# REPOEVAL PROTOCOL
# Everest Ecosystem — Instant Repository Evaluation
# Date: March 28, 2026 | Status: PERMANENT
# Trigger: Any GitHub repository URL shared in chat
# Origin: Chase AI "5 Repos" video → honest eval → this protocol

---

## TRIGGER

```yaml
trigger: "Any github.com/{owner}/{repo} URL in a message"
action: "INSTANT execution. No asking. No planning."
pattern: "Same as Transcript Squad — link = execute"
```

---

## PIPELINE

```yaml
repoeval_pipeline:

  1_clone:
    action: "git clone --depth 1 into /home/claude/repo-eval/{repo}"
    timeout: 30s
    on_fail: "Report CLONE_FAILED, stop"

  2_analyze:
    read:
      - README.md (full)
      - Core source files (top 3 by size)
      - package.json / pyproject.toml / Cargo.toml
      - CLAUDE.md / AGENTS.md (if exists)
      - Test files (count + framework)
    extract:
      purpose: "One sentence — what does this do?"
      architecture: "Language, framework, key modules"
      loc: "Lines of code in core"
      tests: "Count, framework, pass rate if visible"
      maturity: "Stars, age, contributors, release cadence"
      install: "How hard to set up? (1-liner vs complex)"

  3_classify:
    question: "Does our stack already do this?"
    outcomes:
      OVERLAP: "We have equivalent capability → go to COMPARE"
      PARTIAL: "We have some of this but gaps exist → go to COMPARE + GAP"
      NEW: "We don't have this at all → go to ADOPT_EVAL"

  4a_compare: # For OVERLAP and PARTIAL
    dimensions: "4-6 relevant dimensions"
    per_dimension:
      them: "Score 1-10 [VERIFIED from repo analysis]"
      us: "Score 1-10 [VERIFIED/UNTESTED/INFERRED per Honesty Protocol]"
      verdict: "THEY WIN | WE WIN | TIE"
      evidence: "Specific proof for both scores"
    rules:
      - "NEVER assume we're better without proof"
      - "If tools available to verify our side → AUTO-VERIFY (Rule 4)"
      - "UNTESTED scores are honest, invented scores are violations"
    output:
      - Side-by-side evaluation artifact
      - Action items to close gaps (prioritized)
      - Overall: "They lead by X" or "We lead by X"

  4b_adopt_eval: # For NEW capabilities
    framework: "CC Native vs Custom Eval (memory #13)"
    criteria:
      security: "1-100 — auth, encryption, data exposure"
      value: "1-100 — what problem does this solve for us?"
      stability: "1-100 — age, stars, maintenance, breaking changes"
      integration: "1-100 — how easy to plug into our stack?"
      cost: "1-100 — free? API costs? infra requirements?"
    weighted_score: "Average of 5 criteria"
    decision:
      ADOPT: "Score >= 80 — install and integrate"
      EVAL: "Score 60-79 — 7-day pilot, track in cc_feature_comparison"
      WATCH: "Score 40-59 — interesting but not ready"
      REJECT: "Score < 40 — doesn't fit our needs"
    output:
      - Score card with all 5 criteria
      - Decision: ADOPT / EVAL / WATCH / REJECT
      - If ADOPT: concrete next steps (install commands, config, SKILL.md)
      - If EVAL: pilot plan with success criteria

  5_store:
    supabase: "Insert into repo_evaluations table"
    fields:
      - repo_url, repo_name, stars, purpose
      - classification (OVERLAP/PARTIAL/NEW)
      - overall_them, overall_us (for comparisons)
      - adopt_score, adopt_decision (for new repos)
      - action_items (JSON array)
      - evaluated_at

  6_report:
    format: "React artifact with house brand colors"
    content: "Scores, verdicts, action items, decision"
    honesty: "Every score tagged VERIFIED/UNTESTED/INFERRED"
```

---

## HONESTY PROTOCOL INTEGRATION

All scores follow the Honesty Protocol (HONESTY-PROTOCOL.md):

```yaml
scoring_rules:
  - "Every score must have a tag: VERIFIED / UNTESTED / INFERRED"
  - "VERIFIED requires evidence from actual repo analysis or our stack testing"
  - "UNTESTED is always acceptable — zero penalty"
  - "If we can test our side NOW, we must (AUTO-VERIFY Rule 4)"
  - "Wrong VERIFIED → logged to honesty_violations"
  - "BLANK > WRONG — say 'UNTESTED' rather than invent a number"
```

---

## EXAMPLES

### Example 1: OVERLAP
```
User shares: https://github.com/karpathy/autoresearch

Classification: OVERLAP with AUTOLOOP
Action: Side-by-side comparison on 5 dimensions
Result: They lead by 1.6 points
Action items: Add continuous scoring, experiment log, NEVER STOP mode
```

### Example 2: NEW — ADOPT
```
User shares: https://github.com/louislva/claude-peers-mcp

Classification: NEW (we have no CC-to-CC messaging)
Adopt Score: 72 (EVAL)
Decision: 7-day pilot — install on Hetzner, test with SUMMIT/CODER
Success criteria: Reduces context loss between sessions by >50%
```

### Example 3: NEW — REJECT
```
User shares: https://github.com/some-tool/very-niche-thing

Classification: NEW
Adopt Score: 35 (REJECT)
Decision: Doesn't solve a problem we have. Skip.
```

---

## ANTI-PATTERNS

```yaml
banned:
  - "Evaluating a repo without cloning it first"
  - "Saying 'looks interesting, want me to evaluate?' — just do it"
  - "Scoring our stack favorably without testing"
  - "Recommending ADOPT without install steps"
  - "Declaring ADOPT and never installing (GWS CLI pattern)"
  - "Building a plan to evaluate instead of evaluating"
```

---

## ACTIVATION

This protocol activates on any GitHub URL.
It does not require permission.
It follows the same instant-execution pattern as Transcript Squad.
