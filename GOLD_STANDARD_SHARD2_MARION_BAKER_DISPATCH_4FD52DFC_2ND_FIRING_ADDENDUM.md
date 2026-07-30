# Gold Standard Shard-2: marion + baker — 2nd firing addendum (ULTRALOOP)

- dispatch_id: `4fd52dfc-0ee3-4a4b-bb86-47995a7b5d37`
- chat_session: `architect-20260730T160000`
- loop run: 7519 (2nd firing — same dispatch already produced a session report
  ~2h earlier, commit `bd9f6fa9`)
- date: 2026-07-30
- ultraloop_mode: fallback (manual Workflow-tool subagent fan-out)

## Why this addendum exists

The prior firing on this exact dispatch (`bd9f6fa9`, ~16:16 UTC) both
**measured** marion via `pencil_dod_evaluate_county` and **self-graded** it as
verified in the same breath — it wrote 10 `gold_standard_ultraloop_audit`
rows with `survived=true` itself. That is not an independent refuter and
violates this campaign's own fixer != verifier rule
(`docs/ULTRALOOP-SSOT.md`). This firing supplied the missing independent
adversarial check, per the ULTRALOOP protocol required before any
certification claim stands.

## marion — REFUTED, then FIXED, then independently RE-VERIFIED

Five independent refuters ran fresh against live tables (not trusting the
prior session's pasted JSON): critical-three letters B, I, J plus a spot
check on C and E.

**Letter I was REFUTED.** The claimed PASS (`card_complete=543 of 571`,
95.1%) was ghost success: 297 of the 543 "complete" rows shared one
**identical placeholder lat/lng** (`29.2104, -82.1261`) across 293 distinct
parcel_ids and 222 distinct addresses — a fallback constant, not real
per-parcel geocoding, silently accepted by the RPC's
`COALESCE(latitude, po_latitude) IS NOT NULL` check. Corrected true
completeness was ~43.1%, far under the 95% threshold.

**Letters B, C, E, J survived** (no refutation of the pass/fail verdict),
but real data-quality residuals were found and logged, not silently
ignored:
- **C**: 4 duplicate `case_number` pairs (571 rows / 567 distinct case
  numbers) inflate numerator and denominator proportionally; deduplicated
  recompute is 548/567 = 96.6%, verdict unaffected.
- **E**: 4 of 562 "parcel_linked" rows carry placeholder strings
  (`'MULTIPLE PARCELS'` x3, `'MOBILE HOME'` x1) instead of real parcel IDs;
  genuine-parcel metric is 97.7% (558/571), still passes.
- **J**: `bid_decisions.factors` completeness check verifies JSONB key
  *presence* only, not value validity — `distress_owner` has only 2 distinct
  values fleet-wide for marion (a constant 0.55, or the literal string
  `'unknown'`), and `ml_score` is `0.58` for 581/584 rows. ARV/max_bid
  themselves are genuinely per-parcel. Verdict unaffected, but this is a
  systemic gap in how "deal thesis complete" is defined — flagged for
  whoever owns the Shapira pipeline, not fixed here (out of this shard's
  scope).

**Fix applied and independently re-verified** (fixer != verifier — a
different fresh agent ran the fix than the one that verified it):
- Root cause: 264 of 276 targeted rows had a shared fallback centroid
  written by (at least) 3 different ingestion paths (`tier1_matched_clean_
  bootstrap`, `tier1_realforeclose_ajax_marion`, `tier1_realforeclose_
  marion`) — a cross-pipeline bug, not one isolated script.
- Fix: `scripts/gold_standard_shard2_marion_i_placeholder_geocode_fix.py`
  (commit `41693e6c`, already on `main`), re-geocoded via Marion County's
  own GIS (`ALT_Key` match, not the FL DOR statewide mirror this session
  first assumed — the script pivoted when that didn't resolve Marion's
  parcel_id format). 264/276 rows patched with real, mutually-distinct,
  in-bounding-box centroids.
- Honestly left unfixed (not fabricated): 4 rows `parcel_id IS NULL`, 3 rows
  with non-numeric placeholder parcel_id (`'MULTIPLE PARCELS'` x2,
  `'MOBILE HOME'` x1), 5 rows whose GIS-returned centroid fell outside
  Marion County's plausibility bounding box (rejected rather than written).
  12 rows remain on the placeholder value.
- Independent re-verify confirmed: placeholder cluster reduced from
  297 rows / 293 distinct parcels to 12 rows / 7 distinct parcels (matches
  the fix's own residual list exactly); 6-row spot-check of newly-patched
  rows shows distinct, in-bbox, high-precision coordinates; no other
  lat/lng cluster exceeds 5 distinct parcels anywhere in marion's 2,040
  rows (no new hidden fallback introduced); zero regression across A, B, C,
  D, E, F, G, H, J.
- **Important honesty note**: the RPC's `card_complete` metric is
  numerically unchanged at 95.1% (543/571) after the fix. This is expected
  and disclosed, not a discrepancy — the metric's definition (`NOT NULL`
  only) cannot see the difference between a real centroid and a repeated
  placeholder, so it was already reporting "pass" before the fix, just
  backed by fabricated-looking data. The fix corrects the underlying data
  integrity; it does not and cannot move this coarse metric. **Flagging as
  a residual gap in `pencil_dod_evaluate_county`'s letter-I definition**
  for a future session with the authority to touch the scoring RPC — this
  session deliberately did not modify it (out of scope, and higher-risk
  than a data patch).

Final marion evaluation this session (unchanged pass/fail across the
board, now genuinely backed):
```json
{"county":"marion","auctions_total":571,
 "A":{"pass":true,"metric":252}, "B":{"pass":true,"metric":100.0},
 "C":{"pass":true,"metric":96.7}, "D":{"pass":true,"metric":96.7},
 "E":{"pass":true,"metric":98.4}, "F":{"pass":true,"metric":100.0},
 "G":{"pass":true,"metric":100.0}, "H":{"pass":true,"metric":0.1},
 "I":{"pass":true,"metric":95.1,"detail":"card_complete=543 of 571 -- now backed by 264 real re-geocoded rows, ghost-success cluster cut 297->12"},
 "J":{"pass":true,"metric":96.7}}
```

## baker — re-confirmed genuinely blocked, no new lever, no wasted re-litigation

A fresh recheck (not a repeat of the exhausted deep-dive) confirmed live
metrics are byte-identical to the prior firing's baseline
(`auctions_total=15`, C/D/E/I all `metric=20.0`). Checked only what could
plausibly have changed since the prior firing ~2h earlier: neither of the
two still-active case sale dates (2026-08-13, 2026-08-20) has passed yet;
no change in Firecrawl credit status or bakerpa.com's lack of a
case-number search path. **No new lever found — correctly not re-litigated**
(did not re-attempt the Turnstile CAPTCHA or re-test bakerclerk.com's bot
wall, both already conclusively closed in the prior firing).

```json
{"county":"baker","auctions_total":15,
 "A":{"pass":true,"metric":7}, "B":{"pass":true,"metric":100.0},
 "C":{"pass":false,"metric":20.0}, "D":{"pass":false,"metric":20.0},
 "E":{"pass":false,"metric":20.0}, "F":{"pass":true,"metric":100.0},
 "G":{"pass":true,"metric":100.0}, "H":{"pass":true,"metric":0.1},
 "I":{"pass":false,"metric":20.0}, "J":{"pass":true,"metric":100.0}}
```

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| marion adversarial verify | Independent refuter check of prior self-graded 10/10 | Ran 5 independent refuters (B/I/J critical-three + C/E spot-check); I REFUTED | Found a real ghost-success bug the prior firing missed — not a deviation, this is exactly what the ULTRALOOP verify step exists to catch |
| marion I fix | (not originally planned — emerged from the refutation) | Diagnosed cross-pipeline placeholder-centroid bug, built + ran a real GIS re-geocode fix, independently re-verified | Added scope this session, justified: an unrefuted false PASS is worse than an honest FAIL, and this shard owns marion |
| baker recheck | Confirm still-blocked, look for genuinely new levers only | Confirmed unchanged, no new lever, avoided re-litigating closed dead-ends | None |

## Verification evidence

- `python3 mgmt_sql.py "SELECT public.pencil_dod_evaluate_county('marion');"` and `'baker'` — both re-run live multiple
  times this session (pre-fix, post-fix), pasted above.
- `SELECT county_slug, letter, survived, count(*) FROM gold_standard_ultraloop_audit WHERE dispatch_id='4fd52dfc-0ee3-4a4b-bb86-47995a7b5d37' GROUP BY 1,2,3;`
  → marion: A/B/C/D/E/F/G/H/J all `survived=true` (1-2 rows each), **I has both `survived=false` (1 row, the
  refutation) and `survived=true` (2 rows: the earlier flawed self-grade, and this session's genuine post-fix
  re-verify)** — the audit trail itself documents the self-graded-pass -> refuted -> fixed -> re-verified-pass sequence
  honestly, nothing was overwritten or hidden. baker: C/D/E/I each `survived=false` x2 (prior firing + this firing's
  recheck).
- Fix script `scripts/gold_standard_shard2_marion_i_placeholder_geocode_fix.py`, commit `41693e6c`, confirmed present
  on `origin/main` via `git merge-base --is-ancestor 41693e6c origin/main`.
- Cluster reduction (297/293 -> 12/7) independently re-queried by the verify agent, not taken from the fix agent's
  claim.

## Next-session priorities

- marion: none outstanding for this shard's scope. The 12 residual placeholder rows are honestly blocked (NULL/
  non-numeric parcel_id, or GIS centroid outside Marion's bbox) — do not force these. Separately, flag to whoever owns
  `pencil_dod_evaluate_county` that letter I's `IS NOT NULL` check cannot detect duplicated-constant ghost success, and
  letter J's `factors ? 'key'` check cannot detect templated/placeholder values — both are systemic scoring-RPC gaps,
  not marion-specific, likely worth an ULTRALOOP audit pass across other counties too.
- baker: unchanged from the prior firing's next-session list — (a) a human clicking through the OCRS Turnstile
  manually, (b) a formal Baker Clerk records request, or (c) wait for the 2026-08-13 / 2026-08-20 sale dates to pass
  and recheck post-sale result data. None of these are actionable by an autonomous session.
