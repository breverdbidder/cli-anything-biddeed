# GOLD STANDARD SHARD-5: levy, jackson, sarasota — Session Report

dispatch_id: e1b98987-617e-4804-aac8-3c21bfbb3933
chat_session: architect-20260723T160000
issue: #13505
date: 2026-07-23

## Plan vs Actual

| County | Letter | Planned | Actual | Deviation |
|---|---|---|---|---|
| levy | A | fix foreclosure lane (fc=0) | re-verified genuine dead end, corrected a stale lead (agverso.com is the county library catalog, not court records) | no fix possible today — no fabrication, documented for future sessions |
| jackson | C/D | reconcile parity (86.3%) | **100% PASS** — 10-row calendar-harvest promote | none |
| jackson | I | card completeness (83.6%) | **unchanged (83.6%)** — 10/12 rows enriched (geo+value), but letter gated on a zoning-substrate join none of the 12 satisfy | refuted by adversarial verifier: real fix, real side-effect (E 95.9%→97.3%), but I itself did not move |
| sarasota | C/D | reconcile parity (37.2%, worse than stale brief) | **98.2% PASS** — 208-row calendar-harvest promote across 29 dates | none |
| sarasota | G | zoning parking coverage (0%) | **0%→18.8%** (still FAIL) | scope-corrected mid-session: true denominator is 32 county-wide applicable parcels, not the ~280 auction-linked parcels the first attempt targeted (see Deviation Log) |
| sarasota | I | card completeness (78.9%) | **92.1%** (still FAIL) — 46 new parcel_zones rows via 3 real GIS sources | 27 rows genuinely blocked (absent from source GIS), not fabricated |
| sarasota | J | deal-thesis completeness (0%) | **100% PASS** — 341-row bid_decisions generator | 212/341 rows use disclosed assessed-value fallback banding (no comps infra exists in this DB) — structural-completeness pass per evaluator contract, not a value-accuracy claim |

## Deviation Log

**Sarasota G — hit-list correction.** The first pass (background workflow, then my own follow-up) prioritized zoning districts by raw parcel_count (R-1 North Port 108 parcels, AC-10 69, RSF-3 26, AC-6 22, RSF-2 10 — a 235-parcel hit list). Before writing any ordinance-sourced values I checked `v_zoning_district_applicability` and found **all of those districts are flagged `pk1000_applicable=false`** — parking-per-1000sf is a commercial/office metric and the applicability view correctly excludes single-family/multi-family residential and Activity Center mixed-use codes from the parking denominator. The true denominator (`v_zoning_gold_standard_kpi_v3.pk1000_applicable_parcels`) is only **32 parcels county-wide** (not auction-scoped), and of those, 25 have **no matching `zoning_districts` row at all** (zone codes `RSF-4, RE-1, RE-2, CT, RSM-9, SAPD, CN, G, MP, OUE-1` exist in `parcel_zones` but were never catalogued as districts) — a genuine data-infrastructure gap, not a research-time gap. Only `CG`/`CSC`/`PID` (7 parcels) are both applicable and properly catalogued. I sourced a real Sarasota County commercial parking rate (zoneomics.com mirror of the County UDC: 1 space/250sf general commercial/retail = 4.00/1000sf) and backfilled `CG` + confirmed `CSC` already had it, moving pk1000 6/32→18.8%. `PID`'s use (commerce/economic/industrial, ambiguous) was left NULL rather than guessed. **Impact:** downstream sessions should not re-attempt the residential/Activity-Center hit list for sarasota G — it is structurally excluded from the denominator. The real next step is creating `zoning_districts`+`zone_standards` rows for the 10 orphaned codes (25 parcels), which requires per-code Sarasota County ordinance research, not a value backfill.

**Firecrawl unavailable.** firecrawl-scrape/search returned 402 (out of credit) for the entire session. All web research fell back to the built-in WebFetch tool, WebSearch, direct httpx/curl, and (for JS-rendered SPAs — levy.agverso.com, library.municode.com) a Playwright+Chromium install (`npm install --no-save playwright && npx playwright install chromium`) to trace live network/API calls. This worked for agverso.com (revealed it's the county library OPAC, not court records) but Municode's content API required a bearer token the Angular client sets client-side that a bare `fetch(..., {credentials:'include'})` didn't carry — that specific avenue was abandoned in favor of a zoneomics.com mirror + WebSearch, which did yield real, citable numbers.

## Verification Evidence (BEFORE → AFTER, live pencil_dod_evaluate_county)

### levy — 9/10 (unchanged; A confirmed genuine dead end)
```
BEFORE (2026-07-23T16:00Z): A fail metric=0 (fc=0 td=29); B-J all PASS
AFTER  (2026-07-23T16:46Z): A fail metric=0 (fc=0 td=29); B-J all PASS
```
Re-verified live via WebFetch: levyclerk.com foreclosure page still states "There are no foreclosure sales available at this time." levy.agverso.com rendered via Playwright (network trace: `/searchapi/`, `/agapi/` endpoints, body text confirms Auto-Graphics Inc. library OPAC) — corrected a prior session's open lead; this is the Levy County **public library catalog**, unrelated to court/foreclosure records. `pipeline.counties.notes` updated with this correction so no future session re-investigates it. A remains a genuine dead end pending an actual scheduled Levy foreclosure sale.

### jackson — 7/10 → 9/10
```
BEFORE: {"A":{"pass":true,"metric":15},"B":{"pass":true,"metric":100},"C":{"pass":false,"metric":86.3,"detail":"matched_clean=63"},"D":{"pass":false,"metric":86.3,"detail":"matched_any=63"},"E":{"pass":true,"metric":95.9},"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":3.4},"I":{"pass":false,"metric":83.6,"detail":"card_complete=61 of 73"},"J":{"pass":true,"metric":100},"auctions_total":73}
AFTER:  {"A":{"pass":true,"metric":15},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":100,"detail":"matched_clean=73"},"D":{"pass":true,"metric":100,"detail":"matched_any=73"},"E":{"pass":true,"metric":97.3,"detail":"parcel_linked=71"},"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":0.3},"I":{"pass":false,"metric":83.6,"detail":"card_complete=61 of 73"},"J":{"pass":true,"metric":100},"auctions_total":73}
```
**C/D fix:** ran `scripts/shard6_run3025_2nd_dispatch_jackson_cd_parity.py` with 2 new (sale_type, auction_date) targets not in its original TARGETS list (foreclosure 2026-07-23, tax_deed 2026-08-25) — live RealAuction/RealTaxDeed AJAX calendar harvest, exact case_number match, 10/10 promoted. Adversarially re-verified independently (not part of this fix's own claim).
**I attempt (refuted — no letter movement):** enriched 10/12 incomplete rows with real lat/long/assessed_value from the FL statewide cadastral ArcGIS service (9 tax-deed parcels) + 1 case fully resolved (parcel_id + geo + value from the same source). 2 rows (322025CC000895CCAXMX, 322025CA000120CAAXMX) remain genuinely blocked — no address/legal description in the DB to match against any parcel source, and every lookup path tried (RealForeclose detail pages, Jackson Clerk OCRS docket search, Wayback Machine, county GIS) was session-gated or empty. Independently confirmed via `SELECT pz.parcel_id FROM parcel_zones pz WHERE parcel_id IN (<10 fixed ids>)` → 0 rows: none of the 10 fixed parcels have a zone_code match in `parcel_zones`, which is I's real (and previously undiagnosed) bottleneck for jackson — not address/geo/value completeness. Side effect: E improved 95.9%→97.3% (70→71 of 73 parcel-linked) because one row gained a real parcel_id.

### sarasota — 5/10 → 8/10
```
BEFORE (2026-07-23T16:00Z): {"A":{"pass":true,"metric":59},"B":{"pass":true,"metric":98.0},"C":{"pass":false,"metric":37.2,"detail":"matched_clean=127"},"D":{"pass":false,"metric":37.2,"detail":"matched_any=127"},"E":{"pass":true,"metric":95.2},"F":{"pass":true,"metric":98.0},"G":{"pass":false,"metric":0,"detail":"density=74.9 far=88.6 pk1000=0.0"},"H":{"pass":true,"metric":0.3},"I":{"pass":false,"metric":78.9,"detail":"card_complete=269 of 341"},"J":{"pass":false,"metric":0,"detail":"deal_complete=0"},"auctions_total":341}
AFTER  (2026-07-23T16:46Z): {"A":{"pass":true,"metric":93,"detail":"fc=93 td=248"},"B":{"pass":true,"metric":98.3,"detail":"verified=119 closed_sold=121"},"C":{"pass":true,"metric":98.2,"detail":"matched_clean=335"},"D":{"pass":true,"metric":98.2,"detail":"matched_any=335"},"E":{"pass":true,"metric":95.9,"detail":"parcel_linked=327"},"F":{"pass":true,"metric":98.3,"detail":"tier1_sold=119 closed_sold=121"},"G":{"pass":false,"metric":18.8,"detail":"density=75.2 far=86.9 pk1000=18.8"},"H":{"pass":true,"metric":0.2},"I":{"pass":false,"metric":92.1,"detail":"card_complete=314 of 341"},"J":{"pass":true,"metric":100,"detail":"deal_complete=341"},"auctions_total":341}
```
(auctions_total grew 341→341 flat during this session's fix window, but the county's calendar-sweep grew it from ~187 at brief-authoring time to 341 by session start — denominator drift is from routine ingestion, not this session's writes; each fix below independently re-confirmed auctions_total unchanged across its own before/after pair.)

**C/D (survived adversarial verify):** `scripts/gold_standard_shard6_run5361_sarasota_cd_parity_calendar_harvest.py` (new, committed) ran the jackson-proven harvest_date()+exact_match_and_promote() pattern across all 29 (sale_type, auction_date) pairs with `parity_status IS NULL`. All 29 dates returned live calendar data (zero 0-item dates), 208/214 rows promoted. Residual 6 rows remain `parity_status IS NULL` (not in this session's calendar snapshot). Refuter independently re-ran the evaluator, the residual query, traced all 208 changed rows to 28 distinct `parity_source` tags matching the script's own reported per-date counts exactly, and confirmed the mechanism against the actual committed script — verdict: **survived=true**.

**I (survived adversarial verify):** 46 new `parcel_zones` rows inserted from 3 real GIS sources (`scgov_arcgis`=24, `northport_gis_arcgis`=19, `cos_zoning_arcgis`=3) for auction parcels previously absent from the zoning substrate. Refuter independently verified row timestamps, source attribution, and reproduced the "genuinely absent from source" claim for residual blockers by directly querying the live ags3.scgov.net ParcelProperty FeatureServer for 4 sample parcel IDs (0 features returned, confirmed real gap not a lookup mistake). 27 rows remain blocked (8 have literal "Address Not Available" placeholders with no parcel_id at all; the rest are condo units absent from the county's parcel-hosted GIS layer). Verdict: **survived=true** (genuine improvement; letter itself still below the 95% pass bar).

**G (self-verified, not routed through the background workflow's verify stage — the workflow's own G attempt was blocked by a transient DB-connectivity outage and never wrote anything):** After the outage cleared, I re-diagnosed live and found the workflow's original hit list was scoped wrong (see Deviation Log). Backfilled `zone_standards.parking_per_1000sf=4.00` for `CG` (new row) confirmed `CSC` already had 4.00 from a prior session, sourced from zoneomics.com's mirror of the Sarasota County UDC general-commercial parking rate (1 space/250sf). Before: `pk1000_applicable_parcels=32, pct=0.0`. After: same 32-parcel denominator, `pct=18.8`. `PID` (1 parcel, ambiguous commerce/industrial use) intentionally left NULL rather than guessed.

**J (survived adversarial verify):** `shard_j_generator_sarasota_20260623.sql` → committed as `shard_j_generator_sarasota_20260723.sql` (new, committed) extends the county-agnostic shard28 J generator pattern. 341/341 rows now satisfy the full evaluator contract (arv, max_bid, ml_score, all 5 factor keys). Refuter confirmed via `to_regclass` that no comps/valuation infrastructure exists in this DB (`property_valuations`, `gen_valuations_comps_batch`, `shapira_scores`, `distress_*_scores` all absent) — 212/341 rows use a disclosed assessed-value-derived fallback banding, matching the same posture used in the reference brevard/duval generator run. This is a structural-completeness pass per the evaluator's own field-presence contract, not a value-accuracy claim. Verdict: **survived=true**.

## Fleet-Awareness Compliance

Confirmed via `gh run list --status in_progress` at session start: 7 other GOLD STANDARD shard sessions were mid-flight concurrently (shards 1, 2, 3, 7, 9, 10, 12). Per PARALLEL-FLEET RULES, **`gold_standard_loop()`/`gold_standard_certify()` were NOT run** — only per-county `pencil_dod_evaluate_county` evaluations, as required when other sessions are mid-flight. `git pull --rebase origin main` was run before every push; all commits landed directly on main, no side branches.

## Commits

- `fb9f23ac` fix(gold-standard-shard6-run5361): sarasota C/D 37.2%->98.2% — 208-row parity backfill
- `719c233d` fix(gold-standard-shard5-run5361): sarasota J 0%->100% PASS — 341-row bid_decisions generator
- (this report)

## Next-Session Priorities

1. **jackson I**: the real bottleneck is zoning-substrate linkage (`parcel_zones` zone_code match), not address/geo/value — 12 parcels need a Jackson County zoning lookup, and 2 of those additionally need a parcel_id found via a non-address-matching method (docket/legal description recovery).
2. **sarasota G**: build `zoning_districts` + `zone_standards` rows for the 10 orphaned zone codes (`RSF-4, RE-1, RE-2, CT, RSM-9, SAPD, CN, G, MP, OUE-1`, 25 parcels) — this is the only path to 95%, not further residential/Activity-Center backfill (those are correctly excluded from the denominator).
3. **sarasota I**: 27 rows are structurally blocked (dead addresses / condo units absent from county GIS) — likely at or near the practical ceiling without a different source (e.g. property appraiser tax roll instead of GIS parcel layer).
4. **levy A**: dead end confirmed twice now (2026-07-11 and 2026-07-23) — do not re-investigate agverso.com (confirmed library catalog) or floridapublicnotices.com/civitekflorida.com (session-walled) without a new lead.
