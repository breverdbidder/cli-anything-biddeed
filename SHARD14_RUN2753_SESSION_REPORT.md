# SHARD-14 Session Report — loop run 2753

dispatch_id: `84da506f-e01d-444f-8e53-2f9304c29599`
chat_session: `architect-20260703T160000`
shard counties: hendry, santa_rosa, alachua, liberty
ultraloop_mode: **native** (Workflow tool — 1 adversarial refuter + 3 parallel investigators; refuter verdict `survived=true`)

## Result summary

| County | Before (A B C D E F G H I J) | After | Change |
|---|---|---|---|
| liberty | 2/10 (H, J only) | **3/10** (E, H, J) | **E: 0.0%→100.0% (parcel_linked=1 of 1).** Real, exact, unique address match against `fl_parcels`. Shipped live. |
| hendry | 8/10 (C, D fail) | 8/10 (C, D fail) | No change. Re-confirmed live: C/D 5.3% is structural — only 1 of 19 hendry auctions has ever had an independent outcome record (`tax_deed_outcomes`=0 rows, `foreclosure_outcomes`=1 row). Already exhaustively investigated by SHARD-4 RUN2550 this morning; freshness re-check found nothing changed. |
| santa_rosa | 8/10 (C, D fail) | 8/10 (C, D fail) | No change, but root cause of the remaining gap is now precisely identified (see below) — not previously known. |
| alachua | 6/10 (C, D, E, I fail) | 6/10 (C, D, E, I fail) | No change. Re-confirmed the 6 remaining NULL-parcel_id rows have zero usable identifying data (no owner_name, no legal_description, placeholder address only) — genuinely blocked without court-document retrieval, not a DB-lookup problem. |

Only liberty crossed real ground this session. The other three counties were already exhaustively worked by other shards earlier today (SHARD-4 RUN2550, SHARD-6 RUN2484, SHARD-2 RUN2450) and this session's job on them was honest re-verification, not redundant re-attempts — all three are genuinely stuck on structural/data-availability blockers, not bugs or stale numbers.

## What shipped

1. **liberty E fix** (`supabase/migrations/20260703_shard14_liberty_e_parcel_link.sql`, commit `dc7cd372`): Liberty's single auction row (case `24-CA-22`, "20892 NE Burlington rd., Hosford, FL 32334") had no `parcel_id`/geo/value. Found an exact, unique street-address match in `fl_parcels`: `parcel_id='0261S6W00725000'`, `centroid_lat=30.3600103`, `centroid_lng=-84.8051394`, `av_sd=90150` (assessed_value), `jv=104221` (market_value). Applied live via PostgREST PATCH (psql pooler auth fails in this sandbox — same constraint prior shard sessions documented today). Independent refuter re-derived all 4 checks from scratch (uniqueness, co_no sanity, row-write confirmation, live RPC re-run) — verdict `SURVIVED`.

2. **Data-quality finding (flagged, not silently worked around):** `fl_parcels.co_no` does **not** use the FL-DOR-standard numbering that `fl_counties.co_no` uses. `fl_counties` says Liberty=39; the actual Liberty rows in `fl_parcels` (confirmed by Bristol/Hosford/Sumatra/Telogia city names — all exclusively Liberty County FL communities) live at `co_no=49`. This is an internal cross-table inconsistency in the schema, not a bug in this fix (the match was made empirically by city/address, not by trusting `fl_counties.co_no`), but it's a real risk for any future script that joins `fl_parcels` to `fl_counties` by `co_no` assuming DOR-standard numbering. Worth a dedicated audit across all 67 counties before anyone relies on that join.

3. **santa_rosa root-cause pinpointed (no fix possible yet, no fabrication attempted):** the 19 remaining unmatched/`mca_only` santa_rosa rows split into 5 synthetic seed rows (fake data, `SANTA-ROSA-FC/TD-2026-00X`, flagged for Ariel same as glades/madison) and 14 real tax-deed rows. Queried `public.realforeclose_aids` for those 14 by case_number and parcel_id with no date restriction at all: **zero hits**. Root cause: `realforeclose_aids` has 62 rows for santa_rosa and **all 62 are `auction_type='FORECLOSURE'`** — the AJAX harvest that already works for `santarosa.realforeclose.com` has never been run against `santarosa.realtaxdeed.com`. This is a missing-source-coverage gap, not a matching-logic gap or a "check a wider date range" problem as originally guessed by this morning's session. No DB writes made (no genuine match existed to apply).

## Verification evidence (live, pasted verbatim)

### SQL VERIFICATION
```sql
SELECT public.pencil_dod_evaluate_county('liberty');
```
Timestamp: 2026-07-03T16:xx:xxZ (captured twice, before and after the PATCH below)

**Before** (2026-07-03, session start):
```json
{"A":{"pass":false,"detail":"fc=1 td=0","metric":0},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":false,"detail":"matched_clean=0","metric":0.0},"D":{"pass":false,"detail":"matched_any=0","metric":0.0},"E":{"pass":false,"detail":"parcel_linked=0","metric":0.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":false,"detail":"density= far= pk1000=","metric":null},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":4.3},"I":{"pass":false,"detail":"card_complete=0 of 1","metric":0.0},"J":{"pass":true,"detail":"deal_complete=1 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"liberty","auctions_total":1}
```

**After** (same session, post-PATCH to `multi_county_auctions` id `c7b7a994-47ee-4491-942a-8deb06e7101a`):
```json
{"A":{"pass":false,"detail":"fc=1 td=0","metric":0},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":false,"detail":"matched_clean=0","metric":0.0},"D":{"pass":false,"detail":"matched_any=0","metric":0.0},"E":{"pass":true,"detail":"parcel_linked=1","metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":false,"detail":"density= far= pk1000=","metric":null},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":0.0},"I":{"pass":false,"detail":"card_complete=0 of 1","metric":0.0},"J":{"pass":true,"detail":"deal_complete=1 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"liberty","auctions_total":1}
```

Re-confirmed independently by refuter agent (cold DB query, did not reuse my numbers) — verdict `SURVIVED`.

hendry (unchanged, re-confirmed live):
```json
{"A":{"metric":2,"pass":true},"B":{"metric":100.0,"pass":true},"C":{"metric":5.3,"pass":false},"D":{"metric":5.3,"pass":false},"E":{"metric":100.0,"pass":true},"F":{"metric":100.0,"pass":true},"G":{"metric":100.0,"pass":true},"H":{"pass":true},"I":{"metric":100.0,"pass":true},"J":{"metric":100.0,"pass":true}}
```

santa_rosa (unchanged, re-confirmed live):
```json
{"A":{"metric":16,"pass":true},"B":{"metric":100.0,"pass":true},"C":{"metric":69.8,"pass":false},"D":{"metric":69.8,"pass":false},"E":{"metric":100.0,"pass":true},"F":{"metric":100.0,"pass":true},"G":{"metric":100.0,"pass":true},"H":{"pass":true},"I":{"metric":100.0,"pass":true},"J":{"metric":100.0,"pass":true}}
```

alachua (unchanged, re-confirmed live):
```json
{"A":{"metric":3,"pass":true},"B":{"metric":100.0,"pass":true},"C":{"metric":35.0,"pass":false},"D":{"metric":35.0,"pass":false},"E":{"metric":85.0,"pass":false},"F":{"metric":100.0,"pass":true},"G":{"metric":100.0,"pass":true},"H":{"pass":true},"I":{"metric":82.5,"pass":false},"J":{"metric":100.0,"pass":true}}
```

`gold_standard_loop()`/`gold_standard_certify()` were **not** run — confirmed via `git log`/migration-file timestamps that multiple other shard sessions are mid-flight today across dozens of counties (per PARALLEL-FLEET RULES, loop/certify only runs when no other session is mid-flight).

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Recon existing tooling | Fork from existing harness, not build from scratch | Explore agent found canonical `pencil_dod_evaluate_county`, `refresh_parity_tier1_outcomes`, `shard6_parcel_linkage.py` pattern, and confirmed all 4 counties already had same-day session reports | None |
| liberty E fix | Not explicitly planned (liberty had no obvious lever in the brief beyond "structural blocker") | Ran the existing `shard_liberty_clerk_scraper.py` (dry-run, confirmed no new auction data), then found and applied a genuine parcel match via `fl_parcels` | Positive deviation — found a real, previously-undocumented lever |
| hendry/santa_rosa/alachua C/D/E/I | Work per brief's playbooks | Found all three genuinely exhausted by concurrent same-day sessions; pivoted to honest freshness re-verification + one new root-cause finding (santa_rosa tax-deed AJAX gap) instead of redundant re-attempts | Deviation: did not force new "progress" on counties with no real lever available — reported the exhausted state plainly per Honesty Protocol |
| ULTRALOOP verify | Adversarial refuter per claimed letter move | Ran for the 1 substantive claim (liberty E); `survived=true`. Also ran 3 read-only investigation agents (no additional claims requiring refutation — none found a fix to apply) | None |

## Deferred / flagged for next session

- **liberty G/I**: needs real ordinance-sourced zoning data for unincorporated Liberty County (only a Bristol municipal jurisdiction exists; this property is in Hosford/unincorporated territory). Do not synthesize zone_standards values — HARD GUARDRAIL.
- **santa_rosa C/D**: needs the existing AJAX `realforeclose_aids` harvest mechanism run against `santarosa.realtaxdeed.com` (not `.realforeclose.com`, which is already fully harvested) — same code path, different subdomain, ~14 real tax-deed rows would land. Also: 5 synthetic seed rows (`SANTA-ROSA-FC/TD-2026-00X`) should be flagged to Ariel and purged, same pattern as glades/madison.
- **hendry C/D**: structural — needs genuine new independent outcome records to exist (18 of 19 hendry auctions have never closed with a verifiable outcome). No matcher/SQL fix will move this.
- **alachua E (6 remaining rows)**: needs court case-document retrieval (docket/complaint) to find owner name or legal description — no usable identifying data exists in `multi_county_auctions` today. Not a DB-lookup problem.
- **fl_parcels.co_no numbering discrepancy**: flagged as a standalone data-quality risk (fl_parcels co_no does not match fl_counties' DOR-standard co_no for at least Liberty: 49 vs 39). Recommend a fleet-wide audit before any future script trusts that join blindly.
