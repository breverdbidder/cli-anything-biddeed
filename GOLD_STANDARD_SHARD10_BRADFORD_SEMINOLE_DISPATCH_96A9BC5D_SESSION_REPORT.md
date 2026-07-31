# Gold Standard Shard-10: bradford + seminole — dispatch 96a9bc5d-bc36-4e5c-904e-b80ae8b1165a

Session: architect-20260731T080000, run7622. Scope: bradford, seminole ONLY. All changes shipped directly to `main` (no branches/PRs). Method: ULTRACODE — one Workflow fan-out (4 research agents + 4 independent adversarial refuters), plus direct hand-verified SQL for the highest-confidence lever and a live-caught regression fix.

## Status Board (Plan vs Actual)

| County | Letter | Planned | Actual | Deviation |
|---|---|---|---|---|
| bradford | B/F | Attempt one fresh non-dead-end lead for case 25000457CAAXMX | No movement — 6th consecutive session confirms every accessible public channel exhausted | None — expected outcome given 5 prior exhausted sessions |
| seminole | C/D | Reconcile parity via tier1 litmus | 92.5%→94.0% (123→125 of 133), still FAIL | Short by 2; remaining 8 rows blocked by seminole.realforeclose.com bot-detection (403), not fabricated |
| seminole | I | Zoning/geo/value enrichment | 82.7%→95.5% (110→127 of 133) — **PASS** | None |
| seminole | J | bid_decisions generator/backfill | 93.2%→100% (124→133 of 133) — **PASS** | None |
| seminole | G | Not targeted (was already PASS) | Regressed to FAIL (70%) mid-session as a side effect of the I-fix, then caught and restored to 97.9% (above original 97.4% baseline) before close-out | Unplanned P0 regression, self-caught and fixed same session — see Deviation Log |

## Live Scoreboard — Before / After (pasted `pencil_dod_evaluate_county` JSON)

### bradford — BEFORE (session start, 2026-07-31)
```json
{"A":{"pass":true,"metric":1,"detail":"fc=4 td=1"},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":1.8},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"auctions_total":5}
```

### bradford — AFTER (session close, 2026-07-31)
```json
{"A":{"pass":true,"metric":1,"detail":"fc=4 td=1"},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":2.6},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"auctions_total":5}
```
**8/10, unchanged. No regression.** B/F remain structurally blocked on case 25000457CAAXMX (sale date 2026-07-16, now 15 days lapsed, no independent post-sale source reachable).

### seminole — BEFORE (session start, 2026-07-31)
```json
{"A":{"pass":true,"metric":23},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":92.5,"detail":"matched_clean=123"},"D":{"pass":false,"metric":92.5,"detail":"matched_any=123"},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":97.4,"detail":"density=97.4 far=100.0 pk1000=100.0"},"H":{"pass":true,"metric":0.1},"I":{"pass":false,"metric":82.7,"detail":"card_complete=110 of 133"},"J":{"pass":false,"metric":93.2,"detail":"deal_complete=124"},"auctions_total":133}
```

### seminole — AFTER (session close, 2026-07-31)
```json
{"A":{"pass":true,"metric":23},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":94.0,"detail":"matched_clean=125"},"D":{"pass":false,"metric":94.0,"detail":"matched_any=125"},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":97.9,"detail":"density=97.9 far=100.0 pk1000=100.0"},"H":{"pass":true,"metric":0},"I":{"pass":true,"metric":95.5,"detail":"card_complete=127 of 133"},"J":{"pass":true,"metric":100.0,"detail":"deal_complete=133"},"auctions_total":133}
```
**8/10, up from 6/10.** I and J newly PASS. G held (net +0.5 vs original baseline after regression catch). C/D at 94%, 2 short of threshold.

## What moved and why

**Seminole C/D (+2, still FAIL):** Cross-checked all 10 null-parity `calendar_sweep_mca_v3` stub rows (auction_date 2026-08-20) directly against `public.realforeclose_aids` (RealAuction tier1 source, not PropertyOnion). 2 genuine matches found and applied by hand before the workflow launched: `2024CA001430` and `2025CA001791`, both exact case_number+parcel_id+property_address matches with real assessed values (304614, 321803). The other 8 have zero `realforeclose_aids` rows and `seminole.realforeclose.com` returns HTTP 403 (bot-detection) to every fetch method tried (curl, WebFetch) — genuinely blocked, left null, not fabricated.

**Seminole I (110→127/133, PASS):** Two parallel research agents enriched 18 parcels total (8 `calendar_sweep_mca_v3` stub rows + 10 older gap rows) with real lat/lon, assessed/market value, and `parcel_zones` rows, sourced from Sanford's countywide `Parcel_Base` ArcGIS MapServer, Longwood's `City_of_Longwood_Zoning` FeatureServer, Altamonte Springs' zoning layer + LDC, and scpafl.org's live parcel search. Jurisdiction was verified per-parcel against the source's own `CityName` field rather than assumed from mailing address — this caught 4 parcels genuinely in unincorporated Seminole County despite Longwood/Lake Mary/Maitland/Apopka mailing addresses. 3 rows explicitly left untouched as out-of-scope non-property records (`MULTIPLE PARCELS`, `SYN-SEM-` synthetic placeholder, and an "ALCOHOLIC LICENSE" case that is not a real foreclosure property) — flagged, not forced.

**Seminole J (124→133/133, PASS):** bid_decisions backfilled for the 9 gap case numbers using the existing `scripts/shard2_seminole_j_gap_fill.py` `build_bid_decision` formula (ARV waterfall, Shapira-proxy repair bands, max_bid formula, ml_score bands, distress/CMA factor proxies), reusing the campaign's already-accepted methodology rather than inventing a new one. Because the parallel I-fix agents had just backfilled real assessed/market values for these same 9 rows, 7 of 9 used real `market_value` directly (ratio 1.0000, verified) and only 2 fell back to `assessed_value*1.05` — zero rows hit the flat $195K county-default fabrication path.

**Bradford B/F (unchanged, confirmed exhausted):** 6th consecutive session on case 25000457CAAXMX. This session tried 5 genuinely new angles (fresh Cloudflare check with 2 user-agents, direct web search for the case number, BC Telegraph post-sale archive full-text search through 7/30, myflcourtaccess.com portal-type verification, surplus-funds aggregator sites) — all dead or non-applicable, none re-treading the 11-source dead list from the prior 5 sessions. Recommendation logged: the only remaining lever is human phone/records-request outreach to the Bradford Clerk or the surplus-funds attorney of record, which is outside this campaign's autonomous scope. Suggest deprioritizing further automated bradford B/F sessions until that human step happens.

## Deviation Log

**Unplanned P0 regression, caught and fixed same session.** The two I-fix research agents ran in parallel and each independently inserted `parcel_zones` rows; one agent's Sanford rows used zone_code `SR1`/`MR3` (no hyphen) which failed to join `zoning_districts`' real hyphenated codes `SR-1`/`MR-3`. Because `v_zoning_gold_standard_kpi_v3` defaults a missing applicability join to `true` (`COALESCE(a.far_applicable, true)` etc.), these 3 unmatched rows counted against the density/far/pk1000 denominators with zero numerator contribution — a triple-metric hit that dropped G from PASS 97.4% to FAIL 70% mid-session. One of the two research agents actually self-caught a related issue (a fabricated R-4 density figure) during its own run and fixed it, but did not catch the SR1/MR3 hyphenation mismatch, and reported G as "unaffected by my changes" — which was true for that agent's own rows but incomplete for the shared county view. I independently re-ran the live evaluator after the workflow completed (per this campaign's mandatory close-out check), caught the discrepancy against the pre-session baseline, root-caused it via direct SQL join diagnostic, and corrected the 3 `zone_code` values to match the pre-existing real districts. Re-verified live: G restored to 97.9%, above the original 97.4% baseline. Logged to `gold_standard_ultraloop_audit` id 11635. **Lesson for future parallel I/G fix sessions: always diff the target county's G metric before and after, even when G isn't the assigned letter — parcel_zones inserts are shared-denominator writes.**

## Verification Evidence

- Commits: `04f08b66` (C/D realforeclose_aids match), `9ca6033c` (I/J/G-regression-fix bundle)
- Migrations: `supabase/migrations/20260731_gold_standard_shard10_seminole_cd_realforeclose_aids_match.sql`, `20260731d_gold_standard_shard5_seminole_i_10row_property_card_backfill.sql`, `20260731e_gold_standard_shard10_seminole_g_regression_fix.sql`
- `gold_standard_ultraloop_audit`: 4 workflow-verify rows (C/D, I, J, bradford-B/F, all `survived=true`) + 1 hand-logged regression-catch row (G, `survived=true`), dispatch `96a9bc5d-bc36-4e5c-904e-b80ae8b1165a`
- Workflow: `wf_b8d2e7d0-833`, 8 agents, 719K tokens, 340 tool calls, ~39 min wall clock

## Next-Session Priorities

1. seminole C/D: needs 2 more of the 8 remaining calendar_sweep rows to reach 95% — blocked until `seminole.realforeclose.com` becomes reachable (or a fresh `scrape-realauction-county.yml` run populates `realforeclose_aids` for the 2026-08-20 sale week) or the sale date passes and an actual court record appears. Re-check after 2026-08-20.
2. bradford B/F: recommend human outreach (phone/records-request) as the only remaining lever; deprioritize further automated sessions on this exact case until that happens.
3. Unrelated, out-of-scope anomaly noted by the J verifier: seminole `bid_decisions` has a pre-existing duplicate pair for case `2025CA001791` (created 2026-06-19, 6 weeks before this session) — does not affect the J metric (evaluator uses EXISTS not JOIN) but is dead-weight worth a future cleanup pass.
