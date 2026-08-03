# Gold Standard shard-1 (brevard/osceola) — dispatch `1f5f4ede-c466-4c43-a9ec-e6ce1d02c1e5`, loop run 8552

chat_session: `architect-20260803T160000`
mode: ULTRALOOP native (ultracode opt-in — Workflow fan-out: 3 independent adversarial refuters, one per claim)

## Result: brevard 9/10 unchanged (I improved, still FAIL), osceola 8/10 unchanged (G, I correctly re-confirmed as structural blockers, no new lever)

```
brevard:   A,B,C,D,E,F,G,H,J pass / I fail (card_complete=6087 of 7238, 84.1%)
osceola:   A,B,C,D,E,F,H,J pass / G,I fail (density=90.7 far=99.1... pk1000=78.6 / card_complete=127 of 137, 92.7%)
```

The incoming brief's brevard snapshot (`card_complete=5985 of 7099`) did not match live state at session
start (`card_complete=6075 of 7238` — different numerator *and* denominator). Proceeded from the live
evaluator, not the stale brief, per Honesty Protocol. Osceola's brief numbers matched live exactly.

## Brevard — letter I (property card completeness): +12, real GIS-sourced

### Diagnosis (live, session start)
`card_complete=6075 of 7238` (83.9%). Decomposed the 1163-row gap by direct SQL against
`multi_county_auctions`:
- 1106 rows missing `property_address` (known ~98% genuine no-situs vacant/tax-deed land per the
  2026-08-02 session's live GIS check — not re-verified row-by-row again this session, no new
  information since then).
- 13 missing geo, 3 missing value.
- **41 rows had address+geo+value already, missing only a `parcel_zones` link.**

### Fix applied live (2026-08-03)
Ran a live point-in-polygon query for all 41 rows' existing lat/lon against Brevard's own
authoritative unincorporated zoning GIS (`gis.brevardfl.gov/gissrv/rest/services/Planning_Development/
Zoning_WKID2881/MapServer/0`, field `ZONING`). **12 of 41** fell inside this layer's coverage and
returned a real, unambiguous zone code:

| parcel_id | zone | parcel_id | zone |
|---|---|---|---|
| 3004753 | TRC-1 | 24 3606-78-F-13 | RU-1-7 |
| 3004993 | TRC-1 | 24 3630-54-A-6 | RU-2-10 |
| 2612405 | TR-1-A | 24 3525-75-A-2 | RU-1-9 |
| 2612407 | RU-1-11 | 23 3618-BH-106.6-14 | RU-2-15 |
| 24 3536-27-4-18 | RU-1-9 | 21 3507-75-7-10 | RU-1-13 |
| 23 3536-25-3-1 | RRMH-1 | 24 3536-56-F-24 | RU-1-11 |

Inserted into `parcel_zones` (`jurisdiction_id=13`, Unincorporated Brevard County, `source=
'gis_brevardfl_gov_spatial_point_query'`). Migration: `migrations/20260803_gold_standard_shard1_
1f5f4ede_brevard_i_zoning_backfill.sql`.

**The remaining 29 of 41** fell outside this layer's coverage (Palm Bay, Cocoa proper, Rockledge
street patterns) — inside one of Brevard's ~13 incorporated municipalities, which run separate zoning
GIS systems not yet integrated into this pipeline. Same structural ceiling documented by the
2026-08-02 session (`GOLD_STANDARD_SHARD1_BREVARD_JEFFERSON_HOLMES_DISPATCH_A42BF937_SESSION_
REPORT.md`) — not re-litigated, no municipal GIS integrated this session.

### ULTRALOOP adversarial verify — SURVIVED, CONFIRMED
Independent refuter re-selected all 12 live `parcel_zones` rows (contiguous IDs, `created_at` this
session, no duplicates), re-ran 6 of the 12 point-in-polygon queries from freshly-fetched
`multi_county_auctions` lat/lon (not the claim's hardcoded coordinates) and got identical `ZONING`
values, re-ran `pencil_dod_evaluate_county('brevard')` live confirming `6087/7238=84.1%` with zero
regressions on the other 9 letters, and traced the evaluator's own SQL/view definitions to mechanically
confirm the +12 delta rather than accept it as coincidence. **Verdict: SURVIVES, CONFIRMED.**

### Honest before/after
```sql
-- Session start (live): card_complete=6075 of 7238  (83.9%)
-- After 12 real writes:  card_complete=6087 of 7238  (84.1%)
```
I remains a confirmed, evidence-backed data-availability ceiling. Further gains need per-municipality
zoning GIS integration across Brevard's ~13 jurisdictions beyond the county's own unincorporated-only
layer — a substrate-build task for a future session, not another address/zoning-link sweep against
this same endpoint.

## Osceola — letter I (10 residual rows): correctly declined, no new lever

### Diagnosis
`card_complete=127 of 137` (92.7%), matching the brief exactly. The 10 failing rows:
- **9 tax_deed rows** carry a placeholder `property_address` (`'Osceola County, FL 34741'`) and a
  12-digit `parcel_id` (e.g. `192733273000`, `223033000000`, `282529138700`, `152529324000`) with no
  geo/value/zone at all. Checked live against `fl_parcels` (`co_no=59`): each 12-digit value is only a
  **prefix** shared by 16–195 distinct full parcels in `fl_parcels` — no column in
  `multi_county_auctions` (owner, plaintiff, legal description, cert number) disambiguates which one
  a given case corresponds to. Same ambiguous-truncated-parcel pattern this campaign has repeatedly
  declined (`GOLD_STANDARD_SHARD5_OSCEOLA_DISPATCH_AC5F5206_3RD_FIRING_ADDENDUM.md`).
- **1 foreclosure row** (`2025 CA 001721 MF`, synthetic `OSC-2CEAE2B1037A` parcel_id, plaintiff Bank of
  New York Mellon) — a previously-documented placeholder (`gold_standard_ultraloop_audit` id 5997):
  `osceola.realforeclose.com` is offline, the Benchmark docket requires interactive form search (not
  scriptable), and the sale date has already passed so it no longer appears in the clerk's
  forward-looking scheduled-sales PDF.

**Decision: no writes.** Guessing a zone/address/parcel match here would be fabrication.

### ULTRALOOP adversarial verify — SURVIVED, CONFIRMED
Independent refuter re-ran the `fl_parcels` prefix-ambiguity counts (confirmed real, in one case worse
than initially stated — 87–195 matches, not just "10+"), tried a genuinely new disambiguation angle
(owner/plaintiff/legal-description columns, direct clerk-site fetch — both 403/unhelpful), and
separately confirmed the 10th row's true nature (a documented placeholder, not a fresh miss) via public
search and the clerk's own PDF. No new lever found by either the original diagnosis or the refuter.
**Verdict: SURVIVES, CONFIRMED.**

## Osceola — letter G (pk1000): correctly declined, no new lever

### Diagnosis
`density=90.7 far=99.1(N/A-excluded) pk1000=78.6`, metric bound by `pk1000`. Live SQL against
`parcel_zones`/`zoning_districts`/`zone_standards`/`v_zoning_district_applicability` shows exactly
**one** zone code blocking `pk1000` for osceola: **Kissimmee SRPUD, 3 parcels**, `parking_per_1000sf
IS NULL`, `pk1000_applicable=true`. Re-checked Firecrawl credit balance live:
`remaining_credits=-4` (still exhausted, unchanged since the 2026-08-02 holmes session). Re-attempted
direct ordinance fetch (Municode, American Legal Publishing, kissimmee.gov, Wayback Machine) — all
either a JS-only SPA shell with no server-rendered text, or a Cloudflare/Akamai 403. No CONFIRMED-tier
source found. **Guessed standards are banned — declined, not written.**

### ULTRALOOP adversarial verify — SURVIVED, CONFIRMED
Independent refuter re-ran the SQL (confirmed SRPUD/Kissimmee is the sole blocker), re-checked
Firecrawl credits live (`-4`, matches), and made 6 independent fetch attempts of its own choosing
across Municode (2 deep node URLs + a `/Search/GetContentSearchResult` API probe), Wayback Machine,
American Legal Publishing, and kissimmee.gov — all either empty JS shells or 403. A secondary
aggregator (zoneomics.com) loaded but had no extractable parking figure and was correctly excluded as
non-primary/unverifiable. **Verdict: SURVIVES, CONFIRMED.**

## ULTRALOOP audit trail

3 rows inserted into `gold_standard_ultraloop_audit` for dispatch `1f5f4ede-c466-4c43-a9ec-e6ce1d02c1e5`:
brevard/I (applied, survived), osceola/I (declined, survived), osceola/G (declined, survived). All
`ultraloop_mode='native'`.

## Verification protocol followed

- `pencil_dod_evaluate_county` re-run live for both counties, multiple times, before/during/after the
  write — every number in this report is a fresh live read.
- Per PARALLEL-FLEET RULES, did not run `gold_standard_loop()`/`gold_standard_certify()` (other shards
  may be mid-flight this loop run) — used the per-county evaluator only.
- Three independent ULTRALOOP refuter agents (isolated context, fanned out via the Workflow tool) ran
  against this session's own claims — one for the applied write, two for the declines. All three
  survived on first pass with `confidence: CONFIRMED`.
- No fabricated address, zone code, or parking standard was written anywhere this session. The 29
  brevard rows outside unincorporated-GIS coverage and the 10 osceola I rows were identified as
  genuinely unresolvable with current sources and left alone rather than guessed.

### SQL VERIFICATION

```sql
-- Brevard, live, 2026-08-03 ~16:20 UTC (post-fix):
SELECT public.pencil_dod_evaluate_county('brevard');
-- I: {"pass": false, "detail": "card_complete=6087 of 7238", "metric": 84.1}
-- (all other 9 letters PASS, zero regressions)

-- Osceola, live, 2026-08-03 ~16:24 UTC (unchanged, re-confirmed):
SELECT public.pencil_dod_evaluate_county('osceola');
-- G: {"pass": false, "metric": 78.6, "detail": "density=90.7 far= pk1000=78.6"}
-- I: {"pass": false, "metric": 92.7, "detail": "card_complete=127 of 137"}
-- (all other 8 letters PASS, zero regressions)
```

Timestamp UTC: 2026-08-03T16:24Z (session close-out).

## Recommendation for future sessions

1. **Brevard I structural ceiling (~84%)**: further gains need per-municipality zoning GIS
   integration (Brevard has ~13 incorporated jurisdictions each with a separate zoning map beyond the
   county's own unincorporated-only layer) — a genuine substrate-build task.
2. **Osceola I (9 tax_deed rows)**: needs either a court-docket legal-description lookup to
   disambiguate the truncated 12-digit parcel prefixes, or a different upstream scraper fix that
   captures the full parcel_id at ingestion time instead of a truncated one.
3. **Osceola I (1 foreclosure row)**: `2025 CA 001721 MF` needs an authenticated/interactive Benchmark
   docket search (`courts.osceolaclerk.com/BenchmarkWeb`) — out of scope for scriptable tools.
4. **Osceola G (SRPUD)**: do not re-attempt with the same sources (Municode/amlegal/kissimmee.gov/
   Firecrawl) without either restored Firecrawl credits or a browser/Playwright-capable tool to render
   Municode's JS SPA directly — this is the 4th+ session to hit the identical wall.

---
dispatch_id: 1f5f4ede-c466-4c43-a9ec-e6ce1d02c1e5
