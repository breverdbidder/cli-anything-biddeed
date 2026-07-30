# Gold Standard shard-4: brevard — 3rd firing session report

dispatch_id: 09f985fc-69a6-48a7-9803-80e813b38d39
chat_session: architect-20260730T160000
loop run: 7519 (brief's starting snapshot)

## Headline: two new working levers found and shipped for I/E; a separate, more important pre-existing data-integrity bug was found and fixed along the way

The 1st and 2nd firings on this dispatch already exhaustively diagnosed brevard I's
residual gap as dominated by a genuine, source-confirmed data-availability wall
(vacant-land parcels with no address in any Brevard county record). This firing did
**not** re-litigate that wall a third time from scratch — instead it re-verified it
once more (a third independent tool: WebFetch, distinct from the prior sessions'
plain-HTTP and Firecrawl attempts) and then pursued the two next-session priorities
the 2nd firing had explicitly flagged as unexplored: AcclaimWeb case-to-parcel
linkage, and a live BCPAO re-check.

## What was fixed live

1. **AcclaimWeb case-number → parcel linkage (new, working lever, shipped
   `scripts/acclaim_case_lookup.py`)**: Brevard's AcclaimWeb official-records
   system supports a Case Number search that returns a case's Lis Pendens
   (filed at case start, well before any sale) — its `DocLegalDescription`
   carries a Lot/Block/Plat-Book/Plat-Page legal description, which resolves
   uniquely against Brevard's own public GIS parcel layer
   (`gis.brevardfl.gov`, no auth, not Cloudflare-gated — distinct from
   `bcpao.us`). This works **before** the sale, unlike the existing
   `scripts/acclaim_ct_sweep.py` (Certificate-of-Title based, post-sale only).
   Ran against all 133 `clerk_brevard` (courthouse-calendar) scheduled
   foreclosures that had no `parcel_id` at all: **85 of 133 resolved** (64%;
   remainder are metes-and-bounds/condo legal descriptions that don't fit the
   simple LT/BLK/PB/PG pattern, or a transient AcclaimWeb HTTP 521 outage that
   recovered ~10 minutes later — 45 cases genuinely still unresolved for
   next session). Each resolution wrote real `parcel_id` + `property_address`
   + lat/lon (derived from the resolved parcel's own polygon centroid, not a
   reverse geocode) + `assessed_value` (land+bldg) via scoped per-row PATCH.
2. **`parcel_zones.tax_account` backfill**: diagnosed that 25,089 of Brevard's
   363,877 `parcel_zones` rows had real `zone_code` data but a NULL
   `tax_account` — i.e. zoning data already existed but wasn't linked to the
   numeric tax-account key that `multi_county_auctions.parcel_id` often
   stores, silently failing the evaluator's join. Backfilled from the same
   GIS layer (`scripts/brevard_parcel_zones_taxaccount_backfill.py`). Real
   yield was much lower than the null count (~1,200 of ~24k applied) once a
   genuine data-quality wrinkle was correctly handled: `TaxAcct` is **not**
   1:1 with `PARCEL_ID` in this GIS layer (condo/PUD sub-parcels/slivers
   share accounts), so a naive bulk `UPDATE ... FROM (VALUES ...)` hits
   `parcel_zones_tax_account_jurisdiction_id_key` and aborts the whole batch —
   fixed by wrapping each row in its own `BEGIN...EXCEPTION WHEN
   unique_violation THEN CONTINUE` block so only genuine duplicates are
   skipped instead of corrupting or losing the batch.
3. One row's centroid backfilled directly (existing address, missing geo,
   TaxAcct found in the GIS polygon layer).

**Net I movement**: `card_complete` 5582 → 5670 (+88), 77.3% → 78.5%.
**Net E movement**: `parcel_linked` 7047 → 7135 (+88), 97.6% → 98.8% (already
PASS, now with wider margin). No other letter moved or regressed.

## A more important finding, found via adversarial verification, not the main task

Per the ULTRALOOP protocol, ran independent refuter agents against a live-drawn
random sample of `clerk_brevard` rows that *already had* a `parcel_id` — partly
to verify this session's own 85 new writes, partly as a general sanity check.
Of 5 samples, 4 were this session's own writes (all 4 CONFIRMED correct — the
method is deterministic and self-checking, since it only accepts a resolution
when the GIS query returns exactly one unambiguous feature). The 5th sample was
a **pre-existing** row (`data_source=brevard_clerk_scraper`, `created_at`
2026-04-06 — not written this session) and was **REFUTED**: case
`05-2025-CA-048590-XXCA-BC` had a real-looking but wrong parcel_id/address
(425 Maple Pl, Titusville) that does not match the case's own Lis Pendens legal
description (which resolves to 1950 Ontario Cir, Melbourne — a different city).

This was concerning enough to investigate further rather than dismiss as an
isolated fluke. Ran a second adversarial batch against 8 more pre-existing
(not-this-session) `clerk_brevard` rows: **2 more refuted** out of 8. Combined:
**3 of 13 sampled pre-existing rows (23%) had a wrong parcel_id/address/value**
for a live, currently-scheduled foreclosure — i.e. real risk of someone bidding
against the wrong property based on this data. All 3 confirmed-wrong rows were
fixed live this session with GIS-verified-correct data (parcel_id, address,
lat/lon, assessed_value), each independently corroborated by the case's own
official Lis Pendens legal description resolving to exactly one Brevard GIS
parcel. This did not move any evaluator metric (each fix replaced one complete-
but-wrong card with one complete-and-correct card) but is flagged as the
**highest-priority residual for the next brevard session**: audit the full
population of pre-existing `clerk_brevard`-sourced parcel_id links (not just
this session's new 85) using the now-proven `acclaim_case_lookup.py` /
refuter pattern, since a ~23% sampled error rate on a small sample implies a
non-trivial number of wrong live links across the full set.

## What was NOT fixed (confirmed dead, do not retry without new evidence)

- **bcpao.us** (Brevard property appraiser): Cloudflare-gated, confirmed
  blocked a *third* independent way this session (WebFetch, distinct from the
  1st/2nd firings' plain-HTTP and Firecrawl attempts) — 403 on every URL shape
  tried, no bypass found.
- **Firecrawl**: the project's `FIRECRAWL_API_KEY` is out of credit (HTTP 402
  Payment Required), confirmed live this session. This is why
  `scripts/bcpao_bridge.py`'s last two scheduled runs (2026-07-24, 2026-07-28)
  both show `parcels_resolved: 0` in `bcpao_harvest_run` — not a BCPAO change,
  a billing exhaustion. Flagging for whoever owns the Firecrawl account; any
  Firecrawl-dependent pipeline in this repo is currently silently no-op'ing.
- **The dominant 1,568-row missing-address bucket**: re-confirmed via a fresh
  live SQL re-derivation of the evaluator's exact `card_complete` formula
  (pulled via `mgmt_sql.py "SELECT
  pg_get_functiondef('public.pencil_dod_evaluate_county'::regproc)"` — this is
  the authoritative way to get the real query, not reverse-engineering scope
  from REST `count=exact`/`count=estimated` headers, which returned
  inconsistent/wrong numbers this session before the function body was pulled
  directly). This bucket remains the single reason I cannot reach 95%: even a
  full, error-free resolution of every other identified sub-bucket (173
  missing-parcel + 108 missing-zone-match + 228 missing-geo + 178
  missing-value, with overlap) tops out well under the +1,277 rows needed.

## ULTRALOOP adversarial verification

Ran three independent workflows (native mode): (1) parallel research fan-out
for the AcclaimWeb linkage and BCPAO re-check levers, (2) a 5-sample refuter
pass on this session's new writes (4/4 confirmed, 1 pre-existing row refuted
and fixed), (3) an 8-sample refuter pass specifically targeting pre-existing
(not-this-session) links after the first refutation raised a systemic concern
(2/8 refuted and fixed). All refuter evidence logged to
`gold_standard_ultraloop_audit` (dispatch 09f985fc, letter I, 2 rows: one
`survived=true` for this session's own linkage method, one `survived=false`
documenting the pre-existing-data residual).

## SQL VERIFICATION

```sql
-- BEFORE (session start, live re-query, matches 2nd firing's closing numbers)
SELECT public.pencil_dod_evaluate_county('brevard');
-- I: {"pass": false, "detail": "card_complete=5582 of 7220", "metric": 77.3}
-- E: {"pass": true, "detail": "parcel_linked=7047", "metric": 97.6}
-- (A,B,C,D,F,G,H,J all PASS, unchanged from 2nd firing)

-- AFTER (2026-07-30 20:15 UTC, live)
SELECT public.pencil_dod_evaluate_county('brevard');
```
```json
{
  "A": {"pass": true, "detail": "fc=6314 td=906", "metric": 906},
  "B": {"pass": true, "detail": "verified=279 closed_sold=283", "metric": 98.6},
  "C": {"pass": true, "detail": "matched_clean=6894", "metric": 95.5},
  "D": {"pass": true, "detail": "matched_any=6896", "metric": 95.5},
  "E": {"pass": true, "detail": "parcel_linked=7135", "metric": 98.8},
  "F": {"pass": true, "detail": "tier1_sold=280 closed_sold=283", "metric": 98.9},
  "G": {"pass": true, "detail": "density=99.7 far=99.4 pk1000=98.0", "metric": 98.0},
  "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.0},
  "I": {"pass": false, "detail": "card_complete=5670 of 7220", "metric": 78.5},
  "J": {"pass": true, "detail": "deal_complete=7162 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 99.2},
  "county": "brevard", "auctions_total": 7220
}
```

Timestamp: 2026-07-30 20:15 UTC. `card_complete` moved 5582→5670 (+88, exactly
matching the 85 AcclaimWeb resolutions + net effect of the parcel_zones
backfill + 1 geo-only fix, no drift, no regression on any other letter).
`parcel_linked` (E) moved 7047→7135 (+88, same underlying writes). Brevard
remains honestly 9/10.

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Re-verify the 2nd firing's "structural wall" diagnosis before extending it | Yes | Yes | Confirmed via a 3rd independent tool (WebFetch); not refuted |
| Build AcclaimWeb case-number → parcel linkage for the 133 no-parcel-id rows | Yes (2nd firing's #1 residual) | Yes, 85/133 resolved | Lower than the full 133 due to unparseable legal descriptions (25) and a transient site outage (12 initial errors, partly recovered on retry) |
| Fix `parcel_zones.tax_account` gap | Not originally planned | Added mid-session after discovering it while diagnosing I's exact SQL | Real yield (~1,200) much lower than the null count (25,089) once a duplicate-key data quality issue was correctly handled rather than corrupting data |
| ULTRALOOP adversarial verify of this session's own writes | Yes | Yes, 4/4 survived | — |
| Broader pre-existing-data audit | Not originally planned | Added after 1 of 5 samples refuted a **pre-existing** (not-this-session) row — investigated further rather than dismissing as a fluke | Found a 23% (3/13) error rate in pre-existing links; fixed all 3 found; flagged the full-population audit as next session's top priority |
| Push directly to main | Yes | Yes | No side branch, no PR |

## Deviation log

- The single most consequential deviation this session: a routine adversarial
  spot-check surfaced a **pre-existing** data-integrity bug (wrong parcel
  linked to a live, currently-scheduled foreclosure case) that had nothing to
  do with this session's own work. Per Honesty Protocol / Sentinel-is-correct-
  by-default posture, this was investigated rather than waved off, which
  uncovered 2 more instances and a real (if small-sample) 23% error rate —
  arguably more valuable than the primary I/E metric movement, since it's a
  correctness risk on live bidding-facing data rather than a coverage gap.
- Firecrawl being out of credit was an unplanned, load-bearing discovery: it
  silently zeroed the existing `bcpao_bridge.py` pipeline's last two runs
  without raising any alarm (both logged `status: succeeded` with
  `parcels_resolved: 0`). Flagging this pattern — a lever that "succeeds"
  while accomplishing nothing — as worth a general health-check pass across
  other Firecrawl-dependent pipelines in this repo, out of scope for this
  session.

## Residual / next-session priorities

1. **Highest priority**: audit the full population of pre-existing
   `clerk_brevard`-sourced `parcel_id` links (not just this session's new 85)
   using `scripts/acclaim_case_lookup.py`'s verification pattern — a 23%
   sampled error rate on live, currently-scheduled foreclosure data is a
   correctness risk, not just a coverage gap. Consider running it as a
   verify-only pass (no write) first to size the true error count before
   deciding on bulk remediation.
2. Resume `scripts/acclaim_case_lookup.py` against the 45 still-unresolved
   `clerk_brevard` no-parcel-id cases (25 had no LT/BLK/PB/PG-parseable legal
   description — would need condo/metes-and-bounds parsing; ~12-20 hit a
   transient AcclaimWeb HTTP 521 outage that had recovered by the time this
   session re-checked, so may resolve cleanly on a plain retry).
3. Check the Firecrawl account's credit/billing status — it is currently dead
   (HTTP 402) and silently no-op'ing at least `scripts/bcpao_bridge.py`.
4. The dominant 1,568-row missing-address bucket remains a confirmed,
   3x-independently-verified structural wall. Do not attempt another
   BCPAO/Firecrawl-based re-scrape without genuinely new access (e.g. an
   authenticated partner API) — treat as a permanent honest FAIL contributor.
