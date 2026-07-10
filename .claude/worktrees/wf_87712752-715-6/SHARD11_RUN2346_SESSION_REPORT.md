# SHARD-11 Session Report (loop run 2346) — palm_beach, miami_dade (2026-07-02)

Dispatch: `7a6b2043-0106-46ec-8afa-c8362cb2b9bc`. Multiple other shard sessions dispatched at the same `2026-07-02T08:00:00Z` wave — per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not** run; only per-county `pencil_dod_evaluate_county` evaluations are reported below.

## Brief accuracy check
The dispatch brief's miami_dade C/D/E numbers (3.7%) were **stale** — a prior shard had already fixed those criteria. Live query at session start showed miami_dade at 9/10 (A,B,C,D,E,F,G,H,J passing; only I failing at 91.8%). palm_beach's brief numbers (10/10) matched live reality exactly — reconfirmed, no action taken.

## Environment
Direct `psql` to the pooler failed (`password authentication failed`). All reads via PostgREST (`SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`), all DDL/DML via the Supabase Management API (`SUPABASE_ACCESS_TOKEN`, `api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query`).

## palm_beach — 10/10 at session start, reconfirmed, untouched
```json
{"A":{"pass":true,"metric":116},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":99.1},
 "D":{"pass":true,"metric":99.1},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},
 "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.0},"I":{"pass":true,"metric":97.8},
 "J":{"pass":true,"metric":99.1},"county":"palm_beach","auctions_total":685}
```
No fix needed. No files touched.

## miami_dade — 9/10 → 10/10 (GOLD), I criterion closed with one self-caught-and-reverted regression along the way

### Before (session start)
```json
{"A":{"pass":true,"metric":87},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":96.3},
 "D":{"pass":true,"metric":96.3},"E":{"pass":true,"metric":97.5},"F":{"pass":true,"metric":100.0},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},
 "H":{"pass":true,"metric":1.6},"I":{"pass":false,"metric":91.8,"detail":"card_complete=326 of 355"},
 "J":{"pass":true,"metric":100.0},"county":"miami_dade","auctions_total":355}
```

### Diagnosis
`pencil_dod_evaluate_county`'s I criterion requires, per auction row: `property_address` + (`latitude`/`po_latitude`) + (`longitude`/`po_longitude`) + (`assessed_value`/`market_value`) + `parcel_id` present in `v_zoning_gold_standard_card` with `zone_code IS NOT NULL`. Diffed all 355 in-scope rows field-by-field: 29 incomplete, breaking into (a) 9 rows with no parcel_id at all (multi-parcel/business-license case types, e.g. `parcel_id='MULTIPLE PARCELS'`/`'ALCOHOLIC BEVERAGE LICENSE'`), (b) 12 rows with real 13-digit Miami-Dade folios missing geo/value/zoning, (c) 5 duplicate case_number rows riding on (a)/(b) parcels, (d) 3 folios present in the auction data but absent from `fl_parcels` (FL DOR NAL).

### Fix 1 (`20260702_shard11_miami_dade_i_card_backfill.sql`) — 326 → 335, then a caught regression, reverted to 332
Backfilled lat/lon + assessed/market value for 9 parcels from `fl_parcels` (FL DOR NAL, real data — 3 of the 12 folios don't exist in this extract at all, left unresolved rather than fabricated). Added `parcel_zones` rows for 8 parcels via a **live** Miami-Dade zoning ArcGIS point-in-polygon query (`gisweb.miamidade.gov/arcgis/rest/services/LandManagement/MD_Zoning/MapServer`, layers 1+2) against each parcel's real centroid.

Immediately re-verified live and caught a self-inflicted regression: 3 of those 8 zone codes (NCUC, T3-R, E-M) had no pre-existing `zoning_districts` row, so `v_zoning_district_applicability`'s `COALESCE(far_applicable, true)` / `COALESCE(pk1000_applicable, true)` defaulted them to "applicable, no data" — flipping a previously-NULL-and-ignored-by-`LEAST()` metric into a real 0%, crashing **G from PASS(100.0) to FAIL(0.0)**. Reverted those 3 `parcel_zones` inserts in the same migration file. Re-verified: G back to PASS(99.6), I at 93.5% (332/355) — still short of the 95% gate.

### ULTRALOOP research + adversarial verify (Workflow `wf_31fa8987-96f`, native mode, 6 agents, 546.8K tokens, 130 tool calls)
Fanned out 3 research agents (condo-unit folio lookups, the 3 orphan folios, ordinance classification for NCUC/T3-R/E-M) and 3 independent refuters, one per finding, each re-querying live sources rather than trusting the researcher's prose.
- **condo_folios**: refuter REJECTED nothing outright but confirmed every case in this bucket is still missing at least one required field (value, in all cases) even after applying the confirmed parts — **excluded entirely, nothing written**.
- **orphan_folios**: refuter independently re-hit the cited APIs live and CONFIRMED all 3 folios (active, `CANCEL_FLAG=N`), addresses, lat/lon (reprojected to <2m), and exact 2026 assessed/market values via an independent re-pull — flagged the researcher's cited URL as non-reproducible (missing a required param) but confirmed the underlying data once corrected.
- **zoning_categories**: refuter CONFIRMED NCUC and T3-R via pinpoint primary-ordinance citations (Miami-Dade Naranja district regs PDF; Miami21 Code Article 5). REJECTED E-M's specific numeric claims (32% lot coverage etc.) as unsourced — the researcher had been blocked from Municode by 403/503 and those figures had no citation in its report.

### Fix 2 (`20260702_shard11_miami_dade_i_card_closeout.sql`) — 332 → 337
Applied only the survived findings: added `zoning_districts` rows for NCUC (jurisdiction 626, `category='mixed-use'`, `far_regulated=false`, `density_regulated=true`, Sec. 33-284.66-75) and T3-R (jurisdiction 855, `category='residential'`, `far_regulated=false`, `density_regulated=true`, Miami21 Art. 5 Illustration 5.3, with an exact `max_density_du_acre=9` from the ordinance table), then re-added their `parcel_zones` rows. Verified the 3 orphan folios' resulting zone codes (`RU-4L` unincorporated, `RMF4` Aventura) both already had fully-populated `zoning_districts`/`zone_standards` rows — zero regression risk — and added their `parcel_zones` + geo/value backfill. Live re-verify: **G held PASS (99.3, tiny expected dip from NCUC's honestly-NULL specific density value) — no regression. I at 94.9% (337/355)** — one parcel short of the gate.

### Fix 3 (`20260702_shard11_miami_dade_i_em_zoning_gate_close.sql`) — 337 → 338, gate crossed
The one remaining single-field gap was `33-5022-008-0170` (E-M, Palmetto Bay) — zoning only. Rather than use the refuter-rejected numbers, this session independently re-fetched `https://www.palmettobay-fl.gov/1674/E-M-Zoning-District` directly (HTTP 200) and confirmed verbatim: 15,000 sq ft minimum lot, 32% max lot coverage, 35 ft/2-story max height, no FAR mentioned anywhere. Added the jurisdiction, a `zoning_districts` row (`category='residential'`, `far_regulated=false`, `density_regulated=true`), and a `zone_standards` row with `max_density_du_acre=2.90` — derived by arithmetic from the confirmed 15,000 sq ft minimum lot (43,560/15,000), not guessed.

### After (final, live)
```json
{"A":{"pass":true,"metric":87},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":96.3},
 "D":{"pass":true,"metric":96.3},"E":{"pass":true,"metric":97.5},"F":{"pass":true,"metric":100.0},
 "G":{"pass":true,"metric":99.3,"detail":"density=99.3 far= pk1000="},
 "H":{"pass":true,"metric":2.1},"I":{"pass":true,"metric":95.2,"detail":"card_complete=338 of 355"},
 "J":{"pass":true,"metric":100.0},"county":"miami_dade","auctions_total":355}
```

**miami_dade is now honestly 10/10.**

| Letter | Session start | After fix 1 (+revert) | After fix 2 | After fix 3 (final) |
|---|---|---|---|---|
| I | FAIL (91.8%, 326/355) | FAIL (93.5%, 332/355) | FAIL (94.9%, 337/355) | **PASS (95.2%, 338/355)** |
| G | PASS (100.0) | PASS (99.6) — after self-caught regression to 0.0 and revert | PASS (99.3) | PASS (99.3) |
| A,B,C,D,E,F,H,J | PASS | PASS (unchanged) | PASS (unchanged) | PASS (unchanged) |

Residual, honestly unresolved (17 of 355 rows, not fabricated):
- 9 rows with no linkable parcel_id (multi-parcel/business-license case types)
- 2 rows (`2026-007470-CA-01` x2 sale_types) with an internally-inconsistent source address (NE-quadrant street name + Doral zip mismatch) — flagged as bad source data needing manual correction, not a lookup gap
- 4 condo-unit cases where only the parent building parcel (not the specific unit) could be confirmed, or the unit was genuinely ambiguous among multiple same-house-number buildings
- 1 case (`2026-001741-CA-01`, 601 Washington Ave Miami Beach) with a confirmed folio/geo but no confirmed valuation source

## ULTRALOOP audit trail
2 rows persisted to `gold_standard_ultraloop_audit` (`dispatch_id=7a6b2043-...`, `ultraloop_mode='native'`), letters I and G, both `survived=true`, with the live re-verification command/result and the full refuter chain embedded in `refuter_evidence`.

## Files
- `supabase/migrations/20260702_shard11_miami_dade_i_card_backfill.sql`
- `supabase/migrations/20260702_shard11_miami_dade_i_card_closeout.sql`
- `supabase/migrations/20260702_shard11_miami_dade_i_em_zoning_gate_close.sql`
- This report.

All committed and pushed directly to `main` per the SHIP-TO-MAIN mandate.
