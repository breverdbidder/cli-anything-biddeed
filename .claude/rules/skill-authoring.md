---
pattern: "**/SKILL.md"
---

# Instruction Engineering Patterns (auto-loaded)

Before writing or editing ANY SKILL.md, load and apply docs/INSTRUCTION-ENGINEERING-PATTERNS.md.

## Mandatory Structure for SKILL.md

1. **Role**: Own [domain] as [framing], not [anti-pattern].
2. **Working Mode**: Map → Separate evidence from hypothesis → Smallest intervention → Validate.
3. **Focus Areas**: 6-8 items naming concrete boundaries/tradeoffs.
4. **Quality Gates**: verify/confirm/check/ensure/call_out — binary pass/fail.
5. **Return Format**: scope → finding+evidence → intervention → validated → residual.
6. **Guard Rail**: Single "Do not [#1 failure mode]" line.

## Confidence Labels (NEVER-LIE enforcement)
- CONFIRMED: Backed by code evidence, DB query, or test result.
- HYPOTHESIS: Inferred from patterns but not directly verified.
- UNKNOWN: Cannot determine — requires runtime check.

Every finding MUST carry a label. NEVER present HYPOTHESIS as CONFIRMED.
