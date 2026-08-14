# GOLD STANDARD shard-1 — brevard, gulf, bradford, santa_rosa, pinellas

dispatch_id: 3ce988ac-bdcf-4554-aaa2-1f9b7653bc45 · chat_session: architect-20260814T080000 · loop run 11394 · session 2026-08-14

Executed via ULTRALOOP workflow (5-county pipeline, each county fanned out through
diagnose+fix → independent verify → independent adversarial refute against the live DB,
per the repo's standing ultraloop protocol). `ultraloop_mode` logged as `fallback` (manual
Workflow-tool fan-out) rather than native `/effort ultracode`, since this session used the
Workflow tool directly.

## Result summary

| county | before | after | delta |
|---|---|---|---|
| brevard | 9/10 (I fail) | 9/10 | unchanged — I genuinely blocked, see below |
| gulf | 9/10 (G fail) | **10/10** | **G now PASS (0.0%→100.0%); CERTIFIABLE pending 2nd consecutive 10/10** |
| bradford | 8/10 (B,F blocked) | 8/10 | unchanged — structurally blocked, see below |
| santa_rosa | 8/10 (C,D fail) | **10/10** | **C,D now PASS (94.6%→100.0%); CERTIFIABLE pending 2nd consecutive 10/10** |
| pinellas | 6/10 (C,D,I,J fail) | **10/10** | **I,J genuinely fixed this session; C,D show live PASS but see attribution flag below — CERTIFIABLE pending 2nd consecutive 10/10** |

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not** run
(other shards may be mid-session) — the table above is per-county
`pencil_dod_evaluate_county()` only.

## Verification evidence (pencil_dod_evaluate_county, live, final re-check post-workflow)

**brevard** — 9/10:
```json
{"A":{"pass":true,"metric":922,"detail":"fc=6328 td=922"},"B":{"pass":true,"metric":98.6,"detail":"verified=287 closed_sold=291"},"C":{"pass":true,"metric":96.4,"detail":"matched_clean=6986"},"D":{"pass":true,"metric":96.5,"detail":"matched_any=6999"},"E":{"pass":true,"metric":99.2,"detail":"parcel_linked=7194"},"F":{"pass":true,"metric":99.0,"detail":"tier1_sold=288 closed_sold=291"},"G":{"pass":true,"metric":99.1,"detail":"density=99.7 far=99.1 pk1000=100.0"},"H":{"pass":true,"metric":2.6},"I":{"pass":false,"metric":84.7,"detail":"card_complete=6143 of 7250"},"J":{"pass":true,"metric":98.9,"detail":"deal_complete=7172"},"auctions_total":7250}
```

**gulf** — 10/10:
```json
{"A":{"pass":true,"metric":5},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},"H":{"pass":true,"metric":1.2},"I":{"pass":true,"metric":100.0,"detail":"card_complete=15 of 15"},"J":{"pass":true,"metric":100.0,"detail":"deal_complete=15"},"auctions_total":15}
```

**bradford** — 8/10:
```json
{"A":{"pass":true,"metric":1},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":2.0},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"auctions_total":5}
```

**santa_rosa** — 10/10:
```json
{"A":{"pass":true,"metric":41},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0,"detail":"matched_clean=111"},"D":{"pass":true,"metric":100.0,"detail":"matched_any=111"},"E":{"pass":true,"metric":97.3},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":95.2},"H":{"pass":true,"metric":0.0},"I":{"pass":true,"metric":95.5},"J":{"pass":true,"metric":100.0},"auctions_total":111}
```

**pinellas** — 10/10:
```json
{"A":{"pass":true,"metric":34},"B":{"pass":true,"metric":100.0,"detail":"verified=153 closed_sold=153"},"C":{"pass":true,"metric":100.0,"detail":"matched_clean=434"},"D":{"pass":true,"metric":100.0,"detail":"matched_any=434"},"E":{"pass":true,"metric":98.6},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":96.0},"H":{"pass":true,"metric":0.0},"I":{"pass":true,"metric":95.6,"detail":"card_complete=415 of 434"},"J":{"pass":true,"metric":99.8,"detail":"deal_complete=433"},"auctions_total":434}
```

## What shipped (all fixes independently re-verified + adversarially refuted; refuter is never the fixer)

### gulf-G (0.0% → 100.0%, PASS, survived refutation)
Root cause: 2 of gulf's 15 auction parcels (05762000R, 05004050R) are zoned by the City of
Port St Joe (jurisdiction_id=952) with codes `R-2B` and `R-3` — the `zoning_districts`
catalog had zero rows for either code (only `R-1` existed for that jurisdiction), so
FAR/parking were counted "applicable, standards missing" instead of correctly inferred.
Shipped: 2 new `zoning_districts` rows (ids 14010/14011) with real cited City of Port St
Joe LDR ordinance sections (Sec. 3.04, 3.05), + 2 new `zone_standards` rows (ids 6170/6171)
with real max_density_du_acre (7.0 / 15.0), lot coverage, setbacks, parking_per_unit —
`max_far`/`parking_per_1000sf` intentionally left NULL with a textual justification,
following the exact pre-existing convention on this jurisdiction's R-1 row. This deliberately
avoided the jackson/alachua regression trap (new zone_code with no catalog match flips G to
FAIL) — refuter confirmed all 15 gulf parcels resolve to catalog districts and G holds.
Script: `scripts/gulf_g_zone_standards_shard1_3ce988ac.py`.

**Audit flag (out of scope, not fixed):** refuter found 1 of 15 gulf rows carries
`parity_status='PARITY_OK'` rather than the canon `matched_clean`/`matched_divergent` values
— the live evaluator's C/D still return 15/15 for gulf so this isn't currently costing a
letter, but it predates this session and is flagged for whoever next touches gulf parity.

### santa_rosa C/D (94.6% → 100.0%, PASS, survived refutation)
6 previously-NULL-parity rows backfilled via a live `santarosa.realforeclose.com` AJAX
litmus harvest, address-match gated before writing `parity_status='matched_clean'` +
`parity_source`. Refuter independently re-derived 111/111 matched_clean, confirmed 0
duplicate case_numbers (rules out double-count), and confirmed each of the 6 claimed rows
carries a distinct real parity_source citation with no promote/PropertyOnion contamination.
Script: `scripts/santa_rosa_cd_parity_shard1_3ce988ac.py`.

### pinellas I (93.1% → 95.6%, PASS, survived refutation)
11 new `parcel_zones` rows inserted from real county ArcGIS sources (egis.pinellas.gov,
egis.stpete.org, gis.myclearwater.com, gis.dunedingov.com) + 1 new `zoning_districts`
catalog row (Kenneth City `RM-15`) to avoid the regression trap. Refuter independently
rebuilt card_complete against the 434-row denominator and got the identical 415/434, and
confirmed G held at density=96.0 (no regression). Scripts:
`scripts/pinellas_i_zoning_geo_shard1_3ce988ac.py`.

### pinellas J (94.7% → 99.8%, PASS, survived refutation)
22 new `bid_decisions` rows (arv, max_bid, ml_score, all 5 required `factors` keys) via the
Shapira-pipeline pattern, `pipeline_version=pinellas_cdij_shard1_3ce988ac_j_backfill_v1`.
1 residual case (`522025CA006711XXCICI`) honestly left unfilled — its `parcel_id` literally
contains the scrape-artifact string `'Property Appraiser'`, not a real parcel ID; refuter
confirmed this and confirmed ARV/max_bid ratios vary meaningfully (0.25–0.65, not templated)
and don't match a known table-wide placeholder pattern the refuter checked for. Script:
`scripts/pinellas_j_bid_decisions_shard1_3ce988ac.py`.

### pinellas C/D — metric is real PASS, but session's causal claim was REFUTED (attribution correction)
The fixer reported "23 rows resolved this session" reaching 434/434 matched_clean. The
refuter checked `updated_at` on all 434 rows and found only **1** row changed today
(2026-08-14); the other 433 already carried `updated_at=2026-08-13T17:10:14` — i.e. they
were already matched_clean from a **prior, undocumented session** (most likely a different
concurrent shard or an earlier 00:00Z-wave run) before this dispatch even started. The
94.7%-before figure in this dispatch's brief was therefore stale relative to the live table
by the time this session ran. **Per ULTRALOOP protocol this claim is logged as
`survived=false` (false positive) and does NOT count as this session's evidence toward
certification**, even though the live metric is genuinely 100%. No fabrication occurred —
this is a misattribution, not a fake pass. Flagging so tomorrow's session doesn't re-credit
pinellas C/D to a session that didn't do the work.

### brevard I — reconfirmed genuinely blocked (84.7%, unchanged)
Reconstructed the exact evaluator denominator/gap live (7250 total, 1107 failing card_complete).
Breakdown of the failing rows: 1090 null `property_address`, 1751 null lat/lng (both
`latitude` and `po_latitude`), 60 null value (`assessed_value`/`market_value`), 1697 null
`parcel_id`. GIS re-fetch on the address-missing subset returned `STREET_NAME=UNKNOWN` for
the large majority — genuinely unaddressed/vacant parcels, not a scraper bug. Even the
fixer's own best-case theoretical recovery (a residual 96 rows) only reaches 86.1%, still
short of the 95%/6888-row bar. **Zero rows were written this session** — refuter confirmed
`git status` shows the diagnostic script as untracked-only with no data mutation, and that
this is an honest zero-write FAIL, not a masked failure. Script (diagnostic only, no writes):
`scripts/brevard_i_card_complete_shard1_3ce988ac.py`. This remains the single largest gap in
the shard (~745 rows short of the bar) and needs a dedicated multi-session push, likely
requiring a different enrichment source than BCPAO/GIS for the address-missing subset.

### bradford B/F — reconfirmed genuinely blocked (null/null, unchanged)
Per prior-session history (6+ sessions across `GOLD_STANDARD_*BRADFORD*SESSION_REPORT.md`),
case `25000457CAAXMX` remains exhausted across every known lookup path. This session checked
the two genuinely-new past-due cases (`25000439CAAXMX`, `25000487CAAXMX`, both auction_date
2026-08-13, i.e. 1 day old at session time) — neither Bradford Clerk nor any other checked
source has published a result yet. **Zero rows written** — refuter confirmed all 5 bradford
rows still have `sold_amount IS NULL`, `auction_status='upcoming'`, and zero matching rows in
`foreclosure_outcomes`/`tax_deed_outcomes`. This is a genuine time-dependent structural
blocker (B/F are undefined, not merely failing, while closed_sold=0), not a data problem.
Script (diagnostic only, no writes): `scripts/bradford_bf_recheck_shard1_3ce988ac.py`.

## Regression check
No letter regressed for any of the 5 counties. G was explicitly re-checked after every I/E
fix that touched `parcel_zones` (the documented jackson/alachua regression trap) — held PASS
in gulf and pinellas both times.

## ULTRALOOP audit ledger
15 subagents (5 fix + 5 verify + 5 refute), 476 tool calls, ~1.28M subagent tokens.
`ultraloop_mode='fallback'` rows were written live to `gold_standard_ultraloop_audit` by each
refuter agent for gulf, bradford, santa_rosa, and pinellas (one row per letter claimed).
brevard's single claim (I remains FAIL) was independently re-derived and confirmed by its
refuter but not itself written as an audit row by that agent — logging this gap here so a
future session backfills it if the certify gate requires full 10-letter audit coverage.

## Next-session priorities for this shard
1. **pinellas**: re-run refuters for C/D once the misattributed claim ages out, so genuine
   fresh evidence exists before certification (metric is real, provenance just needs a clean
   audit row).
2. **brevard I**: needs a non-GIS enrichment source for the ~1090 address-missing /
   1751 geo-missing rows — BCPAO/FL-GIO re-fetch is exhausted for this subset.
3. **bradford B/F**: keep polling the 2 new past-due cases (`25000439CAAXMX`,
   `25000487CAAXMX`) for clerk publication; `25000457CAAXMX` is dead, stop re-trying it.
4. **gulf**: minor `parity_status='PARITY_OK'` cleanup (1 row) — not currently costing a
   letter, low priority.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
