# Gold Standard shard-11: gadsden I (municipal zoning) — dispatch 52bf028c, loop run 5361

## Result: 0/1 letter moved — genuinely blocked, one false lead self-caught before write

| Letter | Before | After | Notes |
|---|---|---|---|
| I | FAIL 56.5 (13/23) | FAIL 56.5 (13/23) | Structurally capped at max 21/23=91.3% by E's parcel-link gap (out of this item's scope); genuinely blocked for the 8 municipal parcels after 3 new angles + 5 extension angles, all dead or insufficient |

**Zero DB writes this session.** Item scope: gadsden I (municipal zoning for the 8
Quincy/Chattahoochee auction parcels). E and H were explicitly out of scope for this item
(separate items in the same dispatch). Per BLANK > WRONG, no zone_code was written without a
genuine spatial/lookup source backing it.

## What happened

Per the item brief, tried 4 named new angles plus follow-on extensions when leads surfaced:

### 1. City of Quincy's own ArcGIS org — found, then confirmed a FALSE LEAD
Web search surfaced `cityofquincy.maps.arcgis.com` (owner `quincyadmin`), a real, separate
ArcGIS Online organization distinct from the county's ARPC-hosted org — exactly the kind of
untried angle the brief named. It has a live "Zoning" webapp with a genuine, publicly-queryable
`Planning_View/FeatureServer/2` layer (`ZoneCode`/`ZoneDescription` fields, `dataLastEditDate`
Nov 2025 — recently maintained).

**Caught before writing anything**: queried the layer with `outSR=4326` to get real lat/lon
geometry, and the returned coordinates are `47.22°N, -119.85°W` — **Quincy, Washington** (Grant
County, WA), not Quincy, Florida. Independently cross-confirmed via the org's `Addressing_View`
layer, which returns `Zip=98848` (a Washington zipcode) on a sample query. The "Grant County
Commercial/Industrial/Residential High/Urban Reserve" zone descriptions in the initial distinct-
values query were the first tell, missed at first glance, then confirmed decisively via geometry.
**Nothing from this source was written to the DB.**

### 2. Chattahoochee's own Municode client, separate from `gadsden_county` (clientId 5945)
Prior sessions only ever checked the *county's* Municode client. `library.municode.com/fl/
chattahoochee` is a genuinely separate, real Municode product for the city, confirmed via Google's
own index returning real chapter titles (`Chapter II — LAND USE DISTRICTS`, nodeId
`PTIIILADERE_CHIILAUSDI_2.02.00USALWILAUSDI_2.02.02PUTYUS`) — i.e. Google's crawler executed the
JS and saw real content that no fetch method available in this sandbox could reproduce: plain curl
returns the 117-line Angular shell (same empty-SPA pattern the prior session hit for
`gadsden_county`), WebFetch returns HTTP 403 on both the root and the deep-link nodeId URL,
Firecrawl is confirmed still at **0 remaining_credits** (checked live this session via
`api.firecrawl.dev/v1/team/credit-usage`), and no browser-automation tool is available as a
deferred tool in this sandbox. Content is real but unreachable by any method tried.

### 3. Wayback Machine CDX API for the Chattahoochee Municode pages
All snapshots from 2018 through 2026 are 2–3KB — the same empty Angular shell as the live page.
Wayback never captured JS-rendered content for this domain. Confirmed dead end.

### elaws.us mirror (found via search while chasing #2) — real ordinance text recovered
The same search that found the Chattahoochee Municode client also surfaced
`chattahoochee.elaws.us/code/chii` — the elaws.us mirror domain family a prior session already
used successfully to source Quincy's and Chattahoochee's existing `zoning_districts` catalog rows
(confidence 0.60–0.90, already in the DB before this session). Fetched it live: **HTTP 200, 69KB
of real ordinance text**, verbatim-matching the district codes and figures already in the DB —
R-1 (Low Density Residential, 4 du/ac, 40% lot coverage), R-1MH (4 du/ac), R-2 (Medium Density,
6 du/ac, 60%), R-3 (High Density, 10 du/ac, 80%), B-1 Commercial (FAR 1.0 in the CBD blocks / 0.75
elsewhere, with a real central-business-district block list), I-C, I Industrial (FAR 0.75, with a
verbatim adjacency setback table for RLD/RLD-MH/RMD/RHD). This is a genuine independent
confirmation that the existing `zoning_districts`(jurisdiction_id=1003) rows are real and
correctly sourced — but it is chapter *text*, not a parcel-boundary dataset, so it does not by
itself unlock per-parcel assignment.

### Extension angles tried once the above surfaced possibilities
- **`gadsdencountypropertyappraiser.org/gis-maps/`** (a domain distinct from the confirmed-dead
  `qpublic.schneidercorp.com` and `gadsdencountyfl.gov`): HTTP 200, but inspection of the page
  content shows this is an unofficial WordPress lead-gen/data-broker site (GeneratePress theme,
  a fake "Analyzing Property Data..." loading-spinner widget, generic templated marketing copy
  identical to boilerplate used across many similar SEO sites) — **not** the real Gadsden County
  Property Appraiser. Not used as a source.
- **`gis.fdot.gov/arcgis/rest/services/Parcels/MapServer`** (statewide FDOT parcels, in case it
  carries a zoning attribute): `HTTP 499 Token Required` — no credentials available. Dead end.
- **Zoneomics per-address zoning report** (`zoneomics.com/zoning-maps/florida/quincy/{address}/
  {lat}/{lon}`): confirmed via WebFetch that the actual zone-code *value* is paywalled — the page
  only shows that a "Zone Code" field exists, not its content, without purchasing a report. Out
  of scope per the $10 session cap and not a free authoritative government source regardless.
- **`fl_parcels.dor_uc` (county-appraiser use-code) as a zone_code proxy**: all 8 municipal
  auction parcels have real, already-ingested `dor_uc='001'` (DOR "Single Family" use code), which
  crosswalks to `zone_code='SFR'` under this project's own established `DOR_UC_MAP` (used for the
  county's Phase-1 zoning baseline elsewhere). **Deliberately rejected as a write** for this item:
  DOR_UC reflects *current use*, not *zoning district boundary* — a parcel can be SFR-used while
  zoned commercial or mixed-use, so this would not be a real zoning assignment and risks the exact
  fabrication pattern this project has been burned by before (gulf B/F, franklin, sibling-shard
  lake-G incidents). Not written.

## Net: I stays FAIL at 56.5% (13/23)

No genuine, authoritative, per-parcel spatial-or-lookup zoning source exists for the 8 Quincy/
Chattahoochee municipal auction parcels that is reachable from this sandbox. All 4 named angles
plus 5 extension angles were tried and each came back dead, insufficient, or (in one case) a false
lead that was caught before any write. Even in a hypothetical full win on all 8 municipal parcels,
I is structurally capped at 21/23 = 91.3% this session because 2 of 23 auctions have no parcel_id
at all (E's gap, explicitly out of this item's scope) — so I could not have crossed the 95% PASS
threshold regardless.

## Recommendation for the next gadsden session (I item)

- Do not re-try `cityofquincy.maps.arcgis.com` — conclusively confirmed to be Quincy, WASHINGTON
  (Grant County), not Florida. This is now closed, not just "not yet tried."
- Do not re-try Wayback for `library.municode.com/fl/chattahoochee` — exhaustively empty across
  8 years of snapshots.
- The one open, genuinely promising thread: `library.municode.com/fl/chattahoochee`'s real,
  Google-indexed chapter content (confirmed real via search-engine crawl, not a guess) is reachable
  only by a JS-executing fetch this sandbox does not have access to. If a future session gets
  Firecrawl credits refilled or a real browser-automation tool available, re-target that exact
  URL (`?nodeId=PTIIILADERE_CHIILAUSDI_2.02.00USALWILAUSDI_2.02.02PUTYUS`) — though note the
  elaws.us mirror already recovered equivalent text, so the marginal value is mainly for
  cross-verification/confidence-bump, not new content.
- The real blocker for I is not ordinance text (that exists, twice-confirmed now) — it is a
  **parcel-to-district spatial boundary** for Quincy/Chattahoochee. No such source (city GIS,
  county GIS, statewide FDOT, or paid aggregator) is reachable from this sandbox. This may
  require a manual public-records request or a stealth-capable fetch method for
  `myquincy.net`/`gadsdencountyfl.gov` (both confirmed Cloudflare Turnstile/Akamai WAF-blocked,
  again, this session, via plain curl with a real browser UA).

## Live evaluation JSON — BEFORE (session start, 2026-07-21)
```json
{"A":{"pass":true,"detail":"fc=16 td=7","metric":7},"B":{"pass":true,"detail":"verified=1 closed_sold=1","metric":100.0},"C":{"pass":true,"detail":"matched_clean=22","metric":95.7},"D":{"pass":true,"detail":"matched_any=22","metric":95.7},"E":{"pass":false,"detail":"parcel_linked=21","metric":91.3},"F":{"pass":true,"detail":"tier1_sold=1 closed_sold=1","metric":100.0},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":1.7},"I":{"pass":false,"detail":"card_complete=13 of 23","metric":56.5},"J":{"pass":true,"detail":"deal_complete=23 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"gadsden","V2_LITMUS":null,"auctions_total":23}
```

## Live evaluation JSON — AFTER (post-research, same session)
```json
{"A":{"pass":true,"detail":"fc=16 td=7","metric":7},"B":{"pass":true,"detail":"verified=1 closed_sold=1","metric":100.0},"C":{"pass":true,"detail":"matched_clean=22","metric":95.7},"D":{"pass":true,"detail":"matched_any=22","metric":95.7},"E":{"pass":false,"detail":"parcel_linked=21","metric":91.3},"F":{"pass":true,"detail":"tier1_sold=1 closed_sold=1","metric":100.0},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":1.8},"I":{"pass":false,"detail":"card_complete=13 of 23","metric":56.5},"J":{"pass":true,"detail":"deal_complete=23 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"gadsden","V2_LITMUS":null,"auctions_total":23}
```

Identical except H's freshness metric, which drifted naturally with wall-clock time (no writes
made to `last_seen_at`).

## SQL VERIFICATION
```sql
SELECT public.pencil_dod_evaluate_county('gadsden');
-- returns the "AFTER" JSON above, run live 2026-07-21 via PostgREST RPC.
-- No INSERT/UPDATE/DDL statements were executed against parcel_zones, zoning_districts,
-- zone_standards, or jurisdictions this session (zero DB writes for the I item).

SELECT count(*) FROM parcel_zones WHERE jurisdiction_id IN (925, 1003, 1005);
-- {"count": 0}  -- confirmed unchanged (Quincy=925, Chattahoochee=1003, Havana=1005)

SELECT id, county_slug, letter, survived FROM gold_standard_ultraloop_audit
WHERE dispatch_id='52bf028c-78fe-49ad-ae77-284c02a1f201' AND county_slug='gadsden'
ORDER BY id DESC LIMIT 1;
-- id=8221 | gadsden | I | true
```

dispatch_id: 52bf028c-78fe-49ad-ae77-284c02a1f201
item_key: gadsden_I_municipal_zoning
