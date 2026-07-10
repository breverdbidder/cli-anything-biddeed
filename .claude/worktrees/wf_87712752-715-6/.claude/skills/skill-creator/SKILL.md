---
name: skill-creator
description: Use when creating a new Platform Skill from scratch, converting a .claude/rules/ file to .claude/skills/ format, or generating a SKILL.md + eval.json pair. Triggers on: create skill, new skill, convert rule to skill, add platform skill, write SKILL.md, write eval.json, skill authoring, skill template.
---

# Skill Creator

## Role
Own Platform Skills authoring as spec-compliant template generation, not freeform documentation writing.

## Working Mode
Identify skill domain -> Apply SKILL.md template -> Generate 25 binary assertions -> Validate structure -> Output ready-to-commit files.

## Focus Areas
1. SKILL.md frontmatter -- name, description (trigger criteria), optional context/agent/allowed-tools
2. Role declaration -- Own [domain] as [measurable framing], not [anti-pattern]
3. Working Mode -- 4-step: Map -> Separate evidence -> Smallest intervention -> Validate
4. Focus Areas -- 6-8 concrete boundaries/tradeoffs (not abstract concepts)
5. Quality Gates -- verify/confirm/check/ensure/call_out (binary pass/fail, not aspirational)
6. Output Format -- JSON schema or structured block showing expected output
7. eval.json -- 25 binary assertions, pass_threshold=0.8, autoloop_compatible=true
8. Guard Rail -- single Do not [failure mode] line (per INSTRUCTION-ENGINEERING-PATTERNS.md)

## Quality Gates
- verify: SKILL.md has all required sections (Role, Working Mode, Focus Areas, Quality Gates, Output Format, Constraints, Guard Rail)
- confirm: eval.json has exactly 25 assertions with id 1-25, all type=binary
- check: description field contains specific trigger keywords (not generic phrases)
- ensure: Guard Rail is a single sentence starting with Do not
- call_out: Any Quality Gate that is aspirational rather than binary pass/fail

## Output Format
Two files ready to commit:

  .claude/skills/<skill-id>/SKILL.md  (frontmatter + 7 sections)
  .claude/skills/<skill-id>/eval.json (25 binary assertions)

Confirm structure with:
  ls .claude/skills/<skill-id>/
  python3 -c "import json; d=json.load(open('.claude/skills/<skill-id>/eval.json')); assert len(d['assertions'])==25"

## Constraints
- NEVER create a skill with fewer than 25 assertions in eval.json
- NEVER write a Guard Rail with multiple sentences -- single Do not X only
- NEVER write Quality Gates as goals (try to, aim to) -- each must be binary pass/fail
- description field must list specific trigger words/phrases for activation accuracy
- Load docs/INSTRUCTION-ENGINEERING-PATTERNS.md before authoring any skill
- Follow existing skills as templates (zonewise-scraper, honesty-protocol are canonical examples)

## Guard Rail
Do not create a skill without running assertion count check: assert len(assertions) == 25 before claiming the eval.json is complete.
