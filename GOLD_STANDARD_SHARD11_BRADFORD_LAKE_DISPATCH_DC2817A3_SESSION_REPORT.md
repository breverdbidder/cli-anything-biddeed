# GOLD STANDARD shard-11 — dispatch dc2817a3 (bradford, lake)

dispatch_id: dc2817a3-7057-402b-b887-17d6d31cc998
chat_session: architect-20260731T000000
mode: ULTRALOOP native (Workflow tool fan-out-and-verify, 4 fix agents + 4 independent adversarial refuters across 2 waves)

## VERIFICATION PROTOCOL — before/after (verbatim from pencil_dod_evaluate_county)

### bradford (unchanged 8/10 — no regression, no fabrication)

**Before (session start):**
```json
{"A":{"pass":true,"detail":"fc=4 td=1","metric":1},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":true,"detail":"matched_clean=5","metric":100.0},"D":{"pass":true,"detail":"matched_any=5","metric":100.0},"E":{"pass":true,"detail":"parcel_linked=5","metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":7.6},"I":{"pass":true,"detail":"card_complete=5 of 5","metric":100.0},"J":{"pass":true,"detail":"deal_complete=5 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"bradford","auctions_total":5}
```

**After (final, re-verified live):**
```json
{"A":{"pass":true,"detail":"fc=4 td=1","metric":1},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":true,"detail":"matched_clean=5","metric":100.0},"D":{"pass":true,"detail":"matched_any=5","metric":100.0},"E":{"pass":true,"detail":"parcel_linked=5","metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":8.1},"I":{"pass":true,"detail":"card_complete=5 of 5","metric":100.0},"J":{"pass":true,"detail":"deal_complete=5 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"bradford","auctions_total":5}
```

**B/F — 6th consecutive session confirming genuine block.** Only 1 of bradford's 5 auctions has a lapsed sale date (case 25000457CAAXMX, VyStar Credit Union vs Ebenal, 18737 Charlotte Ave Brooker, sale date 2026-07-16, now 15 days past due). 5 prior sessions exhausted bradfordclerk.com, bctelegraph.com, surplusindex.com, Wayback, RealAuction (N/A), officialrecords.bradfordclerk.com, myfloridacounty.com ORI (Turnstile-gated), civitekflorida.com OCRS (Turnstile-gated), Box.com doc link. This session tried genuinely new angles (courtlistener.com, judyrecords.com, trellis.law, direct case/party/address web search) — all dead-ended into the same pre-sale legal notice or returned no data. **Zero writes made.** No CAPTCHA bypass attempted (hard prohibition).

### lake (unchanged 4/10 on pass/fail — one real data-integrity fix landed on G)

**Before (session start):**
```json
{"A":{"pass":true,"detail":"fc=98 td=11","metric":11},"B":{"pass":true,"detail":"verified=8 closed_sold=8","metric":100.0},"C":{"pass":false,"detail":"matched_clean=13","metric":11.9},"D":{"pass":false,"detail":"matched_any=27","metric":24.8},"E":{"pass":false,"detail":"parcel_linked=80","metric":73.4},"F":{"pass":true,"detail":"tier1_sold=8 closed_sold=8","metric":100.0},"G":{"pass":false,"detail":"density=93.8 far=100.0 pk1000=","metric":93.8},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":8.6},"I":{"pass":false,"detail":"card_complete=68 of 109","metric":62.4},"J":{"pass":false,"detail":"deal_complete=80","metric":73.4},"county":"lake","auctions_total":109}
```

**After (final, re-verified live):**
```json
{"A":{"pass":true,"detail":"fc=98 td=11","metric":11},"B":{"pass":true,"detail":"verified=8 closed_sold=8","metric":100.0},"C":{"pass":false,"detail":"matched_clean=13","metric":11.9},"D":{"pass":false,"detail":"matched_any=27","metric":24.8},"E":{"pass":false,"detail":"parcel_linked=80","metric":73.4},"F":{"pass":true,"detail":"tier1_sold=8 closed_sold=8","metric":100.0},"G":{"pass":false,"detail":"density=93.2 far=100.0 pk1000=","metric":93.2},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":0.1},"I":{"pass":false,"detail":"card_complete=68 of 109","metric":62.4},"J":{"pass":false,"detail":"deal_complete=80","metric":73.4},"county":"lake","auctions_total":109}
```

## What moved and how (VERIFIED, per-letter)

- **E (parcel linkage, 73.4% unchanged):** Re-ran `scripts/shard14_lake_e_ownername_match.py` live against all 29 unlinked FC rows (21 repeats from a prior diagnosis + 8 genuinely new since). 0/29 unique ArcGIS OwnerName matches — 2 ambiguous, 27 zero/no-surname-position hits. Genuine ceiling reconfirmed, not re-attempted with looser matching rules. **0 writes.**
- **C/D (parity litmus, 11.9%/24.8% unchanged):** Built `scripts/shard11_dc2817a3_lake_fuzzy_match.py` (rapidfuzz-based street-number+name + owner-surname dual-dimension matcher) against the 668-row PropertyOnion archive, per the standing pre-authorization for supplementary fuzzy litmus. Found 3 real, independently-verified matches (2020CA001954, 2025CA002239, 2025CA000481) and wrote `parity_status='matched_clean'` with a new non-tier1 `parity_source` tag. **These are real, DB-verified writes** — but the evaluator's C/D formula requires `parity_source LIKE 'tier1%'`, so they correctly do not move the pass/fail metric. This is flagged as a formula-vs-evidence gap for a future session (promoting a fuzzy-matched, dual-dimension-confirmed source to tier1-eligible is a policy call, not something this session should decide unilaterally).
- **G (zoning density, 93.8%→93.2%, an honest decrease):** Found a leftover fabrication a prior defabrication pass had missed — `zoning_districts` id=10716 ("R-1", jurisdiction 835/Leesburg) was still named "Single Family Residential (Shard7 Synthetic)" with invented values (max_density_du_acre=4.0, max_far=0.35, no source_url). Corrected to real Lake County Municode Table 3.02.06 values (1.0 du/acre, FAR 0.20), and deleted 4 orphaned synthetic `parcel_zones` rows (`SYN-LAKE-*` parcel_ids with zero backing in `multi_county_auctions`). The metric ticking down (93.8→93.2) is the **correct, honest result of removing fabricated data**, not a regression — confirmed via independent refuter re-verification of both the corrected rows and the deletions.
- **I (card completeness, 62.4% unchanged):** Diagnosed the 12-row gap sitting behind E's 29-row ceiling (parcel-linked but zone_code-missing): 9 Eustis, 2 Clermont, 1 Leesburg. Leesburg's real ArcGIS zoning endpoint was network-unreachable (TCP/TLS reset, not a 404/auth wall) 3x; Eustis has no discoverable zoning REST service (only a Future-Land-Use layer, deliberately not substituted — different regulatory field); Clermont's real layer returned a genuine miss (sanity-checked against a known-good coordinate on the same layer). **0 writes**, honest ceiling documented.
- **J (deal completeness, 73.4% unchanged):** Investigated an apparent "98→80 regression" flagged in the dispatch brief and disproved it: git/migration evidence (`supabase/migrations/20260724v_shard2_lake_j_ghost_purge_full_regen.sql`) confirms 80/109 is the **correct final honest state** from a same-day 2026-07-24 ghost-success purge (a prior session's constant `ml_score=0.55` stub rows were correctly nulled, not a later external regression). The 29 still-failing case_numbers are the exact same rows E's ceiling already covers — no real assessed_value/market_value/parcel_id exists to compute a genuine ARV from. **0 writes** (generating one would require fabrication).

## Adversarial verification

All 6 fix claims (bradford B/F, lake E, lake C/D, lake G, lake I, lake J) were independently re-verified by refuter agents that did not write the original fix — each re-ran `pencil_dod_evaluate_county` fresh (not trusting pasted JSON), spot-checked actual DB rows for real provenance, and checked for regressions across all 10 letters. **6/6 survived (refuted=false, survives=true).** No regressions found in any letter for either county. 8 rows logged to `public.gold_standard_ultraloop_audit` (ids 11374-11381), one per county+letter, `ultraloop_mode='native'`.

## Files created (committed this session)

- `scripts/shard11_dc2817a3_lake_e_29row_run_log.py` — E re-run evidence log
- `scripts/shard11_dc2817a3_lake_fuzzy_match.py` — new C/D fuzzy litmus matcher (rapidfuzz)
- `scripts/shard11_dc2817a3_lake_g_r1_defabricate.py` — R-1 defabrication fix (applied live)
- `scripts/shard11_dc2817a3_lake_i_gap_diagnosis.py` — I 12-row gap diagnosis
- `scripts/shard11_dc2817a3_lake_j_root_cause_evidence.py` — J root-cause disproof of the apparent regression

## Residual gaps / next-session priorities

1. **Lake C/D policy gap:** 3 real fuzzy-matched rows exist but don't count under the tier1-only formula — either (a) extend the evaluator to accept a sufficiently-confident dual-dimension fuzzy match as tier1-eligible, or (b) keep the bar as-is and treat this as evidence-gathering only. Needs an explicit decision, not a unilateral code change.
2. **Lake I:** Leesburg's ArcGIS zoning endpoint (`map.leesburgflorida.gov/arcgis/rest/services/CommunityDevelopment/Planning_and_Zoning/MapServer`) is a real, discovered, but currently-unreachable-from-this-sandbox endpoint — worth a retry from a different egress path. Eustis has no known zoning REST service at all — needs fresh discovery.
3. **Lake G:** 3 parcels (843/R-1A, 843/R-2 both Mount Dora, 1030/Moderate Density Res Groveland) remain genuinely unresolvable — Municode is reCAPTCHA-gated for every lake jurisdiction tried, and no ordinance PDF with the needed dimensional table was found.
4. **Bradford B/F:** genuinely exhausted via every non-CAPTCHA-bypass method across 6 sessions. Recommend either accepting this as a structural ceiling until the sale naturally resolves through some future public channel, or escalating for a human-in-the-loop Turnstile-solve exception if that's ever authorized.

## Scope note

This dispatch assigned bradford + lake only. No other shard's counties were touched. No cron jobs, gold-standard-loop scoring functions, or other counties' rows were modified. `SET statement_timeout=0` guidance was not applicable — all writes went through the PostgREST REST API (direct psql password auth is broken in this sandbox), which is not subject to the same statement-timeout concern.
