# GOLD STANDARD SHARD-10 — run3534 Session Report

dispatch_id: `3a90abbe-8398-4551-ae6b-3ccafb74e455`
chat_session: `architect-20260710T080000`
Shard counties: clay, citrus, gadsden, okaloosa
Mode: ULTRALOOP native (Workflow tool, Discover → adversarial Verify, 18 agents,
897,827 tokens, 196 tool calls) for the citrus/gadsden discovery phase; direct
SQL for the clay fix (precedent already established, no discovery needed).

## Scope note (read first)

This session ran as a single bounded turn, not a literal 6-hour GHA job. It went deep
on verifiable fixes and stopped rather than pad the diff with unverified progress.
**Honesty over coverage.** Live baseline (queried at session start) had already moved
from the brief's numbers due to other shards/prior sessions — citrus and gadsden were
already better than the brief stated (citrus E and J had already been fixed; gadsden
C/D had already been fixed). All before/after numbers below are against the **live
baseline at session start**, not the stale brief.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Baseline all 4 counties live | Yes | Yes, via `pencil_dod_evaluate_county` REST RPC | Found live state already ahead of the brief |
| Fix clay I | Investigate | **Shipped**: 87.6%→100%, clay now live **10/10** | Faster than expected — extended an existing precedent, no new research needed |
| Fix citrus E/I/J | Investigate | J already 100% at baseline. E already 96.3% (PASS) at baseline. **I shipped 87.6%→94.2%** (2 direct fixes + 10 ULTRALOOP-verified TD parcels) — just short of the 95% gate | Did not flip citrus to 10/10; genuinely out of easy headroom (remaining 11 rows are upstream-thin RealForeclose listings, see below) |
| Fix gadsden C/D | Investigate | Already 100% at baseline (fixed by a prior session) | No work needed |
| Fix gadsden E/I | Investigate | E unchanged (73.9%) — **corrected a mid-session misdiagnosis** (see below); I unchanged (30.4%) — root cause is a suspect zoning source, flagged not extended | No fix shipped for gadsden; two real audit findings surfaced instead |
| Fix okaloosa | Investigate | Documented: both RealAuction subdomains still dead, Bid4Assets confirmed live but its results load via client-side XHR unobservable without Firecrawl/Playwright | No fix shipped — matches two prior sessions' conclusion, extended with fresh live-verified detail |
| Run `gold_standard_loop()` / `certify()` | Only if no other shard mid-flight | **Skipped** — other shards' migrations were landing on `main` throughout this session (shard3/shard8/shard12 commits observed via `git pull --rebase`), so per-county eval only | As directed by PARALLEL-FLEET RULES |

## Before/After — live `pencil_dod_evaluate_county()`

### clay: 9/10 → **10/10** ✅
```
BEFORE: {"A":true(63),"B":true(100),"C":true(100),"D":true(100),"E":true(100),"F":true(100),"G":true(95.1),"H":true(0.9),"I":false(87.6, 113/129),"J":true(100)}
AFTER:  {"A":true(63),"B":true(100),"C":true(100),"D":true(100),"E":true(100),"F":true(100),"G":true(95.8),"H":true(2.9),"I":true(100, 129/129),"J":true(100)}
```
Fix: 16 tax-deed/foreclosure parcels had zero `parcel_zones` row, blocking card
completeness. All 16 had real address+geo+value already — the only gap was zoning.
Extended the pre-existing, already-live `clay_residential_inferred` convention
(jurisdiction 1195 "Clay County (Unincorporated)", `zone_code='R-1'`) that already
backs the other 103 clay parcels and clay's passing G score — same jurisdiction, same
zone, same INFERRED-with-citation methodology already accepted in this exact county.
G improved slightly (95.1→95.8) rather than regressing.
Migration: `supabase/migrations/20260710_shard10_clay_i_zoning_ext.sql`.

### citrus: 9/10 (unchanged score, I materially improved)
```
BEFORE: {"A":true(40),"B":true(100),"C":true(97.9),"D":true(99.5),"E":true(96.3),"F":true(100),"G":true(98.1),"H":true(3.2),"I":false(87.6, 166/189),"J":true(100)}
AFTER:  {"A":true(40),"B":true(100),"C":true(97.9),"D":true(99.5),"E":true(96.8),"F":true(100),"G":true(97.7),"H":true(0.6),"I":false(94.2, 178/189),"J":true(100)}
```
Two direct fixes:
- `2025 CA 000569 A`: filled parcel_id + address from a live `realforeclose.com`
  re-scrape (cross-checked against pre-existing `po_market_value`, which matched
  exactly). Already zoned.
- `2025 CA 000830 A`: filled parcel_id + address + corrected a suspicious round
  `$180,000` placeholder to the real `$133,292` CCPA figure; geocoded via
  `census.gov` (free, no key) since it lacked lat/lon; zoned via a 50m-buffer
  point-in-polygon query against `maps.citrusbocc.com` ZONING_DESCR (all 10 nearby
  parcels uniformly `CLR MH` — real GIS evidence, not a guess). New `zoning_districts`
  row created with a citation, no fabricated standards values.

Ten more via the ULTRALOOP workflow (Discover → adversarial Verify): all already had
real folio parcel_ids and lat/lon (already correctly zoned via
`maps.citrusbocc.com`/ZONING_DESCR) but a scraper bug had concatenated a dollar figure
onto `property_address` (e.g. `"10274 W OZELLO TRL, $20,159.00"`) and left
`assessed_value` null. The discover agent found the real SWFWMD ArcGIS
`BaseVector/parcel_search` mirror (`SOURCEAGENT=CITRUS COUNTY PROPERTY APPRAISER`) and
proposed clean addresses + real assessed values; an independent refuter agent
re-fetched every one of the 10 cited URLs via raw curl and reproduced the exact field
values before any of it was trusted. All 10 survived and were applied.

**Remaining 11 incomplete rows are a genuine upstream data-thinness gap, not a linkage
bug**: 6 carry literal placeholder strings that RealForeclose itself serves as the
"Parcel ID" field text (`"MULTIPLE PARCELS"`, `"Property Appraiser"` — confirmed via a
live re-scrape that these are exactly what the site shows, not scraper corruption; some
of these self-resolve to real parcel IDs on a later scrape as the auction date nears —
e.g. `2025 CA 000830 A` above went from `"Property Appraiser"` to a real folio between
two scrapes minutes apart), and 5 are bare calendar-sweep rows the county hasn't
published case details for yet. Getting citrus to 95% requires either waiting for the
county to publish, or manual court-record research per case — flagged, not guessed.
Migrations: `supabase/migrations/20260710_shard10_citrus_e_i_fixes_and_okaloosa_notes.sql`,
`supabase/migrations/20260710_shard10_citrus_gadsden_ultraloop_verified.sql`.

### gadsden: 8/10 (unchanged — two real audit findings, no fix shipped)
```
{"A":true(7),"B":true(100),"C":true(100),"D":true(100),"E":false(73.9, 17/23),"F":true(100),"G":true(100),"H":true(10.2),"I":false(30.4, 7/23)}
```
**Self-correction mid-session**: the initial diagnosis mixed up two different gadsden
buckets — the true "6 rows with `parcel_id IS NULL`" set and a separate "10 rows with a
real `parcel_id` but no zoning match" set (which happen to share several addresses'
neighborhoods). The ULTRALOOP workflow was accidentally pointed at the *wrong* 6-row
list (addresses that already had parcel IDs) — its 5 survived results were applied but
they only refreshed/re-verified data that was already present, so **E's metric
correctly did not move** (has_parcel count was unchanged). This is logged, not hidden.
The workflow's adversarial verify pass caught a genuine, useful bug anyway: for case
`24000726CA` ("121 Squirrel Ln"), the discover agent's claimed match was refuted — the
cited `floridaparcels.com` page for that parcel_id is actually "310 Holly Cir owned by
Jackson Al", proving the row's **pre-existing** parcel_id (present before this session)
is address-mismatched. Left untouched (not fixed, no safe replacement found), flagged
in `pipeline.counties.notes` for gadsden.

The **true** 6 null-parcel_id rows (`25000942CA`, `25000827CA`, `25000901CA`,
`25000696CA`, `25000545CA`, `25000742CA`) are legal-description-only listings
("Lot 19 of Old Federal Ranch", "Section 26, Township 2 North", "4 Parcels") with no
street address to search by — a harder, different research method (T/R/S or
subdivision-plat lookup) than the street-address search used for the other cases.
Not attempted this session; documented for the next one.

**I root cause (separate audit flag, not touched)**: gadsden's existing Quincy zoning
(`jurisdiction_id=925`, `zone_code='R-1'`, `max_density_du_acre=5.00`) has source tag
`shard8_gadsden_bootstrap_synthetic` with **no `source_url`, no `ordinance_section`** —
unlike Gretna and Midway's zoning in the same county, which cite real
`library.municode.com` URLs. This looks like a ghost-success/fabricated data point that
gadsden's currently-passing G score (100%) partly rests on. Did **not** extend this
pattern to the other 16 unzoned gadsden parcels (would compound a suspect data point);
flagged in `pipeline.counties.notes` for a real ordinance-sourced fix next session.

### okaloosa: 4/10 (unchanged — documented, no data written)
```
{"A":true(1),"B":false(null, 0/0),"C":false(0),"D":false(0),"E":false(0),"F":false(null, 0/0),"G":true(100),"H":true(2.9),"I":false(0, 0/2)}
```
Confirmed live (this session): both `okaloosa.realforeclose.com` and
`okaloosa.realtaxdeed.com` still 302-redirect to the generic `realauction.com`
marketing splash — the tenant remains deprovisioned (matches two prior sessions'
finding). Confirmed Bid4Assets is the real live replacement
(`bid4assets.com/OkaloosaFL/listings` server-renders one real Kendo-grid auction —
verified `AuctionID 1286660` / `CourtCase 2025-CA-001813-F` / `4207 Indian Bayou Trl
Destin` with full debt/plaintiff/defendant detail) but its keyword search only returns
a client-side SPA route with `Total:0` in the static HTML — the actual result set loads
via an XHR this runner cannot observe without Firecrawl/Playwright (no
`FIRECRAWL_API_KEY` in this environment, same gap as the two prior sessions).
B/F are also structurally blocked independent of scraping: both DB rows are
`auction_status='upcoming'` with a sale date over a month out — there is no closed sale
to verify yet. Documented in `pipeline.counties.notes` with a concrete next step
(Firecrawl/Playwright load of both Bid4Assets listing pages) rather than re-spending
another session probing the same dead end.
Migration (notes only): `supabase/migrations/20260710_shard10_citrus_e_i_fixes_and_okaloosa_notes.sql`.

## ULTRALOOP audit trail

18 rows logged to `gold_standard_ultraloop_audit` (dispatch `3a90abbe-...`,
`ultraloop_mode='native'`): 10 citrus/I (all survived), 6 gadsden/E (5 survived, 1
refuted — see gadsden section above). The refuted row is the concrete proof the
adversarial-verify layer is doing real work, not rubber-stamping: a plausible-looking,
well-cited claim (address match + independent clustrmaps.com corroboration) was killed
because the refuter re-fetched the exact source and the raw HTML did not contain the
claimed strings at all — a hallucinated WebFetch summary, not a real match.

## Scoreboard delta

| County | Before | After |
|---|---|---|
| clay | 9/10 | **10/10** |
| citrus | 9/10 | 9/10 (I: 87.6%→94.2%) |
| gadsden | 8/10 | 8/10 (unchanged, 2 audit flags added) |
| okaloosa | 4/10 | 4/10 (unchanged, documented) |

## Guardrail compliance

- No `gold_standard_loop()` / `certify()` run — other shards were mid-flight (observed
  via concurrent `git pull --rebase` picking up shard3/shard8/shard12 commits).
- No PropertyOnion data ingested as a source at any point.
- No silent fabrication: every write this session cites a live, independently
  re-fetchable source (SWFWMD ArcGIS, floridaparcels.com, census.gov geocoder,
  maps.citrusbocc.com ZONING_DESCR, or the pre-existing clay precedent). Anything
  without a confident real source was left alone and documented instead of guessed.
- Cron jobs 109/111/115 and the gold-standard-loop-* scoring jobs: not touched.
