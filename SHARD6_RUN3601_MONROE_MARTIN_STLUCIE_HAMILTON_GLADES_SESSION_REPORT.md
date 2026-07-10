# GOLD STANDARD SHARD-6 — run 3601 — monroe/martin/st_lucie/hamilton/glades

dispatch_id: 63b0acb8-5a08-4589-89fe-d5efb54576b5
session: architect-20260710T080000

## Summary

Live evaluator state was pulled fresh for all 5 assigned counties (the brief's loop_run_id
3534 snapshot was already stale — live is loop_run_id 3601). Today's 00:00Z wave had already
worked 4 of these 5 counties hours earlier (martin/lake via shard14, hamilton via shard13,
glades via shard8) — cross-checked their commits/migrations first to avoid duplicating
same-day dead ends. No letter's PASS/FAIL status changed for martin, hamilton, or glades this
session (each has a real, externally-confirmed blocker, documented below). Real, concrete
value shipped: (1) root-caused martin's new G regression to 2 specific zoning districts with
NULL density values, and explicitly declined to backfill a number because the only reachable
source was a secondary aggregator, not primary Municode text; (2) root-caused st_lucie's I
gap to 7 specific rows, backfilled real address/geo/value data for them from an authoritative
government GIS source, and *verified the metric honestly did not move* because those parcels
are outside the county's current zoning-substrate coverage; (3) refreshed 12+ day stale
`gold_standard_ultraloop_audit` evidence for monroe (already 10/10) that would have silently
blocked certification.

## monroe — 10/10, no action needed

CONFIRMED via live `pencil_dod_evaluate_county('monroe')`, unchanged from the brief:

```json
{"A":{"pass":true,"metric":1},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":96.2},"D":{"pass":true,"metric":96.2},"E":{"pass":true,"metric":96.2},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":20.5},"I":{"pass":true,"metric":96.2},"J":{"pass":true,"metric":96.2}}
```

Its `gold_standard_ultraloop_audit` evidence had gone stale (oldest row 2026-06-28, 12+ days —
past the 7-day SQL CERTIFY GATE window), which would have silently blocked certification even
though the county is fully passing. Refreshed all 10 letters with fresh `survived=true` rows
this session (same fix class as shard13's marion refresh a few hours earlier).

## martin — 7/10 (brief said 8/10; G regressed since)

Before (brief, loop_run_id 3534) vs after (live, this session):

```json
// BEFORE (brief): A,B,C,D,F,G,H,J pass; E,I fail — 8/10
// AFTER (live, unchanged by this session):
{"A":{"pass":true,"metric":1},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":96.9},"D":{"pass":true,"metric":96.9},"E":{"pass":false,"metric":93.8},"F":{"pass":true,"metric":100.0},"G":{"pass":false,"metric":90.3},"H":{"pass":true,"metric":1.7},"I":{"pass":false,"metric":93.8},"J":{"pass":true,"metric":100.0}}
```

**E/I**: already re-attempted exhaustively by shard14 this same session-day (00:00Z wave) —
1 structurally-unlinkable "MULTIPLE PARCEL" case, 1 needing Martin GIS discovery
(gis.martin.fl.us DNS-fails, FL statewide cadastral FeatureServer timed out). Not
re-attempted here to avoid re-running a same-day dead end.

**G (new finding, root-caused this session)**: density dropped 100.0% → 90.3% because 3 of
31 zoning-applicable parcels have `NULL max_density_du_acre`:

| parcel_id | district | district_id |
|---|---|---|
| 52-38-41-005-000-01581-5 | R-2B (Residential Estate Density) | 11323 |
| 13-38-40-006-000-47030-8 | PUD-R (Planned Unit Development – Residential) | 11324 |
| 11-39-41-001-000-03220-0 | PUD-R | 11324 |

Attempted to find the real Martin County LDR Table 3.12.1 value to backfill: `library.municode.com`
returned HTTP 403, the `martincounty-fl.elaws.us` mirror returned HTTP 503. The only reachable
source was a secondary aggregator (zoneomics.com, read via a summarizing fetch), which itself
suggests R-2B's actual standard is "1 dwelling unit per lawfully-established lot" (not a
du/acre figure at all) and that PUD-R has no fixed table density — density is set per
individual PUD Zoning Agreement per the Comprehensive Plan. **Declined to write any
`zone_standards` value or `v_zoning_district_applicability` flag on this evidence quality** —
doing so would repeat the exact ghost-success pattern this campaign has caught and reverted
multiple times for zoning data (e.g. `20260703_shard5_franklin_synthetic_parcel_zones_cleanup.sql`).
Logged as a diagnostic finding in `gold_standard_ultraloop_audit` for a future session with
real primary-source access.

## st_lucie — 9/10 (brief said 7/10; C/D already fixed today, only I remains)

Before (brief, loop_run_id 3534, C/D failing) vs after (live, this session):

```json
// AFTER (unchanged by this session — C/D were already fixed by an earlier pass today):
{"A":{"pass":true,"metric":13},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":97.6},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":1.6},"I":{"pass":false,"metric":87.8},"J":{"pass":true,"metric":100.0}}
```

**I (root-caused this session)**: 10 of 82 rows fail `card_complete`. Queried each directly:

- 1 row (`2024CA000214`) has no address or parcel_id at all.
- 1 row (`26-001`) has a placeholder `"TBD"` address.
- 7 rows had real addresses + parcel_ids but were missing lat/lon and (6 of 7) assessed/market
  value: `2023CA002858`, `2023CA002350`, `2025CA001294`, `2025CA002292`, `2025CA001088`,
  `2023CA000239`, `2025CA002297`.

Found and queried a real authoritative source — the St Lucie County Property Appraiser's own
ArcGIS FeatureServer (`map.paslc.gov/arcgis/rest/services/PROD/SLCPA_PublicParcels`), which
exposes `PropertyID` (matches our short numeric `parcel_id`), the 15-digit `ParcelID`/folio,
`SiteAddress`, `JustMarketValue`, and parcel geometry. All 7 `PropertyID`s matched exactly on
`SiteAddress` against our existing records — confirms correct parcel identity, no false-positive
risk. Backfilled real `latitude`/`longitude` (polygon centroid) and `market_value` for all 7 via
live PostgREST PATCH.

**Checked before claiming any gain**: none of the 7 parcel_ids exist in `parcel_zones` (required
for `card_complete`'s zoned-parcel criterion). Verified via a live 0-result bounding-box query
against both St Lucie County's own unincorporated Zoning ArcGIS layer
(`slcgis.stlucieco.gov/hosting/rest/services/LandUse/Zoning`) and the City of Port St Lucie's
separate Zoning FeatureServer (`services1.arcgis.com/YdUP5V6WwzeG8T8r/.../Zoning` — the correct
jurisdiction for 5 of the 7 addresses) — both return zero zoning polygons at these parcel
locations. One row (`2023CA000239`, parcel `5481`, an unincorporated-county address) DID
resolve a real zone (`PUD`) from the county's layer, but no "Unincorporated St Lucie County"
jurisdiction row exists in our `jurisdictions` table to attach it to — creating one is a bigger
structural change than this session's scope, left undone rather than rushed.

Re-ran `pencil_dod_evaluate_county('st_lucie')` after the writes: **I unchanged at 87.8%
(72 of 82)** — confirms the prediction, no false claim of improvement. The 7 rows' new data is
real and now on file; matching the bay/duval precedent, they will auto-resolve to
`card_complete` once st_lucie's zoning substrate loads for Port St Lucie/Fort Pierce — no
further backfill needed then.

## hamilton — 4/10, unchanged (matches shard13's same-day exhaustive diagnosis)

```json
{"A":{"pass":true,"metric":6},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":43.8},"D":{"pass":false,"metric":43.8},"E":{"pass":false,"metric":68.8},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.7},"I":{"pass":false,"metric":6.3},"J":{"pass":true,"metric":100.0}}
```

B/F are structurally undefined (zero closed auctions on file, not a scraper gap). C/D are at a
genuine ceiling for still-active/unredeemed tax-deed certs. E/I are blocked by
`qpublic.schneidercorp.com` and `hamiltonpa.com` both returning HTTP 403 to plain scraping — all
re-confirmed by shard13 hours before this session. Not re-investigated here to avoid
duplicating a same-day dead end; see shard13's report for the full breakdown.

## glades — 1/10, A-lane blocker confirmed still live

```json
{"A":{"pass":false,"metric":0},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":null},"D":{"pass":false,"metric":null},"E":{"pass":false,"metric":null},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":false,"metric":null},"I":{"pass":false,"metric":null},"J":{"pass":false,"metric":null}}
```

`fl_counties` confirms glades has zero parcels ingested; `multi_county_auctions` has zero
glades rows. Re-checked live via `gh run list`/`gh run view` on `discover-auction-dates.yml`:
still failing as of `2026-07-10T07:29:41Z` (30 minutes before this session), and the log
confirms the same root cause shard8 found this morning — `firecrawl 402` (Payment Required).
`FIRECRAWL_API_KEY` is absent from this session's environment too. **Not a code fix** — this is
a billing/account action for Ariel. Escalating again: this same workflow gates glades' A-lane
plus every other county queued behind it.

## Ultraloop audit refresh (concrete deliverable this session)

24 rows inserted into `gold_standard_ultraloop_audit` under this session's `dispatch_id`
(verified via REST count header): 10 monroe (full refresh, all now within the 7-day certify
window), 13 st_lucie (9 letter re-verifications + 1 honest I-diagnostic finding, some
duplicated across two insert batches — verified count is exact), 1 martin (G root-cause
diagnostic, fix explicitly declined).

### SQL VERIFICATION

```
-- Live re-evaluation, 2026-07-10T09:2x-09:5xZ (this session):
pencil_dod_evaluate_county('monroe')   -- 10/10, unchanged
pencil_dod_evaluate_county('martin')   -- 7/10, E/G/I fail (G newly regressed, root-caused)
pencil_dod_evaluate_county('st_lucie') -- 9/10, I fails (root-caused, real enrichment applied, metric honestly unchanged)
pencil_dod_evaluate_county('hamilton') -- 4/10, unchanged (matches shard13 same-day)
pencil_dod_evaluate_county('glades')   -- 1/10, unchanged (Firecrawl 402 confirmed still live)

-- Audit ledger write, confirmed via REST count header:
GET .../gold_standard_ultraloop_audit?dispatch_id=eq.63b0acb8-5a08-4589-89fe-d5efb54576b5
-- content-range: 0-23/24  =>  24 rows

-- multi_county_auctions writes, confirmed via PATCH return=representation (7 rows,
-- case_numbers 2023CA002858/2023CA002350/2025CA001294/2025CA002292/2025CA001088/
-- 2023CA000239/2025CA002297): latitude/longitude/market_value now populated, sourced from
-- map.paslc.gov PROD/SLCPA_PublicParcels, SiteAddress exact-matched per row.
```

No `gold_standard_loop()`/`gold_standard_certify()` call was made — `git log --since
"2026-07-10 00:00"` showed multiple sibling shards (shard14, shard13, shard8, plus
wakulla/taylor/franklin/bradford commits) actively landing work on main throughout this
session's window, so per PARALLEL-FLEET RULES this session reports per-county evaluations
only.

## Residuals carried forward (next session should start here)

1. **martin G**: get primary-source Martin County LDR Table 3.12.1 text (Municode 403'd,
   elaws.us mirror 503'd this session — try again, or a different fetch path) to confirm the
   real `max_density_du_acre` for R-2B, or confirm R-2B/PUD-R should be marked
   `density_applicable=false` instead of assigned a number. Do not guess.
2. **martin E**: 1 "MULTIPLE PARCEL" structural case + 1 needing Martin GIS discovery — already
   dead-ended twice today (shard14 + implicitly here); needs a genuinely different approach
   (e.g. Martin County Property Appraiser's own site rather than the county's general GIS).
3. **st_lucie I**: needs real zoning-substrate loading for Port St Lucie
   (`services1.arcgis.com/YdUP5V6WwzeG8T8r/.../Zoning`) and Fort Pierce — a real parcel-zones
   spatial-join ingestion build, same class of work already flagged for bay/duval. Also needs a
   new "Unincorporated St Lucie County" `jurisdictions` row for the 1 unincorporated parcel.
4. **hamilton**: needs authenticated/browser-based Hamilton Property Appraiser fetch (both
   `qpublic.schneidercorp.com` and `hamiltonpa.com` 403 plain scraping) — no browser-automation
   tool was available in this session either.
5. **glades**: escalate Firecrawl billing to Ariel directly — unblocks glades A plus every
   other county behind `discover-auction-dates.yml`.
