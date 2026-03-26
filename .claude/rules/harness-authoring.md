---
pattern: "**/HARNESS.md"
---

# Instruction Engineering for HARNESS.md (auto-loaded)

Before writing or editing ANY HARNESS.md, load docs/INSTRUCTION-ENGINEERING-PATTERNS.md.

## Harness-Specific Patterns

### Ownership Declaration (line 1)
```
Own [harness domain] as [measurable framing], not [anti-pattern].
```
Examples:
- zonewise: "Own county conquest as evidence-driven parcel coverage, not aspirational claims."
- auction: "Own foreclosure analysis as risk-quantified deal intelligence, not checklist processing."

### Guard Rails (mandatory per harness)
Every HARNESS.md MUST end with a guard rail section:
```yaml
guard_rails:
  - "Do not [#1 failure mode for this harness]"
  - "Do not [#2 failure mode]"
```

### Quality Gates → eval.json Mapping
Every quality gate in HARNESS.md MUST have a corresponding assertion in eval.json:
- verify → binary assertion checking evidence exists
- confirm → assertion checking gain + tradeoff stated
- call_out → assertion checking unknowns are surfaced

### Confidence Labels on All Outputs
Harness output MUST tag every claim: CONFIRMED | HYPOTHESIS | UNKNOWN.
