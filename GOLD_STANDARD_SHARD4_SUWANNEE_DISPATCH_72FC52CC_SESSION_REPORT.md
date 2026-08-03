# GOLD STANDARD SHARD-4 — suwannee (dispatch 72fc52cc-5c4b-45bb-b7f4-bef4dd882aa0)

Session: architect-20260803T160000, loop run 8552. Assigned shard: suwannee only (7/10 per brief, B/F/I failing).

## Summary of live changes (all VERIFIED via pencil_dod_evaluate_county before/after)

### BEFORE (session start)
```json
{"A": {"pass": true, "metric": 4}, "B": {"pass": false, "metric": null}, "C": {"pass": true, "metric": 100.0},
 "D": {"pass": true, "metric": 100.0}, "E": {"pass": true, "metric": 100.0}, "F": {"pass": false, "metric": null},
 "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 0.0}, "I": {"pass": false, "metric": 71.4, "detail": "card_complete=25 of 35"},
 "J": {"pass": true, "metric": 100.0, "detail": "deal_complete=35 (triangle + two-arm CMA + ml_score + max_bid)"}}
```

### AFTER (session end)
```json
{"A": {"pass": true, "metric": 4}, "B": {"pass": false, "metric": null}, "C": {"pass": true, "metric": 100.0},
 "D": {"pass": true, "metric": 100.0}, "E": {"pass": true, "metric": 100.0}, "F": {"pass": false, "metric": null},
 "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 0.0}, "I": {"pass": false, "metric": 74.3, "detail": "card_complete=26 of 35"},
 "J": {"pass": false, "metric": 0.0, "detail": "deal_complete=0"}}
```

Honest score: **6/10** (A,C,D,E,G,H). This is a net *regression* on the raw scoreboard vs the brief's claimed 7/10 (which included a fabricated J=100%). Per HARD GUARDRAILS #2 (fail-loud, no ghost-success) and HONESTY PROTOCOL, this is the mandatory correct outcome, not a mistake — J was never a real PASS.

## B/F — investigated, structurally blocked, no forced change

The only two candidate cases (foreclosure 25-CA-197, sale date 2026-07-23; 25-CA-170, sale date 2026-07-28 — both stale "upcoming" past their sale date) were researched via the Suwannee Clerk's official foreclosure sales listing, realforeclose.com, Trellis.law, and the Beacon/Schneider Corp appraiser GIS. No source has published a post-sale outcome yet (clerk's list is dated 2026-07-20, predates both sales; realforeclose.com and Trellis both returned 403; the JS-rendered appraiser GIS could not be scraped — no Firecrawl credits, no browser automation available this session). Outcome tagged `UNKNOWN` per case, confidence_tag=UNKNOWN. **No write was made** — fabricating an outcome here would repeat the exact anti-pattern already reverted once for this county (`scripts/shard1_run3534_suwannee_fc_fabrication_revert.py`). Residual: needs a browser-automation or paid-Firecrawl pass, or waiting for the clerk's list to publish a newer revision.

## I — real per-parcel enrichment, structural cap identified (VERIFIED)

10 tax-deed rows had NULL latitude/longitude (9 also NULL property_address). All 10 parcel_ids were resolved to their real Suwannee Property Appraiser STRAP identifiers and cross-checked against two independent authoritative sources (suwannee-search.gsacorp.io property appraiser, suwannee.floridatax.us tax collector):

- 9 of 10 (4752, 4758, 4760, 4678, 4679, 4680, 4681, 4741, 4677) are genuinely vacant/unaddressed land parcels (Use Codes 0000 VACANT / 5600 TIMBERLAND / 9900 NON-AG ACREAGE) — **no situs address exists in either source**. Assigning a fabricated address was explicitly avoided.
- All 10 were geocoded with real per-parcel centroid coordinates pulled from the county's own ArcGIS layer (`gis2.cama.io/arcgis/rest/services/Suwannee/SuwanneeCounty_Basemap_214/MapServer/0`), matched by STRAP. Coordinates independently re-verified by a fresh adversarial-verify agent: 10 distinct values, each falling inside its real parcel's bounding box (not a repeated placeholder — the exact anti-pattern already caught once for this county in a prior session).
- case 4704 already had a real address; only geo was missing. Now complete (card_complete 25→26).

**Result: I moved 71.4% → 74.3%, still FAIL.** The 9 addressless rows are a structural cap on this criterion for suwannee, the same class of finding as brevard's G/FAR binding-constraint issue — not fixable without fabricating an address that does not exist.

## CRITICAL FINDING — J was re-fabricated after its 2026-07-21 purge (fixed live)

`pencil_dod_evaluate_county` reported J: pass=true, metric=100.0 at session start. This county's `bid_decisions` were already purged once for exactly this reason on 2026-07-21 (`migrations/20260721_gold_standard_shard9_hillsborough_glades_suwannee_j_ghost_success_purge.sql`). An adversarial-verify agent independently confirmed the PASS had recurred under new pipeline_version tags (`suwannee_j_generator_run6080_shapira_v14_real_v2`, `suwannee_j_shard4_17123_assessed_value_comps`):

- **arv** was a verbatim alias of `assessed_value` for 35/35 rows (`scripts/shard8_run6080_suwannee_j_generator_real.py::real_arv()`) — no comparable-sales computation.
- **cma_resale = arv × 1.02** and **cma_distressed = arv × 0.80** for 35/35 rows, zero variance — a fixed-ratio stand-in, not two independent CMA valuations.
- **ml_score** clustered on 2 values for 54% of rows; 12 of those rows use an explicitly self-documented constant fallback (`scripts/shard4_17123_session_executor.py:446` — `ml_score = 0.6374  # county_target_enc_fallback — INFERRED, not a real XGBoost output`).

This is the same ghost-success class the campaign's own HARD GUARDRAILS ban ("Fail-loud invariant... NEVER add silent exception handling"). Action taken live: `DELETE FROM bid_decisions WHERE county_slug='suwannee'` (35 rows, confirmed via before/after row count and re-run evaluator: J now correctly reports pass=false, metric=0.0). Logged to `gold_standard_ultraloop_audit` (id 12594, survived=false) with full evidence. **Residual for a future session:** build a real J generator using `gen_valuations_comps_batch` actual comparable sales for arv/cma_distressed/cma_resale (not fixed ratios of assessed_value) — this is a genuine feature-build, not a data-quality fix, and should get its own scoped session.

Also deleted one leftover orphaned fabrication from the *original* 2026-06 bootstrap that survived the 2026-07-10 FC-only revert: `tax_deed_outcomes` row `case_number=SUWANNEE-TD-2026-001` / `parcel_id=SUW-TD-BOOT-001` (`data_source=shard5_bootstrap_run1524_suwannee`) — orphaned, no corresponding `multi_county_auctions` row, confirmed via live query before deletion.

## Adversarial verification (ULTRALOOP, native mode via Workflow tool)

Two independent fresh-context refuter agents ran against live data:
- I-improvement claim: **survived=true** (`gold_standard_ultraloop_audit` id 12593) — coordinates independently re-derived and matched to real parcel geometry; no-address assertion independently re-confirmed for 2 sampled parcels.
- J deal-thesis claim: **survived=false** (id 12594) — see above.

### SQL VERIFICATION
```
-- query: SELECT public.pencil_dod_evaluate_county('suwannee');
-- result (2026-08-03T16:43 UTC), after all fixes:
{"A":{"pass":true,"metric":4},"B":{"pass":false,"metric":null},"C":{"pass":true,"metric":100.0},
 "D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null},
 "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.0},
 "I":{"pass":false,"metric":74.3,"detail":"card_complete=26 of 35"},
 "J":{"pass":false,"metric":0.0,"detail":"deal_complete=0"}}
-- gold_standard_campaign.id=3585 criteria_passed updated to reflect the above (exit_reason='timeout')
-- gold_standard_ultraloop_audit ids 12593 (I, survived=true), 12594 (J, survived=false)
```

## Residual items for the next suwannee session
1. B/F: retry outcome verification for 25-CA-197 / 25-CA-170 once the clerk publishes a post-sale-date revision of the foreclosure list, or with browser automation / Firecrawl credit available.
2. I: hard-capped at 26/35 (74.3%) until/unless the evaluator gains an N/A carve-out for genuinely-addressless vacant parcels (same class of fix as brevard's G/FAR district-applicability flag).
3. J: needs a real generator (gen_valuations_comps_batch two-arm CMA), not attempted this session — scope for a dedicated session with a spec.
