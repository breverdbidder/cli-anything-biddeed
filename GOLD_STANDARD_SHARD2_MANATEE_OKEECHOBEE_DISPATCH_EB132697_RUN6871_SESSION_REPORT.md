# Gold Standard Shard-2 — manatee + okeechobee (dispatch `eb132697-0dba-4430-81b3-6f8c67d9ccfb`, loop run 6871)

## Scoreboard: before -> after

| County | Before | After | Notes |
|---|---|---|---|
| manatee | 10/10 | 10/10 | Re-verified live, no change needed |
| okeechobee | 7/10 (C,D,I failing) | 10/10 | C, D, I fixed; G regressed then fixed inline |

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| manatee | Verify all 10 letters, no known gaps | Re-ran `pencil_dod_evaluate_county('manatee')`, confirmed all 10 PASS live, logged 10 fresh audit rows | None |
| okeechobee C/D | Reconcile parity to >=95% | Found and fixed the actual root cause (see below), reached 100% | Went deeper than "reconcile" — fixed the recurring cause, not just this cycle's symptom |
| okeechobee I | Enrich property cards to >=95% | Found + fixed real zoning linkage gap for 14 parcels via live GIS lookup, reached 100% | As planned |
| okeechobee G | Not in original scope (was passing) | Regressed by the I-fix, then corrected in the same session | Unplanned but required — see below |

## What happened

### C/D — root cause, not just symptom (verified evidence)
Okeechobee's `okeechobee.realforeclose.com` "foreclosure" lane actually serves a mix of sale types — live-scraped cards for cases 2026TD052/055/070/072/079/080/081 carry the source's own `Auction Type: TAXDEED` field, but `.github/scripts/calendar_sweep_mca.py` discarded that field and stamped every card in a sweep with the job's hardcoded `SALE_TYPE` env value (`foreclosure` for this lane). Since the upsert `on_conflict` key includes `sale_type`, every sweep cycle re-inserted a duplicate `foreclosure`-labeled row for cases a prior session had already clerk-verified and reclassified to `tax_deed`, undoing that fix and explaining why C/D had been flapping 94.2%->100%->94.2% across sessions per the audit trail.

Fix shipped: `.github/scripts/calendar_sweep_mca.py` now resolves `sale_type` from the card's real `Auction Type` field when it maps to a known value (`TAXDEED`->`tax_deed`, `FORECLOSURE`->`foreclosure`), falling back to the job's `SALE_TYPE` otherwise — a no-op for every county whose source already agrees with its lane. Committed `a0e46857`, pushed to `main` as `5281d84b`.

Data cleanup: deleted the duplicate `foreclosure`-labeled rows for the 7 affected cases (verified each had a more-complete, clerk-parity-matched `tax_deed` sibling row before deleting). **This had to be repeated three more times during the session** — a second, unidentified writer (rows land with `data_source=NULL`, `auction_type=NULL`, but `tier1_source_run_id`/`tier1_verified_at` set, distinct fingerprint from `calendar_sweep_mca.py`'s always-populated `data_source='calendar_sweep_mca_v3'`) recreated the same 7 duplicates at 17:50Z, 19:30Z, and 19:45Z — the last recreation was 5 minutes *after* the code fix was live on `main`, meaning the fix above only addresses one of (at least) two ingestion paths writing this data. County was clean as of the last check this session; **flagging this second path as the top open item for the next okeechobee session** (see Residual below).

### I — 14 parcels linked to real zoning via live GIS lookup
`card_complete` was 52/66 (78.8%) after the C/D dedup shrank the denominator. Diagnosed the gap as 14 auction parcels never linked in `parcel_zones` (zero rows, not a format mismatch). Reverse-engineered Okeechobee's zoning GIS (`gz.floridapa.com/mapserver`, `ol_themes.map`, 10 categorical WMS raster layers, point-in-polygon-by-pixel-fill since `GetFeatureInfo` is not queryable on this map) via one research agent, calibrated against a known DB-confirmed parcel/zone pair (reproduced `RSF` exactly), then resolved all 14 parcels' real zone codes. An independent adversarial-refuter agent reproduced the calibration plus 4 of the 14 claims (including the lowest-confidence boundary case) from scratch and confirmed all 5. Inserted 14 `parcel_zones` rows. `card_complete` reached 66/66 = 100%.

### G — regression caught and fixed in the same session
Adding the 14 parcels regressed G (far/pk1000 100%->66.7%) because one resolved zone (`zoning_ResidentialMultiFamily` layer) was labeled `RMF` — a label derived from the GIS layer name, not a real Okeechobee zoning code. Research confirmed Okeechobee County's actual LDC has **no** district named RMF or "Residential Multi-Family" (zero hits in a full district-list search); that label only exists in the separate City of Okeechobee municipal code. The county's real multi-family-permitting district is **RG (Residential, General)**, Sec. 2.04.03, max density 5.0 du/acre, explicitly not FAR-regulated (Sec. 2.01.05.A: FAR applies only to non-residential) and not given a fixed parking ratio (same pattern as RSF/RMH). Source: a third-party Municode mirror (zoneomics.com) since `library.municode.com` (403) and `elaws.us` (503) were both unreachable this session — recorded with `confidence_score=0.6` and an explicit honesty marker rather than claimed as primary-verified. Inserted the `RG` zoning_district + zone_standards rows and corrected the parcel's `zone_code` from `RMF` to `RG`. G returned to 100/100/100.

## Verification evidence (live RPC output, pasted verbatim)

Final `pencil_dod_evaluate_county('okeechobee')`:
```json
{"A":{"pass":true,"metric":17,"detail":"fc=49 td=17"},
 "B":{"pass":true,"metric":100.0,"detail":"verified=6 closed_sold=6"},
 "C":{"pass":true,"metric":100.0,"detail":"matched_clean=66"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=66"},
 "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=66"},
 "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=6 closed_sold=6"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000=100.0"},
 "H":{"pass":true,"metric":0.1,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":true,"metric":100.0,"detail":"card_complete=66 of 66"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=66 (...)"},
 "auctions_total":66}
```
Final `pencil_dod_evaluate_county('manatee')`: all 10 letters PASS, unchanged from session start (A=3, B=100, C=96.5, D=96.5, E=96.5, F=100, G=96.3, H=0.0, I=96.5, J=100, auctions_total=86).

4 `gold_standard_ultraloop_audit` rows logged for okeechobee (C, D, I, G) with refuter evidence and `survived=true`; manatee's 10 pre-existing fresh audit rows (this same dispatch, earlier in the session) already cover all 10 letters.

Per PARALLEL-FLEET RULES, did **not** run `gold_standard_loop()`/`gold_standard_certify()` fleet-wide — other shards' work is clearly interleaved with this county's data in real time (see Residual below), so only per-county `pencil_dod_evaluate_county` was used.

## Residual / open items for next session
1. **TOP PRIORITY**: a second writer path independently recreates the same 7 okeechobee duplicate rows (fingerprint: `data_source=NULL`, `auction_type=NULL`, `tier1_source_run_id` set, `source_platform=realforeclose`, `provenance=primary_scrape`) roughly every 15–100 minutes. Not `calendar_sweep_mca.py` (which always sets `data_source='calendar_sweep_mca_v3'`). Investigated `continuous-executor.yml` (every-30-min task-queue dispatcher), `calendar-sweep-{dark,gap}-counties.yml` and `calendar-sweep-mcp-remaining.yml` (all last ran this morning, not in the afternoon window) without finding the trigger. County was left clean (10/10) as of the last check, but will likely flap again until this second path is found and fixed the same way C/D was.
2. G's `RG` district standards are sourced from a third-party Municode mirror (zoneomics.com) because the primary source was unreachable this session (403/503) — worth re-verifying against `library.municode.com` directly once it's reachable, though the values are internally consistent with sibling districts already in the DB.
3. Given the residual above, do not certify okeechobee off this session's snapshot alone — re-run `pencil_dod_evaluate_county('okeechobee')` fresh at the start of the next session before trusting 10/10.
