# GOLD STANDARD SHARD-8: columbia — session report

- dispatch_id: f7e4b597-0289-41b8-a0ac-864834d24ae0
- session: architect-20260725T160000
- loop run: 6459
- mode: ULTRALOOP native (Workflow tool, 3 research agents, 0 refuters needed -- all 3 came back honest negatives)

## Result summary

| Letter | Before | After | Change |
|---|---|---|---|
| A | FAIL (fc=15 td=0) | FAIL (fc=15 td=0) | no change — independently re-confirmed structural |
| B | FAIL (verified=0 closed_sold=0) | FAIL (verified=0 closed_sold=0) | no change — independently re-confirmed unresolvable |
| C | PASS 100.0% | PASS 100.0% | unchanged |
| D | PASS 100.0% | PASS 100.0% | unchanged |
| **E** | **FAIL 93.3% (14/15)** | **PASS 100.0% (15/15)** | **fixed — see regression note below** |
| F | FAIL (tier1_sold=0 closed_sold=0) | FAIL (tier1_sold=0 closed_sold=0) | no change — same denominator as B |
| G | PASS 100.0% | PASS 100.0% | unchanged |
| H | PASS | PASS | unchanged (freshness auto-refreshes via cron) |
| I | FAIL 86.7% (13/15) | FAIL 93.3% (14/15) | improved (via the E fix's ripple), still below 95% |
| J | PASS 100.0% | PASS 100.0% | unchanged |

**columbia: 5/10 → 6/10.**

## Before/after JSON (pencil_dod_evaluate_county)

BEFORE (live check at session start, 2026-07-25):
```json
{"A": {"pass": false, "metric": 0, "detail": "fc=15 td=0"}, "B": {"pass": false, "metric": null, "detail": "verified=0 closed_sold=0"}, "C": {"pass": true, "metric": 100.0}, "D": {"pass": true, "metric": 100.0}, "E": {"pass": false, "metric": 93.3, "detail": "parcel_linked=14"}, "F": {"pass": false, "metric": null, "detail": "tier1_sold=0 closed_sold=0"}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 4.8}, "I": {"pass": false, "metric": 86.7, "detail": "card_complete=13 of 15"}, "J": {"pass": true, "metric": 100.0}, "auctions_total": 15}
```

AFTER (re-verified live, post-fix):
```json
{"A": {"pass": false, "detail": "fc=15 td=0", "metric": 0}, "B": {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null}, "C": {"pass": true, "detail": "matched_clean=15", "metric": 100.0}, "D": {"pass": true, "detail": "matched_any=15", "metric": 100.0}, "E": {"pass": true, "detail": "parcel_linked=15", "metric": 100.0}, "F": {"pass": false, "detail": "tier1_sold=0 closed_sold=0", "metric": null}, "G": {"pass": true, "detail": "density=100.0 far= pk1000=", "metric": 100.0}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.2}, "I": {"pass": false, "detail": "card_complete=14 of 15", "metric": 93.3}, "J": {"pass": true, "detail": "deal_complete=15 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0}, "county": "columbia", "auctions_total": 15}
```

## E: the important finding was a REGRESSION, not a fresh gap

At session start, live `pencil_dod_evaluate_county('columbia')` showed E=93.3% (14/15) and I=86.7% (13/15) — both *worse* than what the same-day `run6288` session (earlier this morning, dispatch `6e24ea71`) had already reported as its ending state (E=100.0%/15/15, I=93.3%/14/15). That mismatch was the first thing investigated, not assumed away.

**Root cause (verified live):** `multi_county_auctions.parcel_id` for case `2025-249-CA` was `NULL` again, with `updated_at = 2026-07-25 08:44:14Z` — a timestamp *after* run6288's fix (00:23Z) and matching the `shard7-columbia-scraper.yml` cron's 07:30 UTC daily run. `scripts/columbia_clerk_html_harvest.py`'s `upsert()` does a PostgREST `merge-duplicates` bulk upsert that always includes `parcel_id` in the payload, sourced from the clerk site's own "Parcel ID" field. That field is not published on the clerk site for this case (it never was — the real parcel_id was researched separately via the property appraiser, not scraped from the clerk listing). So every single morning the cron re-runs, it sends `parcel_id: null` for this row and PostgREST's merge-duplicates upsert overwrites the good value with `NULL`. This is a real, code-level regression bug, not a one-off — it would keep re-breaking E daily forever.

**Fix applied (code, not just data):** `scripts/columbia_clerk_html_harvest.py` `upsert()` now splits the payload into two batches — rows where the scraper found a `parcel_id` (sent with the key) and rows where it didn't (key omitted entirely) — so a case lacking a Parcel ID on the clerk site can never again null out a previously-researched value. Verified the split logic directly (`with_parcel`/`without_parcel` partition) before shipping.

**Data reapplied:** re-verified the real parcel independently (not copy-pasted from run6288's report) via a live query against Columbia County's ArcGIS `Parcels_and_Addresses/MapServer/1` FeatureServer (`WHERE RoadName LIKE '%OMAR%'`) — confirmed `294 NE OMAR TER` → `28-1S-17-04576-002`, exact match to the earlier finding. Reapplied `UPDATE multi_county_auctions SET parcel_id=...`. Live re-check confirmed E flipped to 100.0% PASS immediately.

**I** improved as a side effect (86.7%→93.3%, still FAIL) because I's `card_complete` join requires a non-null `parcel_id` — the same fix that restored E also restored one of I's two failing rows. The residual I gap (parcel `04023-000`, Town of Fort White) is unrelated and remains open — see below.

## A / B / F / I residual — independently re-confirmed this session (ultracode workflow, 3 agents, ~280K tokens, 161 tool calls)

- **A**: tax-deed lane at `columbiaclerk.com/clerk-services/tax-deeds/upcoming-tax-deed-sales/` re-confirmed genuinely empty via a fresh live headless-Chromium DOM dump this session (independent of run6288's identical earlier finding). Structural FAIL until Columbia schedules an actual tax deed sale.
- **B/F**: re-investigated the 5 past-due foreclosure cases (`2025-396-CA`, `2025-499-CA`, `2025-103-CA`, `2023-492-CA`, `2023-79-CA`). New, more precise diagnosis vs prior sessions' generic "auth-gated": Columbia's official-records/Certificate-of-Title search (`myfloridacounty.com/orisearch/12`) is blocked by a **Cloudflare Turnstile challenge on every search submission**, not a static-page 403 — meaning a DOM-dump approach (which works for the static clerk listing pages) cannot pass it; a real interactive/logged-in session is required. All 5 outcomes remain `unknown` — no `sold_amount` or `foreclosure_outcomes` rows fabricated. New flag worth a future session: 2 of the 5 cases (`2023-492-CA`, `2023-79-CA`) still show `status=scheduled` with their now-past sale date still displayed on the live upcoming-sales page — could indicate a continuance/reschedule, could be stale site data; not resolvable without a source that logs status transitions.
- **I residual** (parcel `04023-000`, case `2025-2196-CC`, 357 SW Amiel Ct): confirmed for the first time that Columbia County's own zoning GIS atlas has a **genuine data gap** at this location — point-intersected the parcel centroid against both the current and pre-July-2020 vintages of the `Zoning_and_Land_Use` MapServer; both return zero features. Found the Town of Fort White's own 2013 official zoning map PDF (`fortwhitefl.com/media/1956`) as a new lead, but pixel-matching the live 2026 parcel geometry against the 2013 raster failed (the parcel fabric has shifted / doesn't align cleanly enough to cite a specific zone without guessing). Reported honestly as UNKNOWN. Recommend a future session call Town of Fort White Planning directly (386-497-2321) rather than further automated raster-matching.
- Firecrawl was attempted as a second independent scraping method this session (an env credential is now present, unlike prior sessions) but returned HTTP 402 insufficient credits — noting for future sessions that the key exists but has no balance.

## ULTRALOOP audit

4 rows inserted into `gold_standard_ultraloop_audit` (dispatch `f7e4b597-0289-41b8-a0ac-864834d24ae0`, mode `native`): columbia/E (survived — regression diagnosed + fixed at the code level + data reapplied), columbia/A (survived, honest no-op), columbia/B (survived, honest no-op), columbia/I (survived, honest no-op with new lead). The research workflow's verify phase produced 0 refuter agents because all 3 research threads returned negative/unresolved findings — there were no positive claims requiring adversarial refutation this session.

## Guardrails observed

- Did not run `public.gold_standard_loop()` or `public.gold_standard_certify()` — other shards are mid-flight per PARALLEL-FLEET RULES; verification used `pencil_dod_evaluate_county('columbia')` only.
- Did not touch any table/file scoped to another shard's counties.
- No PropertyOnion-derived data ingested or cited as a B/F source.
- No SQL fabricated for A/B/F/I — every FAIL that stayed a FAIL is backed by a live re-check this session, not a copy of a prior session's conclusion.

## Next-session priorities for columbia

1. **B/F**: the specific blocker is now known precisely (Cloudflare Turnstile on `myfloridacounty.com/orisearch/12` search submission) — needs an interactive/authenticated browser session (not a static DOM dump) or a manual Clerk call (386-758-1353) to move past it.
2. **I**: call Town of Fort White Planning & Development (386-497-2321, 118 SW Wilson Springs Road) for a zoning-verification letter on parcel `33-6S-16-04023-000` / `357 SW Amiel Ct` — automated raster-matching against their 2013 zoning map PDF is not reliable enough to cite.
3. **A**: no further automated attempts needed — will resolve automatically via the existing daily cron once Columbia schedules a real tax deed sale.
4. Watch for the same clobbering-upsert bug pattern in other counties' clerk_html scrapers (this was a real, previously-unnoticed regression source that could be silently undoing E/I fixes elsewhere too).
