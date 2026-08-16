# GOLD STANDARD shard-1 — brevard, st_lucie, hernando, holmes, wakulla (dispatch 3eefe79f-65ee-4e6f-b194-cc8d8db9fb0e)

chat_session: architect-20260816T080000, loop run 11871

## Summary

Ran the ULTRALOOP protocol via a native `Workflow` (5 Diagnose agents → conditional Fix agents →
conditional adversarial Verify agents, one pipeline lane per county, `ultraloop_mode='native'`).

**hernando: 8/10 → 10/10.** I and J both flipped FAIL→PASS, both survived independent adversarial
re-verification. Shipped and pushed to main as commit `97df84f6`.

**brevard: I claim REFUTED, no real progress.** The fix agent believed it wrote 2 new address rows
via municipal ArcGIS (Palm Bay), but the adversarial verifier proved via `updated_at` timestamp
forensics that those exact 2 rows (parcel_id 2811986, 2852162) were already written by a **prior**
session's commit `25d2fb48` (already on `main` before this session started) — the "fix" re-derived
already-existing data and made no net change. Metric is byte-identical before/after: 85.5%
(6202/7252 in the live re-check; the diagnose-time snapshot read 6198, a 4-row difference from
unrelated concurrent fleet activity, not from this session's work). Logged to
`gold_standard_ultraloop_audit` id=15975 with `survived=false` — a false positive, not counted.

**st_lucie: 9/10, C confirmed structurally capped this session** (not previously understood this
precisely) — `matched_clean` excludes `CLERK_SSOT_CANCELLED` rows by the live evaluator's own filter
logic (verified by reproducing the function body against a fresh pull of all 221 rows), so the C/D
gap is an evaluator-design ceiling, not a missing-data problem. No fix attempted or needed to
determine this; no write made.

**wakulla: 6/10, no letters actionable this session.** C/E/I/J all gate on the identical 6 rows
(4 confirmed-dead via 2 independent techniques re-run today with positive/negative controls, 1 old
confirmed-dead redeemed-certificate row, 1 recoverable-but-insufficient row). Even a perfect fix of
the one recoverable row only reaches 33/38=86.8%, still below the 95% threshold — mathematically
incapable of flipping any letter this session regardless of effort. Correctly not attempted (this
exact ceiling has now been independently reconfirmed by 3 sessions in the last 48h: 72cb38f7,
84b6c4bb, 0c4d6721).

**holmes: 6/10, no drift, structural ceiling reconfirmed for the 18th+ time.** B/F byte-identical
since 2026-07-10 (verified=0, closed_sold=0 — nothing has closed yet, no source publishes a
disposition). C/D at 68.8% (11/16), unchanged from the dispatch brief's own baseline (the brief's
own numbers, not the stale f60cabe3 numbers this session's agent initially cross-checked against —
confirmed E/I/J/C/D moved 2026-08-15 via an unrelated fleet-wide clerk-parity bug fix, not this
session). No new avenue found; the one retry attempted (floridapublicnotices.com HAL-JSON query)
was inconclusive, not new evidence, and changed nothing.

## VERIFICATION PROTOCOL — before/after (verbatim from `pencil_dod_evaluate_county`, live RPC)

**Session-start baseline (dispatch brief, re-confirmed live before any work):**
```
brevard:  A✓864 B✓98.5 C✓97.3 D✓97.4 E✓99.6 F✓98.9 G✓99.1 H✓1.3 I✗85.8(6094/7099) J✓100.0  -- 9/10
st_lucie: A✓110 B✓100.0 C✗83.7(185) D✓100.0 E✓95.5 F✓100.0 G✓95.0 H✓0.1 I✓95.0 J✓99.1      -- 9/10
hernando: A✓13  B✓100.0 C✓100.0 D✓100.0 E✓100.0 F✓100.0 G✓97.2 H✓0.2 I✗69.1(47/68) J✗72.1(49/68) -- 8/10
holmes:   A✓6   B✗null  C✗68.8(11) D✗68.8(11) E✓100.0 F✗null G✓100.0 H✓1.8 I✓100.0 J✓100.0  -- 6/10
wakulla:  A✓8   B✓100.0 C✗84.2(32) D✓100.0 E✗84.2(32) F✓100.0 G✓100.0 H✓1.8 I✗84.2(32) J✗84.2(32) -- 6/10
```

**Session-end (this report, fresh RPC calls, UTC 2026-08-16T08:29Z):**
```json
brevard:  {"A":true,"metric":922,"B":true,"metric":98.6,"C":true,"metric":96.4,"D":true,"metric":96.6,"E":true,"metric":99.2,"F":true,"metric":99.0,"G":true,"metric":99.1,"H":true,"metric":2.2,"I":false,"metric":85.5,"detail":"card_complete=6202 of 7252","J":true,"metric":98.9} -- 9/10, NO CHANGE (I claim refuted)
st_lucie: {"A":true,"110","B":true,"100.0","C":false,"metric":83.7,"detail":"matched_clean=185","D":true,"100.0","E":true,"95.5","F":true,"100.0","G":true,"95.0","H":true,"0.1","I":true,"95.0","J":true,"99.1"} -- 9/10, NO CHANGE (C confirmed structural)
hernando: {"A":true,"13","B":true,"100.0","C":true,"100.0","D":true,"100.0","E":true,"100.0","F":true,"100.0","G":true,"97.6","H":true,"1.2","I":true,"metric":100.0,"detail":"card_complete=68 of 68","J":true,"metric":100.0,"detail":"deal_complete=68"} -- 10/10 ✅
holmes:   {"A":true,"6","B":false,"null","C":false,"68.8","D":false,"68.8","E":true,"100.0","F":false,"null","G":true,"100.0","H":true,"0.3","I":true,"100.0","J":true,"100.0"} -- 6/10, NO CHANGE
wakulla:  {"A":true,"8","B":true,"100.0","C":false,"84.2","D":true,"100.0","E":false,"84.2","F":true,"100.0","G":true,"100.0","H":true,"2.8","I":false,"84.2","J":false,"84.2"} -- 6/10, NO CHANGE
```

## What was fixed and shipped (hernando, commit `97df84f6`)

- **I**: 21 rows inserted into `public.parcel_zones` (jurisdiction_id=1330), `zone_code` copied
  verbatim from `zoning_assignments` where `zone_source='county_gis_spatial_join'` for the 21
  parcels that had `zoning_code IS NULL` in `v_auction_property_card`. All 21 independently
  re-verified live post-write (0 mismatches, no fabrication).
- **J**: `scripts/hernando_j_generator_19_fl_gio.py` (new, forked from the existing
  `hernando_j_generator_26.py` pattern) generated 19 `bid_decisions` rows with real FL GIO
  `market_value` as ARV (`arv_source='fl_gio_cadastral_jv'`), Shapira formula
  `ARV*0.70 - 15000 - 10000 - MIN(25000, 0.15*ARV)` for `max_bid`, full triangle + two-arm-CMA
  factors. Fail-loud guard present and did not trigger (19 parsed, 19 inserted). Verifier
  independently reproduced the formula on 5 sampled rows — exact match every time.
- **G regression guard**: while inserting the 21 new `parcel_zones` rows, the fix also added 2 new
  `zoning_districts` rows (CITY id=14119, PDP(REC) id=14120) marked `far_regulated=pk1000_regulated=
  density_regulated=false` to avoid inflating G's applicable-parcel denominator with unregulated
  districts (the same LEFT-JOIN-default-applicable bug pattern seen and fixed for pinellas, baker,
  st_johns, sumter, columbia, gadsden in prior sessions). G stayed PASS (97.2%→97.6%, no regression).
- Migration: `supabase/migrations/20260816_gold_standard_hernando_ij_parcel_zones_and_g_regression_fix_3eefe79f.sql`

## What was refuted (brevard I — false positive, not counted)

Fix agent's claim of "2 new rows written live this session via Palm Bay municipal ArcGIS" was
independently disproven: both rows (parcel_id 2811986, 2852162) carry `updated_at =
2026-07-31T08:26:06Z`, matching 1261 other brevard rows from an unrelated mass batch job, and commit
`25d2fb48` ("fix: brevard I — Palm Bay municipal address-point exact-parcel backfill (2 rows)") was
already on `main` before this session began. The fix agent's PATCH request landed on rows that
already held the correct value, so no net data change occurred despite a well-intentioned, correctly
non-fabricated write attempt. Separately, the fixer's stated candidate count (146/164 non-PropertyOnion
address-missing rows) does not match a live recount (1033 non-PropertyOnion NULL-address rows via
`data_source IS NULL OR data_source <> 'propertyonion'`) — an apparent `<>`/NULL semantics bug in the
fixer's filter that underscopes the real gap by ~6x. **Actionable follow-up for a future brevard I
session:** re-run the real candidate query (NULL-safe: `data_source IS NULL OR data_source NOT ILIKE
'%propertyonion%'`) against the full ~1033-row gap, not the ~150-row subset this and prior sessions
scoped themselves to.

## ULTRALOOP audit rows this dispatch

```
id=15975  brevard/I   survived=false  (false positive, logged not counted)
id=15988  hernando/I  survived=true
id=15989  hernando/J  survived=true
id=15990  hernando/G  survived=true  (regression check)
```

No `gold_standard_loop()` / `gold_standard_certify()` run this session — PARALLEL-FLEET RULES
require skipping the full loop when other shards may be mid-flight, and this dispatch has no way to
confirm otherwise; per-county `pencil_dod_evaluate_county` calls were used for all verification
instead.

### SQL VERIFICATION

```sql
-- Close-out record (applied live via Supabase PostgREST, 2026-08-16T08:29:47.049Z UTC):
SELECT dispatch_id, target_counties, criteria_passed, criteria_total, exit_reason, session_end_at
FROM public.gold_standard_campaign
WHERE dispatch_id = '3eefe79f-65ee-4e6f-b194-cc8d8db9fb0e';
-- id=4452:
-- criteria_passed = {
--   "brevard":  {"A":true,"B":true,"C":true,"D":true,"E":true,"F":true,"G":true,"H":true,"I":false,"J":true},
--   "st_lucie": {"A":true,"B":true,"C":false,"D":true,"E":true,"F":true,"G":true,"H":true,"I":true,"J":true},
--   "hernando": {"A":true,"B":true,"C":true,"D":true,"E":true,"F":true,"G":true,"H":true,"I":true,"J":true},
--   "holmes":   {"A":true,"B":false,"C":false,"D":false,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true},
--   "wakulla":  {"A":true,"B":true,"C":false,"D":true,"E":false,"F":true,"G":true,"H":true,"I":false,"J":false}
-- }
-- criteria_total=10, exit_reason='timeout', session_end_at='2026-08-16T08:29:47.049+00:00'
```

Timestamp UTC: 2026-08-16T08:29Z.

## Recommendation for future sessions

- **hernando is 10/10 live.** Needs a second consecutive 10/10 daily run to auto-certify per campaign
  rule — no action needed, just don't regress it.
- **brevard I**: do not re-trust the ~150-row candidate scoping used by this and the immediately
  prior session (`25d2fb48`) — the real non-PropertyOnion gap is ~1033 rows per this session's live
  recount; fix the `<>`/NULL filter semantics bug before the next attempt.
- **wakulla C/E/I/J**: mathematically incapable of passing until more than 1 of the 6 gap rows
  becomes recoverable (currently only 1 of 6 is even theoretically resolvable, capping at 86.8%).
  Do not re-attempt the 4 confirmed-dead TXD rows without a genuinely new source.
- **st_lucie C**: structural evaluator-design ceiling (CLERK_SSOT_CANCELLED exclusion). Would need an
  AI-architect decision on whether that exclusion rule should change, not further data work.
- **holmes B/C/D/F**: unchanged 18th-session structural ceiling. Treat as a documented floor, not a
  target, absent a policy change (human-in-the-loop courthouse step) or new online source.

---
dispatch_id: 3eefe79f-65ee-4e6f-b194-cc8d8db9fb0e
