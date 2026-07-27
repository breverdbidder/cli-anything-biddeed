# Gold Standard — Shard-4 (st_lucie), dispatch 8198896f-0420-4072-9f46-30ab50c7779e, loop run 6871

## Scope
Shard assignment: st_lucie only. Brief claimed 10/10 (A-J all PASS). Session
mode: ultracode fan-out (Workflow: 6 parallel adversarial refuter agents, one
per stale letter A/B/E/F/H/J), per ULTRALOOP PROTOCOL.

## Why this session existed despite a "10/10" brief
`gold_standard_ultraloop_audit` showed 6 of 10 st_lucie letters (A, B, E, F,
H, J) with their most recent `survived=true` evidence dated 2026-07-10 or
2026-07-18 — both outside the EVALUATOR V6 7-day certify freshness window as
of today (2026-07-27). C/D/G/I were already fresh (2026-07-25). Per the
WIRING MANDATE and EVALUATOR V6 certify gate ("requires survived=true rows
... for ALL 10 letters within 7 days"), this county was at real risk of
blocking certification on staleness alone, independent of whether the
underlying metrics were still true. Goal: refresh the audit trail with real,
adversarially-verified evidence.

## Environment note
Direct `psql`/`psycopg2` connections (both pooler and direct host, per
`SUPABASE_DB_PASSWORD`) failed with `password authentication failed` in this
session's sandbox. The Supabase REST API (PostgREST, service-role key) worked
throughout and was used for all queries and the one write in this session.

## Baseline (brief, claimed live 2026-07-27 loop run 6871)
```json
{"A":13,"B":100.0,"C":98.2,"D":100.0,"E":98.2,"F":100.0,"G":97.9,"H":0.1,"I":96.4,"J":100.0,"auctions_total":111}
```
Orchestrator's own fresh RPC call at session start reproduced this exactly.

## Work performed
1. **Staleness audit** of `gold_standard_ultraloop_audit` per letter — found
   A/B/E/F/H/J last verified 2026-07-10 (17 days stale), well outside the
   7-day certify window.
2. **Ultracode workflow**: 6 parallel refuter agents, one per stale letter,
   each independently re-queried live Supabase data and was explicitly
   instructed to hunt for the specific ghost-success patterns this campaign
   has documented fleet-wide (B/F anomaly-band inflation, PropertyOnion
   contamination, denominator/numerator scope mismatches, ghost linkage,
   templated fabrication).
3. **Orchestrator meta-verification** of every refuter verdict before
   logging (per "the verifier of a fix is never the agent that wrote it," and
   here — the verifier of a *refuter* is also independently checked):
   - **E**: refuter found 4 rows with `parcel_id='Property Appraiser'`.
     Orchestrator re-ran the full 111-row scan independently and found **7**
     bogus values total (`'Property Appraiser'` x4, `'AIRCRAFT'`,
     `'MULTIPLE PARCEL'`, `'TIMESHARE'`) — worse than the refuter reported.
     **Fixed live**: nulled all 7 via `UPDATE ... SET parcel_id=NULL`.
   - **H**: refuter's refutation was itself checked and found to be an
     artifact of an incomplete methodology (see below) — overturned.
   - **J**: refuter's templating claim was independently reproduced from
     scratch by the orchestrator (distinct ml_score/factor-triple/CMA-value
     counts) and confirmed.
4. **Re-verification** of E, I (side-effect) via a fresh live RPC call after
   the fix.
5. **Audit trail refresh**: 7 rows logged to `gold_standard_ultraloop_audit`
   (ids 10405-10411), `dispatch_id=8198896f-0420-4072-9f46-30ab50c7779e`.

## Findings detail

### A — SURVIVED
`fc=98 td=13`, matches evaluator and brief exactly. Refuter flagged the
tax_deed lane as a frozen ~3-month-stale batch (all 13 rows dated
2026-04-06/2026-05-04; 10/13 `upcoming`-past-due with
`needs_source_rescrape=true`; 3/13 cancelled; 0 sold) vs the foreclosure
lane's active pipeline (25/98 upcoming ≥ today, 2 sold). This is a genuine
**evaluator-design gap** (A checks lane existence, not lane activity) — not a
data-accuracy bug. Logged survived=true; staleness flagged as residual for
architect review.

### B — SURVIVED
`foreclosure_outcomes` has exactly 2 rows, both RealAuction-sourced
(`realforeclose:st_lucie:shard1-ffd85d01`), zero PropertyOnion markers.
`tax_deed_outcomes`=0. `multi_county_auctions` sold/closed=2, exact
cross-match on case_number + dollar amount. Full status breakdown
(`upcoming:96, cancelled:13, sold:2`) rules out a hidden denominator bucket.
100.0% ratio is genuine — not the Brevard/Duval-style inflated-ratio anomaly.

### E — GHOST-SUCCESS FOUND AND FIXED LIVE (regression disclosed)
7 of the 111 `multi_county_auctions` rows for st_lucie had non-parcel garbage
strings stored in `parcel_id` — clearly scraper artifacts (a UI label
captured instead of a real parcel number):

| case_number | bogus parcel_id |
|---|---|
| 2024CA001834 | Property Appraiser |
| 2025CC001033 | Property Appraiser |
| 2023CA002852 | Property Appraiser |
| 2023CA000465 | Property Appraiser |
| 2024CA000958 | AIRCRAFT |
| 2024CA000330 | MULTIPLE PARCEL |
| 2025CA002738 | TIMESHARE |

Fixed live: `UPDATE multi_county_auctions SET parcel_id=NULL WHERE
county='st_lucie' AND parcel_id IN ('Property Appraiser','AIRCRAFT','MULTIPLE
PARCEL','TIMESHARE')` — 7 rows affected, confirmed via PATCH response.
**E now honestly reports FAIL: parcel_linked=102/111 = 91.9%** (was ghost-PASS
98.2%). Per HONESTY PROTOCOL, an honest FAIL is correct and required over a
false PASS.

### F — SURVIVED
tier1_sold_amount populated for both sold rows, exactly matching
sold_amount. Reverse scope check (any row with tier1_sold_amount set,
regardless of status) returns the identical 2 rows — no numerator/denominator
scope mismatch. 100.0% genuine.

### H — SURVIVED (refuter's own refutation overturned)
The refuter computed elapsed time from `last_seen_at` alone (max
`2026-07-27T15:56:06Z` vs then-current `~19:29:35Z` ≈ 3.56h) and flagged the
RPC's `metric=0.1` as inconsistent. But the deployed evaluator
(`supabase/migrations/20260718_gtm22_phase1_3_pencil_dod_snapshot_param_and_loop_rewire.sql`)
computes `last_seen` as `max(GREATEST(last_changed_at, last_seen_at,
scraped_at, scrape_timestamp, created_at))` per row — not `last_seen_at`
alone. Orchestrator independently queried all 5 columns across all 111 rows:
`MAX(scraped_at) = 2026-07-27T19:32:22.955194Z` (case `2026CA000534`),
captured **6 seconds before** an orchestrator RPC call at `19:32:16Z` (HTTP
`Date` header confirmed same second) — a live scrape was running during this
very session. True GREATEST-based elapsed time is genuinely ~0.0-0.1h. The
refuter's methodology (only 1 of 5 GREATEST columns) was the error.

### I — SIDE-EFFECT REGRESSION disclosed
Not one of the 6 original stale targets (last audited 2026-07-25, still fresh
at session start). Fixing E's ghost-linkage directly caused I to regress live
from 96.4% (`card_complete=107/111`) to **91.9% (`card_complete=102/111`)** —
the same 7 rows' zoning-card completeness depended on the same fabricated
parcel_id matching a zoning parcel. I's true completeness was always
102/111; the prior 107/111 was itself ghost-inflated by the same bad values.

### J — GHOST-SUCCESS FLAGGED, NOT FIXED THIS SESSION
Mechanical field-completeness claim is true: all 110 distinct MCA
case_numbers have a matching `bid_decisions` row with arv/max_bid/ml_score
non-null and all 5 required factor keys present (RPC `J=100.0` genuinely
reflects field presence). But the orchestrator independently reproduced the
refuter's deeper finding from scratch: across all 142
`county_slug=st_lucie` `bid_decisions` rows —
- `ml_score` takes only **3** distinct values across 142 rows: 0.75 (71
  rows), 0.82 (21 rows), 0.58 (50 rows)
- `(distress_owner, distress_location, distress_property)` collapses to
  **3** distinct combinations: (0.6, 0.65, 0.7) in 85 rows, (0.55, 0.55, 0.5)
  in 50 rows, and a dict-wrapped variant with byte-identical boilerplate
  notes in 7 rows
- `cma_distressed.value` is `65000.0` in 50 rows and `32500.0` in 16 rows —
  46% of all 142 rows share just 2 values, despite covering 111 structurally
  different properties

This is a templated/bucket-fill pattern, not genuine per-property
Shapira-model + two-arm-CMA computation, even though every value carries
`honesty_marker=INFERRED`. J's evaluator only checks field *presence*, not
value *authenticity*, so this ghost-success is invisible to the current
metric. Repairing the `bid_decisions`/CMA generator is out of scope for an
audit-refresh session — flagged for architect-level triage, consistent with
the fleet-wide J concern already documented in this campaign's 2026-06-12
brief history.

## Final state (verified live, session end, 2026-07-27T19:36:59Z)
```json
{"A":{"pass":true,"metric":13,"detail":"fc=98 td=13"},
 "B":{"pass":true,"metric":100.0,"detail":"verified=2 closed_sold=2"},
 "C":{"pass":true,"metric":98.2,"detail":"matched_clean=109"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=111"},
 "E":{"pass":false,"metric":91.9,"detail":"parcel_linked=102"},
 "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=2 closed_sold=2"},
 "G":{"pass":true,"metric":97.9,"detail":"density=97.9 far= pk1000="},
 "H":{"pass":true,"metric":0.0,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":91.9,"detail":"card_complete=102 of 111"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=111 (flagged, see above)"},
 "auctions_total":111}
```
**8/10** (A,B,C,D,F,G,H,J pass; E,I fail) — down from the brief's claimed
10/10, because 2 of those 10 passes were ghost-successes riding on 7 rows of
fabricated `parcel_id` data that this session found and purged.

### SQL VERIFICATION
```sql
-- Before fix
SELECT public.pencil_dod_evaluate_county('st_lucie');
-- E: {"pass":true,"metric":98.2,"detail":"parcel_linked=109"}
-- I: {"pass":true,"metric":96.4,"detail":"card_complete=107 of 111"}

-- Bogus parcel_id rows found (7)
SELECT case_number, parcel_id FROM multi_county_auctions
WHERE county='st_lucie' AND parcel_id IN ('Property Appraiser','AIRCRAFT','MULTIPLE PARCEL','TIMESHARE');
-- 2024CA001834, 2025CC001033, 2023CA002852, 2023CA000465 -> 'Property Appraiser'
-- 2024CA000958 -> 'AIRCRAFT'; 2024CA000330 -> 'MULTIPLE PARCEL'; 2025CA002738 -> 'TIMESHARE'

-- Fix applied
UPDATE multi_county_auctions SET parcel_id = NULL
WHERE county='st_lucie' AND parcel_id IN ('Property Appraiser','AIRCRAFT','MULTIPLE PARCEL','TIMESHARE');
-- 7 rows affected (confirmed via PATCH return=representation)

-- After fix
SELECT public.pencil_dod_evaluate_county('st_lucie');
-- E: {"pass":false,"metric":91.9,"detail":"parcel_linked=102"}
-- I: {"pass":false,"metric":91.9,"detail":"card_complete=102 of 111"}
-- 2026-07-27T19:36:59Z
```

## Ultraloop audit trail
7 rows logged to `gold_standard_ultraloop_audit`
(dispatch_id=8198896f-0420-4072-9f46-30ab50c7779e, ids 10405-10411):
A(survived=true), B(survived=true), E(survived=false, fix applied),
F(survived=true), H(survived=true), I(survived=false, disclosed side-effect),
J(survived=false, flagged not fixed).

## Verdict: HONEST REGRESSION, CORRECTLY DISCLOSED
This session did not "improve" st_lucie's scoreboard — it went from a false
10/10 to a genuine, freshly-verified 8/10. Per HONESTY PROTOCOL and SHIP GATE,
this is the correct outcome: a false PASS carried toward certification is
worse than an honest FAIL, and both letters that regressed did so because
this session removed fabricated data (not because it broke anything working).

## Next-session priorities
1. **E/I fix**: backfill real `parcel_id` for the 7 identified cases via St
   Lucie Property Appraiser GIS. 2 of 7 (2025CA002738, 2023CA000465) have no
   `source_url` at all — genuine source gap. 4 of the remaining 5 have
   placeholder addresses (`"St. Lucie County FL — <case>"`, also fabricated).
   Only case 2024CA000958 has a real street address (436 SW CRAWFISH DR, Port
   St Lucie FL 34953) immediately usable for a live GIS lookup.
2. **J architect review**: the templated-bucket pattern found here for
   `bid_decisions` should be checked against other counties before treating
   J passes fleet-wide as trustworthy — this is likely not st_lucie-specific.
3. **A criterion design**: fleet-level decision on whether A should also
   check lane activity/freshness, not just lane existence — st_lucie's
   tax_deed lane has been frozen since ~2026-05-04 with zero live scrape
   activity or sold outcomes.
