# GOLD STANDARD SHARD-12 — miami_dade, run 3786

dispatch_id: `19fbd0ec-ad81-487d-9007-a82601d91d04`
chat_session: `architect-20260711T160000`
Mechanism: ultracode Workflow `wf_09273ba4-8c7` — 3 parallel research+fix agents (C/D, I-address, I-zone) + 1 adversarial verifier, followed by orchestrator-level root-cause work on a session-internal G regression.

## Scoreboard

| Letter | BEFORE | AFTER | Change |
|---|---|---|---|
| A | PASS 87 | PASS 87 | — |
| B | PASS 100.0 | PASS 100.0 | — |
| **C** | **FAIL 92.4** (329/356) | **FAIL 94.9** (338/356) | +9 rows, still short of 95% gate |
| **D** | **FAIL 92.4** (329/356) | **FAIL 94.9** (338/356) | +9 rows, still short |
| E | PASS 96.1 (342/356) | PASS 96.6 (344/356) | +2 (parcel_id backfill side effect) |
| F | PASS 100.0 | PASS 100.0 | — |
| G | PASS 99.3 | PASS 99.3 | dipped to FAIL 0.0% mid-session, root-caused + fixed live (see below) |
| H | PASS | PASS | — |
| **I** | **FAIL 94.4** (336/356) | **PASS 96.1** (342/356) | **FLIPPED TO PASS** |
| J | PASS 100.0 | PASS 100.0 | — |

**County status: 8/10 PASS** (was 7/10). Only C and D remain, both at 94.9% — 0.3pp short of the 339/356 gate. NOT certified this session (C/D still fail).

Live evaluation command used throughout: `curl -s -X POST "$SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -d '{"p_county":"miami_dade"}'`

### SQL VERIFICATION

```
BEFORE (session start):
{"A":{"pass":true,"metric":87},"B":{"pass":true,"metric":100.0},
 "C":{"pass":false,"metric":92.4,"detail":"matched_clean=329"},
 "D":{"pass":false,"metric":92.4,"detail":"matched_any=329"},
 "E":{"pass":true,"metric":96.1,"detail":"parcel_linked=342"},
 "F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":99.3},
 "H":{"pass":true,"metric":5.7},
 "I":{"pass":false,"metric":94.4,"detail":"card_complete=336 of 356"},
 "J":{"pass":true,"metric":100.0},"auctions_total":356}

AFTER (2026-07-11, session close):
{"A":{"pass":true,"metric":87},"B":{"pass":true,"metric":100.0},
 "C":{"pass":false,"metric":94.9,"detail":"matched_clean=338"},
 "D":{"pass":false,"metric":94.9,"detail":"matched_any=338"},
 "E":{"pass":true,"metric":96.6,"detail":"parcel_linked=344"},
 "F":{"pass":true,"metric":100.0},
 "G":{"pass":true,"metric":99.3,"detail":"density=99.3 far=100.0 pk1000="},
 "H":{"pass":true,"metric":0.3},
 "I":{"pass":true,"metric":96.1,"detail":"card_complete=342 of 356"},
 "J":{"pass":true,"metric":100.0},"auctions_total":356}
```
Timestamp: 2026-07-11T21:48Z (UTC)

## What actually happened

### C/D — residual-27 investigation, real evidence, honest ceiling reached
The 27 unmatched rows were re-checked live against the RealForeclose/RealTaxDeed AJAX calendar for their exact claimed dates — zero matches, confirming these are not a matcher bug but genuinely wrong/stale dates or a different tracking system. 9 of 16 distinct case numbers were resolved to real evidence (RealForeclose/RealTaxDeed live listing detail with a real judgment amount/aid, or the Miami-Dade Clerk's RealTDM tax-deed case system with app number/status/sale date) and promoted, correcting auction_date where wrong. 10 distinct case numbers remain genuinely UNKNOWN after exhaustive checking (a 60-week calendar sweep plus RealTDM by case and by parcel, all negative) — left untouched, not guessed.

**Adversarial finding + resolution:** the workflow's refuter flagged these 9 promotions as ghost-success (no outcome-table backing), citing the 2026-07-04 miami_dade C/D revert precedent. I independently checked this live, fleet-wide: **2,000+ rows across 20+ counties** (polk 537, duval 326, miami_dade 324 pre-existing, putnam 288, palm_beach 187, ...) share the identical shape — matched via a real calendar-item confirmation, no outcome-table row yet (because the auction hasn't sold). This is the deliberate, fleet-standard C/D methodology, distinct from the 07-04 defect (case-number-format-only, zero external confirmation of any kind). B/F already separately gate on sale-outcome verification. I did not revert the 9 rows, but logged the full disagreement and evidence in `gold_standard_ultraloop_audit` for the AI Architect to settle fleet-wide, since it bears on many other counties' future certifications, not just this one. Practically moot for certification this session either way — C/D still fails 95% regardless of which reading is correct.

### I — closed to PASS
- 1 of 3 parcel-only-missing rows resolved (folio 30-3053-106-0510, condo unit, cross-checked against an independent listing citing the same APN).
- All 8 no-address rows remain UNKNOWN — every primary source (RealForeclose/RealTaxDeed detail pages, Clerk civil case search) is login-walled or CAPTCHA-gated; no secondary aggregator has these cases indexed. Not guessed.
- 5 zoning-join-fail parcels resolved: 3 had a shared fake-precision centroid (25.7617, -80.1918) in `multi_county_auctions`, corrected to real per-folio coordinates from Miami-Dade's GIS property-polygon layer, then real point-in-polygon zoning lookups run at the corrected points. The 2 previously "genuinely blocked" parcels (inside incorporated municipalities not covered by the county's unincorporated-only zoning layer) resolved via the county's separate, authoritative county-wide "Municipal Zone" layer, which does cover incorporated cities.
- Independently re-verified by the workflow's adversarial agent: all 5 `parcel_zones` inserts confirmed live with distinct real zone codes and jurisdiction mappings; a direct WebFetch spot-check against the cited ArcGIS layer matched the claim exactly.

### G — caught and fixed a session-internal regression
The Miami Beach `CD-2` parcel_zones insert (part of the I fix) exposed a pre-existing, unrelated bug: jurisdiction 960's `zoning_districts` table holds a mislabeled generic county-style code set, not Miami Beach's real municipal codes — `CD-2` wasn't among them. The resulting failed join defaulted this parcel to "applicable but unmatched" across far/pk1000/density in `v_zoning_gold_standard_kpi_v3`, crashing G from 99.3% PASS to 0.0% FAIL mid-session. I traced this live through the view definitions, confirmed the causal chain (not a concurrent/unrelated process, as the I-zone agent's report had assumed), and fixed it by inserting one real `zoning_districts` + `zone_standards` row for (960, 'CD-2') sourced from Miami Beach Code §142-306 (max_far=1.5, max_height_ft=50, confidence_score=0.75; parking left NULL — not confirmed, not guessed). This also fixed pk1000 as a side effect (the applicability view hardcodes pk1000 as not-applicable for real zoning districts, removing this parcel from that ratio's denominator instead of counting it as a 0%-matched applicable row). G verified back to 99.3% PASS live.

## Guardrails followed
- No PropertyOnion data ingested as a source.
- No cron jobs 109/111/115/scoring touched.
- No other counties touched.
- Every DB write cites a real, checkable external source; every case that couldn't be resolved with confidence was left as UNKNOWN, not guessed.
- `gold_standard_ultraloop_audit` has 5 rows for this dispatch (C×2, D×1, I×1, G×1) — survived=true for I and G, survived=false for C/D per the ultraloop protocol's conservative default (documented disagreement preserved for future review).

## Deferred / next-session priorities
1. **C/D residual (10 distinct cases, 18 rows):** genuinely blocked by login walls / CAPTCHA on RealForeclose/RealTaxDeed AID detail pages and the Miami-Dade Clerk civil case search. A Firecrawl-capable session (this session's `FIRECRAWL_API_KEY` was absent from the environment) or an authenticated RealForeclose session could likely close some of these — county needs just 1 more real match to cross the 339/356 C/D gate.
2. **I residual (10 cases: 8 no-address, 2 address-inconsistent):** same login/CAPTCHA blocker as above.
3. **Fleet-wide C/D interpretation question** logged in `gold_standard_ultraloop_audit` (dispatch `19fbd0ec-ad81-487d-9007-a82601d91d04`, letter C) needs an AI Architect ruling: does C/D require outcome-table backing, or is real calendar-listing confirmation sufficient? Affects 20+ counties' existing matched_clean populations, not just miami_dade.
4. **Jurisdiction 960 (Miami Beach) zoning_districts table** is pre-existing mislabeled (generic Miami-Dade County codes instead of real Miami Beach codes) beyond the single CD-2 row patched this session — a full re-scrape of Miami Beach's actual zoning ordinance is out of scope for this dispatch but should be flagged for whichever session next touches Miami Beach zoning.

Files: `supabase/migrations/20260711w_shard12_miami_dade_cd_i_g_run3786.sql` (documents all live writes), `scripts/shard_run_miamidade_residual27_reharvest.py` (new, reusable case-number-targeted reharvest sweep, produced by the C/D agent).
