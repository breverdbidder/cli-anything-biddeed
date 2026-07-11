# Gold Standard shard-12 (run3713) — martin

Session: 2026-07-11, dispatch_id `9528efeb-cb38-4b1b-9b7f-54bf36b3a98a`, chat_session
`architect-20260711T080000`. Method: ULTRALOOP protocol — 4 parallel research agents fanned out
via the `Workflow` tool (native mode), each followed by an independent adversarial refuter agent
re-querying the same live sources from scratch. All 4 findings survived (`refuted: false`),
logged to `gold_standard_ultraloop_audit` ids 5568–5570 (`survived=true`).

## Scoreboard (pencil_dod_evaluate_county, before → after, live-verified)

| Letter | Before | After | Note |
|---|---|---|---|
| A | PASS 1 | PASS 1 | unchanged |
| B | PASS 100.0 | PASS 100.0 | unchanged |
| C | PASS 96.9 | PASS 96.9 | unchanged |
| D | PASS 96.9 | PASS 96.9 | unchanged |
| E | FAIL 93.8 (30/32) | **FAIL 90.6 (29/32)** | honest regression — see below |
| F | PASS 100.0 | PASS 100.0 | unchanged |
| G | FAIL 0.0 | **PASS 100.0** | fixed |
| H | PASS 1.4 | PASS 0.0 | unchanged (freshness) |
| I | FAIL 9.4 (3/32) | **FAIL 40.6 (13/32)** | large improvement, not yet passing |
| J | PASS 100.0 | PASS 100.0 | unchanged |

**7/10 → 8/10.** Before/after JSON pasted in full below.

Before (from dispatch brief):
```json
A PASS metric=1 [fc=31 td=1] | B PASS metric=100.0 | C PASS metric=96.9 | D PASS metric=96.9 |
E FAIL metric=93.8 [parcel_linked=30 of 32] | F PASS metric=100.0 | G FAIL metric=0.0
[density=0.0 far= pk1000=] | H PASS metric=1.4 | I FAIL metric=9.4 [card_complete=3 field_complete=30
auctions=32] | J PASS metric=100.0
```

After (live `pencil_dod_evaluate_county('martin')`, 2026-07-11 08:31Z):
```json
{"A":{"pass":true,"metric":1,"detail":"fc=31 td=1"},"B":{"pass":true,"metric":100.0,"detail":"verified=1 closed_sold=1"},
"C":{"pass":true,"metric":96.9,"detail":"matched_clean=31"},"D":{"pass":true,"metric":96.9,"detail":"matched_any=31"},
"E":{"pass":false,"metric":90.6,"detail":"parcel_linked=29"},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=1 closed_sold=1"},
"G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},"H":{"pass":true,"metric":0.0,"detail":"hours since last_seen (SLA 48h)"},
"I":{"pass":false,"metric":40.6,"detail":"card_complete=13 of 32"},"J":{"pass":true,"metric":100.0,"detail":"deal_complete=32 (triangle + two-arm CMA + ml_score + max_bid)"},
"county":"martin","auctions_total":32}
```

## G: fixed (0.0 → 100.0)

Root cause: only 3 of martin's 32 auctions had any `parcel_zones` link at all, both linked zoning
districts (`R-2B`, `PUD-R`) had `max_density_du_acre = NULL`, and both were `density_applicable=true`
by default (no override), so `pct_density_of_applicable` was `0/2 = 0.0`.

Research (live, adversarially re-verified): Martin County LDR Table 3.12.1 has **no flat
units/acre figure for R-2B** — it's governed by footnote (a), "one single-family dwelling unit per
lawfully established lot." **PUD/PUD-R has no code-table density at all** — confirmed directly from
a live 2025 Martin County staff report (Paddock at Palm City PUD, P177-002): density is negotiated
per individual PUD zoning agreement/master site plan (LDR Policy 4.1E.6/4.1E.8), with a real example
landing at 6.7 units/acre — a project-specific negotiated number, not a code default. Both are
genuinely N/A for this KPI's `max_density_du_acre` field, not an oversight.

Fix: set `density_regulated=false` on `R-2B`/`PUD-R`/new `PUD` districts (removes them from the
applicable denominator — the same mechanism the evaluator already uses for liberty's FAR gap).
Added `RS-6` (Martin LDR Table 3.12.1 Category A, real value **6.0 units/acre**, sourced from a
zoneomics.com mirror of the table, schema-cross-validated against a live martin.fl.us government
PDF that quotes the same table's column structure verbatim). `far_regulated=false` set on all four
districts — CONFIRMED (not inferred) via direct PDF read: Table 3.12.1 has zero FAR columns for
any residential district. `pk1000_applicable` is hardcoded `false` fleet-wide in the KPI view, so
parking never blocks G.

Net: only 1 parcel (the RS-6 one) remained density-applicable after the correct N/A flags, and it
now has a real value → `pct_density_of_applicable = 100.0` → **G: PASS**.

Migration: `supabase/migrations/20260711h_gold_standard_martin_e_g_i_parcel_zoning_fix.sql`

## I: substantially improved, not yet passing (9.4% → 40.6%, 3/32 → 13/32)

Same root cause as G (near-zero `parcel_zones` coverage). Found the real, live Martin County GIS
zoning source (`geoweb.martin.fl.us` ArcGIS REST — Parcel Polygons layer `MapServer/10` joined via
computed centroid to the Zoning layer `MapServer/8`, point-in-polygon), sanity-checked against all
3 pre-existing DB rows (exact match on `R-2B`, `PUD-R` ×2). Resolved zone codes for 24 of martin's
27 non-null-parcel auctions; added 10 new `parcel_zones` links for the districts we could safely
back with a correctly-configured `zoning_districts` row (`R-2B`, `PUD-R`, `PUD`, `RS-6`) — all 10
parcels already had address/lat-lng/value populated, so linking zoning alone flipped them to
`card_complete`.

**Deliberately did not link 9 more resolved-but-unsupported parcels**, because doing so without a
matching `zoning_districts` row would make the KPI view's applicability CTE default
`far_applicable`/`pk1000_applicable` to `true` (`COALESCE(..., true)` when no district row exists),
introducing new unmet requirements and making **G worse, not I better**. Residual gap breakdown (19
of 32 still not card-complete):
- 6 municipality-passthrough parcels (`STUART` ×5, `Indiantown` ×1) — Martin County's own GIS
  convention: the municipality, not the county, holds zoning authority here. Needs the City of
  Stuart / Village of Indiantown's own zoning ordinance — not researched this session.
- 3 `NO_PARCEL_MATCH` folios — not found anywhere in Martin's own parcel dataset (possibly
  malformed/retired folios; one of these, `04-38-41-012-000-01020-3`, is the same PIN independently
  confirmed fabricated in the E work below — consistent cross-validation).
- 2 out-of-county anomalies (`SITUS_CITY=JUPITER`, centroid falls outside the Martin County
  boundary layer entirely) — likely Palm Beach County parcels mis-attributed to martin upstream.
- 2 parcels newly given a *real* `parcel_id` by this session's E fix (`B-1` commercial zone,
  `STUART` passthrough) but not zoning-linked — see E section.
- 3 personal-property/timeshare liens with no parcel at all (see E section) — I is structurally
  unreachable for these three, same as E.
- Some real-property parcels among the above may still lack address/geo/value even once zoned —
  not separately audited this session.

Residual work for a future session: source City of Stuart's own zoning ordinance (5 parcels) and
Village of Indiantown's (1 parcel); investigate the 3 `NO_PARCEL_MATCH` folios; source `R-2A`,
`A-2`, `R-4`, and "Golden Gate Redevelopment Zoning District" (Ord. 1147) density values so those
GIS-resolved-but-undocumented codes can be linked without risking a G regression.

## E: honest regression (93.8% → 90.6%) — fabrication purge, not a fix

Found: 3 auction rows (`23001555CCAXMX`, `25001632CCAXMX`, `25001634CCAXMX`) carried
`parcel_id = 'MARTIN-SYNTHETIC-<case>'` — a self-labeled placeholder, not a real folio. These are
confirmed-real auction rows (distinct AIDs, judgment amounts, auction dates, `provenance=
primary_scrape`, `created_at` pre-dating the script that wrote the placeholder) for
personal-property and timeshare foreclosures that genuinely have no assessable real-property parcel
to attach — `scripts/shard12_run1113_martin_fix.py` itself tags them as such, and a 2026-07-04
migration had already flagged one of the three as fabricated. Per HARD GUARDRAILS and the
calhoun/liberty precedent (purge found fabrication rather than build on it), nulled all 3.

Also found and fixed: case `25002267CCAXMX` carried a *different* fabricated PIN
(`04-38-41-012-000-01020-3`, confirmed via the live Martin County Property Appraiser JSON API to
not exist anywhere in that PIN's real block) — corrected, along with a previously-`NULL` sibling
case at the same address (`25000442CAAXMX`), to the real parcel `19-37-41-000-000-00520-7` (owner
FRANKIE MARTIN INVESTMENTS LLC, confirmed via exact PA API address match). A third previously-blank
case (`25000195CAAXMX`, no address at all) was resolved to `31 SE OCEAN BLVD, STUART, FL` / PIN
`04-38-41-015-004-00160-7` via two independent, convergent first-party signals (our own scraper's
stored lat/long, reverse-geocoded through Martin County's own official GeocodeServer, landing
16.6m from the PA's parcel centroid for that address) — flagged **HYPOTHESIS**, not court-docket
confirmed (both `martin.realforeclose.com`'s case-detail view and `court.martinclerk.com`'s case
search are JS/CAPTCHA-gated and could not be rendered by any tool available this session).

Net effect: **30/32 (with 3 fabricated) → 29/32 (all real) = 90.6%.** This is worse as a raw number
and correct as data. E is now structurally capped below the 95% threshold for martin: 3 of its 32
auctions are non-real-property liens with no parcel to assign, and `auctions_total` is not scoped
by `sale_type` in the evaluator — flagged as a fleet-level denominator question, not something
fixable at the county level. Migration: same file as G/I above.

## Residual gaps flagged for next session

- I: City of Stuart (5 parcels) + Village of Indiantown (1 parcel) zoning ordinances; 3
  `NO_PARCEL_MATCH` folios; `R-2A`/`A-2`/`R-4`/Golden Gate CRA density values.
- E: structural ceiling at 90.6% unless `auctions_total` gets a sale-type carve-out fleet-wide.
- J/H/B/C/D/F/A: unchanged, verified stable this session, no action taken (out of scope per this
  session's E/G/I mandate).

## ULTRALOOP audit

`gold_standard_ultraloop_audit` ids 5568 (G), 5569 (I), 5570 (E) — all `survived=true`, dispatch_id
`9528efeb-cb38-4b1b-9b7f-54bf36b3a98a`, `ultraloop_mode='native'`. Per the parallel-fleet rule, did
**not** run `public.gold_standard_loop()`/`certify()` this session (other shards may be mid-flight);
per-county evaluation via `pencil_dod_evaluate_county('martin')` only, pasted above.
