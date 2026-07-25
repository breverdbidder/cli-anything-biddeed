# Gold Standard shard-5 (sumter) — dispatch 75094a54, run6459

## Outcome: sumter 9/10 -> 10/10 (all letters PASS)

## What happened
The prior turn of this same session (dispatch_id `75094a54-64f2-4f36-a62f-1c190ac5162a`,
chat_session `architect-20260725T160000`) diagnosed criterion I's sole residual row
(`case_number=2025-CA-000255`, `parcel_id=D29A024`, `property_address=NULL`), wrote and
committed the fix migration (`supabase/migrations/20260725_sumter_i_d29a024_reverse_geocode_address.sql`,
commit `11ac1f23`), attempted to wire an auto-apply GHA workflow (`4358ee27`), then reverted
it for lack of `workflows` permission (`dee06bd2`) — leaving the migration **committed but
never executed live**. Per SHIP GATE, a committed-but-unexecuted migration is `WIP`, not
`SHIPPED`.

This session executed the already-committed migration live via the Supabase Management
API (`mgmt_sql.py`, which uses `SUPABASE_ACCESS_TOKEN` — no DB password needed, no GHA
workflow required) and adversarially verified the result before treating it as done.

## Fix
- Sumter GIS ArcGIS reverseGeocode: failed (consistent with prior session's HTTP 500 note)
- US Census TIGER reverse geocoder: HTTP 404 (independently reproduced by this session's
  refuter step via direct `curl`, not just re-trusting the migration's own fallback logic)
- OpenStreetMap Nominatim: succeeded — `property_address = 'US 301, WILDWOOD, FL 34785'`

Wrote via a single guarded `UPDATE ... WHERE property_address IS NULL` (idempotent,
denominator-safe — card_complete moved by exactly 1 row, 10->11 of 11, `auctions_total`
unchanged at 11).

## Adversarial verification (ULTRALOOP)
Independently re-derived the reverse-geocode from the same lat/lon via separate `curl`
calls (not a re-run of the migration):
- Nominatim reverse check on `28.893758,-82.03573` returned `road=US 301`, `postcode=34785`
  — matches the written value exactly. 34785 is Wildwood, FL's official USPS zip.
- Census TIGER independently 404s — confirms the migration's fallback chain behavior
  (attempt 2 skipped, attempt 3 Nominatim used) rather than an unverifiable claim.
- Vacancy precedent: the 2026-07-24 session already confirmed via Sumter GIS ArcGIS
  parcels layer that `Physical_A = 'Unassigned Location RE'` for this PIN, corroborated
  against the parent parcel and 3 developed neighbors carrying real addresses — so this
  is genuinely vacant/unaddressed land, not an undetected scrape gap, and a forward
  address was correctly never fabricated for it. The reverse-geocode nearest-road label
  is the same technique already established as legitimate for vacant parcels by shard14
  (TD-5056, TD-5058, TD-5054).

Logged to `gold_standard_ultraloop_audit` (id=10158, county_slug=sumter, letter=I,
survived=true, ultraloop_mode=fallback — this environment's `/effort ultracode` menu
was not accessible from this non-interactive session, so audit fan-out/refute was done
via direct independent re-derivation rather than a native ultracode subagent tree).

## SQL VERIFICATION

Query:
```sql
SELECT public.pencil_dod_evaluate_county('sumter');
```

Before (start of this session, matches the dispatch brief):
```json
{"A":{"pass":true,"metric":4},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},
 "D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},
 "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":4.6},
 "I":{"pass":false,"detail":"card_complete=10 of 11","metric":90.9},
 "J":{"pass":true,"metric":100.0},"county":"sumter","auctions_total":11}
```

After (2026-07-25T17:43:36Z, re-queried live post-fix):
```json
{"A":{"pass":true,"metric":4},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},
 "D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},
 "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":1.2},
 "I":{"pass":true,"detail":"card_complete=11 of 11","metric":100.0},
 "J":{"pass":true,"metric":100.0},"county":"sumter","auctions_total":11}
```

**sumter: 10 of 10 letters PASS.** Certification is not self-declared here per canon —
`gold_standard_certify()` requires two consecutive 10/10 daily 07:30Z runs plus fresh
(<=7 day) survived audit rows for all 10 letters. This session did NOT run
`public.gold_standard_loop()` or `gold_standard_certify()` directly, per PARALLEL-FLEET
RULES (other shards were mid-flight concurrently this run — shard2/shard7/shard8 commits
same day). Per-county `pencil_dod_evaluate_county` was used instead, as instructed.

## No other work needed this session
All other 9 letters were already PASS at session start and untouched. No cross-shard
files or counties were touched.
