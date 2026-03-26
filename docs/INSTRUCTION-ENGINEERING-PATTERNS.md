# Instruction Engineering Patterns for Claude Code

> Extracted from [VoltAgent/awesome-codex-subagents](https://github.com/VoltAgent/awesome-codex-subagents) (136 agents, 10 categories).
> Adapted from OpenAI Codex `.toml` format → Claude Code CLAUDE.md / SKILL.md / HARNESS.md format.
> Date: 2026-03-25

---

## 1. THE FOUR-PHASE WORKING MODE

Every high-quality agent instruction follows a 4-step execution pattern. Adopt this as the standard for all SKILL.md and HARNESS.md files.

```yaml
working_mode:
  phase_1_map: "Map the boundary — identify scope, entry points, failure surfaces"
  phase_2_separate: "Separate confirmed evidence from hypotheses before acting"
  phase_3_intervene: "Implement the SMALLEST coherent intervention with highest impact"
  phase_4_validate: "Validate one normal path, one failure path, one integration edge"
```

### Why this works
- Phase 1 prevents acting on assumptions
- Phase 2 stops hallucinated root causes
- Phase 3 enforces minimal engineering (aligns with COST DISCIPLINE)
- Phase 4 catches regressions without exhaustive testing

### Template for SKILL.md

```markdown
## Working Mode
1. **Map** the [scope boundary] and identify the concrete [pain point / failure surface].
2. **Separate** evidence-backed root causes from symptoms. Do not guess.
3. **Implement** the smallest coherent intervention that [specific goal].
4. **Validate** one happy path, one failure path, one integration edge.
```

---

## 2. OWNERSHIP DECLARATION PATTERN

Every agent opens with a single sentence declaring what it OWNS and HOW it frames the work. This prevents scope creep and anchors behavior.

### Pattern

```
Own [domain] as [framing], not [anti-pattern].
```

### Best examples from the repo

| Agent | Declaration |
|-------|-------------|
| reviewer | "Own PR-style review work as **evidence-driven quality and risk reduction**, not checklist theater." |
| refactoring | "Own behavior-preserving refactoring as **developer productivity and workflow reliability engineering**, not checklist execution." |
| llm-architect | "Own LLM architecture review as **system design for reliability, controllability, and measurable quality**." |
| context-manager | "Own context packaging as **signal curation for downstream subagents**." |
| security-auditor | "Own security auditing as **evidence-driven quality and risk reduction**, not checklist theater." |

### Template

```markdown
## Role
Own [what this agent does] as [positive framing with measurable outcome], not [specific anti-pattern to avoid].
```

### Apply to cli-anything harnesses

```markdown
## Role
Own zonewise county conquest as evidence-driven parcel coverage verification, not aspirational percentage claims.
```

---

## 3. FOCUS AREAS AS DECISION CHECKLIST

Instead of vague "consider these things," the best agents list 6-8 specific focus areas that function as a decision checklist during execution. Each item names a **concrete boundary or tradeoff**, not an abstract concept.

### Anti-pattern (vague)
```
- Consider performance
- Think about security
- Handle errors properly
```

### Good pattern (specific boundaries)
```
- context construction quality and relevance filtering strategy
- prompt-tool-retrieval contract boundaries and error propagation
- structured output constraints and downstream parsing robustness
- fallback/degradation strategy for model/tool/retrieval failures
- latency/cost budget alignment with product requirements
- orchestration complexity versus debuggability and maintainability
```

### Key insight
Each focus item names TWO things in tension: "X versus Y" or "X and Y boundary." This forces the agent to make tradeoff decisions rather than just listing concerns.

### Template for SKILL.md

```markdown
## Focus Areas
- [boundary A] and [boundary B] contract fidelity
- [resource X] versus [resource Y] tradeoff alignment
- [failure mode] detection and [recovery strategy] robustness
- [input surface] validation and [output contract] stability
- [operational concern] implications for [deployment/rollback]
- [complexity measure] budget versus [maintainability goal]
```

---

## 4. QUALITY CHECKS AS GATE CONDITIONS

Quality checks are NOT aspirational — they are binary gate conditions that must pass before the agent returns output. Frame them as verification actions, not hopes.

### Pattern: verb-first, evidence-required

```markdown
## Quality Checks
- **verify** [specific claim] maps to [concrete evidence type]
- **confirm** [each recommendation] includes [expected gain AND tradeoff cost]
- **check** [compatibility/regression risk] for [specific downstream impact]
- **ensure** [low-confidence items] are marked as hypotheses, not facts
- **call out** [what requires runtime/environment validation beyond static analysis]
```

### The five standard gates (adapt per agent)

| Gate | What it catches |
|------|----------------|
| `verify` evidence mapping | Prevents hallucinated findings |
| `confirm` gain + tradeoff | Prevents one-sided recommendations |
| `check` compatibility | Prevents breaking downstream |
| `ensure` confidence labeling | Prevents false certainty |
| `call out` remaining unknowns | Prevents premature "DONE" declarations |

### Apply to AUTOLOOP eval

```yaml
quality_gates:
  - verify: "output maps to real Supabase data, not invented numbers"
  - confirm: "each recommendation includes expected impact AND cost"
  - check: "changes don't break existing harness tests"
  - ensure: "uncertain items marked HYPOTHESIS not FACT"
  - call_out: "what needs production verification"
```

---

## 5. STRUCTURED RETURN CONTRACT

Every agent defines exactly what it returns. This is the **output schema** — non-negotiable, same structure every time. Prevents rambling and ensures downstream consumers (other agents, Ariel, dashboards) can parse results.

### The universal 5-item return contract

```markdown
## Return Format
1. **Scope**: Exact boundary analyzed (file, component, service, diff area)
2. **Finding**: Key finding(s) or risk hypothesis WITH supporting evidence
3. **Intervention**: Smallest recommended fix and expected risk reduction
4. **Validated**: What was verified and what still needs runtime checks
5. **Residual**: Remaining risk, priority, and concrete next actions
```

### Variants by agent type

**For read-only/review agents:**
```
- scope analyzed
- findings with evidence
- recommended fix + risk reduction
- what was validated
- residual risk + follow-ups
```

**For write/builder agents:**
```
- workflow boundary changed
- primary friction source + evidence
- smallest safe change + tradeoffs
- validations performed
- residual risk + follow-ups
```

**For orchestration agents:**
```
- multi-agent plan (local vs delegated split)
- per-agent ownership + output contract
- dependency/wait/integration timeline
- conflict-resolution strategy
- main coordination risk + fallback
```

**For context/research agents:**
```
- context packet (architecture, constraints, risks)
- key files/symbols and relevance
- assumptions with confidence levels
- unresolved unknowns + discovery order
- handoff notes for downstream agents
```

---

## 6. THE GUARD RAIL PATTERN

Every agent ends with a single "Do not..." constraint that prevents the most common failure mode for that agent type. This is the **kill switch** — one line that catches the #1 way the agent would go off-rails.

### Pattern

```
Do not [most tempting failure mode] unless explicitly requested by [authority].
```

### Best examples

| Agent Type | Guard Rail |
|------------|-----------|
| reviewer | "Do not dilute findings with style-only commentary" |
| architect-reviewer | "Do not push a full architectural rewrite for scoped defects" |
| refactoring | "Do not mix unrelated feature work into structural refactor changes" |
| llm-architect | "Do not conflate benchmark gains with production reliability" |
| security-auditor | "Do not claim full security assurance from static review alone" |
| code-mapper | "Do not propose architecture redesign or code edits" |
| docs-researcher | "Do not make code changes or speculate beyond documentation evidence" |
| context-manager | "Do not include broad repository summaries that are not decision-relevant" |
| multi-agent-coordinator | "Do not delegate urgent blocking work that the parent should execute immediately" |

### Apply to BidDeed.AI agents

```markdown
# HARNESS.md guard rails
- zonewise: "Do not declare county coverage complete without DB row count verification"
- auction: "Do not present ML predictions as certainties — always include confidence interval"
- reports: "Do not include Property360/Mariam references in BidDeed.AI-branded outputs"
- sentinel: "Do not retry more than 3 times — escalate to Telegram after max retries"
```

---

## 7. SANDBOX MODE AS PERMISSION BOUNDARY

Agents are explicitly tagged as read-only or write-capable. This prevents review agents from making changes and build agents from only analyzing.

### Apply to Claude Code rules

```yaml
# .claude/rules/ permission mapping
review_agents:
  sandbox: read-only
  examples: [reviewer, security-auditor, architect-reviewer, code-mapper]
  rule: "Analyze and report. Never modify files."

builder_agents:
  sandbox: workspace-write
  examples: [refactoring-specialist, mcp-developer, backend-developer]
  rule: "Map → Implement → Validate. Commit with descriptive messages."

research_agents:
  sandbox: read-only
  examples: [docs-researcher, context-manager, search-specialist]
  rule: "Source-of-truth verification only. Never speculate beyond evidence."
```

---

## 8. MODEL ROUTING BY COGNITIVE LOAD

The repo routes to different models based on task complexity. Adapt for your Smart Router.

```yaml
# Codex routing (reference)
deep_reasoning: gpt-5.4  # architecture, security, financial
fast_scanning: gpt-5.3-codex-spark  # search, docs, context packaging

# BidDeed.AI Smart Router equivalent
quality_tier: Claude Sonnet  # architecture decisions, security review, lien analysis
bulk_tier: Gemini Flash  # scraping, data transforms, context packaging
cheap_tier: DeepSeek V3.2  # parsing, formatting, report generation
```

---

## 9. MULTI-AGENT COORDINATION PRINCIPLES

From the `multi-agent-coordinator` — the most sophisticated orchestration patterns:

```yaml
coordination_rules:
  critical_path_first: "Parent handles immediate blockers BEFORE delegating"
  disjoint_scopes: "At most ONE owner per write-critical scope"
  explicit_contracts: "Every delegate gets: objective, output schema, boundary"
  wait_strategy: "Define when to block vs continue local work"
  conflict_resolution: "Plan merge strategy BEFORE launching parallel work"
  contingency: "What happens when delegate returns partial/uncertain results"
```

### Apply to SUMMIT dispatch

```yaml
# summit_dispatch_rules.yaml
pre_dispatch:
  - verify: "task has single owner per write scope"
  - define: "output contract for each Claude Code session"
  - plan: "merge strategy if sessions produce conflicting changes"

during_execution:
  - parent_handles: "blocking issues that need immediate resolution"
  - delegate_handles: "bounded, high-yield parallel work"
  - wait_points: "defined with explicit integration contracts"

post_execution:
  - reconcile: "results from all sessions against integration checklist"
  - resolve: "conflicts using pre-planned merge strategy"
  - report: "residual risk and follow-up branches"
```

---

## 10. CONFIDENCE LABELING PATTERN

The best agents explicitly distinguish between confirmed facts and hypotheses. This is critical for the NEVER-LIE rule.

```markdown
## Confidence Protocol
- CONFIRMED: Backed by code evidence, DB query, or test result
- HYPOTHESIS: Inferred from patterns but not directly verified
- UNKNOWN: Cannot determine from available context — requires runtime check

Every finding MUST carry one of these labels. NEVER present HYPOTHESIS as CONFIRMED.
```

### Apply to all harness outputs

```yaml
# eval.json assertion pattern
assertions:
  - name: "confidence_labeling"
    check: "every finding in output has CONFIRMED|HYPOTHESIS|UNKNOWN label"
    weight: 2  # double-weighted — catches the #1 trust violation
```

---

## COMPOSITE TEMPLATE: SKILL.md v2

Combining all patterns into an upgraded SKILL.md template:

```markdown
# [AGENT NAME] SKILL

## Role
Own [domain] as [positive framing], not [anti-pattern].

## Working Mode
1. **Map** the [scope] and identify [concrete target].
2. **Separate** evidence from hypotheses. Do not guess.
3. **Implement** the smallest intervention that [goal].
4. **Validate** one happy path, one failure path, one edge.

## Focus Areas
- [boundary A] and [boundary B] contract fidelity
- [resource X] versus [resource Y] tradeoff
- [failure mode] detection and [recovery] robustness
- [input surface] validation and [output contract] stability
- [operational concern] for [deployment/rollback]
- [complexity] budget versus [maintainability]

## Quality Gates
- **verify** findings map to concrete evidence
- **confirm** recommendations include gain AND tradeoff
- **check** downstream compatibility impact
- **ensure** uncertain items labeled HYPOTHESIS
- **call out** what needs runtime validation

## Return Format
1. Scope analyzed
2. Findings with evidence and confidence label
3. Smallest intervention + expected impact
4. What was validated vs needs runtime check
5. Residual risk + prioritized next actions

## Guard Rail
Do not [most tempting failure mode for this agent type].

## Permission
[read-only | workspace-write]
```

---

## QUICK REFERENCE: PATTERN → PROBLEM SOLVED

| Pattern | Problem It Solves |
|---------|------------------|
| 4-Phase Working Mode | Agents act on assumptions without mapping first |
| Ownership Declaration | Scope creep, vague responsibilities |
| Focus Areas as Decisions | Abstract checklists that don't drive action |
| Quality Gates | Hallucinated findings presented as facts |
| Return Contract | Rambling output that can't be parsed downstream |
| Guard Rail | Agent's #1 failure mode goes unchecked |
| Sandbox Mode | Review agents making changes, builders only analyzing |
| Model Routing | Expensive models used for simple tasks |
| Coordination Principles | Parallel agents with conflicting writes |
| Confidence Labeling | NEVER-LIE violations — hypothesis as fact |
