# Gold Standard SHARD-13: lee — session report

dispatch_id: `850748bb-e511-4a3d-bfe5-3714665723b5`
chat_session: `architect-20260731T000000`
workflow run: `wf_f6c41622-17b` (ULTRALOOP native, 8 subagents: 2 fix, 2 research, 1 register-link, 3 adversarial verify)

## Scope

Shard-13 assigned only `lee`, already 8/10 (A,B,C,D,F,G,H,J PASS). Targets: **E** (parcel linkage) and **I** (property card completeness), the critical-three list includes neither for this county, but both are structurally coupled (I depends on E + zone-link).

## Before / after (live `pencil_dod_evaluate_county('lee')`)

| Letter | Before | After | Gate | Status |
|---|---|---|---|---|
| A | PASS 40 | PASS 40 | — | unchanged |
| B | PASS 100.0 | PASS 100.0 | — | unchanged |
| C | PASS 98.8 | PASS 98.8 | — | unchanged |
| D | PASS 98.8 | PASS 98.8 | — | unchanged |
| **E** | **FAIL 91.3** (294/322) | **FAIL 92.9** (299/322) | 95 | **improved, still FAIL** |
| F | PASS 100.0 | PASS 100.0 | — | unchanged |
| G | PASS 100.0 | PASS 100.0 | 95 | unchanged, regression-checked |
| H | PASS 0.1 | PASS 0.0 | — | unchanged |
| **I** | **FAIL 85.7** (276/322) | **FAIL 87.0** (280/322) | 95 | **improved, still FAIL** |
| J | PASS 100.0 | PASS 100.0 | — | unchanged |

**8/10.** No regression on any of the 8 previously-passing letters (independently re-verified live, not assumed).

## What moved E (+5 rows, 294→299)

Lee County ArcGIS FeatureServer SITEADDR lookup for 5 new-address rows that hadn't been attempted by any prior lee session (25-CA-002165, 25-CA-005615, 25-CA-006129, 25-CA-003367, 25-CA-003581). Each got parcel_id + lat/lng + assessed_value backfilled from a single confident ArcGIS match. Full detail and source STRAPs in the migration file.

**Not fixed, documented honestly (no guesses):**
- 25-CA-002593: real match found, blocked by a `uq_mca_county_sale_date_parcel` unique-constraint collision with case 25-CA-003385 (duplicate-case data issue, needs a dedup decision).
- 25-CA-004959: resolves to an unnumbered unit in a ~140-unit condo building; only unit-less ArcGIS match is a $0-assessed common-element parcel, not a real match.
- 4 rows (20-CA-005572, 24-CC-004249, 18-CC-004510, 25-CA-007100): **re-confirmed unfixable for the 3rd consecutive session** — addresses genuinely don't exist in Lee's ArcGIS layer at the claimed house numbers/street names.
- 16 rows: no property_address at all (calendar_sweep_mca_v3), blocked on Lee Clerk 403/Akamai + Firecrawl no-credit, same wall every prior session — needs a new data source, not another ArcGIS attempt.

## What moved I (+4 rows, 276→280)

4 parcels that already carry a zone code **already registered** in `zoning_districts`/`zone_standards` (R1@815 ×2, RS-1@630 ×1, plus one already-zone-linked row missing only geo) — zero G-metric risk since no new district rows were created. All backfilled via live-verified ArcGIS lat/lng (+parcel_zones insert where needed, dedupe-checked first).

## What did NOT move I, and why (correct, not a failure)

Two research agents found real Lee/Fort-Myers-Beach/Bonita-Springs LDC text for 6 zone codes blocking 6 more rows (CPD, CS, RS-2 @ unincorporated Lee; MH-1 @ Bonita Springs; RS-1, RM-2 @ Fort Myers Beach) — but **none had a confirmable published numeric value** for the dimension that would need to be `regulated=true` (CPD/CS are project-specific or coverage-regulated, not density/FAR-table districts; RS-2 has a lot-size standard but no published density figure; MH-1 has no density/parking row in its standards table; RS-1/RM-2 are legacy codes superseded by a 2003 town-wide rezoning). The registration agent **declined all six** rather than insert a guessed number — correctly, per this project's BLANK>WRONG rule and the explicit prohibition on ghost-success G-denominator entries. This is a genuine structural gap (some FL zoning districts don't have a fixed per-district density/FAR table), not something more ArcGIS querying will resolve — see Next Session Priorities below for the actual unblock.

## Adversarial verification (ULTRALOOP)

3 independent refuter agents re-queried the DB fresh (not trusting the fix agents' self-reports):
- **E-fix**: all 5 claimed writes CONFIRMED (real STRAP format, FL lat/lon bounds).
- **I-safe-fix**: all 5 claimed writes CONFIRMED (lat/lng bounds, exactly-one parcel_zones row per parcel, correct zone_code/jurisdiction).
- **Register-link + G-regression gate**: the refuter initially flagged a false "undisclosed write" — both the I-safe-fix agent and the register-link agent were given the identical `source='lee_arcgis_2026_shard13'` tag in my workflow prompts, so the refuter attributed the (already-separately-verified) I-safe-fix writes to the register-link agent's claim. Not a double-write or fabrication — confirmed by cross-checking against the independently-CONFIRMED I-safe-fix verification. **The actual purpose of that gate — checking for a silent G regression — came back clean**: `v_zoning_gold_standard_kpi_v3` and a fresh `pencil_dod_evaluate_county` both showed density/far/pk1000 = 100.0/100.0/100.0, matching the documented pre-session baseline exactly.
- Lesson for future ultraloop workflows: give every parallel fix/register agent a **distinct** source tag, even when they touch related rows, so refuters don't need to cross-attribute.

All 3 survival votes logged to `gold_standard_ultraloop_audit` (dispatch `850748bb-e511-4a3d-bfe5-3714665723b5`, letters E/G/I, `survived=true`).

## SQL VERIFICATION

```sql
-- run 2026-07-31T00:35 UTC via POST rpc/pencil_dod_evaluate_county {"p_county":"lee"}
```
```json
{"A":{"pass":true,"metric":40,"detail":"fc=282 td=40"},
 "B":{"pass":true,"metric":100.0,"detail":"verified=20 closed_sold=20"},
 "C":{"pass":true,"metric":98.8,"detail":"matched_clean=318"},
 "D":{"pass":true,"metric":98.8,"detail":"matched_any=318"},
 "E":{"pass":false,"metric":92.9,"detail":"parcel_linked=299"},
 "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=20 closed_sold=20"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000=100.0"},
 "H":{"pass":true,"metric":0.0,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":87.0,"detail":"card_complete=280 of 322"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=322"},
 "county":"lee","auctions_total":322}
```

## Next session priorities

1. Resolve the 25-CA-002593 / 25-CA-003385 duplicate-tuple collision so the already-confirmed ArcGIS match can be written (E +1).
2. Condo-unit matching strategy for 25-CA-004959-style rows (unit number missing from auction record).
3. **Policy decision needed**: how should the G/I formula treat Planned-Development (CPD-style, project-specific) and legacy-superseded (RS-1/RM-2@912-style) zone codes that structurally have no fixed per-district density/FAR/parking table? Either explicitly exclude them from the applicable-parcel denominator (same treatment as conservation/CON districts) or accept I cannot reach 95% for lee without one. Re-running the same ordinance search next session will find the same answer.
4. The 16-row no-address bucket is the single largest remaining E gap, blocked on Lee Clerk 403/Akamai + Firecrawl no-credit across at least 3 sessions now — needs a genuinely new data source (authenticated session, alternate clerk portal, or court-record API), not another ArcGIS pass.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
