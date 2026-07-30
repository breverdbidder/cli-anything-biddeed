# Gold Standard shard-4: brevard — session report

dispatch_id: 09f985fc-69a6-48a7-9803-80e813b38d39
chat_session: architect-20260730T160000
loop run: 7519 (brief's starting snapshot)

## Headline finding: I's residual gap is a structural, source-confirmed data-availability wall, not a scraping/pipeline gap

The brief listed brevard as 9/10, only letter I failing (77.3% at session start via the brief's
loop-run-7519 snapshot; 77.3% again via a fresh live re-query — no drift). I re-scraped BOTH
independent authoritative address sources live during this session:

1. **FL DOR Statewide Cadastral FeatureServer** (`services9.arcgis.com/.../Florida_Statewide_Cadastral`,
   CO_NO=15) — full re-dump, 345,999 Brevard parcels, keyset-paginated (`ALT_KEY` is not
   server-side filterable on this layer, confirmed live via repeated 400s on any `ALT_KEY=`/`IN()`
   predicate — must dump-and-join client-side; `PARCEL_ID`/`PARCELNO`/`CO_NO` ARE filterable).
2. **Brevard County's own GIS parcel layer** (`gis.brevardfl.gov/gissrv/rest/services/Base_Map/
   Parcel_New_WKID2881/MapServer/5`, `TaxAcct` field, batch `IN (...)` queries work directly on
   this layer) — queried all 1,235 real (non-null, non-SYN) parcel_ids in the gap set.

Both sources independently return the literal string `UNKNOWN` (or blank) for street name/city on
**1,350 of 1,352 matched parcels** — cross-source agreement is exact. `USE_CODE_DESCRIPTION` on the
sampled accounts confirms these are genuinely vacant land (`VACANT RESIDENTIAL LAND`, `ACREAGE -
VACANT`), which legitimately lack a site address in any official record. This is not new: the
2026-07-28 shard-1 session (dispatch 2f4312f9) already found and purged the same UNKNOWN-poisoned
placeholder data and diagnosed "needs a live BCPAO ArcGIS re-scrape" as the residual. That re-scrape
has now happened, live, from two independent sources, and reconfirms the same honest FAIL rather
than uncovering a new fixable population.

## What was fixed live

- **brevard I**: 2 rows had a real (non-UNKNOWN) address already but were missing
  latitude/longitude/assessed_value only — backfilled from the live FL DOR cadastral re-scrape.
  `card_complete` moved from 5578 → 5580. This is real, verified, and non-regressive on every other
  letter — but at this scale it does not move the percentage meaningfully (77.3% both before and
  after, to 1 decimal).
- Fixed a pagination bug in the enrichment tooling itself before it could cause harm: offset-based
  PostgREST pagination without an explicit `ORDER BY` returned duplicate rows non-deterministically
  (inflated an intermediate gap count 10x); added `order=id.asc` with client-side dedup. Also caught
  that the evaluator's card_rows denominator excludes non-tier1 PropertyOnion rows — an early gap
  query that didn't apply this filter overcounted the "no parcel_id" bucket by ~10x (1768 vs the
  true 173, which matches letter E's own gap exactly). Neither bug shipped to the database — caught
  in dry-run stats before any write.
- Fixed a second, more serious bug before any bulk write: PostgREST bulk upsert-by-primary-key
  (`Prefer: resolution=merge-duplicates`) fails with a NOT NULL constraint violation on this table,
  because Postgres validates the full implicit INSERT row against NOT NULL columns *before*
  resolving the ON CONFLICT branch, even though the row already exists and would only ever be
  UPDATEd. Switched to per-row scoped PATCH (`?id=eq.<uuid>`), which is a real UPDATE and has no
  such issue. Flagging for any future session that reaches for bulk upsert-by-id on this table.

## What was NOT fixed (and why — genuine external/structural blockers)

- **1,350 UNKNOWN-address rows**: no legitimate address available. bcpao.us (the county property
  appraiser's own site, the most likely remaining source) is Cloudflare-challenge-gated and could
  not be reached without solving a CAPTCHA — out of scope, not attempted. Fabricating a placeholder
  or legal-description-as-address substitute was considered and rejected: it would satisfy the
  evaluator's literal `IS NOT NULL` check while reproducing exactly the ghost-success pattern this
  project has purged repeatedly (most recently brevard I itself, 2026-07-28). **Not attempted.**
- **173 rows with no parcel_id at all**: all sourced from the `brevard_clerk` foreclosure-calendar
  scrape, which captures `case_number` + `auction_date` only — no parcel identifier at the source.
  This is the same population letter E already reports as its residual 2.4% gap. Fixing it requires
  a per-case lookup (courthouse calendar detail page, or Brevard's AcclaimWeb official-records search
  by case number → Lis Pendens/judgment doc → legal description → parcel_id cross-reference via the
  property appraiser). Confirmed AcclaimWeb (`vaclmweb1.brevardclerk.us/AcclaimWeb`) supports Case
  Number search live. This is a genuine per-case research task (173 cases), not a mechanical batch
  join — out of scope for a same-session mechanical fix. **Flagging as the highest-leverage
  next-session lever** (also lifts letter E toward 100%).
- **63 rows with a real parcel_id that matched neither address source**: likely retired/merged tax
  accounts or format drift. Small population, not pursued this session given the much larger,
  already-diagnosed 1,350-row and 173-row buckets dominate the gap.

## ULTRALOOP adversarial verification

Ran a 2-agent independent refuter workflow (`ultraloop_mode=native`) against a 4-account sample of
the "no legitimate address available" claim, blind to each other. Net: 7 of 8 per-account checks
SURVIVED outright. The 1 apparent `REFUTED` (agent found `4060 AURANTIA RD, MIMS, FL 32754` via
Brevard's Accela Address Locator reverse-geocoding the parcel centroid, score 100) was independently
re-examined by the second agent and found to be a **nearest-neighbor geocoding artifact**: the
matched address point sits 126ft away and outside the parcel's own polygon — it belongs to an
adjacent platted lot, not the one being checked. Logged to `gold_standard_ultraloop_audit` with
`survived=true` and this reconciliation documented in `refuter_evidence`.

**New guardrail surfaced by this adversarial pass**: reverse-geocoding parcel centroids against
Brevard's Accela Address Locator is unsafe for bulk vacant-land enrichment — it returns a
high-confidence (score 100) address belonging to a *different* nearby parcel rather than failing
cleanly. Any future session attempting this as an I-fix lever must verify polygon containment before
trusting a locator result, not just accept a high match score.

## SQL VERIFICATION

```sql
-- BEFORE (session start, matches brief's loop-run-7519 snapshot, re-confirmed live)
SELECT public.pencil_dod_evaluate_county('brevard');
-- I: {"pass": false, "detail": "card_complete=5578 of 7220", "metric": 77.3}
-- (A,B,C,D,E,F,G,H,J all PASS, unchanged from brief)

-- AFTER (2026-07-30 16:38 UTC, live)
SELECT public.pencil_dod_evaluate_county('brevard');
```
```json
{
  "A": {"pass": true, "detail": "fc=6314 td=906", "metric": 906},
  "B": {"pass": true, "detail": "verified=279 closed_sold=283", "metric": 98.6},
  "C": {"pass": true, "detail": "matched_clean=6894", "metric": 95.5},
  "D": {"pass": true, "detail": "matched_any=6896", "metric": 95.5},
  "E": {"pass": true, "detail": "parcel_linked=7047", "metric": 97.6},
  "F": {"pass": true, "detail": "tier1_sold=280 closed_sold=283", "metric": 98.9},
  "G": {"pass": true, "detail": "density=99.7 far=99.4 pk1000=98.0", "metric": 98.0},
  "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 4.4},
  "I": {"pass": false, "detail": "card_complete=5580 of 7220", "metric": 77.3},
  "J": {"pass": true, "detail": "deal_complete=7162 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 99.2},
  "county": "brevard", "auctions_total": 7220
}
```

Timestamp: 2026-07-30 16:38 UTC. `card_complete` moved 5578→5580 (+2, exactly matching the 2 rows
patched — no drift, no regression on any other letter). Rounds to the same 77.3% at 1 decimal;
brevard remains honestly 9/10.

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Diagnose I's residual gap composition | Yes | Yes | Found 3 distinct sub-populations (1350 vacant-land/no-address, 173 no-parcel, 63 unmatched) instead of one homogeneous gap |
| Mechanically enrich via live BCPAO/DOR re-scrape | Yes | Yes, but small yield | 2 rows, not the ~1350 hoped for — source data genuinely lacks addresses, verified from 2 independent sources |
| Cross-check against Brevard's own (non-statewide) GIS | Not originally planned | Added mid-session | Statewide DOR aggregation could plausibly have been stale/incomplete vs the county's own system; checked directly, found identical UNKNOWN pattern — strengthens rather than weakens the finding |
| ULTRALOOP adversarial verify | Yes | Yes | Caught and correctly reconciled a false-positive refutation (nearest-neighbor geocoding artifact) rather than either accepting it naively or dismissing it without cross-check |
| Push directly to main | Yes | Yes | No side branch, no PR |

## Deviation log

- Two tooling bugs (non-deterministic pagination inflating a diagnostic count 10x; PostgREST bulk
  upsert-by-id violating NOT NULL on the INSERT branch of ON CONFLICT) were caught in dry-run before
  either could write bad data or silently under-report. Neither reached the database.
- The brief's implicit hope (per the 2026-07-28 report's residual note) was that a live BCPAO
  re-scrape would recover most of the ~1,600-row I gap. That did not hold up under fresh, live,
  dual-source verification — the honest finding is the opposite: the gap is structurally blocked at
  the source for ~85% of it. Reporting this plainly rather than searching for a marginal population
  to inflate the headline number.

## Residual / next-session priorities

1. **Highest leverage**: build the AcclaimWeb case-number → parcel_id linkage for the 173 rows
   currently missing `parcel_id` entirely (all `brevard_clerk`-sourced calendar rows). This is a
   genuine per-case lookup, not a batch job — likely needs `browser-use` or similar (per the
   2026-07-28 report, not installed on this runner) since AcclaimWeb search results were not
   confirmed to be scrapable via plain HTTP fetch this session. Would lift both I and E.
2. bcpao.us remains Cloudflare-gated for all sessions so far (this one and 2026-07-28) — if a
   legitimate authenticated/partner API access path exists, it would be the most direct route to
   the remaining 1,350-row address gap; otherwise this population should be treated as a permanent,
   honest FAIL contributor and excluded from future "let's re-scrape" attempts (already tried twice,
   two independent sources, both confirm no data).
3. Do not reuse the plain reverse-geocode-centroid approach against Brevard's Accela Address Locator
   for bulk enrichment without polygon-containment verification — proven to return wrong (but
   high-confidence) neighboring-parcel addresses this session.
