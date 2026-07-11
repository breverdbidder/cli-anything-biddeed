# GOLD STANDARD SHARD-1 — 3rd firing session report
dispatch_id: a1f33d10-ebc0-4542-9b60-3ce11d2d9630 · chat_session: architect-20260711T160000

This dispatch fired a **third time** with an identical brief. The first firing
closed out at commit `d48ebc49`/`5173ee52`; the second firing (`317cf8a7`)
shipped zero DB writes after every remaining lead failed adversarial
verification. This session did NOT repeat that research — it (1) ran an
independent provenance sweep of existing zoning data that the prior two
firings never did, which surfaced and purged **two live ghost-successes**, and
(2) fanned out fresh research on new angles (not the previously-exhausted
paths) via a 35-agent ULTRALOOP workflow (4 research + 31 adversarial
verifiers), which found and shipped real Columbia zoning data.

## Status Board (BEFORE → AFTER, live `pencil_dod_evaluate_county`)

| County | Before (session start, live) | After (session end, live) | Notes |
|---|---|---|---|
| duval | 10/10 | 10/10 | Re-confirmed, no drift, no writes needed |
| gadsden | **8/10 (false)** | **7/10 (honest)** | G was a ghost-success PASS resting on 7 fabricated parcel_zones rows; purged, G now honestly FAIL |
| okeechobee | 8/10 | 8/10 | No pass/fail flip, but G (62.7→17.4) and I (90.7→40.7) corrected to honest numbers after purging 28 fabricated AG zone links |
| columbia | 5/10 | **7/10** | G: FAIL(null)→PASS(100.0%). I: 0.0%→53.3% (still FAIL). Real GIS zoning shipped for the first time this county has ever had. |

## Part 1 — Ghost-success discovery and purge (before any new research)

An independent sweep of `parcel_zones.source` across all four counties (not
part of either prior firing's checklist) found:

**Gadsden (CRITICAL — PASS→FAIL correction):** all 7 `parcel_zones` rows for
jurisdiction 925 ("Quincy") were tagged `source='shard8_gadsden_bootstrap_synthetic'`,
zone_code='R-1', all matching real gadsden auction parcel_ids but never
independently confirmed against real GIS/property-appraiser zoning data. This
was the **entire** basis for gadsden's G reading PASS at 100.0% — a live
ghost-success that both prior firings' own audit trail had flagged as
"unsourced" (shard10 run3534, this dispatch's 1st firing) but never purged,
and neither firing's adversarial verification pass caught because they only
re-checked their *own* new claims, not pre-existing data. Purged. Gadsden's
honest score is 7/10, not 8/10.

**Okeechobee (magnitude correction, no flip):** 28 of 53 `parcel_zones` rows
(jurisdiction 943) were tagged `source IN ('shard5-run651-synthetic',
'shard4-run2346-synthetic')`, zone_code='AG', all matching real okeechobee
auction parcels. G and I were already FAIL before this purge, so no pass/fail
flip — but the 2nd firing's report claimed I moved "40.7%→90.7%" from a real
STRAP address backfill; after purging the pre-existing fabrication, I reads
40.7% — **identical to the original dispatch-brief figure**, confirming the
address backfill was real but the zoning portion of that "improvement" was
inherited fabrication, not new work.

Both purges: `supabase/migrations/20260711r_shard1_okeechobee_gadsden_ghost_zoning_purge_a1f33d10_3rd.sql`.
A third, unrelated dead ghost row (Columbia jurisdiction 974, zoning_districts
id 10717, explicitly named "Shard7 Synthetic", zero live references) was also
purged for hygiene: `supabase/migrations/20260711q_shard1_columbia_ghost_zoning_district_purge_a1f33d10_3rd.sql`.

## Part 2 — Real Columbia zoning (new data, this session)

Discovered Columbia County's live ArcGIS Enterprise Portal at
`gis.columbiacountyfla.com/portal` (Zoning_Atlas + Parcels FeatureServers) via
a fresh web search — the previously-tried `gis.columbiacountyfla.com/arcgis`
path (both prior firings assumed this was "real, independently re-fetched
infrastructure") is in fact a bare default-IIS landing page with no working
ArcGIS REST service; the two firings' confidence in that host was misplaced,
this session found the actual live path.

Shipped: `supabase/migrations/20260711s_shard1_columbia_unincorporated_zoning_gis_wiring_a1f33d10_3rd.sql`
- New jurisdiction "Unincorporated Columbia County" (none existed — the only
  prior jurisdiction row, "Lake City", is the wrong municipal code for these
  rural parcels)
- 4 real zoning_districts (A-1, A-3, RSF-2, RSF/MH-2) with adversarially
  re-verified min-lot-size + setbacks from the live GIS layer
- max_density_du_acre derived from the verified min-lot-size via the standard
  1-unit-per-minimum-lot convention (same methodology already used elsewhere
  in this campaign for jefferson G, hendry G — not a new pattern)
- 9 of 15 target parcels' real zone_code (of 14 candidates run through
  adversarial verification: 9 survived, 5 refuted and deliberately not
  written, 1 confirmed to sit in the separate Town of Ft. White jurisdiction
  with no source yet)

## What did NOT survive / remains genuinely blocked

- **Gadsden E** (2 parcels, cases 25000942CA/25000901CA): still UNKNOWN. FL
  GIO's Gadsden CO_NO=30 was independently re-verified as *correct* this
  session (official FL DOR county-number PDF, digit-for-digit) — so the prior
  400 error was not a wrong-number issue; root cause remains unidentified.
  qpublic.net remains 403-blocked (Cloudflare/bot detection, reconfirmed).
- **Gadsden I** (21 parcels): still architecturally blocked. No ArcGIS/GIS
  parcel-boundary layer reachable for any Gadsden jurisdiction (fresh search,
  still nothing). Jurisdiction inference by address-city-match was completed
  for all 21 (Chattahoochee/Havana/Quincy/Unincorporated, confidence
  `address-city-match` only) but per guard rail this is a prerequisite, not
  sufficient to write a parcel_zones.zone_code without an independently
  sourced document.
- **Okeechobee G** (RSF/RMH density, Commercial FAR): still UNKNOWN. No
  ordinance table found for zoning-district-level (as opposed to FLU-based)
  dimensional standards despite a fresh, differently-scoped search this
  session (municode SPA / 403 to WebFetch each time). One promising finding —
  Okeechobee's PD district has no ordinance-wide FAR number (site-specific per
  development order, § 7.02.03(E) footnote 6 + § 7.02.02(C)) — **failed
  independent adversarial re-verification** (the refuter could not itself get
  past the same municode block to confirm) and was correctly not written.
- **Columbia A/B/F**: confirmed (via `pipeline.counties` notes from an earlier
  session's real headless-Chromium harvest, re-checked live this session) to
  be a **timing** blocker, not a tooling blocker — all 15 Columbia auction
  rows have future `auction_date`s (2026-07 through 2026-09), zero have closed,
  and the tax-deed lane genuinely has zero current listings. No amount of
  clerk-portal access changes this until real auctions occur. Not re-attempted.

## Verification Evidence (live, this session)

```
SESSION START (re-confirmed live, matched 2nd firing's close exactly):
duval:      10/10
gadsden:    8/10  (false — G ghost-success)  E FAIL 91.3%  I FAIL 30.4%  G PASS 100.0% (fabricated)
okeechobee: 8/10  G FAIL density=62.7 (partly fabricated)  I FAIL 90.7% (partly fabricated)
columbia:   5/10  A/B/F FAIL, G ghost-purged-already FAIL, I FAIL 0.0%

SESSION END (live, this session):
duval:      10/10  A85 B100.0 C99.4 D99.5 E100.0 F100.0 G100.0 H4.8 I96.3 J99.0
gadsden:    7/10   A7 B100.0 C95.7 D95.7 E91.3(FAIL) F100.0 G null(FAIL,honest) H2.9 I0.0(FAIL,honest) J100.0
okeechobee: 8/10   A10 B100.0 C100.0 D100.0 E96.3 F100.0 G0.0(density17.4,honest,FAIL) H2.9 I40.7(honest,FAIL) J100.0
columbia:   7/10   A0(FAIL) B null(FAIL) C100.0 D100.0 E100.0 F null(FAIL) G100.0(PASS,real) H2.9 I53.3(FAIL) J100.0
```

## Migrations shipped (all applied live via Supabase Management API, then committed)

1. `20260711q_shard1_columbia_ghost_zoning_district_purge_a1f33d10_3rd.sql` — dead fabricated zoning_districts row purge (commit `6302bb10`)
2. `20260711r_shard1_okeechobee_gadsden_ghost_zoning_purge_a1f33d10_3rd.sql` — live ghost-success parcel_zones purge, gadsden+okeechobee (commit `27c72dc3`)
3. `20260711s_shard1_columbia_unincorporated_zoning_gis_wiring_a1f33d10_3rd.sql` — real Columbia zoning (commit `94e008ab`)

`gold_standard_ultraloop_audit`: 4 refuted rows (gadsden G/I ghost, okeechobee G/I ghost, logged as `survived=false`) + 2 survived rows (columbia G, columbia I) + this report, dispatch_id `a1f33d10-ebc0-4542-9b60-3ce11d2d9630`.

## Honesty Protocol compliance

Every write this session traces to a live, independently re-fetched source
(gis.columbiacountyfla.com ArcGIS FeatureServer responses, re-queried by a
separate adversarial agent than the one that found it) or is a deletion of
data that was explicitly self-labeled or provenance-confirmed as synthetic.
Nothing was guessed. Two live ghost-successes were found and purged rather
than left standing, including one that was silently inflating a PASS on the
public scoreboard (gadsden G). `gold_standard_loop()`/`gold_standard_certify()`
were intentionally **not** run — multiple concurrent shard sessions pushed to
main during this session (confirmed via repeated `git pull --rebase`), so per
PARALLEL-FLEET RULES this session reports per-county evaluations only.

## Next-Session Priorities

1. **Gadsden E** (25000942CA, 25000901CA): root-cause why FL GIO's ArcGIS REST
   rejects CO_NO=30 with HTTP 400 despite the number being confirmed correct —
   may be an endpoint/parameter issue, not a county-number issue.
2. **Gadsden I**: needs a real per-parcel GIS/property-appraiser zoning source
   independent of qpublic.net (still 403-blocked) — jurisdiction assignment
   for all 21 parcels is now done (address-city-match confidence) and ready to
   pair with a real zone_code source the moment one is found.
3. **Okeechobee G**: needs the zoning-DISTRICT-level (not FLU-level) dimensional
   standards table for RSF/RMH/C — Okeechobee's LDC Chapter 90 exists at
   library.municode.com/fl/okeechobee_county but is SPA-blocked to both curl
   and WebFetch; needs either a PDF mirror or a tool that can execute its
   client-side JS.
4. **Columbia I remainder** (5 refuted parcels: 02123-027, 04236-236,
   00312-008, 00130-000, 04232-001): re-attempt with a stricter, slower query
   pattern against the now-known-good gis.columbiacountyfla.com ArcGIS
   endpoint — the service is real, only the specific spatial-intersect results
   for these 5 could not be independently reproduced this session.
5. **Columbia A/B/F**: not a research task — just wait for the 15 already-listed
   auctions' `auction_date`s to pass (earliest 2026-07-15), then re-scrape.
