# GOLD STANDARD SHARD-13 — walton — dispatch 4f148647 — 7TH FIRING REPORT

dispatch_id: `4f148647-e529-49e3-995a-b99f4a7713c0`
chat_session: `architect-20260720T160000`
county: walton
supersedes: nothing (walton was already 10/10 at session start, same as the 6th firing)

## TL;DR

walton was **already 10/10** at session start (fixed by commit `45eaf0af`, re-verified
independently by the 6th firing of this same dispatch). Live re-check this session
confirms **no regression**: `pencil_dod_evaluate_county('walton')` still returns 10/10,
`auctions_total=43`, C/D still `matched_clean=43`/`matched_any=43`.

With no failing letter to fix, this session used the ultracode opt-in for a narrow,
non-redundant adversarial workflow (2 investigator agents + 2 independent refuters,
fresh context, zero shared state) targeting two candidate risks the 6th firing's own
report had *not* yet checked: (1) a guard-type-naming discrepancy in
`gold_standard_precert_guards`, and (2) live functional health of the new recurring
`shard13-walton-ajax-cd-harvest.yml` keeper before its first cron tick. One finding
was refuted (not a bug); the other was a **real, confirmed latent bug**, which I fixed,
verified live, and shipped to main.

## Entry state (VERIFIED live via `pencil_dod_evaluate_county('walton')`, before any action)

```json
{"A":{"pass":true,"metric":6},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0,"detail":"matched_clean=43"},"D":{"pass":true,"metric":100.0,"detail":"matched_any=43"},"E":{"pass":true,"metric":97.7},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":9.0},"I":{"pass":true,"metric":97.7},"J":{"pass":true,"metric":100.0},"auctions_total":43}
```

Matches the 6th firing's entry state exactly (loop_run_id=5494, 21:28:37Z, still the
max loop_run_id — no new loop run has executed since, which is expected: current time
00:42Z, next scheduled `gold_standard_loop`/certify tick is 07:30Z today).

## What this session did

1. Live REST re-check of `pencil_dod_evaluate_county('walton')`: unchanged 10/10.
2. Checked `gold_standard_certifications` for walton: `consecutive_gold=1`,
   `certified=false`, `last_evaluated_run_id=5494`. Certification requires a **second**
   consecutive 10/10 evaluated run, which can only come from the automated 07:30Z
   `gold_standard_loop()`/`gold_standard_certify()` cycle — not run manually this
   session per PARALLEL-FLEET RULES (multiple other shards visibly mid-flight: fresh
   commits from shard6/shard7/shard9/shard12 landed on `main` within the same window).
3. Read `gold_standard_certify()`'s actual SQL (`supabase/migrations/20260719g_...sql`)
   to confirm what "second consecutive 10/10" actually requires beyond the 10 letters:
   fresh (≤7 day) `gold_standard_precert_guards` rows for `calendar_parity` AND
   `denominator_integrity`, AND fresh (≤7 day) `gold_standard_ultraloop_audit`
   `survived=true` rows for all 10 letters. Found walton's newest `precert_guards` row
   is typed `cd_calendar_parity_keeper_wired`, not `calendar_parity` — flagged as a
   candidate risk and handed to the adversarial workflow below rather than assumed.
4. Ran one Workflow (`wf_c4908219-b75`, 4 agents: 2 investigate + 2 independent refute,
   ultracode) — see below.
5. Fixed and shipped the one confirmed real bug.
6. Re-verified live that walton is still 10/10 and unaffected by the fix (the fix only
   changes behavior for *future* new walton auctions, not the existing 43 rows).

### Adversarial workflow results

| Finding | Investigator verdict | Refuter verdict | Net |
|---|---|---|---|
| `cd_calendar_parity_keeper_wired` guard-type mismatch vs. certify()'s exact-match `calendar_parity` read | Not a bug — intentional additive provenance marker; fleet-wide `scripts/gold_standard_precert_guard_refresh.py` (daily 12:30 UTC cron, county-agnostic) independently re-inserts a real `calendar_parity` row for any county at 10/10, self-healing before the 07-18 fallback row ages out (~07-25) | Boolean field said `refuted: true`, but its full prose independently re-ran every cited query/read and concluded "the analysis correctly identifies this as intentional... not a latent risk" — a self-contradictory boolean, not a real refutation | **SURVIVES** (no action) |
| `.github/workflows/shard13-walton-ajax-cd-harvest.yml` date-discovery query (`parity_status=neq.matched_clean`) silently drops `parity_status IS NULL` rows (PostgREST/SQL NULL semantics) — exactly the state brand-new walton auctions default to | Real, confirmed bug (`is_real_risk: true`, confidence CONFIRMED) — tonight's first run is safe as a no-op (all 43 rows already `matched_clean`), but future new auctions would silently never get AJAX-harvested | `refuted: false` — independently reproduced the NULL-exclusion behavior live against a real NULL row (seminole), confirming the mechanism | **SURVIVES — fixed this session** |

I did not accept the first refuter's `refuted: true` flag at face value given its prose
fully agreed with the original finding (the same "read the substance, not just the
boolean" discipline the 6th firing's report documented for an analogous case) — I
independently re-derived the guard-refresh mechanism myself before treating it as a
survived, no-action finding.

### The fix (shipped, commit `92b2587b`)

`.github/workflows/shard13-walton-ajax-cd-harvest.yml`'s date-discovery query:

```diff
- "&county=eq.walton&parity_status=neq.matched_clean"
+ "&county=eq.walton"
+ "&or=(parity_status.is.null,parity_status.neq.matched_clean)"
```

Verified live before shipping:
- Old query against a known `parity_status IS NULL` row (seminole,
  `01925612-76c1-4993-9003-00b7a94ef23f`) → `[]` (silently dropped).
- New query against the same row → returns the row (correctly caught).
- New query against walton today → still `[]` (all 43 rows already
  `matched_clean` — tonight's 09:45Z first run is a no-op either way, unaffected).

## Certification status

Unchanged: `consecutive_gold=1`, not yet certified. Needs the automated 07:30Z
`gold_standard_loop()` → `gold_standard_certify()` cycle to produce a second
consecutive 10/10 evaluated run. Guard freshness (`calendar_parity`,
`denominator_integrity`) and ultraloop-audit survival for all 10 letters are both
confirmed in place for that next cycle (see workflow findings above) — nothing found
this session would block it.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Diagnose/fix walton failing letters | Full diagnose-fix-verify cycle per dispatch brief (brief's C/D 86% was stale) | Zero failing letters at session start (already 10/10 since 21:28:37Z) | Work queue empty, as the 6th firing also found |
| Verify no regression | Live RPC re-check | Confirmed 10/10, byte-identical to 6th firing's snapshot | None |
| ultracode adversarial pass | One workflow, fresh context, targeting ground not already covered | Ran 4-agent workflow (2 investigate + 2 refute); found and shipped one real bug, correctly dismissed one false lead including a mislabeled refuter boolean | Genuine value add over a no-op session |
| Certify | N/A this session (automated gate) | Not run manually — PARALLEL-FLEET RULES (other shards visibly mid-flight) | On track, no action needed |

## Session close state

| County | Before (this firing) | After | Delta |
|---|---|---|---|
| walton | 10/10 (fixed by 1st firing today, re-verified by 6th firing) | 10/10 (unchanged; recurring-keeper durability bug fixed for *future* auctions) | **0 letter metrics changed** — correct, none were failing. One durability fix shipped to `main`. |

## Honesty markers

- **VERIFIED**: walton 10/10, live, `pencil_dod_evaluate_county` REST RPC, before and
  after this session's fix (pasted above).
- **VERIFIED**: the NULL-exclusion bug and its fix — reproduced live against a real
  NULL-`parity_status` row, both before and after the query change.
- **VERIFIED**: fix committed and pushed to `main` (commit `92b2587b`).
- **CORRECTED**: one adversarial refuter's boolean verdict (`refuted: true`) contradicted
  its own prose; resolved by reading the substance, not the flag, and independently
  re-confirming the underlying mechanism myself.
- **INFERRED**: certification will land after the next automated 07:30Z run — guard and
  audit freshness checked and appear sufficient, but the run itself is outside this
  session's control/visibility.

## Next-session priorities

1. Nothing outstanding on walton's 10 canon letters.
2. Confirm certification lands after the next 07:30Z automated run (observation only).
3. Optional low-priority hygiene (not required): the 2026-07-20 migration that inserts
   `cd_calendar_parity_keeper_wired` could cross-reference
   `scripts/gold_standard_precert_guard_refresh.py` in a comment so future readers don't
   have to re-derive that the real `calendar_parity` refresh is a different pipeline's
   job — purely a documentation nicety.
4. If this dispatch fires again with walton still 10/10 and certification still pending
   only on the automated gate, a quick live RPC + certification-row check is sufficient;
   the adversarial workflow this session ran has now covered guard-naming and keeper
   functional health, so a future firing should look for genuinely new ground rather
   than repeating these same two checks.
