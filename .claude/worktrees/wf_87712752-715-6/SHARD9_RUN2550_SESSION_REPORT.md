# SHARD-9 Session Report — run 2550

dispatch_id: `cc40d3bf-95ed-4508-8e0d-6e1c29dd101c`
session: `architect-20260703T080000`
shard counties: citrus, lafayette, suwannee, manatee
ultraloop_mode: **native** (Workflow tool, fan-out fix + independent adversarial verify per county)

## Result summary

| County | Before (A B C D E F G H I J) | After | Change |
|---|---|---|---|
| citrus | 8/10 (C,D fail) | 8/10 (C,D fail) | C 31.0%→31.6% (matched_clean 54→55). D unchanged 35.1%. Real but tiny gain — see structural note below. |
| lafayette | 8/10 (C,D fail) | **10/10 — ALL PASS** | C 0.0%→100.0%, D 0.0%→100.0% |
| suwannee | 8/10 (C,D fail) | **10/10 — ALL PASS** | C 50.0%→100.0%, D 50.0%→100.0% |
| manatee | 6/10 (A,C,D,G fail) | 6/10 (A,C,D,G fail) | C/D 40.6%→26.1% — investigated, root-caused, NOT a bug (see below) |

## What shipped

Ran the already-proven `public.refresh_parity_tier1_outcomes(p_county)` canonical parity matcher
(same lever used earlier today by shard-5/shard-6 for bradford/palm_beach/monroe/hendry/miami_dade/
st_lucie) for all four shard counties, via a Workflow-orchestrated ULTRALOOP: one fixer agent per
county ran the RPC and captured before/after `pencil_dod_evaluate_county` JSON across all 10
letters; one independent refuter agent per county re-queried the live DB itself (not trusting the
fixer's numbers) and checked for regressions before the claim was allowed to count. 7 claims logged
to `gold_standard_ultraloop_audit` (dispatch_id above).

Full before/after JSON, migration file, and audit rows: `supabase/migrations/20260703_shard9_citrus_lafayette_suwannee_manatee_cd_parity.sql`.

**lafayette and suwannee are now 10/10** — certification lands automatically after a second
consecutive 10/10 daily 07:30Z loop run per canon; not something this session triggers manually.

## citrus — real but structural

matched_clean moved 54→55 (one new case-pass match). matched_any unchanged at 61. citrus has 174
total auctions, 114 of them closed-like (completed/cancelled/redeemed), but only 61 have ANY
independent outcome record to match against today. This is a coverage gap, not a matcher bug —
closing it needs more `foreclosure_outcomes`/`tax_deed_outcomes` rows for citrus, not another run
of the same function.

## manatee — regression caught, investigated, and NOT force-fixed

**This is the important finding of the session.** Running the matcher for manatee dropped
matched_clean 28→18 (C/D 40.6%→26.1%) — confirmed independently by the refuter agent, not stale
data. I treated this as a P0 (per HARD GUARDRAILS / SHIP GATE, a live production regression on a
criterion that feeds `bid_decisions` cannot be left in place) and investigated before accepting or
force-reverting it:

- A **concurrent shard-6 session** fixed a case-sensitivity bug in `refresh_parity_tier1_outcomes`
  earlier the same day. That fix tightened matching (the shard-6 migration itself describes it as
  "strictly monotonic, never regresses" — true in general, but manatee's pre-existing matched_clean
  rows on **cancelled** auctions were never reachable by a genuine join in the first place).
- Direct query: `foreclosure_outcomes` has exactly 5 rows for manatee, **all `outcome='sold'`**,
  matching the 5 completed auctions 1:1. `tax_deed_outcomes` has **zero** manatee rows. There is no
  independent record of any manatee auction being cancelled — so none of the 16 cancelled manatee
  auctions could ever have been genuinely tier1-verified.
- Conclusion: the pre-session 40.6% baseline was itself a ghost-success artifact (tier1-prefixed
  `matched_clean` labels on cancelled rows that could not have come from a real outcomes join) —
  the same failure class other shards purged today for bradford/columbia/franklin/escambia.
- I attempted one restorative fix: re-applied the pre-authorized (2026-06-19) clerk-supplementary
  rule — "rows sourced directly from the official realforeclose platform are already clerk-verified"
  — to the 14 newly-null cancelled rows. Verified live that this **did not move the metric at all**,
  because the evaluator was tightened on 2026-07-02 to additionally require
  `parity_source LIKE 'tier1%'`, which the clerk-supplementary label never satisfies. Since the
  label couldn't move the metric and doesn't represent genuine independent verification, I
  **reverted it** rather than leave a cosmetic label on production data. BLANK > WRONG.

**26.1% is the current honest, verified ceiling for manatee C/D.** Closing it needs either real
independent cancelled-auction outcome records (none currently exist for manatee) or an
architecture decision — flagged for AI Architect review, not decided unilaterally here — on
whether cancelled auctions with zero available independent record should be excluded from the C/D
denominator the way redeemed/other exclusions already work elsewhere in canon.

## manatee A — blocked, not fabricated

`fc=69 td=0` (zero tax-deed auctions in the non-PropertyOnion-contaminated set). Diagnosing or
fixing this requires `pipeline.counties` (lane platform config), which lives in a schema PostgREST
does not expose in this sandbox. No `supabase` CLI was installed, and direct `psql` to the pooler
with `SUPABASE_DB_PASSWORD` returned a password-auth failure. No `exec()`/raw-SQL RPC is available
either. Did not attempt a workaround that would require guessing at tax-deed lane configuration —
flagging as a genuine environment blocker for a session with working CLI/psql access.

manatee G (density 90.4%, 5 districts short per the fleet-wide zoning-hitlist pattern) was not
touched this session — deprioritized behind the manatee A blocker and the C/D regression
investigation given time spent.

## Verification evidence (live, pasted verbatim)

```
citrus:    {"A":{"metric":30,"pass":true},"B":{"metric":100.0,"pass":true},"C":{"metric":31.6,"pass":false},"D":{"metric":35.1,"pass":false},"E":{"metric":100.0,"pass":true},"F":{"metric":100.0,"pass":true},"G":{"metric":100.0,"pass":true},"H":{"metric":0.1,"pass":true},"I":{"metric":96.6,"pass":true},"J":{"metric":100.0,"pass":true}}
lafayette: {"A":{"metric":1,"pass":true},"B":{"metric":100.0,"pass":true},"C":{"metric":100.0,"pass":true},"D":{"metric":100.0,"pass":true},"E":{"metric":100.0,"pass":true},"F":{"metric":100.0,"pass":true},"G":{"metric":100.0,"pass":true},"H":{"metric":32.1,"pass":true},"I":{"metric":100.0,"pass":true},"J":{"metric":100.0,"pass":true}}
suwannee:  {"A":{"metric":2,"pass":true},"B":{"metric":100.0,"pass":true},"C":{"metric":100.0,"pass":true},"D":{"metric":100.0,"pass":true},"E":{"metric":100.0,"pass":true},"F":{"metric":100.0,"pass":true},"G":{"metric":100.0,"pass":true},"H":{"metric":0.1,"pass":true},"I":{"metric":100.0,"pass":true},"J":{"metric":100.0,"pass":true}}
manatee:   {"A":{"metric":0,"pass":false},"B":{"metric":100.0,"pass":true},"C":{"metric":26.1,"pass":false},"D":{"metric":26.1,"pass":false},"E":{"metric":95.7,"pass":true},"F":{"metric":100.0,"pass":true},"G":{"metric":90.4,"pass":false},"H":{"metric":0.1,"pass":true},"I":{"metric":95.7,"pass":true},"J":{"metric":100.0,"pass":true}}
```

Captured 2026-07-03 via `SELECT public.pencil_dod_evaluate_county('<county>')` per PARALLEL-FLEET
RULES (skipped `gold_standard_loop()`/`gold_standard_certify()` — multiple other shard sessions
were confirmed mid-flight today via the migrations directory, so the loop was not run per the
"otherwise skip loop" instruction).

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| citrus C/D | fix to PASS | real +0.6pt gain, still FAIL | Structural coverage gap, not a matcher problem — flagged, not force-fixed |
| lafayette C/D | fix to PASS | **PASS, 10/10** | None |
| suwannee C/D | fix to PASS | **PASS, 10/10** | None |
| manatee C/D | fix to PASS | investigated a regression instead, ended FAIL at a lower (but honest) number | Caught a live regression mid-session, root-caused it to a ghost-success artifact rather than a bug I introduced, attempted and reverted one restorative fix after confirming it didn't help |
| manatee A | stretch goal | blocked | `pipeline` schema not reachable from this sandbox |

## Deferred / next session

- manatee A: needs `pipeline.counties` access (CLI/psql) to diagnose tax-deed lane config.
- manatee C/D: needs an AI Architect decision on cancelled-auction denominator treatment, or real
  independent cancelled-outcome data for manatee.
- manatee G: density gap (90.4%→95%), not started this session.
- citrus C/D: needs broader independent outcome coverage, not another matcher invocation.
