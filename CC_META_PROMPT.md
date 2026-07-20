# CC DISPATCH CONTRACT (META-PROMPT v1)

**Status:** canonical. Every `/loop` brief inherits this file.
**Owner:** Ariel Shapira. **Authored:** 2026-07-20.
**Where it lives:** commit to repo root as `CC_META_PROMPT.md` and reference by line
one of every issue body: `Operating contract: CC_META_PROMPT.md. Read it first.`

This file exists because the same four failure classes keep recurring:
terminal state assigned on stale evidence, absence of evidence read as failure,
"done" claimed without observed output, and burst dispatch that kills the runner.
Everything below is a rule with a scar behind it.

---

## 0. PRIME DIRECTIVE

**VERIFIED means output was observed. It does not mean code was written.**

If you did not see the output, the status is `UNTESTED`.
If you saw output that contradicts the goal, the status is `BLOCKED`.
If you completed part and could not complete the rest, the status is `PARTIAL`.
There is no fourth option, and "it should work" is not one of them.

A brief that comes back green when it is not green costs more than a brief that
fails loudly, because it poisons every downstream decision made on top of it.

---

## 1. BEFORE YOU START

1. **Read every comment on the issue.** The brief may have been revised after it
   was opened. Comments override the body where they conflict.
2. **Re-derive the numbers.** Any count in the brief (row counts, county counts,
   status censuses) is a snapshot from when it was written and is probably stale.
   Query live and report what you actually found. If your live number differs
   from the brief's by more than ~10%, say so before proceeding.
3. **Inspect before you assume.** Paste the current source of any function you are
   about to patch and the current schema of any table you are about to alter.
   Never write a patch against a remembered signature.
4. **Confirm the scope lock.** Re-read the non-goals. If completing the goal
   appears to require touching something in the non-goals list, stop and report
   `BLOCKED` — do not decide the non-goal was probably fine.

---

## 2. EVIDENCE RULES

### 2.1 Absence of evidence is not evidence of failure
This is the single most expensive bug class in this system. It has cost
certifications, blocked completed work permanently, and mass-revoked counties
that were passing live checks.

- "Not evaluated" is **not** "evaluated and failed."
- "Query returned no rows" is **not** "the thing does not exist" — prove which.
- "Endpoint timed out" is **not** "endpoint is down."
- "I could not read it" is **not** "it is empty."

Whenever you are about to write a terminal or negative state (revoked, blocked,
failed, dead, missing), first prove you had evidence to judge on. If you did not,
leave the state untouched and log why.

### 2.2 Never trust a scoreboard
Aggregate/rollup tables and summary views drift from reality. Cross-check against
the live source of truth (RPC, base table, real query) before using any summary
figure as evidence. `gold_standard_scoreboard` is known-untrustworthy — never
cite it as proof of anything.

### 2.3 The DoD query itself may be wrong
Briefs are written by a fallible author. If a verification query in the brief
errors or checks the wrong object, **do not silently substitute your own and
report green.** Run the corrected query, paste both, and log a `PARTIAL` row
noting the brief's bug. This has already happened once (`pg_tables.forcerowsecurity`
does not exist — it is `pg_class.relforcerowsecurity`) and catching it was correct
behavior worth repeating.

### 2.4 Errored is not failed
When evaluating stored SQL or external checks in bulk, keep four buckets, never
two: `TRUE`, `FALSE`, `ERRORED`, `SKIPPED`. Collapsing `ERRORED` into `FALSE`
hides broken checks as legitimate failures forever.

---

## 3. WRITE DISCIPLINE

### 3.1 Dry run before any bulk or destructive write
If a task will modify more than ~20 rows, change a terminal state, or touch a
live loop, you run it read-only first and post the projected result as an issue
comment **before** writing. Include counts per bucket and a sample of ~10 affected
rows with the evidence that justified each.

### 3.2 Idempotency is proven, not asserted
Any change landing in a cron-driven loop must be safe to run repeatedly. Prove it:
run twice, show the second run is a no-op. "It uses `if not exists`" is not proof.

### 3.3 Bounded batches
Anything sweeping a backlog gets a per-run cap. An unbounded first sweep inside a
`*/5` or `*/20` job will overrun the tick and stack invocations.

### 3.4 Additive by default
Prefer new columns/tables over altering existing ones. Never drop, never change a
type, never rewrite a canonical read view without an explicit approval line in the
brief naming that object. `gold_standard_*`, `insights`, `taxi_meter_*`, and
`multi_county_auctions` are protected — read freely, write only when named.

### 3.5 Rollback path stated before you apply
Know the undo before you do the do. If a step fails midway, roll back, then report
`BLOCKED` with the failing output. Do not leave a half-applied migration and
describe it as partial success.

---

## 4. CREDENTIALS AND CONNECTIVITY

Known-good fallback ladder for database work:

1. `supabase migration` / psql via pooler (transaction 6543, then session 5432)
2. Direct db host
3. **Management API** — `https://api.supabase.com/v1/projects/{ref}/database/query`
   with `SUPABASE_ACCESS_TOKEN` (sbp_ token). This is a sanctioned no-HITL path.

Rules:
- **Never echo a secret.** Build request payloads via file, never print the curl.
- If a credential fails, say exactly which one and on which endpoints. A stale
  credential silently routed around is a landmine for every workflow that lacks
  your fallback. `SUPABASE_DB_PASSWORD` was found stale on all three DB endpoints
  on 2026-07-19 — if it fails again, report it as a finding, not a footnote.
- **Never rotate a credential yourself.** Surface it. Auth changes are Ariel-only.

---

## 5. CONCURRENCY AND RUNNER HEALTH

The CC runner is a shared, rate-limited resource on a single OAuth identity.
Burst dispatch takes down every concurrent brief, including ones that would
have succeeded.

- **Do not self re-dispatch.** If your run fails, report; do not fire another.
- **Do not dispatch sibling work.** Completing a brief never includes enqueuing
  more briefs unless the brief says so explicitly.
- If you detect other CC runs in flight, prefer serial execution and say so.
- If the CC step fails fast (<2 min) with an auth or quota signature, report
  `BLOCKED: runner quota/auth` immediately and stop. Retrying burns the budget
  that the recovery needs.

---

## 6. REPORTING FORMAT

Post one issue comment. It must contain, in this order:

1. **Headline:** `TASK — VERIFIED | PARTIAL | BLOCKED | UNTESTED`
2. **What was actually run** — commands, endpoints, connection method used.
3. **Observed output** — pasted verbatim in fenced blocks, per DoD item.
   Every DoD checkbox gets its evidence or an explicit "not done, because."
4. **Negative tests** — the things that were supposed to fail, and their errors.
   A brief with no negative test result is not verified.
5. **Deviations from spec** — every one, however minor, with the reason.
6. **Findings** — anything you noticed that was not the task. Stale credentials,
   suspicious counts, dead workflows, contradictions in the data. These are
   often worth more than the task itself.
7. **Commit SHA** and branch.

Then log rows to `public.agent_ops_log`:
`dispatch_id`, `task`, `status` (VERIFIED|BLOCKED|PARTIAL|SKIPPED),
`evidence` (observed output or root cause), `severity` (info|warn|blocker).
Ops outcomes only — never write auction or anomaly data there; that is
`public.insights`.

---

## 7. WHEN TO STOP

Stop and report `BLOCKED` rather than improvising when:

- A dry run produces a result set you cannot fully explain.
- Completing the goal requires touching a non-goal.
- A credential, permission, or schema is not what the brief assumed.
- The change would revoke, delete, or terminally mark records on evidence you
  did not directly observe.
- You have retried a transient failure 3 times.

Three honest `BLOCKED` reports are worth more than one confident green that
turns out to be false. Escalation format:

`BLOCKED: [issue]. Tried: [attempts]. Root cause: [finding]. Recommend: [fix].`

---

## 8. BRIEF TEMPLATE

Every issue body should follow this shape:

```
Operating contract: CC_META_PROMPT.md. Read it first.
READ ALL COMMENTS ON THIS ISSUE BEFORE STARTING.

/loop
/goal <one paragraph: what is broken, what "fixed" looks like, why it matters>

## Context / live numbers to re-derive
## Required behavior          (numbered, each independently testable)
## Order of work              (inspect → dry run → checkpoint → apply → prove)
## Explicit non-goals         (the scope lock — what must NOT be touched)
## Definition of Done         (checkboxes; each demands observed output;
                               MUST include at least one negative test)
## Protocol                   (Honesty Protocol V3; rollback; where to log)
```

A brief missing the non-goals section or the negative test is an incomplete
brief. Ask for it rather than guessing at the boundary.