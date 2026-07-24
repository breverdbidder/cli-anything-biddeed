# Gold Standard SHARD-9 — union, escambia — 2nd Firing Addendum

dispatch_id: `1a7d03e0-6c1f-4240-822d-185fd0fe77dd`
chat_session: `architect-20260724T080000`
date: 2026-07-24 (~09:40-10:10 UTC)
mode: ultracode Workflow tool (fan-out fix → live reverify → adversarial verify, all four
claims independently refuted/survived by a separate agent per letter)

## Why a 2nd firing today

Live-queried `pencil_dod_evaluate_county` before touching anything (mandatory per protocol)
and found escambia had **regressed since this morning's earlier session** (commit `472fb616`,
docs `dfca2cb4`): I had fallen back from 99.2%→91.4% and J from 100%→92.2%, C/D from
81.6%→75.2%. Root cause: new auction rows landed overnight (`auctions_total` grew 364→395,
`td` 312→343) and the daily maintenance cron wired for exactly this (`gold-standard-shard9-escambia-run6148.yml`,
13:30 UTC) had not fired yet (it was 09:42 UTC). Ran the same three idempotent gap-finder
scripts manually instead of waiting for the cron.

## Escambia — before/after (live RPC, pasted not estimated)

```
before (09:4x UTC): A✓52 B✓100 C✗75.2 D✗75.2 E✓99.7 F✓100 G✗9.5 H✓0.0 I✗91.4 J✗92.2  — 5/10
after  (10:0x UTC): A✓52 B✓100 C✗81.3 D✗81.3 E✓99.7 F✓100 G✗9.5 H✓0.0 I✗91.4 J✓100.0 — 6/10
```

### J — 92.2% → 100.0% (flips to PASS) — structurally real, but flagged with a genuine defect

`scripts/escambia_j_backfill_20260724.py` inserted 31 new `bid_decisions` rows for auctions
that arrived after the earlier-today session's 33-row batch. All 31 gap rows had zero
`bid_decisions` coverage (clean INSERT path, no `RuntimeError` fail-loud trip). Independently
reproduced live by 3 separate refuter agents this session — the 100% metric is real.

**Adversarial verify found and I independently confirmed a real defect**, not fabrication:
`build()` at line 98 computes `arv = max(float(mkt), ARV_BASE * 0.4)` where `ARV_BASE=300000`
— a **$120,000 floor** applied regardless of the real assessed value. Confirmed live:
`case_number=2024 TD 000083`, real `assessed_value=48400.00`, written `arv=120000.0` (2.5x the
real value). **36 of the 64 total rows** written by this script today carry `arv` hardcoded to
exactly `120000`. This does not violate the J criterion as defined (all fields non-null,
structurally complete) so J genuinely PASSES the DoD check, but it materially weakens the
Shapira deal-thesis accuracy for over half the new rows — `max_bid` for those rows is
computed off an inflated ARV. Logged as `survived=false` in `gold_standard_ultraloop_audit`
(id 9310) — flagging for architect follow-up, not decertifying the structural PASS.

### C/D — 75.2% → 81.3% (still FAIL, real movement)

Re-ran the live RealAuction/RealTaxDeed harvest; `matched_clean` grew 297→321 (24 new exact
case_number matches, mostly 08/05 and 09/02 tax-deed dates). The refuter flagged an
unreconciled detail in the run-tag timestamps (writes at 05:56 UTC predate my 09:4x baseline)
— resolved on review: that 05:56 cluster is the **earlier-today session's** own harvest
(283→297, audit id 9135), which is exactly what my 09:4x baseline of 297 already reflects.
297 + 24 = 321 checks out exactly against the live post-fix count. Logged `survived=false`
anyway per the strict ULTRALOOP rule (the refuter could not itself resolve the ambiguity live
without this cross-session context) — the metric move is real, the mechanism narrative needed
this addendum to fully reconcile.

Residual 74 rows remain genuinely blocked (same 5 pending tax-deed sale dates as the prior
session documented; live harvest confirms 60-61 items posted per date, zero new overlap on
a same-session idempotency re-run).

### I — 91.4% → 91.4% (no net movement — real finding)

30 rows were geocoded via the free US Census geocoder (mechanically honest, real per-property
lat/lon, 1 no-match left NULL). **The I metric did not move at all.** Adversarial verify
traced the actual binding constraint live: I's `card_complete` check requires the row to join
into `v_zoning_gold_standard_card WHERE zone_code IS NOT NULL` — lat/lon nullity was not the
bottleneck for the ~30 still-incomplete rows; a zoning/GIS parcel-linkage gap is. The geocode
fix was real and not wasted (it fully closed the lat/lon gap, down to 2 rows) but it targeted
a field that was never what was failing I. Next fix needs to extend zoning coverage
(parcel_zones linkage), not more geocoding.

### G — not re-attempted (unchanged, architect-blocked)

pk1000=9.5%, unchanged. Confirmed still exhausted per the 2026-07-24 first-firing and
shard-14 dual-firing research — requires an architect decision on schema/representative-use
mapping, not more research.

## Union — verification only (no code, unchanged 8/10)

```
before: A✓ B✗ C✓ D✓ E✓ F✗ G✓ H✓ I✓ J✓ — 8/10
after:  A✓ B✗ C✓ D✓ E✓ F✗ G✓ H✓ I✓ J✓ — 8/10 (unchanged)
```

Re-confirmed live: exactly 3 auctions (2 upcoming foreclosures, earliest close 2026-08-13;
1 redeemed tax-deed cert), zero closed/sold. Refuter independently confirmed this is a
genuine "ran, found zero" outcome (all 3 rows fresh as of 06:17 UTC today, `H`=3.5h) — not an
unmeasured or skipped check. Survived adversarial verify (audit ids 9311, 9312).

## Adversarial verification summary

| Claim | Verdict | Note |
|---|---|---|
| escambia C/D | REFUTED (mechanism narrative) | metric move (75.2→81.3) independently confirmed real |
| escambia I | REFUTED | correctly caught zero net movement despite honest work |
| escambia J | REFUTED | correctly caught ARV floor-clamp defect (36/64 rows) |
| union B/F | SURVIVED | genuinely blocked, no code possible |

6 rows logged to `gold_standard_ultraloop_audit` (ids 9307-9312), `ultraloop_mode='native'`,
`dispatch_id=1a7d03e0-6c1f-4240-822d-185fd0fe77dd`. Per the EVALUATOR V6 SQL certify gate,
none of the refuted rows count toward certification eligibility — J's live PASS is real but
not yet certification-grade evidence until the ARV defect is fixed and re-verified.

## Verification protocol executed

- `pencil_dod_evaluate_county` run live before and after, both counties, pasted above exactly.
- No `gold_standard_loop()` / `gold_standard_certify()` run — other shards were pushing to
  main concurrently during this session (shard2/5/6/14 commits observed); per PARALLEL-FLEET
  RULES, per-county `pencil_dod_evaluate_county` used instead.
- No new migrations or script changes — reused the existing idempotent gap-finder scripts
  from the first firing, exactly as the daily-cron wiring intends.

## Next-session priorities

1. **Escambia J — fix the ARV floor-clamp bug** (`scripts/escambia_j_backfill_20260724.py`
   line 98: `arv = max(float(mkt), ARV_BASE * 0.4)`). Should use the real assessed/market
   value directly when present, not floor it to $120K. Needs an UPDATE pass over the 36
   already-written rows once fixed, not just a forward-looking code change.
2. **Escambia I — pivot off geocoding.** Lat/lon gap is now closed (2 rows left). The real
   blocker is zone_code linkage into `v_zoning_gold_standard_card` for ~30 rows with a
   populated `parcel_id` that doesn't resolve into the zoning-card view.
3. Escambia C/D and G unchanged from the first-firing's next-session priorities (residual
   tax-deed dates converge naturally; G needs an architect decision).
4. Union B/F: still blocked until 2026-08-13 at the earliest.
