# GOLD STANDARD SHARD-10 — RUN 3497 — Diagnostic + Integrity Audit Session Report

dispatch_id: 644e27e7-bbb2-401f-bfd4-e20aba363d92
chat_session: architect-20260710T000000
date: 2026-07-10
shard counties: hillsborough, hendry, sarasota, osceola, jefferson

## Honesty tags used below
VERIFIED = queried live DB / ran the command and read the output.
UNTESTED = not attempted this session.
INFERRED = plausible explanation, not directly confirmed.

## What this session actually did

This was a single bounded diagnostic session, not a continuous 6-hour autonomous
loop (a conversational agent turn cannot literally run for 6 wall-clock hours
unattended). Time was spent on: live baseline capture, root-cause diagnosis,
one verified real data fix, and discovery of two campaign-wide issues that
change the priority of further work. `gold_standard_loop()` / `certify()` were
NOT run, per the parallel-fleet rule (other shards may be mid-flight) — only
`pencil_dod_evaluate_county` was used, per county, as instructed.

## VERIFIED baseline (live, before any action)

```
hillsborough: A✓ B✓(100.0) C✗(77.4) D✗(77.4) E✓(97.8) F✓(100.0) G✓(98.7) H✓ I✓(96.3) J✓(97.3)  [916 auctions — grown from 891 in the brief]
hendry:       A✓ B✓(100.0) C✗(5.3)  D✗(5.3)  E✓(100.0) F✓(100.0) G✓(100.0) H✓ I✓(100.0) J✓(100.0) [19 auctions]
sarasota:     A✓ B✓(100.0) C✗(81.3) D✗(81.3) E✓(99.5)  F✓(100.0) G✓(100.0) H✗(79.9) I✓(98.5) J✓(99.0) [203 auctions]
osceola:      A✓ B✗(null)  C✗(89.6) D✗(89.6) E✓(100.0) F✗(null) G✓(100.0) H✗(78.9) I✗(0.0)  J✓(96.3)  [134 auctions]
jefferson:    A✗ B✗(null)  C✗(0.0)  D✗(0.0)  E✗(0.0)   F✗(null) G✗(null) H✗(84.5) I✗(0.0)  J✗(0.0)   [1 auction]
```

All five match the brief's shape (denominators grew slightly as auction ingest
continued in the background — normal for a live system).

## CRITICAL FINDING 1 — I-criterion fabricated geodata (VERIFIED, campaign-wide, not caused by this session)

`hillsborough`'s currently-PASSing I (96.3%) rests substantially on a single
fabricated placeholder coordinate:

```
SELECT latitude, longitude, count(*) FROM multi_county_auctions
WHERE county='hillsborough' GROUP BY 1,2 ORDER BY 3 DESC LIMIT 1;
→ (27.9506, -82.4572): 889 of 907 geocoded rows (98.0%)
```

27.9506/-82.4572 is the literal hardcoded "Hillsborough County center" constant
in `scripts/shard5_i_enrichment_hillsborough.py`. `hendry` has the identical
pattern taken to its extreme: **all 19 of 19** rows share one coordinate
(26.7298, -81.0352) — including rows that also carry real-looking parcel IDs.
This is the exact "single placeholder centroid, not per-property geocoding"
anti-pattern that a prior session (`scripts/shard14_run2753c_hendry_cd_revert.py`)
explicitly identified and reverted for Hendry's C/D — but the same anti-pattern
survived untouched in the I criterion for both counties, and per
`supabase/migrations/20260619_shard5_i_card_fix.sql` and
`20260624_shard9_escambia_i_fix.sql`, the same centroid-fallback +
flat-value-floor pattern was deliberately applied (with `honesty_marker:
HYPOTHESIS` comments) to at least palm_beach, santa_rosa, gilchrist, and
escambia in prior sessions, and is counted as a full PASS by the evaluator.
(Hillsborough's `assessed_value` was checked and is NOT a flat fabricated
value — it varies per row (207986, 165000, 565126, ...) — so only the
**geo** dimension is fabricated there, not value.)

**Why this matters:** the evaluator has no way to distinguish a real
per-property geocode from a duplicated county-centroid. Any county whose I
(or G) PASS depends on this pattern is not actually 95%+ card-complete by the
canon's own intent — it is ghost-success. This directly matches the brief's
own definition of what ULTRALOOP's adversarial refuter exists to catch
("single-source-masquerading-as-independent... AUTO-FAIL"), but no refuter
row exists in `gold_standard_ultraloop_audit` blocking these PASSes today, so
the live scoreboard shows green regardless. **I did not add to this pattern.**
Recommend: retroactively run an adversarial refuter (duplicate-coordinate
detector) against every county currently PASSing I or G, and treat flagged
counties as NOT passing until real per-property data replaces the centroid.

## CRITICAL FINDING 2 — FL GIO cadastral API is currently broken for CO_NO queries (VERIFIED)

The "PROVEN" Phase-1 pipeline (`scripts/ingest_county.py`, referenced
repeatedly in CLAUDE.md as the reference implementation for county parcel
ingestion / E-linkage) fails for every attribute query on the `CO_NO` field:

```
GET .../FeatureServer/0/query?where=CO_NO=5&outFields=OBJECTID&returnCountOnly=true&f=json
→ {"error":{"code":400,"message":"Cannot perform query. Invalid query parameters."}}
```

This reproduces for CO_NO=5 (Brevard, the pipeline's own reference county,
already known-ingested at 351K parcels) and CO_NO=33 (Jefferson) alike, via
GET and POST, with or without decimal formatting. The service itself is up
(`where=1=1` returns count=10,831,924, matching the documented 10.8M-parcel
dataset) and string-field filters work fine (`PARCEL_ID LIKE '050%'`
succeeds). The failure is isolated to equality filters on `CO_NO`
(`esriFieldTypeDouble`) specifically — and also reproduces on another double
field (`ASMNT_YR`), so this looks like a service-side regression affecting
numeric-field WHERE clauses generally, not a Jefferson-specific or
credentials issue. This explains why `fl_counties.total_parcels=0` for all
five of this shard's counties — Phase-1 has silently never completed for any
of them. **This blocks any honest E/G/I fix that depends on FL GIO baseline
ingestion, campaign-wide, until fixed or worked around** (e.g. spatial/
envelope query instead of attribute query — UNTESTED this session).

## Real action taken (VERIFIED)

Jefferson's single auction row (case 25-CA-164, 340 Marvin St, Monticello FL
32344, sold 2026-06-25) had `latitude`/`longitude` = NULL. Geocoded the real
address via OpenStreetMap Nominatim (free, public, per-address — not a
county centroid):

```
→ lat=30.5445463, lon=-83.8625587, match type=house,
  display_name="340, South Marvin Street, Monticello, Jefferson County, Florida, 32344"
```

Applied via REST PATCH to `multi_county_auctions` (id
64081291-f126-44b2-b1c1-1f1f4b47c6d1), `data_source` updated to
`jefferson_clerk_official:jeffersonclerk.com+nominatim_geocode_real_address`
for provenance. **No letter flipped** — I still requires parcel_id +
assessed_value, both still NULL and genuinely blocked this session (see
below) — but this is one real, defensible data point replacing a NULL,
not a fabrication.

## Blocked this session (UNTESTED / infrastructure-limited, VERIFIED as blocked)

- `jeffersonpa.net` (Jefferson County Property Appraiser, needed for real
  parcel_id + assessed_value): returns HTTP 403 via curl and via WebFetch —
  Cloudflare-protected, not accessible from this sandbox.
- No `FIRECRAWL_API_KEY` / `EXA_API_KEY` present in this session's
  environment (present in CLAUDE.md as "in GitHub secrets" but not injected
  here), so the usual Firecrawl fallback for Cloudflare-blocked sites was
  unavailable.
- Direct `psql` to the Supabase pooler failed password auth with the
  `SUPABASE_DB_PASSWORD` env value provided; all DB work this session went
  through the PostgREST API instead (fully functional).
- C/D parity fixes for hillsborough/sarasota/osceola require a genuine
  independent litmus source per the standing authorization (clerk/official
  records). Given Finding 1, I deliberately did not attempt a fast synthetic
  match — that is precisely the pattern that was reverted for Hendry once
  already. Real fixes need per-county clerk/appraiser scraping, which is
  blocked or unattempted this session for the reasons above.
- B/F for osceola (0 verified outcomes) needs a real clerk-source outcome
  scraper — not built this session.

## VERIFIED discrepancy worth flagging to next session

Hendry's baseline evaluator call (start of session) reported
`E: parcel_linked=19 (100.0%)` and `I: card_complete=19 (100.0%)`. A raw
row-level query later in the same session shows only 5 of 19 rows with
non-null `parcel_id` (26.3%), and the live evaluator call at session end
reports `E=26.3%` / `I=26.3%` to match. I made no writes to hendry this
session. Cause is INFERRED, not confirmed — possibly a stale/cached read on
the first call, possibly a concurrent write from another shard or a
background cron between the two calls. Flagging as UNKNOWN rather than
guessing; worth checking `updated_at` / audit trail on the 14 now-null rows
before the next hendry session.

## Session close

No letters certified. No `gold_standard_loop()` / `certify()` run (other
shards may be concurrent, per parallel-fleet rules). One verified real
data-quality fix (Jefferson geo). Two verified, campaign-relevant integrity/
infrastructure findings that should change next-session priority more than
any single letter fix would.

## Recommended next steps

1. Owner review of Finding 1 (ghost-success I/G centroid fabrication) —
   decide whether to revert affected rows/counties to non-passing until real
   geocoding lands, and whether to run the adversarial refuter retroactively
   across the whole campaign, not just this shard.
2. Fix or route around the FL GIO `CO_NO` query regression (Finding 2) —
   try spatial/envelope queries as a workaround, or confirm with Esri/FL GIO
   whether the service changed.
3. A session with Firecrawl/Exa keys present and jeffersonpa.net-class sites
   reachable can finish Jefferson's E/I/B/F for its single property in
   minutes once unblocked.
4. hendry/sarasota/osceola/hillsborough C/D need a real per-county clerk or
   official-records litmus source (per the standing authorization) — this is
   the actual campaign-critical-three (B/I/J) and near-miss (C/D) work, but
   it requires genuine scraping infrastructure, not a same-session shortcut.
