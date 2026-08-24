# Gold Standard shard-1 — gadsden, indian_river, polk, escambia, highlands

- **dispatch_id**: ee7cda49-1464-44c5-903d-3e7addc3a4dc
- **chat_session**: architect-20260824T080000
- **loop_run at launch**: 13909
- **mode**: ULTRALOOP (ultracode `Workflow`) — 5 pre-diagnosed fix targets, each a
  worktree-isolated fix agent piped into an independent adversarial verifier
  (no shared context, no self-certification). 10 agents, 430 tool calls,
  ~1.05M subagent tokens, ~26 min wall time.

## Scoreboard — before → after (live `pencil_dod_evaluate_county`, re-verified by me independently after the workflow, not reused from any agent's self-report)

| County | Before | After |
|---|---|---|
| gadsden | 10/10 (already passing, fresh audit trail from 2026-08-23) | **10/10**, unchanged |
| indian_river | 9/10 (I FAIL 94.4%) | **10/10** — I: 94.4% → 96.3% PASS |
| polk | 9/10 (J FAIL 93.5%) | **10/10** — J: 93.5% → 100.0% PASS |
| escambia | 8/10 (C,D FAIL 94.3%) | **10/10** — C: 94.3%→95.9%, D: 94.3%→96.1% PASS |
| highlands | 7/10 (C,D FAIL 94.5%, I FAIL 85.5%) | **10/10** — C: 94.5%→97.0%, D: 94.5%→97.0%, I: 85.5%→95.0% PASS |

**All 5 shard counties read 10/10 live as of this session close.** This is a live-metric
result, not a certification — certification still requires the automated 2-consecutive-day
`gold_standard_loop()`/`gold_standard_certify()` gate (see Close-out below).

## Fresh live JSON (queried by me directly, after the workflow, 2026-08-24T08:3x UTC)

```json
gadsden:      {"A":true(25),"B":true(100.0),"C":true(100.0),"D":true(100.0),"E":true(98.5),"F":true(100.0),"G":true(100.0),"H":true(0.3),"I":true(98.5),"J":true(95.5)}
indian_river: {"A":true(37),"B":true(100.0),"C":true(98.1),"D":true(98.1),"E":true(100.0),"F":true(100.0),"G":true(99.0),"H":true(1.1),"I":true(96.3,"card_complete=103 of 107"),"J":true(100.0)}
polk:         {"A":true(157),"B":true(100.0),"C":true(96.3),"D":true(96.3),"E":true(99.9),"F":true(100.0),"G":true(100.0),"H":true(0.1),"I":true(99.9),"J":true(100.0,"deal_complete=775")}
escambia:     {"A":true(80),"B":true(100.0),"C":true(95.9,"matched_clean=473"),"D":true(96.1,"matched_any=474"),"E":true(99.8),"F":true(100.0),"G":true(97.1),"H":true(0.1),"I":true(95.9),"J":true(98.4)}
highlands:    {"A":true(49),"B":true(100.0),"C":true(97.0,"matched_clean=389"),"D":true(97.0,"matched_any=389"),"E":true(95.0),"F":true(100.0),"G":true(99.7),"H":true(0.1),"I":true(95.0,"card_complete=381 of 401"),"J":true(97.5)}
```

## What was done, by target

### indian_river I — 2-row zone-linkage fix
Pre-diagnosed the exact 6-row gap live before dispatch. 2 rows (`2025 CC 003117`,
`2025 CA 000382`) already had complete address/geo/value, missing only zone linkage.
Fixed via Indian River County's live ArcGIS MapServer
(`gisportal.ircgov.com/server3/rest/services/Planning/IRC_Zoning_MS/MapServer/0/query`),
resolving real zone codes RM-6 and A-1, cross-checked against Vero Beach's own zoning
FeatureServer (empty at both points, confirming unincorporated-county jurisdiction is
correct) and the county's official `zoningleg.pdf`. Commit `325e7e64`.
**Verifier independently re-queried the same live ArcGIS endpoint itself** and got exact
zone-code matches; confirmed no PropertyOnion contamination; confirmed no regression on
the other 9 letters. Residual: 4 rows genuinely unfixable this session (2 "MULTIPLE
PARCELS" placeholder cases, 1 "Property Appraiser" placeholder case, 1 real-address row
still missing assessed_value) — not needed to cross 95%, left honest.

### polk J — 50-row Shapira V14 generator run
Pre-diagnosed all 50 gap case numbers live (zero `bid_decisions` rows, all foreclosure,
all added since 2026-08-03). Built `scripts/gold_standard_polk_j_generator_real.py`
(new script, adapted from the proven highlands-J pattern), verified polk IS in
`shapira_models` v14's `county_target_encoding_map` (rate 0.7018...) before using it —
no fallback/guessed rate. ARV sourced from `comps_cma_bulk`/assessed value per row. All
50 gap rows completed (not just the 12 needed), 0 max_bid-bound violations, 0 missing
factor keys. Commit `d2b946d5`.
**Verifier independently re-implemented the J `deal_complete` SQL logic from scratch in
Python** against a fresh paginated fetch and got 775/775 = 100.0%, exact match; spot-
checked 10 ARV values against the underlying `comps_cma_bulk` rows byte-for-byte; confirmed
no schema/evaluator changes shipped (guardrail 4 respected). Regression-checked all 9 other
polk letters — unchanged.

### escambia C/D — 8 near-term foreclosure parity matches + 1 divergent
Pre-diagnosed the 28-row NULL-parity gap, prioritized the 9 imminent (2-8 days out)
foreclosures per this session's own live-source cluster analysis. Reverse-engineered
`escambia.realforeclose.com`'s AJAX calendar endpoint (plain fetch 403s; session-cookie
POST works), field-matched case number / judgment amount / address for 8 rows exactly →
`matched_clean`, plus 1 row (`2026 CC 001962`) found genuinely moved buckets (still-upcoming
→ closed/canceled with a populated judgment) → `matched_divergent` (conservative, correct
per canon — not force-cleaned). Source tagged `tier1_realauction_20260824`. Pure data-plane
write via PostgREST — no code/migration needed, nothing to commit.
**Verifier independently re-derived the same AJAX endpoint itself** (not reusing the
fixer's session) and field-matched all 8 clean rows plus the divergent row; downgraded one
narrow sub-claim (an exact status-text quote) from CONFIRMED to PLAUSIBLE since the raw
capture didn't literally contain it, while confirming the underlying classification
(matched_divergent, not clean) was correct regardless. Flagged that a `tier1_verified_at`
timestamp the fixer cited as corroboration is actually a shared batch stamp on 124 rows,
not case-specific evidence — noted as a process observation, does not change correctness
of the write.

### highlands C/D — tax_deed clerk parser (new lever)
Confirmed the 2026-08-12 diagnosis (no `tax_deed` entry in
`scripts/clerk_ssot/run_parity.py`'s `PARSERS` dict for highlands) still held. Built a real
highlands tax_deed parser against `highlands.realtdm.com` (verified genuinely clerk-owned
via a `highlandsclerkfl.gov` link-through), registered it in `PARSERS`, ran it for the 10
gap case numbers, all confirmed `matched_clean` with `parity_source='tier1_highlands_realtdm_20260824'`.
Commit `648df615`. Left the 9 `shard8_run6046_litmus_fallback`-sourced rows and 2 synthetic
placeholder rows untouched (investigated, correctly out of scope this session).
**Verifier independently drove a fresh Playwright session against `highlands.realtdm.com`**
(curl 403s without a browser session — confirmed real bot-protection, not fabrication) and
re-searched all 10 case numbers itself, getting exact status/date/parcel matches.

### highlands I — 38-row zone-linkage + address backfill (largest gap)
Pre-diagnosed 58 total gap rows (37 zone-linkage-only, 19 missing data entirely) and
explicitly flagged that fixing only the 37 zone-only rows would land at 380/401=94.8% —
1 row short. Fixed all 37 via Highlands County's ArcGIS zoning layer
(`gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0/query`, STRAP-based
lookup) plus 1 additional address backfill (case `25000871`, cross-checked against
`hcpao.org`), landing at 381/401 = exactly the threshold. Commit `8d307f92`. G-safety
checked before/after (99.7% unchanged, no regression from the new zone codes).
**Verifier independently re-fetched `v_zoning_gold_standard_card` for highlands and got
exactly 381 rows**, matching the evaluator precisely; live-refetched 4/38 zone codes from
the same ArcGIS endpoint itself (3/4 exact match, 1 pre-existing narrative discrepancy that
does not affect the net count — a `WHERE NOT EXISTS` guard made that specific insert a
no-op against an already-correct row); flagged a pre-existing, not-fabricated caveat that
177/401 highlands rows (not just this fix's rows) share a county-centroid placeholder
lat/long rather than a real geocode — legitimate under the evaluator's current
`IS NOT NULL`-only definition, noted for a future session, not a defect of this fix.

### Cross-lane note (adversarial layer caught a real attribution error)
The `highlands/I` verify lane ran concurrently with the `highlands/C,D` fix lane and, on
seeing C/D already at 97.0% mid-session, its own fix agent cited the wrong commit
(`209b02a2`, an unrelated flagler-county commit) as the cause. Its verifier caught this:
confirmed the metric (97.0%, real) but marked the **attribution claim** `survived=false`
and logged it as such (audit rows 17658/17659), correctly distinguishing "the number is
real" from "your explanation of why is wrong." The correct attribution (commit `648df615`,
same dispatch, sibling lane) is separately and correctly logged as `survived=true` in
audit rows 17685/17686. This is the ULTRALOOP adversarial-verify layer working exactly as
designed — flagged here for transparency, not as an unresolved issue.

## ULTRALOOP audit trail
22 rows inserted into `gold_standard_ultraloop_audit`, `dispatch_id=ee7cda49-1464-44c5-903d-3e7addc3a4dc`,
`ultraloop_mode=native`: 17588 (indian_river/I), 17599-17608 (polk, all 10 letters),
17619-17620 (escambia/C,D), 17655/17657-17665 (highlands/I lane, all 10 letters — 2 of
which, C/D, are `survived=false` on attribution only, see above), 17685-17686
(highlands/C,D lane, `survived=true`). Zero fabricated data, zero forced passes, zero
PropertyOnion-derived matches counted.

## gold_standard_campaign close-out
Row id 4925 (`dispatch_id=ee7cda49-1464-44c5-903d-3e7addc3a4dc`) updated live:
`criteria_passed` set to real 10/10 A-J maps for all 5 counties, `criteria_total=10`,
`exit_reason='completed_workqueue'`, `session_end_at=now()`. Applied and confirmed via
the PATCH response (see transcript).

Did **not** run `gold_standard_loop()` or `gold_standard_certify()` this session — live
evidence of concurrent fleet activity (commit `209b02a2`, a different same-day flagler
shard, plus several other shard commits interleaved on `main` during this session's
window: alachua, charlotte, st_johns, st_lucie, marion, hamilton). Per PARALLEL-FLEET
RULES, only per-county `pencil_dod_evaluate_county` was used for verification.
**5/5 shard counties read 10/10 live** — this starts/advances each county's
`consecutive_gold` clock toward the automated 2-consecutive-day certify gate; it does not
itself certify.

## Next-session priorities
- All 5 shard counties are 10/10 live. No further fix work needed unless tomorrow's
  automated re-check finds drift (new-row growth has repeatedly regressed I/C/D/J in this
  shard historically as fresh auction rows land — indian_river, polk, and highlands all
  hit exactly this pattern between their last 10/10 and today's brief). Recommend a
  lightweight freshness re-check on the next scheduled run rather than assuming
  permanence.
- escambia's fix was pure data-plane (no commit) — if a future session needs to trace it,
  the evidence trail is `parity_source='tier1_realauction_20260824'` on the 9 written rows
  plus this report.
- highlands C's residual 9-row `shard8_run6046_litmus_fallback` cluster remains
  unresolved (provenance genuinely unclear whether it traces to an independent clerk
  source or a PropertyOnion-derived comparison) — do not blindly relabel; a future session
  should investigate the origin script directly before touching it further. Not needed for
  10/10 this session (headroom: C/D are at 97.0%, 2 points above threshold).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
