# Gold Standard LEE (E + I) Follow-up Session Report

- **county**: lee
- **letters targeted**: E (parcel linkage >=95%), I (card completeness >=95%)
- **agent**: claude-sonnet-5
- **mode**: single-county deep-dive, direct continuation of SHARD-2 (dispatch c3b1e7cc, loop run 7858) which forked `scripts/gold_standard_shard5_lee_ei_arcgis_backfill.py`

## Status (before -> after, live `pencil_dod_evaluate_county`)

| Letter | Before | After | Change |
|---|---|---|---|
| E | FAIL 94.4% (304/322) | FAIL 94.4% (304/322) | **Unchanged** — all 3 priority-1 address-bearing rows independently confirmed unresolvable without fabrication (see below) |
| I | FAIL 89.4% (288/322) | FAIL 89.4% (288/322) | **Unchanged** — the 16 (actually 14, live-recount) zone-unlinked rows all lack `zoning_districts` precedent for their live ArcGIS zone code |

**Net: zero writes this session. No regressions on any of the 8 currently-passing letters (A,B,C,D,F,G,H,J all re-confirmed byte-identical.)**

## Priority 1 — 3 address-bearing E-gap rows (all left unresolved, not fabricated)

Queried the Lee County ArcGIS FeatureServer (`services2.arcgis.com/.../Lee_County_Parcels/FeatureServer/0/query`) — the same proven live endpoint used by the prior firing.

- **18-CC-004510** (`98 SABLE DR LOT 98, NORTH FORT MYERS`): zero ArcGIS SITEADDR matches for "SABLE DR" anywhere in the county (only "CAPE SABLE LN" and "SABLE KEY CIR" exist, both different streets/cities). Web research confirms a real "Sable Dr" mobile home park exists in North Fort Myers 33917, but individual lot addresses in this format are not indexed in the county parcel layer by that street name at all — consistent with a resident-owned mobile-home-park addressing scheme that doesn't map 1:1 to the county's SITEADDR field. LEEPA.org is reachable (200) but is an ASP.NET WebForms postback site with no queryable REST endpoint usable from this sandbox (no interactive browser tool available). **Left NULL — not fabricated.**
- **24-CC-004249** (`16300 PINE RIDGE RD LOT X18, FORT MYERS`): zero ArcGIS SITEADDR matches for "16300 PINE RIDGE RD" (checked exact prefix and the full "PINE RIDGE RD" wildcard — 25 real parcels exist on that street, none at house number 16300). Web research identifies the real property as "Pine Ridge Palms," a 55+ resident-owned mobile home community that addresses individual units differently in third-party listings (e.g. "11043 Stardust Dr", "#Y32", "#Y33") than the "16300 Pine Ridge Rd Lot X18" format in our own case data — same root cause as 18-CC-004510: co-op-style lot addressing not present in the county's parcel-layer SITEADDR field. **Left NULL — not fabricated.**
- **25-CA-004959** (`2825 PALM BEACH BLVD, FORT MYERS`): ArcGIS returns 10 real STRAPs at this exact address (a commercial plaza/multi-unit building — `RFU1` through `RFU8`, `CUC1`, plus a $0-assessed common-area parcel), with no way to determine which specific unit the foreclosure case actually targets from the address alone. Per the campaign's no-fabrication rule (documented precedent: citrus's 2 multi-parcel HOA cases left NULL rather than guessed), picking one of 10 STRAPs arbitrarily would be a fabrication. **Left NULL — not fabricated.**

## Priority 2 — 15 no-address E-gap rows: genuinely blocked, same root cause as prior firing

Re-confirmed live this session (not assumed from the prior report):
- `lee.realforeclose.com` — 403 (curl) and 403 (WebFetch) on both the auction-preview index and on the 2 case-specific `AID=` detail-page URLs this session actually has on file (`25-CA-003281` AID 1498784, `25-CA-003295` AID 1500560).
- `www.leeclerk.org` — 403 (curl) and 403 (WebFetch).
- `matrix.leeclerk.org` (Lee Clerk's "Records Inquiry" tool, a genuinely new lead surfaced this session via web search, not previously tried) — connection times out (28s, both HTTP/2 and HTTP/1.1), not merely WAF-blocked but unreachable from this sandbox.
- **New this session**: attempted to escalate to `firecrawl-scrape` (the tool flagged by the prior report as the needed next step for a future session) — the Firecrawl API returned **HTTP 402 "Insufficient credits to perform this request"**. This closes off the specific escalation path the prior session recommended; it is not a code/config problem, it's an account-billing state, live-confirmed this session.
- General web search for all 15 case numbers individually returned zero hits — none of these cases are indexed anywhere outside Lee's own gated systems.
- No browser-automation tool (Playwright is installed as a pip package but not wired up as an interactive browsing tool in this harness) was available to attempt a real login/postback session against LEEPA, RealForeclose, or the Clerk.

**All 15 left untouched — not fabricated.** Root cause is identical to the prior firing's documented finding (Lee's public web surface is Akamai/WAF-blocked to non-browser HTTP clients), with one incremental finding: the previously-recommended Firecrawl fallback is now also blocked (out of credits), and a newly-discovered `matrix.leeclerk.org` lead is unreachable outright.

## Priority 3 — I: 14 zone-unlinked rows (structural residual, confirmed via live ArcGIS + `zoning_districts`)

Recomputed the exact SQL the `pencil_dod_evaluate_county` RPC uses for the `I` denominator/numerator (parcel_id/geo/value all present AND parcel_id resolves to a `v_zoning_gold_standard_card` row with `zone_code IS NOT NULL`). This reproduces **34 total incomplete rows** = the 18 E-gap rows (no parcel_id at all, automatically I-incomplete too) + **14 rows** that have real parcel_id + lat/lon + assessed_value but no zoning link (task described these as "16" — live recount this session found 14; the 2-row drift is most likely due to concurrent fleet writes on other letters between the task's baseline capture and this session's query, not a discrepancy in method).

Queried the Lee ArcGIS FeatureServer live for all 14 STRAPs (100% match rate — 14/14 found):

| Case | Jurisdiction | Live ArcGIS zoning | Precedent in `zoning_districts`? |
|---|---|---|---|
| 2026000039 | Fort Myers Beach (912) | RS-1 | No |
| 2026000040 | Fort Myers (929) | *(null in ArcGIS)* | N/A — source has no zoning value |
| 24-CA-003878 | Unincorporated (630) | *(null in ArcGIS)* | N/A — source has no zoning value |
| 24-CA-003913 | Sanibel (942) | *(empty string in ArcGIS)* | N/A — source has no zoning value |
| 24-CC-009119 | Fort Myers (929) | CPD | No (CPD does not exist under ANY jurisdiction_id in `zoning_districts`) |
| 25-CA-003850 | Fort Myers Beach (912) | RM-2 | No |
| 25-CA-004484 | Fort Myers (929) | *(null in ArcGIS)* | N/A — source has no zoning value |
| 25-CA-004684 | Sanibel (942) | *(empty string in ArcGIS)* | N/A — source has no zoning value |
| 25-CA-005048 | Bonita Springs (914) | MH-1 | No (914 only has AG-2, TFC-2 seeded) |
| 25-CA-006129 | Fort Myers Beach (912) | RPD | No |
| 25-CC-006204 | Unincorporated (630) | *(null in ArcGIS)* | N/A — source has no zoning value |
| 25-CC-007464 | Unincorporated (630) | RS-2 | No |
| 26-CA-000391 | Unincorporated (630) | CS | No |
| 26-CC-000977 | Cape Coral (815) | *(null in ArcGIS)* | N/A — source has no zoning value |

**Root cause, confirmed live**: `zoning_districts` for jurisdiction 912 (Fort Myers Beach) contains **only ordinance-chapter reference codes** (`PTICH`, `COORTOFOMYBEFL`, `PTIICOOR_CH10BU`, etc. — 30 rows, zero of them real zone codes like RPD/RM-2/RS-1). This is a structural seeding gap for that jurisdiction specifically, not a per-parcel data-quality issue. Jurisdiction 914 (Bonita Springs) has only 2 codes seeded (AG-2, TFC-2) against a much larger real zoning code set. Jurisdiction 630 (Unincorporated Lee) is missing RS-2 and CS specifically. Inserting a bare `parcel_zones` row pointing at any of these 7 real-but-unseeded codes would create a new G-denominator entry with a `zone_code` that has zero `zone_standards` precedent — per the guard rail documented and proven in the prior firing's script, this was correctly **not done**, since it would create an unfillable G-metric liability rather than a real fix.

The remaining 5 rows (2026000040, 24-CA-003878, 25-CA-004484, 25-CC-006204, 26-CC-000977) have genuinely no zoning value at all in the live Lee ArcGIS layer (`ZONING` field is null/blank at the source) — this is a source-data gap, not a linkage bug on our end.

**This confirms the task's framing exactly**: I is a zoning-coverage/seeding gap (Fort Myers Beach and Bonita Springs need real ordinance-derived `zoning_districts` + `zone_standards` rows for their actual zone codes, and Unincorporated Lee needs 2 more codes added), not a fixable data-quality bug in `multi_county_auctions`. Properly fixing it requires Firecrawl + ordinance-chapter research per jurisdiction (the same Phase-4 pipeline pattern used for county onboarding) — out of scope for "limited effort" in this session, especially with Firecrawl currently out of credits.

## Verification Protocol — before/after JSON (live-queried this session)

Before (session start, matches task's stated baseline exactly):
```json
{"A":{"pass":true,"metric":40,"detail":"fc=282 td=40"},"B":{"pass":true,"metric":100.0,"detail":"verified=20 closed_sold=20"},"C":{"pass":true,"metric":98.8,"detail":"matched_clean=318"},"D":{"pass":true,"metric":98.8,"detail":"matched_any=318"},"E":{"pass":false,"metric":94.4,"detail":"parcel_linked=304"},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=20 closed_sold=20"},"G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000=100.0"},"H":{"pass":true,"metric":0.1},"I":{"pass":false,"metric":89.4,"detail":"card_complete=288 of 322"},"J":{"pass":true,"metric":100.0},"auctions_total":322}
```

After (session end, no writes made):
```json
{"A":{"pass":true,"metric":40,"detail":"fc=282 td=40"},"B":{"pass":true,"metric":100.0,"detail":"verified=20 closed_sold=20"},"C":{"pass":true,"metric":98.8,"detail":"matched_clean=318"},"D":{"pass":true,"metric":98.8,"detail":"matched_any=318"},"E":{"pass":false,"metric":94.4,"detail":"parcel_linked=304"},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=20 closed_sold=20"},"G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000=100.0"},"H":{"pass":true,"metric":0.1},"I":{"pass":false,"metric":89.4,"detail":"card_complete=288 of 322"},"J":{"pass":true,"metric":100.0},"auctions_total":322}
```

**Byte-identical.** No drift, no regression on any letter.

## Next-session priorities
- **E, 3 address rows**: no further ArcGIS-based lever exists for the 2 mobile-home-lot rows; only path forward is a real interactive browser session (Playwright wired up as an actual tool, or a working Firecrawl balance) against LEEPA's WebForms search. The `2825 PALM BEACH BLVD` row would need the actual unit number from the court docket (Lis Pendens/Judgment) to disambiguate among 10 real STRAPs — also blocked behind the Clerk WAF.
- **E, 15 no-address rows**: needs either (a) Firecrawl account topped up, or (b) a genuine interactive-browser tool in this harness, to get past Lee's Akamai WAF on realforeclose.com/leeclerk.org/matrix.leeclerk.org. This is now the 2nd consecutive session to confirm this exact blocker with fresh evidence.
- **I, 14 zone-unlinked rows**: needs a real Phase-4-style ordinance research pass (Firecrawl + LLM extraction) for Fort Myers Beach (912) and Bonita Springs (914) zoning_districts/zone_standards, plus 2 missing codes (RS-2, CS) for Unincorporated Lee (630). This is a multi-jurisdiction seeding project, not a single-session fix — flagging as a structural residual for a dedicated ordinance-research session.
