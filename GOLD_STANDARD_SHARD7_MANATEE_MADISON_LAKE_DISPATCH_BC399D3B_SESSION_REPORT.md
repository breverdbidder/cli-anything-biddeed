# Gold Standard Shard-7: manatee, madison, lake — session report

dispatch_id: bc399d3b-f50e-406a-a0f1-66d8f4f5d9d7
chat_session: architect-20260719T160000
loop run: 5153
date: 2026-07-19

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Manatee G | Backfill parking_per_1000sf for 5 districts | 3 of 5 backfilled with real, cited LDC values (GC, NC-M, NC-S). HM/LM left null — genuinely no single per-district ratio exists in the ordinance (two-tier office/non-office formula) | Partial by design, not a shortfall — HM/LM cannot be honestly reduced to one number without an unstated assumption |
| Lake E | Real parcel linkage for unlinked auctions | 6 of 35 remaining unlinked rows matched via live ArcGIS owner-name matching | Smaller than hoped — real ceiling, most remaining rows are ambiguous/no-match |
| Lake G/I | Zoning substrate diagnosis + fix if feasible | Diagnosed real ArcGIS zoning endpoint exists; attempted fix was REFUTED and reverted (see below) | Attempted fix failed adversarial verify; reverted, not shipped |
| Lake C/D | Parity root-cause diagnosis | Diagnosed: prior ceiling analysis is STALE — new reachable clerk portal + po_mca_matches grew from 18→686 rows. No fix attempted (diagnosis-only per scope) | New lead found, real fix deferred to next session |
| Lake J | Diagnose + fix | Fixed for real: 14/14 case_numbers now have honest bid_decisions rows (5 using real assessed_value, 9 using the documented 165000 default only where genuinely null). First-pass fix was REFUTED (fabricated placeholder data contradicting real assessed_value); reverted and regenerated honestly | Two-pass: caught by adversarial verify, corrected before shipping |
| Madison A/B/F | Re-verify accrual-blocked state live | Confirmed live: both madisonclerk.com pages still show zero listings. No action needed, no fabrication | Matches plan exactly |
| Lake fabrication (unplanned) | — | Found LAKE-FC-2026-001/002/003 had resurfaced (2nd recurrence) despite a false "fixed" claim from 2026-07-10. Purged, script hard-quarantined, workflow deleted, logged to honesty_violations | Not in original plan — highest-priority unplanned finding, addressed first |

## Verification Evidence — pasted before/after (SQL VERIFICATION)

### Manatee — BEFORE (session start)
```json
{"A":{"pass":true,"metric":3},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":96.4},"D":{"pass":true,"metric":96.4},"E":{"pass":true,"metric":96.4},"F":{"pass":true,"metric":100.0},"G":{"pass":false,"metric":0,"detail":"density=96.3 far=100.0 pk1000=0.0"},"H":{"pass":true,"metric":5.8},"I":{"pass":true,"metric":96.4},"J":{"pass":true,"metric":100.0},"auctions_total":84}
```
### Manatee — AFTER (verified live, 2026-07-19 ~21:50 UTC)
```json
{"A":{"pass":true,"metric":3},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":96.4},"D":{"pass":true,"metric":96.4},"E":{"pass":true,"metric":96.4},"F":{"pass":true,"metric":100.0},"G":{"pass":false,"metric":64.7,"detail":"density=96.3 far=100.0 pk1000=64.7"},"H":{"pass":true,"metric":6.3},"I":{"pass":true,"metric":96.4},"J":{"pass":true,"metric":100.0},"auctions_total":84}
```
Manatee: **9/10 → 9/10** (G moved 0%→64.7%, still fails the 95% bar; still needs a real HM/LM ratio or ordinance amendment before it can pass — see residual).

### Lake — BEFORE (session start)
```json
{"A":{"pass":true,"metric":11,"detail":"fc=100 td=11"},"B":{"pass":false},"C":{"pass":false,"metric":11.7},"D":{"pass":false,"metric":24.3},"E":{"pass":false,"metric":65.8},"F":{"pass":false},"G":{"pass":false,"metric":73.8},"H":{"pass":true,"metric":1.1},"I":{"pass":false,"metric":35.1},"J":{"pass":false,"metric":84.7},"auctions_total":111}
```
(auctions_total=111 included 3 fabricated LAKE-FC-2026-00X rows, purged this session — see honesty section)

### Lake — AFTER (verified live, 2026-07-19 ~21:47 UTC, post-revert-and-honest-fix)
```json
{"A":{"pass":true,"metric":11,"detail":"fc=97 td=11"},"B":{"pass":false},"C":{"pass":false,"metric":12,"detail":"matched_clean=13"},"D":{"pass":false,"metric":25,"detail":"matched_any=27"},"E":{"pass":false,"metric":73.1,"detail":"parcel_linked=79"},"F":{"pass":false},"G":{"pass":false,"metric":73.8,"detail":"density=73.8 far=100.0 pk1000="},"H":{"pass":true,"metric":0.2},"I":{"pass":false,"metric":36.1,"detail":"card_complete=39 of 108"},"J":{"pass":true,"metric":100,"detail":"deal_complete=108 (triangle + two-arm CMA + ml_score + max_bid)"},"auctions_total":108}
```
Lake: **2/10 → 3/10** (A, H, **J new**). E genuinely improved (65.8%→73.1%, still fails). G/I unchanged (fix attempt reverted, see below — do not re-count as progress).

### Madison — BEFORE and AFTER (unchanged, re-verified live)
```json
{"A":{"pass":false,"metric":0},"B":{"pass":false},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":15.4},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"auctions_total":5}
```
Madison: **7/10 → 7/10**, no change. A/B/F confirmed live (WebFetch, not cached) still genuinely blocked — madisonclerk.com's tax-deed-sales and lands-available pages both explicitly state zero properties as of today. No fabrication, no action taken.

## Critical finding #1 — lake FC fabrication, 2nd recurrence (fixed)

`LAKE-FC-2026-001/002/003` (synthetic rows, addresses like "123 MAIN ST LEESBURG FL") were present live at session start (created 2026-07-11, last touched today). A 2026-07-10 note in `pipeline.counties` claimed the source script was neutered and its cron removed — **that claim was false**; only one commit ever touched those files (the one that created them), and the daily GHA workflow (`shard5-lake-fc-scraper.yml`, cron `30 6 * * *`) was still live and re-upserting them every morning.

Action taken: deleted the 3 rows from `multi_county_auctions`, replaced the script with a hard `sys.exit(1)` quarantine stub, **deleted** the workflow file (not just disabled), logged the false claim to `honesty_violations` (severity CRITICAL, id `f9833e77-95bb-4b16-9859-8d8a7e1b75a7`), and corrected `pipeline.counties.notes`. Confirmed lake A does not depend on this script — 97 real foreclosure rows from `lake_clerk_foreclosure_calendar_v1` already satisfy it. Shipped in commit `61013236` before any other work began.

## Critical finding #2 — two fixes failed adversarial verify and were reverted before shipping

Per this campaign's own ULTRALOOP rule ("refuted = false positive: log it, do not count it, do not certify on it"), an independent verifier agent refuted two of this session's fix claims:

1. **Lake J first pass (REFUTED, fabrication_smell=true).** The generator run wrote 13 of 14 rows with byte-identical placeholder values (`arv=165000.00`, `max_bid=85500.00`, `ml_score=0.55`, identical `factors`), directly contradicting real `assessed_value` already present in `multi_county_auctions` for 5 of those cases (e.g. case `2024CA001282` has `assessed_value=120367` but was written with `arv=165000`). The checked-in generator script's own `compute_arv()` logic is correct (assessed_value-first, verified by reading the code) — whatever produced the fabricated rows did not honor it. **Action:** deleted the 14 fabricated rows, regenerated them by hand using real `assessed_value` where present (5 of 14) and the documented 165000 default only where genuinely null (9 of 14), tagged with an honest `arv_source` column (`assessed_value_real` vs `county_default_no_assessed_value_165k`). Re-verified live: J now 100% (108/108), no placeholder-vs-real contradiction remains in this session's rows.

2. **Lake G/I fix (REFUTED, fabrication_smell=true).** 17 `parcel_zones` rows were written from a live Lake City-Zoning ArcGIS layer, but all 17 joined to `zoning_districts` rows that are actually municode table-of-contents headers (e.g. `code='CH125ZO' name='ZONING'`) for Fruitland Park/Leesburg, with zero real `zone_standards` behind them — the substrate for those jurisdictions is unusable. Net effect was to turn G's pk1000 metric from undefined (0 applicable parcels) into a hard 0%, i.e. it made the live metric look worse while contributing nothing real. **Action:** deleted all 17 rows, confirmed G/I back to the pre-session baseline (G=73.8, I=36.1 — matches "before").

**Not refuted, kept as real progress:** manatee G ordinance backfill (verified against the actual 48-page LDC PDF, HM/LM correctly left null) and lake E owner-name matches (independently re-confirmed against the live ArcGIS FieldMap service for 3 of 6 matches, values matched exactly).

## Critical finding #3 — pre-existing lake `bid_decisions` data-quality issue (NOT fixed this session, flagged for next session)

While investigating the J refutation, found this is a larger, **pre-existing** (not introduced this session) issue: of 121 `bid_decisions` rows tied to lake case_numbers, **42 (35%) share the flat `arv=165000.00` default** despite many having real, different `assessed_value` in the source table, and **13 rows are outright duplicates** (121 rows for 108 distinct case_numbers — `bid_decisions` has no unique constraint on `case_number`). J structurally passes regardless (the evaluator only checks non-null-ness, not correctness), but this means lake's J "pass" rests partly on undifferentiated placeholder data that predates this session. Recommend: next session (a) add a unique constraint or reconcile the 13 duplicate rows, (b) re-derive ARV from real assessed_value for the ~37 pre-existing 165k-default rows where assessed_value actually exists.

## Residuals / next-session priorities

1. **Manatee G (64.7% → need 95%):** HM and LM districts have no single derivable parking ratio in the LDC (two-tier office/non-office formula, page 35 of the LDC PDF). Closing this needs either a policy decision on how to represent per-district ratios that are legitimately use-split, or accepting these 2 districts as permanently N/A (would need `pk1000_regulated=false` set on defensible ordinance grounds, not to dodge the metric).
2. **Lake E (73.1% → need 95%):** 29 rows remain unlinked, all foreclosure-lane clerk-calendar rows with owner name but no address; owner-name matching is genuinely difficult for common surnames/LLCs/estates. Likely near a real ceiling for current methods.
3. **Lake G/I:** real fix requires ordinance-backed `zoning_districts`/`zone_standards` for Lake's municipalities (Fruitland Park, Leesburg, Clermont, etc.) — the zoning GIS layer exists and works (`gis.lakecountyfl.gov/lakegis/rest/services/LocalGov/CityZoning/MapServer`), but there is no real standards substrate to join into yet. This is genuine ordinance-research work, not a data-linking task.
4. **Lake C/D:** new, real, untested lead — `officialrecords.lakecountyclerk.org` and `courtrecords.lakecountyclerk.org/showcaseweb/` are live, public, no-login, and expose a Case Number search tab (unlike the previously-tested dead `or.lakecountyclerk.org`). `po_mca_matches` for lake grew from 18→686 rows since the prior diagnosis via an address-based pass — but the actual `matched_clean`/`matched_any` parity-status distribution behind that growth was not re-derived this session (out of scope for a diagnosis-only task). Next session: re-derive real parity-status numbers before assuming C/D moved, then pursue the new clerk portal per the standing C/D litmus authorization.
5. **Lake bid_decisions cleanup** (see finding #3 above).
6. **Madison A/B/F:** genuinely accrual-blocked, re-verify next time the county might plausibly schedule a sale.

## Commits shipped to main
- `61013236` — lake FC fabrication purge (2nd recurrence) + honesty violation logged
- `1d98e04a` — manatee G real LDC parking backfill (GC/NC-M/NC-S)
- `0b8bd411` — lake J generator scoping fix (idempotency, prevents future duplicate rows)
- Live DB corrections (no migration file, data-only): lake bid_decisions honest regeneration (14 rows), lake parcel_zones revert (17 rows deleted)
