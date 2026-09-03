# `.factory/gtm/STOP` semantics

This document specifies the stop-button mechanism referenced in
`docs/gtm/META.md` §5 ("Stop button: `.factory/gtm/STOP` + label
`factory:halt` on control issue (fails closed) + `spi_gates
gtm_factory_halt`"). There are three independent halt signals; **any one
of them being active is sufficient to halt** (OR, not AND) — this is a
deliberate fail-closed design, not redundancy for its own sake.

## The three signals

1. **File presence: `.factory/gtm/STOP`**
   If this file exists in the repo (on `main`), every GTM workflow
   (`gtm-validate.yml`, `gtm-merge.yml`, and any future builder-dispatch
   workflow) must refuse to do real work and exit non-zero after logging
   why. This is the fastest signal — no network call needed, checked
   straight off the checked-out tree.

2. **Label: `factory:halt` on the pinned control issue**
   The issue titled "CMO FACTORY — control" (see task #7 of this CP, GitHub
   labels as state machine) carries this label when halted. Workflows check
   it via `gh issue view <control-issue> --json labels`.

3. **DB gate: `spi_gates` row `gtm_factory_halt`**
   `public.gtm_watchdog()` (see `factory/gtm/watchdog_sql.sql` and the
   `cmo_factory_watchdog` migration) opens this row when any of its 7
   detectors trips. Workflows check
   `select verified_at is null as open from public.spi_gates where
   gate_key = 'gtm_factory_halt'` — `open = true` (row exists, not yet
   verified/closed) means halted.

## Fails closed

"Fails closed" means: if a workflow **cannot determine** the state of any
of the three signals (network error reading the label, DB unreachable,
`gh` auth failure), it must treat that as **halted**, not as "halt not
found, proceed." The only way to proceed is a **positive, observed**
"not halted" result from all three checks. This mirrors
`CC_META_PROMPT.md` §2.1 ("absence of evidence is not evidence of
[proceeding safely]").

## Who can set each signal

- `.factory/gtm/STOP`: Ariel, or `public.gtm_watchdog()` via a committed PR
  from a workflow with write access (CP0: manual only — no workflow in this
  CP writes this file; that lands with the watchdog's auto-remediation in a
  later CP).
- `factory:halt` label: Ariel, or `public.gtm_watchdog()`'s
  control-issue-comment step (see the `cmo_factory_watchdog` migration —
  it comments on the control issue and, per the DoD in issue #19777, is
  expected to also apply the label once GitHub-API label-write is wired;
  CP0 ships the comment path and the label's existence, not yet the
  watchdog's own label-write call — that is explicitly flagged as
  `[NOT YET]` in `docs/spec/19777.md`).
- `spi_gates.gtm_factory_halt`: only `public.gtm_watchdog()` opens it
  (`SECURITY DEFINER`, no other writer). Only Ariel (or a workflow he
  approves) sets `verified_at` to close it — closing is never automatic.

## Resuming after a halt

Closing all three signals is required before any GTM workflow proceeds:
1. Ariel (or an approved follow-up session) investigates the trip reason
   (`spi_gates.proof` column + the watchdog's control-issue comment).
2. Remove `.factory/gtm/STOP` via a normal PR to `main`.
3. Remove the `factory:halt` label from the control issue.
4. `update public.spi_gates set verified_at = now(), proof = '<resolution
   note>' where gate_key = 'gtm_factory_halt'`.
Partial resumption (2 of 3 signals cleared) still halts — the OR logic
above applies symmetrically to resuming.
