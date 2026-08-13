# Gold Standard — citrus (C/D/E/I), session 2026-08-13

## Scope
citrus only, per dispatch brief targeting letters C, D, E, I (all 89-91% band,
auctions_total=207).

## Baseline (verified live, session start, 2026-08-13)
```json
{"A":{"pass":true,"metric":56,"detail":"fc=151 td=56"},
 "B":{"pass":true,"metric":100.0,"detail":"verified=3 closed_sold=3"},
 "C":{"pass":false,"metric":89.4,"detail":"matched_clean=185"},
 "D":{"pass":false,"metric":90.8,"detail":"matched_any=188"},
 "E":{"pass":false,"metric":90.8,"detail":"parcel_linked=188"},
 "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=3 closed_sold=3"},
 "G":{"pass":true,"metric":95.7,"detail":"density=95.7"},
 "H":{"pass":true,"metric":0.1},
 "I":{"pass":false,"metric":89.4,"detail":"card_complete=185 of 207"},
 "J":{"pass":true,"metric":100.0},
 "auctions_total":207}
```
(6/10 passing at session start)

## Prior context read first (per campaign rule)
- `GOLD_STANDARD_SHARD2_INDIANRIVER_CITRUS_LEE_LIBERTY_COLUMBIA_DISPATCH_C3B1E7CC_SESSION_REPORT.md`
  (2026-08-01, most recent citrus report) — E was flipped to PASS then, but a
  fresh live check this session showed E had regressed back to FAIL because
  16 new rows were ingested 2026-08-13 with null parity/parcel data, pulling
  the denominator back down. Also carried forward the residual on case
  `2023 CA 000716 A` (disputed parcel reverted to NULL by an adversarial
  refuter, with a `clerk_url` pointing to CFN 2024057071 as an unresolved
  lead).
- `GOLD_STANDARD_SHARD5_CITRUS_DISPATCH_A308FAC7_RUN6871_SESSION_REPORT.md`
  (2026-07-27) — documented FL Statewide Cadastral ArcGIS timing out
  repeatedly in this sandbox; re-confirmed the same failure this session
  (single retry, not repeated exhaustively, per cost discipline).
- `GOLD_STANDARD_SHARD4_CITRUS_OSCEOLA_DISPATCH_C271DA62_SESSION_REPORT.md`
  — established that citrus I's remaining CA-type gap rows need Citrus
  Clerk SCORSS/LandmarkWeb (CAPTCHA-gated), not resolvable here.

## Diagnosis
Live query of `parity_status IS NULL` rows for citrus turned up exactly 18
rows: 16 from a single fresh ingestion batch (`created_at` 2026-08-13T06:48:02Z,
case numbers `2026-0154TD` through `2026-0175TD`, all `source_platform=realtaxdeed`,
`auction_date=2026-09-16`) plus 2 older rows (`2025 CA 000376 A`, ingested
2026-05-21; `2025 CA 001016 A`, ingested 2026-07-24) that had simply never
been parity-scored.

## Fix 1 — C/D: 18-row parity backfill (mechanical, matches lake_c_3row pattern)
- Live-harvested the official Citrus RealTaxDeed AJAX auction calendar
  (`citrus.realtaxdeed.com`, proper browser UA required — bare-subdomain
  requests without a UA 403; with UA, 200) for auction date 2026-09-16.
  All 18 items on the live calendar (16 target cases + 2 others) matched our
  16 target case numbers **exactly** by case number and property address —
  confirmed not a scraper artifact, just an un-scored fresh batch.
- For `2025 CA 000376 A`: pulled the recorded Uniform Final Judgment of
  Foreclosure PDF directly from `search.citrusclerk.org` (CFN 2025068929,
  the row's own `clerk_url`) — confirmed exact case number and property
  address (`5006 S ATWOOD TER, INVERNESS, FL 34452`) match. This document
  is a definitive tier-1 source (the actual recorded judgment), independent
  of RealForeclose/PropertyOnion.
- For `2025 CA 001016 A`: row already carried `tier1_authoritative=true`,
  `tier1_sale_status='CANCELED_PER_COUNTY'` from a concurrent system
  verification pass (timestamped minutes before this session's write).
  Independently corroborated: zero items on the live RealForeclose AJAX
  calendar for its `auction_date` (2026-08-20), consistent with a cancelled
  case having dropped off the county's live calendar.
- Wrote `parity_status='matched_clean'` + sourced `parity_source` values to
  all 18 rows (see SQL VERIFICATION below). PO was never consulted for any
  of these — all sourced from the county's own tier-1 platforms.

**Result: C 89.4%->98.1% (203/207) PASS. D 90.8%->99.5% (206/207) PASS.**

## Fix 2 — E: real parcel_id recovery for the same 16 TD rows
The live RealTaxDeed AJAX detail blocks for each of the 16 fresh TD cases
include an "Alternate Key" field — a direct link to
`citruspa.org/_Web/datalets/datalet.aspx?...&pin=<PIN>` — which is the real
Citrus Property Appraiser parcel PIN, not previously captured by the base
harvester (which only parses the generic "Parcel ID" label, absent on this
county's TD template). Extracted all 16 PINs, cross-validated each by
property-address match against the corresponding datalet page (100% match),
and wrote them to `multi_county_auctions.parcel_id`.

**Result: E 90.8%->98.6% (204/207) PASS.**

## Fix 3 — I: partial backfill via citruspa.org datalet + Census/OSM geocoding
For the same 16 TD-row PINs, fetched each citruspa.org datalet page directly
(real HTTP 200s, Tyler/iasWorld CAMA system) and extracted:
- Full site address (street + city + zip) — used to overwrite the garbled
  `property_address` field (previous scraper had concatenated the
  RealTaxDeed calendar's "Assessed Value" figure onto the address string,
  e.g. `"1300 W RILEY DR, $4,850.00"` — real address recovered, garbage
  removed for all 16 rows).
- Real assessed value (2025 non-schedule assessed) and market/just value
  (2026 tax estimate) for all 16 rows.
- The county's own "Zoning 1" designation for all 16 rows.

Cross-referenced each zone code against citrus's official 27-code
`zoning_districts` catalog (verified independently against Citrus County's
own published LDC Chapter 2 PDF, which lists the identical 27 district
abbreviations — confirmed the catalog is complete and accurate, not
missing entries). Per the guard rail established in prior sessions
(SHARD2/lee: never insert a `parcel_zones` row for a zone code with zero
jurisdiction precedent), only inserted `parcel_zones` for codes with a
real catalog match: **MDR** (8 rows) and **RUR** (1 row) = 9 rows total.
Left 4 rows with no-precedent codes (`LD`, `MDRMH`, `R1`, and one case in a
different jurisdiction — City of Crystal River, not yet in our jurisdiction
catalog) unlinked rather than guess a normalization.

For lat/lon: geocoded the real, county-verified street addresses via the
US Census Bureau Geocoder (the pipeline's established pattern, per
`scripts/gold_standard_shard11_leon_i_geocode.py`) — 10 of 16 addresses
matched exactly. One additional address (`461 S Snapp Ave`) that the Census
geocoder missed was independently geocoded via OpenStreetMap Nominatim
(house-level exact match). Declined to write a geocode for
`2026-0174TD` because the Census match echoed back a conflicting street
type (`4TH AVE` vs. our source's `4TH ST`) — logged as a residual rather
than asserted.

**Also fixed a data-quality regression flagged in the prior SHARD2 report**:
recovered the recorded Second Amended Final Judgment Nunc Pro Tunc for case
`2023 CA 000716 A` (CFN 2024057071, per the residual note in that report).
It definitively proves the SHARD2 adversarial refuter was correct — the
address the prior session had linked (`3939 E Bennett St`) was wrong. The
real property is `2834 N REYNOLDS AVE, CRYSTAL RIVER, FL 34428`. Corrected
`property_address` + geocoded lat/lon (Census exact match) on this row.
parcel_id remains unresolved (no address-search path available in this
sandbox to citruspa.org without full ASPX session automation) — left
NULL, documented as residual, not fabricated.

**Result: I 89.4%->94.2% (195/207) — improved but still FAIL, 2 rows short
of the 197/207 (95%) threshold.**

## Guard rails held (documented no-writes)
- 4 zone codes without catalog precedent (`LD` x2 rows, `MDRMH` x1,
  `R1`/City-of-Crystal-River x1) — NOT inserted into `parcel_zones`.
- 5 of 16 addresses failed both Census and OSM Nominatim geocoding
  (rural/new roads not yet in either geocoder's reference data) — lat/lon
  left NULL, not estimated.
- FL Statewide Cadastral ArcGIS (services9.arcgis.com) — single retry,
  timed out again (same structural sandbox limitation documented in the
  2026-07-27 citrus report). Not retried further per cost discipline.
- citrus GIS ZONING_DESCR MapServer (maps.citrusbocc.com) — real, working
  endpoint (schema + where-clause queries return real data), but
  point-in-polygon query by lat/lon returned zero features for our target
  coordinates, and where-clause query by `PRCLKEY` didn't match our PINs
  (likely a different internal key scheme than the PA Altkey/PIN). Not a
  fabrication risk either way — just didn't resolve; not pursued further
  given diminishing returns vs. session budget.
- citruspa.org address-search flow (Tyler/iasWorld ASPX disclaimer +
  postback) — confirmed reachable (real 200s, real VIEWSTATE/form fields)
  but would require full session-state automation to complete; not
  attempted given cost discipline and existing progress already made via
  the datalet-by-PIN path.
- 2 rows (`2024 CA 000179 A`, `2025 CA 000393 A`) have zero data anywhere:
  no `clerk_url`, zero items on the live RealForeclose AJAX calendar for
  their `auction_date`s (consistent with cancelled/postponed, off the live
  calendar) — genuinely unresolvable without a CAPTCHA-gated court-record
  search. Left untouched.

## Verification protocol — before/after JSON (live-queried 2026-08-13)

### SQL VERIFICATION
```sql
-- BEFORE
SELECT public.pencil_dod_evaluate_county('citrus');
-- {"A":{"pass":true,"metric":56},"B":{"pass":true,"metric":100.0},
--  "C":{"pass":false,"metric":89.4,"detail":"matched_clean=185"},
--  "D":{"pass":false,"metric":90.8,"detail":"matched_any=188"},
--  "E":{"pass":false,"metric":90.8,"detail":"parcel_linked=188"},
--  "F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":95.7},
--  "H":{"pass":true,"metric":0.1},
--  "I":{"pass":false,"metric":89.4,"detail":"card_complete=185 of 207"},
--  "J":{"pass":true,"metric":100.0},"auctions_total":207}

-- AFTER
SELECT public.pencil_dod_evaluate_county('citrus');
-- {"A":{"pass":true,"metric":56},"B":{"pass":true,"metric":100.0},
--  "C":{"pass":true,"metric":98.1,"detail":"matched_clean=203"},
--  "D":{"pass":true,"metric":99.5,"detail":"matched_any=206"},
--  "E":{"pass":true,"metric":98.6,"detail":"parcel_linked=204"},
--  "F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":95.9},
--  "H":{"pass":true,"metric":0.0},
--  "I":{"pass":false,"metric":94.2,"detail":"card_complete=195 of 207"},
--  "J":{"pass":true,"metric":100.0},"auctions_total":207}

-- Isolation check: 18 rows PATCHed for parity, 16 for parcel_id/address/
-- values, 1 corrected address (2023 CA 000716 A), 9 parcel_zones inserted
SELECT count(*) FROM multi_county_auctions
  WHERE county='citrus' AND parity_source LIKE 'tier1:realtaxdeed_ajax_harvest_citrus_20260813%';
-- 16
SELECT count(*) FROM multi_county_auctions
  WHERE county='citrus' AND parity_source = 'tier1:citrusclerk_recorded_final_judgment_cfn2025068929';
-- 1
SELECT count(*) FROM multi_county_auctions
  WHERE county='citrus' AND parity_source = 'tier1:realforeclose_ajax_calendar_absence_confirms_cancel_citrus_20260813';
-- 1
SELECT count(*) FROM parcel_zones
  WHERE source LIKE 'citruspa_org_datalet_altkey_%_gold_standard_citrus_i_20260813';
-- 9
```
Timestamp: 2026-08-13 (session live-queried times throughout, see tool log).

## Status Board (before -> after)
| Letter | Before | After | Change |
|---|---|---|---|
| C | FAIL 89.4% (185/207) | **PASS 98.1%** (203/207) | +18 rows, 18-row parity backfill |
| D | FAIL 90.8% (188/207) | **PASS 99.5%** (206/207) | +18 rows, same fix |
| E | FAIL 90.8% (188/207) | **PASS 98.6%** (204/207) | +16 rows, real PIN recovery from RealTaxDeed AJAX detail |
| I | FAIL 89.4% (185/207) | FAIL 94.2% (195/207) | +10 rows; 2 short of threshold; genuine remaining blockers documented |

**Net: 6/10 -> 9/10 passing letters for citrus. C, D, E flipped to verified PASS. I improved materially but still short.**

## Next-session priorities for citrus I (12 residual rows)
1. `2026-0161TD` (zone `LD`) and `2026-0163TD` (zone `MDRMH`) have full
   address/lat/lon/value already — only need a defensible zone-code
   resolution. Worth a dedicated pass to determine whether "LD" is truly a
   display-truncated "LDR" (would need to confirm against another
   independent source, e.g. a full non-truncated CAMA export or the
   citruspa.org owner/parcel print report) and whether "MDRMH" has any
   basis in the LDC beyond the PA's internal CAMA shorthand.
2. `2025 CA 000110 A` (zone `RW`), `2025 CA 000343 A` (zone `LD`),
   `2025 CA 000999 A` (zone `CRA`) — same zone-precedent gap as above,
   pre-existing rows (not from today's batch).
3. `2023 CA 000716 A` — address corrected this session (see Fix 3); still
   needs a real parcel_id. No address-search API worked in this sandbox;
   would need either full ASPX session automation against citruspa.org's
   disclaimer+postback flow, or a working point-in-polygon match against
   `maps.citrusbocc.com`'s parcels layer (not found this session — only a
   ZONING_DESCR layer exists on that server).
4. `2026-0174TD` — real parcel (3279711) is in City of Crystal River, not
   unincorporated Citrus County — needs a Crystal River jurisdiction_id
   added to the `jurisdictions`/`zoning_districts` catalog before a
   defensible `parcel_zones` row can be inserted (zone code `R1` seen on
   the PA datalet has no home in our current single-jurisdiction citrus
   catalog).
5. `2024 CA 000179 A`, `2025 CA 000393 A` — zero data anywhere reachable
   this session (off the live calendar, no clerk_url). Needs a
   CAPTCHA-solving path against Citrus Clerk SCORSS/LandmarkWeb, per the
   2026-07-25 SHARD4 finding.
6. `2026-0154TD`, `2026-0167TD`, `2026-0169TD` — real PIN + zone + values
   recovered this session, but Census/OSM geocoding both missed these
   rural/newer addresses. Consider a different geocoder (Google/Mapbox,
   if budget allows) or a spatial query directly against
   `maps.citrusbocc.com` once its parcels layer (not just ZONING_DESCR) is
   located.
