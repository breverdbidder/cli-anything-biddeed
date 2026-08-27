# CC DISPATCH CONTRACT (META-PROMPT v1)

**Status:** canonical. Every `/loop` brief inherits this file.
**Owner:** Ariel Shapira. **Authored:** 2026-07-20.
**Where it lives:** commit to repo root as `CC_META_PROMPT.md` and reference by line
one of every issue body: `Operating contract: CC_META_PROMPT.md. Read it first.`

---

## CANON — read first

Positioning, avatars, and compliance posture for Winner Data / BidDeed /
ZoneWise are canon, not something to re-derive from a log or prior chat.
Full canon: [`docs/canon/`](docs/canon/README.md) (mirrored in
`everest-battle-cards/canon/`, recorded live in
`public.unified_context.winnerdata_canon_v1`). **Canon overrides any log,
memory line, or prior chat.**

CANON 01 summary (Winner Data):
- **What it is:** FL property-data/intelligence PLATFORM LAYER, 10.5M-parcel moat, supplies all leads for biddeed.ai + zonewise.ai + Protection Partners.
- **What it is NOT:** not an auction-lead vendor, not a mover-lead vendor, not a distressed-property engine.
- **Buyer avatar:** businesses buying resolved property signals (insurance agencies, movers, contractors, investors/small developers) — self-serve small B2B/B2C that ATTOM/Cotality won't onboard.
- **Subject avatar:** MLS active/pending sellers (non-distressed) and auction winners — never contacted.
- **Compliance one-liner:** B2B data sales only — no homeowner contact, no foreclosure/mortgage-relief marketing, no outcome-tied compensation (see [`docs/canon/02_COMPLIANCE_DOCTRINE.md`](docs/canon/02_COMPLIANCE_DOCTRINE.md)).

---

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

### 3.6 FF enrichment: web-search cross-check for principals/registered agents
Permanent pipeline step, added 2026-08-27 (issue #19533). Applies to every FF
batch going forward, not just the batch that motivated it.

**Trigger condition:** after the Sunbiz + Tracerfy + ZoneWise cascade has
already run for a case, run a general web search on `"<principal name>
<related entity or city>"` only if BOTH hold:
1. The case still has an unresolved `business_phone`, `business_website`, or
   `business_email`.
2. The resolved principal or registered agent is a named individual (not
   just an LLC with no natural person attached — nothing to search on
   otherwise).

`scripts/ff_nine_portfolio_enrichment.py::web_search_cross_check_eligible(row)`
is the code-side eligibility check — call it after identity resolution to
decide whether this step applies to a case. The search itself stays a
manual/agent step (matching the right entity, judging source independence,
rejecting aggregators, etc. is a judgment call, not something to automate
into a deterministic batch script).

**Acceptance bar (unchanged from the existing mission rules):** two
independent, mutually corroborating sources minimum before writing anything
as `VERIFIED`. One source is a candidate/unconfirmed — do not write it as
verified. Zero sources leaves the field blank. Enforced in code by
`ff_nine_portfolio_enrichment.py::validate_web_search_cross_check()` /
`build_web_search_evidence_entry()` — both raise rather than let a
single-source result through.

**Related-entity labeling:** if the found phone/email/website belongs to a
related entity (a title company, a family business, etc.) rather than the
target entity itself, the `evidence_ledger` entry MUST carry an explicit
`note` field stating the relationship (e.g. "President/CEO of Majesty Title
Services, a related entity Cassidy also controls") — never present a
related-entity contact as if it were the target LLC's own.
`build_web_search_evidence_entry()` enforces this: it raises if
`is_related_entity=True` and no `relationship_note` is given.
`scripts/render_ff_9buyer_20260827.py::_related_entity_contact_note()`
reads this note back out by shape (any evidence_ledger value with both
`note` and `fields_supported`, not a hardcoded key name) and folds it into
the contact card's source citation so a client PDF never implies a related
entity's contact is the buyer's own.

**Never do:** use this step to search for a private individual's home
address, personal cell, or personal email beyond what a business/
professional bio voluntarily publishes (news releases, sponsor bios,
official org pages). Never use people-search/skip-trace aggregator sites
as a source for this step — those stay in the Tracerfy-only lane. If the
only available info is a home address from an aggregator, leave it blank
rather than write it from an unverified aggregator.

**Reference implementation:** case `2025 CA 000894` (Florida Investors
Capital LLC) — `business_phone`/`business_website` resolved to Majesty
Title Services, LLC (Vincent J. Cassidy's related company), sourced from a
PRWeb press release + a business-wise.org sponsor bio, with the relationship
explicitly noted in `evidence_ledger.cassidy_business_contact.note`.

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

## SESSION DISCIPLINE — CACHE INTEGRITY

- **Never switch models mid-session.** Model is set at dispatch (see issue brief).
  Switching triggers a full prompt-cache bust: the next turn is billed at the
  cache-write rate instead of the cache-read rate — roughly a 20x cost spike.
- **Never change effort_level mid-session**, for the same reason.
- **Set MCP servers in `CLAUDE.md` / `.mcp.json` before session start**, not
  mid-flight — changing the tool schema block mid-session also busts the cache.
- **At session end, report cache metrics** in the `agent_ops_log` evidence
  field: `cache_read=<n> cache_write=<n> hit_pct=<n>%`. See SESSION TEARDOWN
  below for the exact call.

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

---

## SESSION TEARDOWN — COST TELEMETRY (MANDATORY)

At the end of EVERY session — success, failure, or timeout — before closing, run this SQL via Supabase MCP:

```sql
SELECT public.log_cc_session_cost(
  p_issue        := <ISSUE_NUMBER>,           -- this session's GitHub issue number
  p_run_id       := '<GHA_RUN_ID>',           -- GitHub Actions run ID if known, else NULL
  p_shard_label  := '<TASK_LABEL>',           -- copy from /loop line verbatim
  p_model        := '<MODEL_USED>',           -- e.g. 'claude-sonnet-4-6' or 'claude-opus-4-7'
  p_effort_level := '<EFFORT>',              -- 'low' | 'medium' | 'high'
  p_input_tokens := <INPUT_TOKENS>,           -- from session usage stats
  p_output_tokens:= <OUTPUT_TOKENS>,          -- from session usage stats
  p_cache_read   := <CACHE_READ_TOKENS>,      -- from session usage stats, 0 if unknown
  p_cache_write  := <CACHE_WRITE_TOKENS>,     -- from session usage stats, 0 if unknown
  p_started_at   := '<SESSION_START_ISO>',    -- ISO8601 timestamp when session began
  p_ended_at     := now(),                    -- call at actual end time
  p_conclusion   := '<success|failure|timeout>',
  p_dod_met      := <true|false|NULL>,        -- was DoD SQL satisfied?
  p_raw_usage    := '<USAGE_JSON>'::jsonb     -- full usage blob if available, else NULL
);
```

### How to get token counts
- Check the Claude Code session summary at end of run (CC prints usage stats)
- If usage stats unavailable, use 0 for all token fields — the row still lands
- Model: check `claude --version` output or the model field in session metadata

### FINAL STEP — cache hit rate (mandatory before session ends)
Run `/cost` or read the `current_usage` object for token counts, then call:

```sql
SELECT public.record_session_cache_metrics(
  p_run_id       => '<GHA_RUN_ID from env>',
  p_issue        => <issue_number>,
  p_model        => '<model string>',
  p_cache_read   => <cache_read_input_tokens>,
  p_cache_write  => <cache_creation_input_tokens>,
  p_input        => <input_tokens>,
  p_output       => <output_tokens>
);
```

This is separate from `log_cc_session_cost` above — it writes a dedicated
`cache_hit_pct` row to `agent_ops_log` (warns at <30% hit rate) instead of
folding cache figures into a free-text evidence string. Run both calls.

### Why this matters
- $767 was burned in July with zero visibility into which sessions cost what
- This is the only way to get per-session cost, model, and DoD data
- Budget alert fires at $140/month via Telegram — requires this data

### Non-goals
- Do NOT skip this step even if session was a hard failure
- Do NOT guess token counts — use 0 if unavailable, not an estimate
- This call is idempotent-safe — duplicate calls create duplicate rows (acceptable)

---

## AUTO-LEARNINGS (do not hand-edit below this line)
<!-- skill-meta-updater: last updated 2026-08-03 -->
[2026-08-03] PATTERN: Wrong pooler region (us-east-1 vs us-west-2) caused 4.5mo silent skills_catalog failure.
[2026-08-03] PATTERN: Bare except:Exception swallowed upsert failures; job reported success with 0 rows written.
[2026-08-03] PATTERN: Hardcoded Telegram success strings in YAML lie regardless of outcome — compute from real output.
[2026-08-03] PATTERN: `|| echo may-exist` masked a real DB connection failure — never swallow errors optimistically.
[2026-08-03] PATTERN: Supabase Management API 1010s without explicit User-Agent header — always set one.
[2026-08-03] PATTERN: Expired Hetzner Claude OAuth silently zeroed autoloop 2+ months; grep logs for auth-failure text.
[2026-08-03] PATTERN: Invalid workflow YAML blocks workflow_dispatch registration (422), not just the job run itself.
[2026-08-03] PATTERN: Multi-line bash MSG= in `run: |` can dedent and break YAML scalar parsing — validate with PyYAML.
[2026-08-03] PATTERN: Cross-repo GH_PAT failed on one checkout, working elsewhere — check repo scope, not rotation age.
[2026-08-03] PATTERN: autoloop.yml schedule trigger ignores skill input, defaults to 1 of 16 skills nightly.
[2026-08-03] PATTERN: `disabled_manually` workflow state persists silently for months — check `gh api workflows/<id>`.
[2026-08-03] PATTERN: A fixed pooler-region bug recurred in 9 other workflows — grep repo-wide before closing bug class.