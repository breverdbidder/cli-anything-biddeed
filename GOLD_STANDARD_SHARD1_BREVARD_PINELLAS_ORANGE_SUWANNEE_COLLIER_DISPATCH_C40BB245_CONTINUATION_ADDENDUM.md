# Gold Standard Shard-1 Continuation Addendum — dispatch c40bb245-4b9f-475a-a7c7-648a09e836c2

Continuation of the same dispatch (see `GOLD_STANDARD_SHARD1_BREVARD_PINELLAS_ORANGE_SUWANNEE_COLLIER_DISPATCH_C40BB245_SESSION_REPORT.md`, commit `8a299772`), which had already closed brevard/pinellas/orange to 10/10 and left collier G/I as the explicit residual. This session picked up exactly that residual via a native Workflow (ULTRALOOP: fixer != verifier for every claim).

## Re-verified live state at continuation start (matches prior session's "AFTER" exactly)

```
brevard:  10/10 PASS (confirmed live)
pinellas: 10/10 PASS (confirmed live)
orange:   10/10 PASS (confirmed live)
suwannee: 7/10 -- A/B/F genuinely blocked (no online FC lane), unchanged, not re-attempted
collier:  7/10 -- A blocked (CAPTCHA vendor), G=0.0 FAIL, I=89.6 FAIL
```

## What this session did

Ran one Workflow: 14 parallel research agents (one per Collier zoning district code still blocking G), each independently re-verified by a separate refuter agent instructed to personally re-fetch every cited source rather than trust the pasted evidence. 24 subagents, 737 tool calls, ~1.6M tokens.

**Result: heavy infrastructure blocking.** `colliercounty.elaws.us` (Collier's primary LDC host) returned HTTP 503 for essentially every fetch attempt all session (site-wide outage, not a bot-block — confirmed via raw IIS error page). `library.municode.com` serves a bare Angular SPA shell with zero server-rendered legal text. `collier.gov` PDF assets and `app.collierclerk.com` both 403. The Firecrawl API key returned HTTP 402 (insufficient credits) and no local firecrawl CLI was available in this sandbox. No agent fabricated a value in response — every blocked district was correctly reported `found=false, honesty_tag=UNTESTED`.

### Survived (adversarially verified, applied to `zone_standards`)

| Code | Parcels | Value | Evidence |
|---|---|---|---|
| CON | 60 | density=0.2 du/acre (1/5ac) | Fixer + refuter both independently fetched the real Collier GMP Future Land Use Element PDF, verbatim text match, math confirmed |
| E | 50 | density=0.4444 du/acre (1/2.25ac) | Same — real Golden Gate Estates Sub-Element PDF (Ord 2024-37), verbatim match |
| A | 9 | density=0.2 du/acre (1/5ac) | Same — real FLUE PDF (Ord 2024-46), verbatim match across 2 independent copies |
| RMF-12 | 4 | not-regulated (GMP density-rating-system, no fixed table value) | Refuter independently fetched a real GMP PDF, confirmed no fixed "RMF-12" figure exists in it. Flagged caveat: unlike RMF-6 (which has a specific code-clarification doc), no RMF-12-specific doc was found — residual gap, left null rather than guessed |
| VR | 5 | not-regulated | Survived only via cross-corroborating WebSearch-indexed excerpt (primary host down all session) — weaker evidence, documented honestly, confidence_score=0.55 |

### Refuted / not applied (adversarial layer working as designed)

PUD (24 parcels), RT (5), RSF-4 (4) all had plausible claims that were correctly refuted — in every case because the refuter could not independently reproduce the exact fetch (source down), not because the underlying claim was contradicted. Per instructions, default to `survived=false` when the fetch can't be reproduced. No value applied for any of these.

### Genuinely untested, no claim made

C-4 (6 parcels), C-1 (1), C-5 (1), I (1), MH (7), RSF-5 (1) — no citable source found. These 4 commercial/industrial codes (C-1/C-4/C-5/I) are the ones that gate G's overall pass (`G = min(density%, far%, pk1000%)`), so **G cannot reach PASS until at least these are resolved**, independent of density progress.

### Honesty Protocol finding: fabricated existing row deleted

The pre-existing `zone_standards` row for RSF-3 (id=3302) had `source_url = "shard5_bootstrap_collier"` — not a URL. Adversarial re-audit found the claimed `max_far`/`parking_per_1000sf` are the wrong metric *types* for how Collier actually codes single-family districts (FL LDCs use lot-coverage-% and per-unit parking, not FAR/per-1000sf, for single-family). Deleted rather than replaced with another unverified guess. Logged to `honesty_violations` (id=`dda651bc-3e17-46f0-9100-f574a15c2a2a`, severity MODERATE).

## Verification protocol — before/after `pencil_dod_evaluate_county('collier')`

**BEFORE:** `{"G":{"pass":false,"metric":0.0,"detail":"density=9.6 far=0.0 pk1000=0.0"}, "I":{"pass":false,"metric":89.6}}`

**AFTER (live, re-queried post-write):**
```json
{"A":{"pass":false,"metric":0},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":100},"D":{"pass":true,"metric":100},"E":{"pass":true,"metric":100},"F":{"pass":true,"metric":100},"G":{"pass":false,"metric":0.0,"detail":"density=67.9 far=0.0 pk1000=0.0"},"H":{"pass":true,"metric":4.7},"I":{"pass":false,"metric":89.6},"J":{"pass":true,"metric":100}}
```

`v_zoning_gold_standard_kpi_v3` confirms: `pct_density_of_applicable` 9.6% → **67.9%** (127 of 187 applicable parcels now have a real or correctly-not-regulated-documented status; not-regulated rows correctly do NOT count toward the numerator — confirmed empirically, no free lunch). **Real, honest progress. G remains FAIL** — density alone isn't sufficient because `G = min(density, far, pk1000)` and far/pk1000 are still 0.0% (gated by the 4 untested commercial districts).

15 rows logged to `gold_standard_ultraloop_audit` (`dispatch_id=c40bb245-...`, `letter=G`): 14 district claims + the RSF-3 re-audit, each carrying independently-reproduced refuter evidence.

## Collier I: root cause is NOT the G/zone_standards gap (correction to prior session's hypothesis)

The prior session's residual notes guessed I "will likely clear on its own once collier G lands." **This session found that's incorrect.** I's `card_complete=190 of 212` (89.6%, unchanged before/after the G fix) is gated by 22 auction parcels that have **zero `parcel_zones` entry at all** — a linkage gap, not a `zone_standards` values gap. Of those 22:
- 8 are already documented dead-ends from a prior session (`gs_shard1_c40bb245_collier_i.py`): zero match anywhere in the FL DOR statewide cadastral FeatureServer even after zero-padding variants.
- The remaining 14 (`16111240002, 48425920002, 74252360003, 72481000000, 08330640006, 22321600002, 57200720007, 18162720003, 29820000245, 22324800003, 31380520004, 57200480004, 06370000242, 83741800007`) have not been checked against Collier's own zoning GIS specifically.

This session probed for Collier's zoning ArcGIS REST endpoint directly (`gis.colliercountyfl.gov` → 503, `maps.collier.gov` → 404, `collier.mapsonline.net` → timeout, `www.colliercountyfl.gov/arcgis/...` → redirects to the general CMS, not ArcGIS) — consistent with the same infrastructure outage seen throughout this session's LDC research, not a dead end proven separately. **Next-session priority: retry Collier's zoning GIS endpoint discovery once the county's web infrastructure recovers** (this looks like a transient, session-wide outage across multiple independent Collier-hosted services, not 4 unrelated permanent blocks).

## Pinellas ml_score anomaly — root-caused (not fixed, flagged in prior session as follow-up)

Confirmed live: `bid_decisions.ml_score` is exactly `0.72` for all 388/388 pinellas rows (citrus similarly degenerate at `0.74` across 1000 rows; brevard shows healthy variance: 0.82/0.75/0.72/0.6/0.56/0.58). Root cause found: `scripts/shard4_run3713_pinellas_i_j_fix.py:201` hardcodes `"ml_score": 0.72` as a literal constant instead of computing a real per-case score (same pattern found in ~14 other county J-generator scripts, e.g. `scripts/putnam_j_generator.py:72`). This does not flip pinellas J's pass/fail (the DoD metric only checks non-null), so it's out of this shard's letter scope, but it's a real Shapira-model integrity gap with downstream bidding risk. **Recommend a dedicated follow-up session** to re-score affected counties through the actual Shapira model rather than the hardcoded placeholder.

## Residual / next-session priorities

- **collier G**: still needs real FAR + parking values for C-1, C-4, C-5, I (only 9 parcels total, but they hard-gate the whole letter via `min()`) — retry once `colliercounty.elaws.us` / `library.municode.com` / `collier.gov` / Firecrawl credits recover. Consider a browser-rendering fetch path for the Municode Angular SPA (regular WebFetch cannot execute its JS).
- **collier G**: RMF-12/VR not-regulated conclusions are INFERRED-confidence, not VERIFIED — a future session with working elaws.us access should try to confirm directly rather than via WebSearch-indexed snippets only.
- **collier I**: 14 of 22 zone-unlinked parcels need a fresh Collier zoning-GIS point-in-polygon attempt once county GIS infrastructure recovers (this session's probes all failed on infra, not confirmed dead ends).
- **pinellas/citrus ml_score**: needs a real Shapira re-scoring pass, separate investigation from letter tracking.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
