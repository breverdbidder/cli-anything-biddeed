# Dispatch Contract Pointer

Every CC dispatch brief (issue body) MUST open with this exact line:

```
Operating contract: CC_META_PROMPT.md. Read it first.
```

`CC_META_PROMPT.md` (repo root) is the canonical operating contract for all
`/loop` briefs. It defines evidence rules, write discipline, credential
fallback, concurrency limits, and the required reporting format.

Read `CC_META_PROMPT.md` in full before starting any dispatched task. It
overrides ad-hoc habits where they conflict — comments on the issue override
the brief body, and the brief body must reference this contract first.

## Architecture SSOT

Briefs must also read `BIDDEED_SSOT.md` (repo root) — the architecture single
source of truth: what runs where, what is a product surface vs. dispatch
infrastructure, and what is protected. `CC_META_PROMPT.md` is the process
contract; `BIDDEED_SSOT.md` is the architecture contract. Read both before
starting any dispatched task.

Any change to infrastructure (a new box, service, tunnel, deploy target, or
the removal of one) MUST update `BIDDEED_SSOT.md` in the same commit that
makes the change. A brief that changes infrastructure without updating the
SSOT is incomplete, even if its stated DoD otherwise passes.
