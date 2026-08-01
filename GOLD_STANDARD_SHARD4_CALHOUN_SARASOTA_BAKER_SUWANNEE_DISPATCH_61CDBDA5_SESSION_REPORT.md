# Gold Standard Shard-4 Session Report — calhoun / sarasota / baker / suwannee

- dispatch_id: `61cdbda5-c47b-46e0-adca-64b627bbea64`
- github_issue: #17123
- loop_run_at_launch: 7858
- session window: 2026-08-01 08:00Z – 08:59Z
- mode: native ultracode Workflow orchestration (fix agents fanned out, each claim independently adversarially verified by a separate agent that did not write the fix; 2 suwannee claims lost from the automated aggregation by a pipeline-return bug were independently re-verified by the orchestrator directly against the live DB)

## Net result

| county | before (dispatch brief) | after (verified live) | delta |
|---|---|---|---|
| calhoun | 8/10 | 8/10 | 0 (B/F re-confirmed still genuinely blocked) |
| sarasota | 8/10 | 8/10 | 0 net, but composition changed: J FAIL→PASS, I PASS→FAIL (denominator grew 187→367 since the brief was generated, dropping an already-thin card-completeness margin below threshold) |
| baker | 6/10 | 6/10 | 0 net (E moved 33.3%→46.7%, still below 95% threshold) |
| suwannee | 4/10 | 6/10 | **+2 (C, D)** |
| **shard total** | **26/40** | **28/40** | **+2** |

## Before/after JSON (pasted from live `pencil_dod_evaluate_county` calls, re-run by the orchestrator independently of every fix agent)

### calhoun
```json
{"A":{"pass":true,"metric":2},"B":{"pass":false,"metric":null},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.2},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0}}
```
Unchanged from the dispatch brief. B/F re-probed fresh via `calhounclerk.com` WP REST API (foreclosures/taxdeeds/taxdeedoverbids) — zero closed sales across all 8 auctions, confirmed genuinely structurally blocked, no fabrication.

### sarasota
```json
BEFORE: {"J":{"pass":false,"metric":94.3},"I":{"pass":true,"metric":95.2}}
AFTER:  {"J":{"pass":true,"metric":98.6,"detail":"deal_complete=362"},"G":{"pass":false,"metric":66.7},"I":{"pass":false,"metric":94.6,"detail":"card_complete=347 of 367"}}
```
J flipped to PASS: 16 real `bid_decisions` rows inserted via genuine Shapira V14 XGBoost inference (non-constant `ml_score` distribution confirmed, not a placeholder). I regressed from the brief's snapshot (367 auctions now vs 187 at brief time) — 2 rows were parcel-linked this session but neither maps into the zoning crosswalk yet, so I stayed at 94.6% (need ~5 more rows). G re-confirmed structurally blocked: only 9 parking-applicable parcels fleet-wide methodology issue, unchanged, no fabrication attempted.

### baker
```json
BEFORE: {"C":{"pass":false,"metric":20.0},"D":{"pass":false,"metric":20.0},"E":{"pass":false,"metric":33.3},"I":{"pass":false,"metric":20.0}}
AFTER:  {"C":{"pass":false,"metric":20.0},"D":{"pass":false,"metric":20.0},"E":{"pass":false,"metric":46.7,"detail":"parcel_linked=7"},"I":{"pass":false,"metric":20.0}}
```
E moved via 2 verified cross-front-end backfills (baker.realtaxdeed.com sibling-row parcel_id/address/assessed_value copy). Remaining 8 unlinked rows genuinely unresolvable this session: bakerpa.com returned HTTP 521 three times live, bakerclerk.com 403 WAF, civitek OCRS Turnstile-gated, one case (`022026CA000007CAAXMX`) has a literal placeholder "Property Appraiser" text as its own source field.

### suwannee
```json
BEFORE: {"C":{"pass":false,"metric":40.0},"D":{"pass":false,"metric":40.0},"I":{"pass":false,"metric":40.0},"J":{"pass":false,"metric":40.0}}
AFTER:  {"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"I":{"pass":false,"metric":71.4,"detail":"card_complete=25 of 35"},"J":{"pass":false,"metric":74.3,"detail":"deal_complete=26"}}
```
**C and D flipped FAIL→PASS** (spot-checked case numbers 4677/4678/4679 directly by the orchestrator: `parity_status=matched_clean`, real `parcel_id` populated). I moved 40%→71.4% (12 rows enriched via realtaxdeed.com AJAX + Suwannee PA GSA-corp search + Census geocoder; 9 rows remain with no address posted yet by the source, 1 row failed 4 geocoding attempts and was left NULL rather than fabricated). J's dispatch-brief baseline (40%) was already stale at session start — live baseline was actually 74.3% (an earlier uncredited session had written 26 rows); 9 remaining case numbers have zero real ARV inputs (no assessed/market value, no address) and the generator correctly, idempotently skipped them rather than fabricate a value from `opening_bid` (a tax-delinquency figure, not a valuation).

## Genuinely-blocked letters (confirmed via fresh live re-check this session, not carried over from stale prior reports)

- **calhoun B/F**: 0 closed sales of 8 auctions, `calhounclerk.com` WP REST re-probed fresh.
- **suwannee B/F**: 0 closed sales of 35 auctions, RealForeclose/RealTaxDeed + clerk re-probed fresh against the grown dataset.
- **sarasota G**: 9 parking-applicable parcels fleet-wide (per-use-type parking regulation, not a fixed standard) — same structural finding as the prior SHARD-11 session, re-verified live, no fabrication.
- **baker C/D/I**: blocked on the same 8 unresolvable parcel-linkage rows (E's residual) — all 4 official sources unreachable/gated this session.
- **suwannee J**: 9 rows with no real valuation input from any available source.

## Adversarial verification

13 `gold_standard_ultraloop_audit` rows inserted (dispatch `61cdbda5-c47b-46e0-adca-64b627bbea64`, `ultraloop_mode='native'`), all `survived=true`. 11 via independent verifier subagents (never the agent that made the claim); 2 (suwannee C, suwannee D) via direct orchestrator re-verification after a workflow pipeline-aggregation bug dropped them from the automated verify fan-out — caught by re-reading the full agent transcripts rather than trusting the truncated aggregate result.

No anomalies detected (no B ratio outside 95–105% band, no PropertyOnion-sourced data counted as independent, no constant/placeholder ml_score).

## Scripts shipped (committed to main, commit `b8388927`)

- `scripts/suwannee_shard4_c40bb245_enrich_and_cd_parity.py`
- `scripts/suwannee_shard4_c40bb245_j_generator_extend.py`
- `scripts/suwannee_gold_shard_bf_fresh_reverify_20260801.py`
- `scripts/sarasota_shard4_9f070f2b_parcel_geo_link.py`
- `scripts/sarasota_shard4_9f070f2b_j_generator_extend.py`
- `scripts/baker_shard4_c_e_i_case_research_fix.py`

## Residual / next-session priorities

1. **suwannee I** (71.4%→need 95%): 9 rows blocked on source not having posted addresses yet for a 2026-09-03 sale — re-check closer to the sale date; 1 row (case 4704) needs a manual address-format fix for geocoding.
2. **sarasota I** (94.6%→need 95%, ~5 rows from threshold): 12 of 20 failing rows have no address at all (court-docket discovery needed, different pipeline than parcel-linking); the other 8 have a parcel_id but aren't in the zoning crosswalk yet — likely a G-adjacent zoning-coverage gap, not a geo problem.
3. **baker C/D/E/I**: all 4 official Baker County sources (PA, Clerk, OCRS) were unreachable/gated this session — retry when bakerpa.com recovers from its HTTP 521s.
4. **suwannee J** (74.3%→need 95%): 9 rows have zero real valuation source; revisit once/if suwannee I's address backfill lands for those same case numbers.
5. **sarasota G**: fleet-wide parking-methodology decision still open (shared with bay county per prior finding) — not a per-session fix.

## Close-out DB writes performed

- `gold_standard_campaign` (id=3446, dispatch `61cdbda5`): `criteria_passed` filled with real per-county A–J booleans, `criteria_total=40`, `exit_reason='timeout'`, `session_end_at` set to actual completion time.
- 13 rows into `gold_standard_ultraloop_audit`.
- Did not run `gold_standard_loop()`/`gold_standard_certify()` fleet-wide (other shards were mid-flight per PARALLEL-FLEET RULES) — per-county `pencil_dod_evaluate_county` used throughout instead.
