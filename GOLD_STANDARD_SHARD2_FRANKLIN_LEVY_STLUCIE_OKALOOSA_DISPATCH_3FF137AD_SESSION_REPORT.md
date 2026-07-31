# Gold Standard Shard-2: franklin / levy / st_lucie / okaloosa

**dispatch_id:** `3ff137ad-8070-42f9-9c6f-13de33b53292` | **loop_run_id:** 7622 | **chat_session:** architect-20260731T080000
**Mode:** ULTRALOOP fallback (native `/effort ultracode` not invoked from this session shape; used `Workflow` tool directly per the fallback clause — one `agent()` per lever, one independent adversarial refuter per claim, results logged to `gold_standard_ultraloop_audit`).

## Before → After (live `pencil_dod_evaluate_county`, re-verified independently by me after the workflow closed)

| County | Before | After | Delta |
|---|---|---|---|
| franklin | 10/10 (A,B,C,D,E,F,G,H,I,J all PASS) | 10/10 (unchanged) | Audit-freshness refresh only — 5 letters (A,C,D,E,H) had no `gold_standard_ultraloop_audit` row inside the 7-day certify window; re-verified live and logged (ids 11494-11498) so the county stays certify-eligible. |
| levy | 9/10 (A FAIL: fc=0 td=29) | 9/10 (unchanged) | A re-probed fresh (levyclerk.com, floridapublicnotices.com, civitekflorida.com/ocrs/county/38) — dead end reconfirmed live, 3rd independent verification since 2026-07-11. No DB writes. |
| st_lucie | 8/10 (E FAIL 94.1%, I FAIL 94.1%) | 8/10 (unchanged) | 7 unlinked rows investigated — every direct source blocked (RealForeclose needs login, clerk case search Akamai-403'd, PA site has no case-number search, Firecrawl out of credits). No writes; no fabrication. |
| **okaloosa** | **6/10 (C,D,E,I FAIL)** | **9/10 (only I FAIL)** | **C/D/E flipped FAIL→PASS: 57/62 (91.9%) → 59/62 (95.2%).** 2 of 3 unlinked rows backfilled with real parcel_id + lat/long + assessed/market value via okgis.myokaloosa.com ArcGIS. |

## What actually shipped (okaloosa)

Two `multi_county_auctions` rows patched with GIS-sourced, independently re-verified data:

- `898efed2` (case 2025-CA-001837-C, 316 Hollywood Blvd SW, Fort Walton Beach) → `parcel_id=15-2S-24-219A-000B-0100`, lat/long, `assessed_value=market_value=183785`, `parity_status=matched_clean`, `parity_source=tier1_okgis_arcgis_shard2`. Source: `okgis.myokaloosa.com/arcgis/rest/services/Land-Ownership/Parcels_with_Addressing/MapServer/121`, exact single-feature match.
- `fac7e4d8` (case 2025-CA-002023-F, 201 Henderson Resort Way #2201, Destin) → `parcel_id=00-2S-22-1560-0000-2101`, lat/long, `assessed_value=market_value=720000`, `parity_status=matched_clean`. Cross-checked against a second independent county layer (`LocalGovernment/AssessmentInformation` MapServer/323, Tax Parcel Points) which returned the identical PIN and a point geometry matching the written lat/long to full float precision.

Third row (`df00f6fa`, case 2019CA000617F, 662 Harbor Blvd, Destin) deliberately **left unresolved**: the address resolves to 47 distinct condo-unit PINs with no unit number available in any source field, and the Bid4Assets detail page 403'd. Not guessed.

Note on the Henderson Resort row: Okaloosa's own GIS assigns **one PIN to all 8 recorded sub-units** of that building (a timeshare/interval-ownership structure per county records, confirmed across two independent county GIS layers) — a genuine county data quirk, not a scraping bug. Worth flagging fleet-wide as a pattern (echoes an unconfirmed Fla Stat 721.05 timeshare-estate concern raised for martin county in a prior session).

## ULTRALOOP catch: a wrong root-cause claim was refuted before it could ship

The okaloosa fixer agent claimed I's residual FAIL was because `v_zoning_gold_standard_card` has **zero rows fleet-wide** for okaloosa. The independent refuter re-queried the view directly and found **56 real rows** (36 Unincorporated, 7 Crestview, 6 Fort Walton Beach, 4 Destin, 3 Niceville, all with genuine `zone_code`/Municode `standards_source_url` values) — the fixer had misread a PostgREST `Content-Range: 0-0/56` pagination header as "0 total" instead of "1 row returned out of 56 total."

The I metric itself (`56/62`, unchanged, still FAIL) was accurate — only the causal narrative was wrong. Per ULTRALOOP protocol this claim's I-specific audit row was logged `survived=false` (id 11546) while C/D/E logged `survived=true` (ids 11543-11545), and I corrected `pipeline.counties.okaloosa.notes` live with the real framing: the 2 newly-linked parcels simply aren't among the zone-linked set in that view even though other parcels in the same jurisdictions are — a parcel-level gap, not a structural one. Next session should trace the view's actual join path before attempting more I work; `zoning_assignments` itself is confirmed empty for okaloosa county-wide, so the view sources zone linkage some other way.

## Honest non-results (no writes, no fabrication)

- **levy A**: 3rd independent live re-verification (2026-07-11, 2026-07-23, 2026-07-31, all this campaign) confirms the foreclosure calendar is genuinely empty. Real blocker for further progress: no headless-browser tool (Playwright/Firecrawl-browser) was available in-session to crack floridapublicnotices.com's SPA or civitekflorside's JSF session wall — not lack of effort. Firecrawl API returned HTTP 402 (out of credits) when both the st_lucie and levy agents tried to use it as a fallback.
- **st_lucie E/I**: all 7 gap rows traced to genuinely gated sources (RealForeclose requires a registered account for case detail; `courtcasesearch.stlucieclerk.gov` is Akamai-edge-blocked at 403 regardless of headers; the Property Appraiser site has no case-number search and needs an address as a starting point the blocked clerk system would normally supply). Recommended for a future session: a registered RealForeclose account/session, restored Firecrawl credits, or a human call to St Lucie's Research Dept (772-462-6930).

## Verification protocol evidence

Live `pencil_dod_evaluate_county` re-run by me (not the workflow agents) after the workflow closed, pasted above in the Before/After table. `gold_standard_ultraloop_audit` rows: 11494-11498 (franklin freshness), 11499 (levy A), 11500-11501 (st_lucie E/I), 11543-11546 (okaloosa C/D/E/I) — all confirmed present via independent GET.

`gold_standard_scoreboard` still shows okaloosa at 6/10 as of the 07:30Z snapshot — that table updates on the next scheduled `gold_standard_loop()` cron cycle, which per the parallel-fleet rules I did not trigger mid-session (other shards may be mid-flight). The 9/10 figure above is the live, independently-re-verified `pencil_dod_evaluate_county` result, not a scoreboard claim.

## Cost / mechanics

Ran via `Workflow` (ultracode opt-in): 3 fix agents + 3 adversarial refuter agents, 453,822 tokens, 172 tool calls, ~17 min wall-clock for the fanned-out phase. No code changes, no new migrations — pure live data backfill + one `pipeline.counties.notes` correction, both via Supabase Management API / PostgREST (direct `psql` auth to both pooler regions failed in this runner — Management API + PostgREST was the working path, consistent with `scripts/apply_sql_direct.py` / `scripts/apply_brevard_g_fix.py` prior-session patterns).

## Next-session priorities for this shard

1. **okaloosa I**: trace `v_zoning_gold_standard_card`'s real definition/join path (not `zoning_assignments`) to find why the 2 newly-linked parcels aren't zone-matched despite same-jurisdiction peers being matched. 6/62 rows short of 95%.
2. **st_lucie E/I**: needs either a registered RealForeclose session, restored Firecrawl credits, or human-channel lookup (clerk phone/PA office) for 7 case numbers — not solvable with anonymous curl/WebFetch alone.
3. **levy A**: structurally stable dead end (3 consistent verifications). Deprioritize unless a headless-browser tool becomes available in-session, or spend a session on the JSF AJAX handshake against civitekflorida.com with a proper cookie jar + `Faces-Request` headers.
