# GOLD STANDARD shard-2 (lake) — dispatch 63b26c86-ea13-4541-b62a-6ba6f8abc9df

mode: single-pass diagnose/fix/self-verify (no separate refuter agent this session — every claim
backed by pasted live query output in the session transcript, logged to
`gold_standard_ultraloop_audit` with `ultraloop_mode='fallback'`).

## VERIFICATION PROTOCOL — before/after (verbatim from pencil_dod_evaluate_county)

**Before (session start, VERIFIED):**
```json
{"A":{"pass":true,"detail":"fc=119 td=11","metric":11},"B":{"pass":true,"detail":"verified=8 closed_sold=8","metric":100.0},"C":{"pass":false,"detail":"matched_clean=116","metric":89.2},"D":{"pass":true,"detail":"matched_any=130","metric":100.0},"E":{"pass":false,"detail":"parcel_linked=120","metric":92.3},"F":{"pass":true,"detail":"tier1_sold=8 closed_sold=8","metric":100.0},"G":{"pass":false,"detail":"density=91.5 far=93.8 pk1000=50.0","metric":50.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":0.9},"I":{"pass":false,"detail":"card_complete=116 of 130","metric":89.2},"J":{"pass":false,"detail":"deal_complete=119 (triangle + two-arm CMA + ml_score + max_bid)","metric":91.5},"county":"lake","auctions_total":130}
```

**After (final, VERIFIED live):**
```json
{"A":{"pass":true,"detail":"fc=119 td=11","metric":11},"B":{"pass":true,"detail":"verified=8 closed_sold=8","metric":100.0},"C":{"pass":false,"detail":"matched_clean=117","metric":90.0},"D":{"pass":true,"detail":"matched_any=130","metric":100.0},"E":{"pass":false,"detail":"parcel_linked=120","metric":92.3},"F":{"pass":true,"detail":"tier1_sold=8 closed_sold=8","metric":100.0},"G":{"pass":false,"detail":"density=91.6 far=93.8 pk1000=50.0","metric":50.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":0.1},"I":{"pass":false,"detail":"card_complete=120 of 130","metric":92.3},"J":{"pass":false,"detail":"deal_complete=119 (triangle + two-arm CMA + ml_score + max_bid)","metric":91.5},"county":"lake","auctions_total":130}
```

No regressions on A, B, D, F, H (spot-checked full JSON before/after, byte-identical except H's
freshness clock, which is expected).

## C (89.2% -> 90.0%, still FAIL) — 1 real fix, 13-row structural ceiling reconfirmed

Live-ran `scripts/clerk_ssot/parsers/lake.py:parse_foreclosure()` against
`foreclosurecalendar.lakecountyclerkfl.gov` fresh this session (81 rows, 10 currently cancelled).
Cross-referenced against the DB's 14 `CLERK_SSOT_CANCELLED` case numbers. Found the calendar
carries **two entries** for case `2024CA000186` (old cancelled 8/18 sale + new rescheduled,
not-cancelled 12/8 sale) — the exact staleness bug the prior session (2026-08-13,
`scripts/lake_c_ssot_cancelled_reschedule_recheck_7bcb4434.py`) diagnosed and fixed, which had been
silently **re-broken** by a subsequent automated `run_parity.py` run (its `clean_matches` UPDATE
still has no reverse un-cancel path, confirmed still-present bug). PATCHed the row again:
`auction_status: CANCELLED->scheduled, auction_date: 2026-08-18->2026-12-08,
parity_status: CLERK_SSOT_CANCELLED->CLERK_VERIFIED, parity_source: ...->manual_recheck_20260816`.

Remaining 13 `CLERK_SSOT_CANCELLED` rows fresh-cross-checked against the same live calendar: 7
still show `cancelled=true` today, 6 have aged off the forward-looking list entirely with zero
reschedule evidence. **Genuine structural ceiling, unchanged from 3 prior sessions' finding.**
`run_parity.py`'s missing reverse-reconciliation path remains a real, documented, shared-pipeline
fix that is out of scope for a single-county row-level session (touches 9 counties' parity logic,
needs its own review — per guardrail 3, this is adjacent-but-different from a DB schema change and
was left alone).

## D (100%, unchanged PASS) — no action needed.

## E (92.3%, unchanged FAIL) — reconfirmed genuine ceiling

Re-ran `scripts/shard14_lake_e_ownername_match.py --dry-run` live against the current 10
parcel_id-null rows (6 more PropertyOnion-only rows excluded, correctly out of scope per guardrail
1). Result: 0/10 unique matches — 1 ambiguous (4 surname-position hits), 9 zero/no-surname-position
hits against Lake County PA's live ArcGIS FieldMap OwnerName field. All 10 rows carry only
`owner_name` (no property_address, no legal_description) from the Lake Clerk's calendar source —
same root cause 3 prior sessions identified (lake.realforeclose.com offline, clerk calendar
publishes no address/parcel). Conservative unique-match rule correctly declined every ambiguous
case rather than guess. **0 writes, genuine ceiling reconfirmed with fresh live data.**

## F (100%, unchanged PASS) — no action needed.

## G (50.0%, unchanged FAIL) — pk1000 sub-metric ceiling reconfirmed via 4 channels

Diagnosed the exact 2 pk1000-applicable parcels for lake (live-computed from
`parcel_zones` join `zoning_districts` against the applicability formula in
`20260718s_gold_standard_shard12_okeechobee_pk1000_regulated_override_column.sql`):
- Groveland "Town Core" (district id 13727) — already has a real `parking_per_1000sf=2.0`.
- Leesburg "C-1" (district id 13728) — `parking_per_1000sf=NULL`, the sole gap.

Attempted 4 independent channels to source Leesburg's real Sec. 25-358 parking ratio for C-1:
1. Firecrawl API scrape — **real API error, "Insufficient credits"** (not a source-access problem).
2. Direct curl of the Municode node URL — confirmed genuine JS SPA shell (`ng-app`, no
   server-rendered content), same finding as 3 prior sessions.
3. WebSearch (2 query variants) — surfaces only the node URL, zero numeric content in any snippet.
4. zoneomics.com mirror — dead 301 redirect this session, no usable content.

**Genuine, fresh-reconfirmed structural ceiling.** density improved 91.5->91.6 as a side effect of
the I fix below (Mount Dora R-2 and Mascotte MD-SFR both carry real density values), but pk1000
remains the binding LEAST() constraint at 50.0%, unchanged.

## H (PASS) — no action needed, freshness clock resets on every query.

## I (89.2% -> 92.3%, still FAIL) — 4-row real fix landed

Of the 14 card-incomplete rows, 10 share E's structural ceiling (no parcel_id at all). The other 4
had a real `parcel_id`/`property_address`/`latitude`/`longitude`/`assessed_value` but zero
`parcel_zones` linkage. Live point-in-polygon queries against Lake County's
`LocalGov/ParcelPublicAccess` municipal-boundary layer + `LocalGov/CityZoning` layer resolved all 4:

| case_number | parcel_id | city | GIS ZoningCode | resolution |
|---|---|---|---|---|
| 2023CA003042 | 291927005011000002 | Mount Dora | `R-2` | matched existing real `zoning_districts` id=7005 (real setbacks/height/coverage already in DB) |
| 2025CA002465 | 052225010000024800 | Groveland | `Planned Unit Develop` | matched existing real `zoning_districts` id=13003 |
| 2025CA002056 | 092226001100004500 | Minneola | `PUD-R` | no existing district; registered structural placeholder only (Municode-gated, no numeric standard fabricated — matches the established statewide-PUD convention already used 5x elsewhere in this dataset) |
| 2024CA001596 | 152224005000004800 | Mascotte | `Medium Density Single-family Residential` | no existing district; sourced **real** dimensional standards live from `cityofmascotte.com/DocumentCenter/View/1363/Land-Development-Regulation-Table` (fetched PDF, extracted via pdfplumber, MD-SFR row: density 4-8 DU/acre, min lot 6,825sf, setbacks 20/5/20ft, max coverage 40%, max impervious 50%, height 35ft, parking 1 space) |

All 4 linked via new `parcel_zones` rows (`source='lake_county_gis_cityzoning_20260816_live'`).
`card_complete` 116->120 (89.2%->92.3%). Still FAIL — the 10 no-parcel_id rows are the same ceiling
blocking E, genuinely un-fixable without new address/parcel data for those specific cases.

## J (91.5%, unchanged FAIL) — reconfirmed genuine ceiling, one real lead declined on honesty grounds

11 `deal_complete` gap rows. 10 share E's structural ceiling exactly (bid_decisions rows correctly
carry `arv=null` per the prior `lake_j_ghost_purge_full_regen` session — no real parcel/comp data
exists to compute from). The 11th, case `2025CA001392`, has a real `assessed_value=113395` and
`parcel_id`; live ArcGIS lookup surfaced one additional real data point — `LastSalePrice=$164,000`
(2021-11-24, the subject parcel's own prior sale). Considered writing `arv`/`factors.cma_*` from
this, but **declined**: a single-value pass-through (subject-parcel assessed value or subject-parcel
prior sale, not multiple *comparable* properties) is exactly the fabrication class already caught
and reverted in this county (`GOLD_STANDARD_SHARD7_MANATEE_MADISON_LAKE_DISPATCH_BC399D3B_
CONTINUATION_SESSION_REPORT.md` — "asserting a real CMA was performed when none was"). Reusing the
`columbia_j_generator.py` Shapira-formula approach (as the dispatch brief suggested) would produce
the same flat-default fabrication for the other 10 no-data rows and a weak single-point pass-off for
this one — not applied. **0 writes on J this session; genuine structural ceiling.**

## Files created (committed this session)

None — every fix this session was a row-level PATCH/POST through PostgREST against existing tables
(`multi_county_auctions`, `zoning_districts`, `zone_standards`, `parcel_zones`), per guardrail 3
(row-level UPDATEs don't need a migration file). No shared pipeline script or schema was modified.

## Adversarial verification

Self-verified (no separate refuter agent dispatched this session) — every claim above is backed by
live query output pasted in the session transcript (ArcGIS responses, clerk-calendar parse output,
PDF-extraction text, before/after `pencil_dod_evaluate_county` JSON). 5 rows logged to
`gold_standard_ultraloop_audit` (`ultraloop_mode='fallback'`, ids 15968-15972), one per failing
letter, `survived=true` for all (i.e., the claimed diagnosis/fix/non-fix held under review of its
own evidence).

## Residual gaps / next-session priorities

1. **Lake C:** 13 genuinely-cancelled/aged-off rows remain a structural ceiling. The real,
   documented fix (`run_parity.py`'s `clean_matches` UPDATE needs a reverse un-cancel path gated on
   the SSOT parser's live `cancelled` flag, not a blanket `IS DISTINCT FROM 'CLERK_SSOT_CANCELLED'`
   guard) is a 9-county shared-pipeline change, correctly out of scope for a single-county session —
   needs its own dedicated review.
2. **Lake E/J:** 10 rows have only `owner_name`, zero address/parcel signal, and 0/10 unique
   ArcGIS owner-name matches. No further lever exists without a JS-capable browser-automation scrape
   of `officialrecords.lakecountyclerk.org` / `courtrecords.lakecountyclerk.org/showcaseweb/`
   (both disclaimer/login-gated, confirmed live this session, same as 2 prior sessions).
3. **Lake G:** Leesburg C-1's `parking_per_1000sf` remains the sole pk1000 gap. Firecrawl is
   currently out of credits (real, fixable-next-session blocker — once credits are restored, a
   JS-rendering fetch of the Municode Sec. 25-358 page is the most promising untried lever, since
   curl/WebSearch/zoneomics have now been exhausted 2-3x each with the same negative result).
4. **Lake J:** the one row with real comp data (`2025CA001392`) needs a genuine *second* comparable
   property (not the subject parcel's own assessed value or prior sale) before a two-arm CMA can be
   honestly written — worth a targeted MLS/Zillow/Redfin comp search in a future session focused
   specifically on this one case.

## Scope note

Lake only, per shard-2 assignment. No cron jobs, `gold_standard_loop()`/`gold_standard_certify()`,
or other counties' rows touched. `exec_sql` RPC (retired) and direct psql (known-broken) were not
attempted — all writes went through PostgREST table GET/PATCH/POST.
