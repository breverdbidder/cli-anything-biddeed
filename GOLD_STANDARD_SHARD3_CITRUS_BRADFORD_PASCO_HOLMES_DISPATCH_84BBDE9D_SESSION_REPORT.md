# GOLD STANDARD shard-3 — citrus, bradford, pasco, holmes

dispatch_id: 84bbde9d-9e29-4417-a1f3-2c7e10200af7 · chat_session: architect-20260814T160000 · loop run 11435 · session 2026-08-14

## Environment note (read before trusting "6h autonomous" framing in future briefs)

This session ran with live Supabase REST API access (service-role key: read + write via
PostgREST + the `pencil_dod_evaluate_county` RPC all confirmed working) but **no working
SQL execution path**: direct `psql` connections (both pooler `aws-0-us-west-2.pooler.
supabase.com:6543` and direct `db.mocerqjnksmhcjzxrewo.supabase.co:5432`) failed
`password authentication failed` from this sandbox, and the `exec_sql`/`execute_sql`/`exec`
RPCs referenced by older shard scripts no longer exist in the schema cache (404,
`PGRST202`). All work below was done via PostgREST table reads/writes and existing
whitelisted RPCs only. This also means the actual session was well under the nominal 6h
GHA ceiling — reporting real elapsed effort, not a fabricated full-length session, per
HONESTY PROTOCOL.

## Result summary

| county | before | after | delta |
|---|---|---|---|
| citrus | 9/10 (I fail) | 9/10 | unchanged — real diagnostic progress, see below |
| bradford | 8/10 (B,F blocked) | 8/10 | unchanged — reconfirmed genuinely blocked **this morning** by dispatch 3ce988ac (08:00Z wave), not re-run to avoid duplicate same-day effort |
| pasco | 7/10 (C,D,I fail) | 7/10 | unchanged — scope-denominator ambiguity found, no safe fix attempted, see below |
| holmes | 3/10 (B,C,D,F,E,I,J fail) | **6/10** | **E, I, J flipped FAIL→PASS** |

## Verification evidence (pencil_dod_evaluate_county, live, final re-check)

**citrus** — 9/10:
```json
{"A":{"pass":true,"metric":56},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":98.1},"D":{"pass":true,"metric":99.5},"E":{"pass":true,"metric":98.6},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":95.9},"H":{"pass":true,"metric":0.0},"I":{"pass":false,"metric":94.2,"detail":"card_complete=195 of 207"},"J":{"pass":true,"metric":100.0},"auctions_total":207}
```

**bradford** — 8/10:
```json
{"A":{"pass":true,"metric":1},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":6.9},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"auctions_total":5}
```

**pasco** — 7/10:
```json
{"A":{"pass":true,"metric":162},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":93.9,"detail":"matched_clean=326"},"D":{"pass":false,"metric":93.9,"detail":"matched_any=326"},"E":{"pass":true,"metric":98.8},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":95.4},"H":{"pass":true,"metric":0.0},"I":{"pass":false,"metric":93.7,"detail":"card_complete=325 of 347"},"J":{"pass":true,"metric":99.1},"auctions_total":347}
```

**holmes** — 6/10 (BEFORE was 3/10: A,G,H only):
```json
{"A":{"pass":true,"metric":6},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":62.5},"D":{"pass":false,"metric":62.5},"E":{"pass":true,"metric":100.0,"detail":"parcel_linked=16"},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":6.9},"I":{"pass":true,"metric":100.0,"detail":"card_complete=16 of 16"},"J":{"pass":true,"metric":100.0,"detail":"deal_complete=16"},"auctions_total":16}
```

## What shipped

### holmes E/I/J (94.1% → 100.0% each, PASS, live-verified) — genuine fix
A 2026-08-10 scrape run inserted a blank stub row (`case_number="PARCEL-0936.01-004-00C-
008.000"`, parcel_id/address/geo/value all NULL) duplicating an existing complete row for
the identical parcel_id + auction_date + county (`HOLMES-LEGACY-3ca8afb6...`, created
2026-06-19, address "505 W MONTANA AVE., BONIFAY, FL 32425"). This one row was the entire
E and I gap (16/17 → the stub was the only row missing parcel linkage/card fields) and it
also fully accounted for J's gap. Deleted the duplicate stub (id `dc9c33b0-2d40-45dc-
bf49-fbfc86b70394`); re-verified live immediately after — E, I, J all flip to 100%,
auctions_total correctly drops 17→16, no other letter regressed. C/D metric also shifted
(64.7%→62.5%) purely from the denominator drop (numerator unchanged, matched_clean was
never true for the stub either) — still FAIL, no change in pass/fail state, noted for
accuracy not claimed as progress. Script: `scripts/holmes_dedup_shard3_84bbde9d.py`.

**Same-pattern check**: the other 3 new (2026-08-10-ingested) holmes rows with
`case_number` prefix `PARCEL-<parcel_id>` were checked for the same duplicate signature —
none had a matching legacy counterpart; all 3 already carry complete parcel_id/address/
geo/market_value. Not duplicates, no action needed.

### citrus I — real data-quality fix shipped, did NOT move the metric (reported honestly)
Geocoded 4 citrus tax-deed rows (parcel_ids 2041978, 3279711, 1660173, 2074833 — cases
2026-0154TD/0174TD/0167TD/0169TD) via the Citrus BOCC GIS `LandDevelopment/MapServer/0`
Lots layer (ALTKEY field, real polygon centroids, same verified-authoritative source used
by the prior `shard5_run1251_citrus_i_geocode_fix.py`). All 4 already had parcel_id,
address, and market_value populated — only latitude/longitude were NULL before this fix.
**Re-verified live: I metric unchanged (still 195/207).** Root cause: none of these 4
parcels exist in `v_zoning_gold_standard_card` at all (checked directly — 0 rows for all
4 parcel_ids), so the evaluator's "zoned parcel" component of I (per canon: "address+geo+
value+**zoned parcel**") is the actual blocker for at least these 4 rows, not geo/address/
value. This means citrus's remaining ~12-row I gap is a zoning-linkage gap (parcel_zones/
zoning-district coverage), same failure class as the well-documented brevard/duval G
diagnosis, not a geocoding gap. **Flagging for next session**: extend citrus
parcel_zones/zoning_districts coverage to these TD parcels' jurisdictions before
attempting further I work; do not re-attempt geocoding-only fixes on the remaining gap
rows, they will not move the metric.

### bradford — not re-run (avoided duplicate same-day work)
Dispatch `3ce988ac` (this morning's 08:00Z wave, same day) already reconfirmed bradford
B/F genuinely blocked, including checking the 2 newest past-due cases with zero result
published anywhere. Re-running the identical live-site checks a few hours later on a
rural county's court records would not produce new information and would misrepresent
effort as progress. See that session's report for the full evidence chain.

### pasco C/D, I — investigated, no fix attempted (scope ambiguity, reported per BLANK > WRONG)
`multi_county_auctions` for county=pasco contains far more rows (4,380+ with NULL
`parity_status` alone) than the evaluator's `auctions_total=347`, including confirmed
duplicate `PO-xxxxxx` case numbers differing only by address casing (e.g. `PO-1100218`
appears twice, one row complete, one blank). Tried `is_operational=true` as a candidate
scope predicate — returns 618 for pasco, not 347, so that is not the (or not the only)
scoping filter. Could not locate the true 347-row scope definition: no arbitrary-SQL RPC
is available from this session (see Environment note) to inspect
`pencil_dod_evaluate_county`'s source directly, and `gold_standard_cert_scope` has zero
rows for pasco/citrus/holmes/bradford (that snapshot-scope table is brevard/duval-only
per the brief's own EVALUATOR V6 notes). Attempting a bulk parity/dedup fix against an
unverified denominator risks the exact "ghost-success"/anomalous-ratio failure mode this
campaign's HONESTY PROTOCOL exists to prevent, so no write was made. Next session should
resolve the scope predicate first (ideally via a session with working psql/pooler access)
before touching pasco C/D/I at scale.

## Regression check
Re-ran `pencil_dod_evaluate_county` for all 4 counties after the holmes and citrus writes
above; no letter regressed anywhere in the shard.

## Database checkpoint
`gold_standard_campaign` row (id=4383, dispatch_id=84bbde9d...) updated live with
per-county `criteria_passed` A–J booleans, `exit_reason='timeout'`,
`session_end_at` — see live table for current values.

## Next-session priorities (in order)
1. **citrus I**: load parcel_zones/zoning_districts coverage for the TD parcels currently
   absent from `v_zoning_gold_standard_card` (start with the 4 geocoded this session:
   2041978, 3279711, 1660173, 2074833) — this is the actual lever, not further geocoding.
2. **pasco C/D/I**: resolve the true 347-row scope predicate (needs working SQL
   introspection of `pencil_dod_evaluate_county`, not available this session) before any
   bulk write; separately, the `PO-xxxxxx` duplicate-casing rows are a real data-quality
   issue worth a dedup pass regardless of whether they're in-scope.
3. **holmes B/C/D/F**: no new leverage found this session (17-session exhaustion record
   stands); only re-attempt if a new public data source surfaces.
4. **bradford B/F**: same — time-dependent, checked twice today already, wait for new
   case dispositions rather than re-running identical live-site checks.
