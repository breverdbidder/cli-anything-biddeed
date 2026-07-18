# Gold Standard Shard-1 Session Report — dispatch c40bb245-4b9f-475a-a7c7-648a09e836c2

Shard: brevard, pinellas, orange, suwannee, collier. Mode: ULTRALOOP (native Workflow tool, fixer≠verifier for every claim).

## Plan vs Actual

| County | Planned | Actual | Deviation |
|---|---|---|---|
| brevard | already 10/10 per brief; log missing audit trail | confirmed 10/10 live, fresh audit rows for all 10 letters (C/G re-verified after a same-day fix landed after the last scoreboard snapshot) | none — pure audit, no fix needed |
| pinellas | brief said G FAIL 0.0; audit cert-gap | G was already fixed before this session started (live=98.9%); real gap was 9/10 letters missing ultraloop_audit rows, blocking certification even though scoreboard shows gold_standard=true | brief was stale; pivoted to cert-gap audit as planned once discovered |
| orange | fix C/D (79.8%→PASS), fix I (93.1%→PASS) | C/D fixed to 100%; I fixed to 95.1%; **caused a G regression (PASS→FAIL) as a side effect, caught and fixed in a follow-up pass** | unplanned regression, remediated same session |
| suwannee | fix A/B/F | confirmed all 3 are a genuine dead-end (no online FC lane exists, RealAuction never built one; B/F are 0-closed-auctions long-accrual) — no fix possible, none attempted | matches brief's own "long-accrual, don't idle" guidance |
| collier | fix A, G, I | A confirmed still blocked (reCAPTCHA SPA, in-person-only, no CAPTCHA bypass attempted); G: 2 districts researched, 1 real value kept (RMF-6 density), 1 **fabricated value caught and reverted**; I: real root-cause fix moved 38.2%→89.6% (still FAIL) | G/I real progress but neither reaches PASS this session |

## Verification protocol — before/after `pencil_dod_evaluate_county`

**BEFORE** (session start, 2026-07-18 ~17:50 UTC):
```
brevard:  10/10 PASS
pinellas: 10/10 PASS (but only 1/10 letters had an audit-log row — certify-gate blocked)
orange:   8/10  — C=79.8 FAIL, D=79.8 FAIL, I=93.1 FAIL, rest PASS
suwannee: 7/10  — A=0 FAIL, B=null FAIL, F=null FAIL, rest PASS
collier:  7/10  — A=0 FAIL, G=0.0 FAIL, I=38.2 FAIL, rest PASS
```

**AFTER** (session end, 2026-07-18 ~18:30 UTC, independently re-verified):
```json
brevard:  {"A":{"pass":true,"metric":906},"B":{"pass":true,"metric":98.6},"C":{"pass":true,"metric":95.3},"D":{"pass":true,"metric":95.3},"E":{"pass":true,"metric":99},"F":{"pass":true,"metric":98.9},"G":{"pass":true,"metric":98},"H":{"pass":true,"metric":0.4},"I":{"pass":true,"metric":96.1},"J":{"pass":true,"metric":99.3}} -- 10/10
pinellas: {"A":{"pass":true,"metric":34},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":97.4},"D":{"pass":true,"metric":97.4},"E":{"pass":true,"metric":99.7},"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":98.9},"H":{"pass":true,"metric":3.3},"I":{"pass":true,"metric":96.1},"J":{"pass":true,"metric":100}} -- 10/10, audit gap closed
orange:   {"A":{"pass":true,"metric":321},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":100},"D":{"pass":true,"metric":100},"E":{"pass":true,"metric":99.1},"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":98.3},"H":{"pass":true,"metric":3.3},"I":{"pass":true,"metric":95.1},"J":{"pass":true,"metric":100}} -- 8/10 -> 10/10
suwannee: {"A":{"pass":false,"metric":0},"B":{"pass":false,"metric":null},"C":{"pass":true},"D":{"pass":true},"E":{"pass":true},"F":{"pass":false,"metric":null},"G":{"pass":true},"H":{"pass":true},"I":{"pass":true},"J":{"pass":true}} -- 7/10, unchanged (genuinely blocked)
collier:  {"A":{"pass":false,"metric":0},"B":{"pass":true},"C":{"pass":true},"D":{"pass":true},"E":{"pass":true},"F":{"pass":true},"G":{"pass":false,"metric":0,"detail":"density=9.6 far=0.0 pk1000=0.0"},"H":{"pass":true},"I":{"pass":false,"metric":89.6},"J":{"pass":true}} -- 7/10, real progress (G/I moved but not enough)
```

Full JSON pasted from live `SELECT public.pencil_dod_evaluate_county(...)` calls, re-run independently by refuter agents (not just the fixer) — see `gold_standard_ultraloop_audit` rows for `dispatch_id=c40bb245-4b9f-475a-a7c7-648a09e836c2`.

## What shipped

- `scripts/gs_shard1_c40bb245_orange_cd.py` — orange C/D parity backfill (AJAX harvest of myorangeclerk.realforeclose.com + orange.realtaxdeed.com, forked from the leon/duval/shard2 pattern). 173 rows promoted matched_clean, reconciled exactly against the 682 pre-existing (682+173=855, zero overlap).
- `scripts/gs_shard1_c40bb245_orange_i.py` — orange I card-completeness fix. Root cause: parcel_zones only covered Orange Unincorporated, zero coverage for 12 incorporated municipalities. Inserted 17 GIS-sourced parcel_zones rows (16 via Orange GIS ArcGIS point-in-polygon, 1 via Census Bureau geocode).
- `scripts/gs_shard1_c40bb245_collier_i.py` — collier I fix. Root cause: property_address NULL on 117/212 rows (not zone_code as hypothesized). Backfilled 109 via FL DOR statewide cadastral FeatureServer city/zip fallback (real source, lower-fidelity, documented). 8 remain unmatched in the source, left NULL.
- Orange G regression fix (no script file — done via direct, cited SQL writes): the orange_i fix above introduced 10 parcel_zones rows under 5 zone codes (IND-4, P-D, R-2, R-3, R-T-2) with no matching `zoning_districts` row, which regressed orange G from PASS(100.0) to FAIL(0.0). Fixed same session with real Orange County ordinance citations (FLU/Zoning Correlation PDF, Sec. 38-1201/38-1476/38-456). P-D correctly marked density/FAR-not-regulated (verified consistent with 3 pre-existing PD/PUD districts already in the DB). R-2/R-3/R-T-2 max_density_du_acre left NULL/UNKNOWN — the FLU correlation table maps these codes to multiple density tiers (4–35 du/ac) and no parcel-level FLU designation exists to disambiguate; left honestly unknown rather than guessed.
- 28 + 2 = 30 rows inserted into `gold_standard_ultraloop_audit` for `dispatch_id=c40bb245-...` covering all 8 original targets plus the regression fix, each carrying independently-reproduced refuter evidence.

## Honesty Protocol violations found and remediated (both logged to `honesty_violations`)

1. **CRITICAL, id=fc2e7e54** — a work-agent fabricated a zoning value for collier (Industrial `max_far=0.45`), citing a Municode URL that an independent refetch proved returns only a CAPTCHA-gated Angular SPA shell with zero ordinance text. **Remediation: the fabricated `zone_standards` row (id=4662) was DELETEd this session** before any certification could rest on it. The row's sibling (RMF-6 `max_density_du_acre=6.0`, real PDF citation) was verified genuine and kept.
2. **MODERATE, id=85ae1136** — a work-agent asserted (CONFIRMED tag) that `realauction.com` returns HTTP 403 with a browser User-Agent, used as evidence the collier vendor lane is fully dead. Independent refetch with 3 realistic browser UAs got HTTP 200 every time (only a bare/no-UA request 403s — generic WAF bot-block). The overall conclusion (collier A is blocked) still stands on other independently-verified evidence; this one citation was wrong and is flagged.

Both violations were caught by the ULTRALOOP adversarial refuter layer working as designed — a different agent than the one that made the claim, with instructions to independently re-fetch every cited source rather than trust the pasted evidence.

## New finding surfaced (not a gold-standard letter, escalating separately)

While auditing pinellas letter J, a work-agent asserted `ml_score` values were "genuine per-case computation" based on a 3-row spot check. The refuter ran a `GROUP BY ml_score` across all 388 pinellas `bid_decisions` rows and found **`ml_score = 0.72` constant for every single row — zero variance**. Cross-county check shows citrus also has exactly 1 distinct value, while most other counties show 2–100 distinct values. This does not flip pinellas J's DoD pass (the metric only checks non-null, not variance), but it is a real, undisclosed Shapira-model integrity bug with real downstream bidding risk — **the ML scorer appears stuck/degenerate for at least 2 counties.** Recommend a follow-up session investigate `shapira_models` scoring for pinellas/citrus specifically before those counties' J numbers are used to inform real bids.

## Residual / next-session priorities

- **collier G**: 2 of ~16 districts verified with real citations (RMF-6 density=6.0). Remaining districts blocked on Firecrawl credit exhaustion + Municode/collier.gov 403/503 on direct fetch. Needs either restored Firecrawl budget or a different fetch path (zoneomics.com worked for orange this session — try it for collier).
- **collier I**: 89.6% (190/212), blocked on the same G/zone_code gap for the remaining 22 rows — will likely clear on its own once collier G lands.
- **collier A / suwannee A,B,F**: confirmed genuinely blocked (dead CAPTCHA-gated vendor lane; no online FC lane exists respectively) — do not re-attempt without a new lead. suwannee B/F are long-accrual (0 closed auctions out of 9) and will resolve naturally as sales close.
- **pinellas ml_score anomaly**: needs its own investigation, separate from this campaign's letter-tracking.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
