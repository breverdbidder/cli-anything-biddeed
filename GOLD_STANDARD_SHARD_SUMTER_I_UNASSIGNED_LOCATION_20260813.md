# Gold Standard: sumter — letter I, 4-row property_address gap, 2026-08-13

## Context
Task: fix sumter letter I (property card complete, needs >=95%, currently 83.3%, 20/24) by
finding a real `property_address` for 4 rows that already have lat/lon/assessed_value/parcel_id
populated, all NULL only on `property_address`:

| case_number | id | parcel_id |
|---|---|---|
| 1078 | c71a236d-2484-4878-842f-9f8ca2a56ee0 | J16C020 |
| 1159 | 199aef06-d7ca-480e-93b5-add33645c27a | M06C003 |
| 776  | 862b9181-7211-4003-8e2f-eb990c00f13e | G06H033 |
| 104  | b01b0bed-7c2a-4377-a415-b54f273efb92 | C27-268 |

Read both required prior reports first:
- `GOLD_STANDARD_SHARD14_SUMTER_DISPATCH_8EE11DD1_REFIRE_ADDENDUM.md` — left sumter at 6/10
  (attribution dispute on B), I still FAIL 90.9%, tied structurally to E's unlinked parcel.
- `GOLD_STANDARD_SHARD7_SUMTER_DISPATCH_A3C9A3BE_2ND_FIRING_SESSION_REPORT.md` — documented the
  authoritative root cause for a *different* parcel (D29A024, case 2025-CA-000255): Sumter GIS's
  own parcels layer field `Physical_A` (situs address) = `"Unassigned Location RE"`, the
  appraiser's own explicit no-address code, confirmed against neighboring addressed parcels as a
  genuine (not a scrape-gap) absence.

Neither prior report covers these specific 4 parcels — they are a different residual than the E/I
pairing those sessions closed out. Live evaluator at session start confirmed sumter is 9/10, only
I failing at exactly 83.3% (20/24), matching the pre-diagnosis exactly.

## What this session did
1. Confirmed live via REST API that all 4 rows have `property_address=NULL` with lat/lon,
   assessed_value, and parcel_id already populated (matches the pre-diagnosis exactly, VERIFIED).
2. Attempted Sumter County GIS ArcGIS REST services
   (`gis.sumtercountyfl.gov/arcgis/rest/services`) — root services listing itself returns HTTP 500
   (server error), not just the specific layer used by the prior session. Retried after a delay;
   still 500. This channel is currently down county-wide, not a layer-specific gap.
3. Found `www.sumterpa.com/record-search/` 301-redirects to `qpublic.schneidercorp.com` (Schneider
   Geospatial's Beacon platform) — the Sumter County Property Appraiser's actual public parcel
   record system, using a `KeyValue=<parcel_id>` query parameter.
4. Direct `curl` to qPublic returns HTTP 403 (bot-blocked) even with a browser User-Agent.
   Firecrawl scrape returned HTTP 402 (insufficient credits — same failure mode a prior session
   hit on this same county).
5. `r.jina.ai` text-extraction proxy (the same channel a prior sumter session used successfully
   for a Cloudflare-gated PDF) succeeded at HTTP 200 for the qPublic "Report" page variant
   (`PageTypeID=4&PageID=13872&KeyValue=<parcel_id>`) for all 4 target parcels.
6. Verified each response's `Parcel Number` field matches the requested parcel exactly (ruling out
   a cached/fallback/default page), then read the `Site Location` field for each.

## Finding: all 4 parcels are genuinely unaddressed per the county's own record — VERIFIED, no write
Every one of the 4 target parcels shows `Site Location: Unassigned Location RE` on the Sumter
County Property Appraiser's own official qPublic record — the identical no-address code the prior
session (2nd firing of dispatch a3c9a3be) found and authoritatively documented for a different
parcel (D29A024). This is the appraiser's own explicit "no address assigned" marker, not a missing
scrape.

| parcel_id | case | City/Zip on record | Property Usage | Legal Description (excerpt) |
|---|---|---|---|---|
| J16C020 | 1078 | Lake Panasoffkee 33538 | VACANT | LOT 20 BROOKS PARK 1ST ADD PB 4 PG 1 |
| M06C003 | 1159 | Bushnell 33513 | VACANT | COM AT SE COR OF NE 1/4 OF NW 1/4... (metes/bounds) |
| G06H033 | 776 | Wildwood 34785 | VACANT | LOTS 33 TO 39 INCL OAK LAWN ADD PB 2 PG 60 |
| C27-268 | 104 | Wildwood 34785 | MORT/CEMETERY | COMM AT SE COR RUN S 89 DEG 51'40"W 25 FT... (metes/bounds) |

Source (all 4, live-fetched, VERIFIED):
`https://qpublic.schneidercorp.com/Application.aspx?AppID=1207&LayerID=36374&PageTypeID=4&PageID=13872&KeyValue=<parcel_id>`
via `r.jina.ai` proxy, fetched 2026-08-13.

Per repo guardrails ("NEVER fabricate or guess a value... If you cannot find a REAL value from a
live source, leave the field NULL"), **no write was made to `property_address` on any of the 4
rows.** The `City`/`Zip` fields present on the qPublic record are not a street address and writing
them into `property_address` would misrepresent a partial/administrative locality tag as a real
property address — explicitly out of scope per the same fabrication guardrail.

## Why this is a genuine structural gap, not a pipeline bug
- 3 of 4 are `Property Usage: VACANT` raw land with metes-and-bounds or platted-lot legal
  descriptions and no structure — consistent with counties never assigning a 911/situs address to
  undeveloped parcels until a building permit is pulled.
- The 4th (C27-268) is `MORT/CEMETERY` — a cemetery parcel, which structurally never receives a
  standard situs address.
- This matches the exact same authoritative pattern (`Unassigned Location RE`) already confirmed
  by a prior session for a different Sumter parcel via the raw ArcGIS layer field, now confirmed
  independently via the county's public-facing appraiser record for these 4 parcels. Two
  independent Sumter data channels (raw GIS attribute table, public qPublic UI) agree.

## Live before/after (`pencil_dod_evaluate_county('sumter')`)

### Before (session start)
```json
{"I": {"pass": false, "detail": "card_complete=20 of 24", "metric": 83.3}, ...}
```
Full JSON: 9/10 PASS (A,B,C,D,E,F,G,H,J), only I failing.

### After (re-run post-investigation, no writes made)
```json
{"I": {"pass": false, "detail": "card_complete=20 of 24", "metric": 83.3}, ...}
```
Identical — unchanged, confirmed live. No regression, no improvement; a genuine negative result.

## Residual for next sumter session
All 4 remaining letter-I gap rows are now confirmed (not merely suspected) structurally
unaddressable per the Sumter County Property Appraiser's own record. Recommend accepting this as
permanent residual risk for this dataset (4 of 24 auctions are vacant-land/cemetery parcels with
no county-assigned situs address) rather than re-attempting the same address hunt in a future
session, unless a new data source type becomes available (e.g. E-911 addressing database, or a
manual county GIS-addressing-department phone lookup per the disclaimer on the qPublic page itself
which directs address-verification questions to "352-689-4400, GIS Addressing"). Ceiling for I
under current data availability is 83.3% (20/24) — cannot reach the 95% PASS threshold without
either (a) a new source providing addresses that genuinely don't exist in county records, or (b) a
metric-definition change to exempt genuinely unaddressed vacant/cemetery parcels from the
denominator, which is out of this session's scope (no schema/evaluator changes authorized).

Sumter remains 9/10 (A,B,C,D,E,F,G,H,J), I blocked at 83.3% on a confirmed structural data gap.

dispatch scope: letter I only, county sumter, 2026-08-13 session.
