# Gold Standard shard-5 — walton, lee — dispatch 8b9aa985 (2026-08-29 08:00Z wave)

mode: ultracode (1 Workflow, 8 agents, fix+adversarial-verify; plus 1 follow-on single agent for lee-I round 2, plus self-directed close-out work)

## Scoreboard: before → after (live `pencil_dod_evaluate_county`, re-verified fresh at every step; official confirmation via `gold_standard_loop()` run 15252)

```
walton: 9/10 -> 10/10  CERTIFIED (consecutive_gold=4)
  I: FAIL 94.8% (147/155) -> PASS 95.5% (148/155)
  all other letters unchanged, no regressions

lee:    5/10 -> 9/10   NOT certified (I is the sole remaining gap)
  C: FAIL 76.1% (341/448) -> PASS 95.5% (428/448)
  D: FAIL 76.1% (341/448) -> PASS 95.5% (428/448)
  I: FAIL 72.1% (323/448) -> FAIL 90.0% (403/448)  [large gain, gate not reached]
  J: FAIL 76.1% (341/448) -> PASS 100.0% (448/448)
  G: PASS 96.3% -> PASS 97.0% (improved as a side effect, never regressed)
  E: PASS 96.9% -> PASS 97.5% (improved as a side effect)
  A/B/F/H: unchanged PASS
```

## Root causes (both counties diagnosed live before any fix)

**walton I**: 8 gap rows out of 155. 1 (`25CA000534`) had complete address/geo/value/parcel_id but was never linked in `parcel_zones`. The other 7 are genuine structural residuals (multi-parcel cases, a timeshare unit, vacant land with no situs address, cases blocked by 403s on every known source) already exhaustively documented by prior sessions.

**lee C/D/I/J**: all four failures traced to the *same* 107 rows — a fresh batch scraped 2026-08-27 21:07 through 2026-08-29 04:20 (auctions_total grew 330→448 since lee last hit 10/10 on 2026-08-25) that had never been through the parity-matching, card-enrichment, or J-generation pipeline stages. Zero of the 107 case_numbers existed in `bid_decisions` at all before this session.

## What shipped (commits, all live on `main`)

```
b311d58e Gold Standard lee C/D fix: AJAX-calendar harvest for 107 unmatched new-batch rows
307155c2 Gold Standard lee I stage 2a: ArcGIS geo/value backfill (51 rows)
905acb72 Gold Standard lee I stage 2b: zoning-linkage backfill via ArcGIS crosscheck (58 rows)
a5505a46 Gold Standard lee J: fix ghost-fill anti-pattern in newly-generated bid_decisions
99e5a55a Gold Standard lee I round2: 20-row card-completeness backfill via ArcGIS address lookup
```
Plus one direct data fix (no script, 12-row PATCH, see "J self-correction" below) and one direct `parcel_zones` INSERT for walton (id 873533, no migration needed — insert only, no schema change).

## walton I — real fix, no fabrication

`25CA000534` had address/geo/value/parcel_id already populated; it failed I solely because `parcel_zones` had zero rows for parcel `09-3N-19-19700-00N-0660`. Queried Walton's EnerGov ArcGIS FeatureServer (Layers 4 and 19) live: confirmed real parcel (owner OLIVER SHANA N, appraised $94,951, centroid matches DB lat/lng), `ZONE_CLASS='Urban Residential'`. Checked `zoning_districts` for jurisdiction 1333 ("Unincorporated Walton County") — a genuine, already-existing ordinance-backed row was found (id 11996, `ordinance_section='2018-29'`, created in a *prior* session). Only the missing linkage was inserted; no new `zoning_districts` row was fabricated. Walton is now 10/10, confirmed **CERTIFIED** on the official scoreboard (`gold_standard_certifications.certified=true`, `consecutive_gold=4`).

The other 7 gap rows remain unresolved after a fresh independent re-check this session (not just trusted from a prior session's docstring): 2026-0125TD (vacant land, no situs address in any source), 25CA000531A (timeshare, no individually-geocoded parcel), 26CA000062/25CA000044 (multi-parcel judgments, no single canonical parcel), 19CA000472/25CA000142/26CA000030 (case-number-only rows, every known Walton source returns 403 or has no queryable API for these case numbers).

## lee C/D — real fix via proven AJAX-calendar harvest pattern

Forked the proven lee-specific AJAX-calendar exact-match harvester (`scripts/gold_standard_shard10_lee_cd_e_i_ajax_harvest_run3679.py` precedent) against the live RealForeclose/RealTaxDeed calendars for the 5 real auction-date buckets the 107 rows fell into. 87 of 107 rows promoted to `parity_status='matched_clean'` with `parity_source` genuinely prefixed `tier1:` — zero PropertyOnion contamination (independently confirmed by 2 refuter agents). 20 case_numbers were not found on the live calendar pull (real source gap, documented, not forced).

## lee I — two rounds, genuine 72.1%→90.0% gain, structural residual honestly documented

**Round 1** (ArcGIS geo/value + zoning-linkage backfill): 51 rows got real lat/lng/assessed_value from the live Lee County Property Appraiser ArcGIS FeatureServer; 58 rows linked into `parcel_zones` with real ArcGIS-sourced zone codes cross-checked against existing `zoning_districts`. One batch (Bonita Springs `MH-1`, jurisdiction 914) caused a G dip 96.8→96.2 — the district has zero `zone_standards` rows — reverted immediately via DELETE, G confirmed restored. I: 72.1%→85.5%.

**Round 2** (STRAP-transform reverse-engineering): discovered the naive "strip `-`/`.`" transform used in round 1 only works for parcel_id formats whose block segment is already alphanumeric (e.g. `C3`, `L3`, `B2`); Lehigh Acres-style purely-numeric-block parcels (`02`, `03`, `06`...) have **no deterministic numeric→letter mapping** on the live ArcGIS layer (proved via a wildcard STRAP scan — same numeric block maps to different letters on different parcels). Switched to exact address-match lookup (`SITENUMBER`+`SITESTREET`) for this subset: 17 more zoning-links + 3 parcel_id/geo backfills. I: 85.5%→90.0%. G improved to 97.0% (never regressed).

**Honest residual (45 rows, all genuine, none fabricated):** 14 condo/PUD common-element STRAPs with zero ArcGIS ZONING attribute even at the parent parcel; 3 Sanibel T2/T3/T4 STRAPs with empty ZONING; 2 Bonita Springs MH-1 rows (confirmed dead end, zero zone_standards); 1 Cape Coral `R1-D` row with no existing `zoning_districts` row (declined to fabricate one); 11 rows with no parcel_id and no address at all; remainder are address-format mismatches (mobile-home lot numbers) that don't resolve against ArcGIS SITENUMBER/SITESTREET.

## lee J — shipped PASS, with a self-caught-and-corrected incident

`shard9_j_generator.py --county lee` (shared, unedited) generated 118 new `bid_decisions` rows. As anticipated from the walton precedent, 61 rows collapsed to two templated tuples from the generator's `arv = max(mkt, config['arv']*0.4)` $124K floor. A county-scoped ghostfix script (forked from `gs_8da482b6_walton_j_ghostfix.py`) patched all 61 using real per-row market/assessed value.

**Incident, caught by adversarial verify:** 2 of 4 independent refuter agents in the workflow's verify phase found the ghostfix's "0 unresolved" claim was false — a live re-query turned up 12 rows still carrying the fabricated tuple. I independently re-verified this myself post-workflow and found the root cause: `shard9_j_generator.py` is **not** scoped to the new batch — it generates J for *any* lee case_number lacking a `bid_decisions` row, including old (2026-07-01) PropertyOnion-sourced rows (`data_source='propertyonion', tier1_authoritative=false`) that are outside both the new-batch scope and the J evaluator's own denominator (excluded fleet-wide by canon). The ghostfix script's own `mca_by_case` filter (`created_at >= 2026-08-27`) correctly excluded them from its target set — which is exactly why they were left with the fabricated tuple. Since these 12 rows don't affect the certified J metric at all, this wasn't a scoring bug, but leaving fabricated $124,000 ARVs live in production tied to real case numbers is a genuine data-hygiene violation of the "no fabricated data" mandate, so I patched all 12 directly with real `po_market_value`-derived figures. Re-verified live: zero remaining degenerate-tuple rows in the `created_at >= 2026-08-27` window. J stayed 100% PASS throughout (field-presence check, unaffected either way).

**Fleet-wide flag for a future session (not fixed here, out of scope — touches the shared generator used by 7 counties):** `shard9_j_generator.py` has no `data_source != 'propertyonion'` guard, so running it against any county with un-generated PropertyOnion rows will keep producing fabricated-ARV `bid_decisions` for out-of-canon data. A broader query (unscoped by date) found ~1000+ historical rows fleet-wide sharing the same degenerate tuples — pre-existing, not introduced this session, left untouched per scope discipline (K3 surgical changes), but worth a dedicated future session.

## ULTRALOOP audit trail

5 rows logged to `gold_standard_ultraloop_audit` (dispatch `8b9aa985-9e53-41af-824f-461d87f1a951`): walton/I, lee/C, lee/D, lee/J (documents both the refutation and the same-session self-correction), lee/I (round 1+2 combined, self-verified since it's a FAIL→FAIL improvement claim, not a certify-gate-relevant PASS). All `survived=true` after the false initial J claim was caught and fixed.

Workflow run: `wf_efe5a4f0-3ec` (8 agents, 803K tokens, 337 tool calls, fix phase + adversarial verify phase). Follow-on single agent for lee-I round 2 (agent `a0207d7daa42a37d7`, 137K tokens, 53 tool calls).

## Verification protocol compliance

- `SET statement_timeout=0` not applicable (all writes via PostgREST, not raw psql — psql/direct DB password auth confirmed broken again this session, PostgREST used throughout per the documented working pattern).
- `git pull --rebase` run before push; clean rebase, pushed to `main` (`8511798f`).
- No other `cc-runner-ghonly.yml` shard session was in-flight at close-out (`gh run list --status=in_progress` showed only this session's own run) — `gold_standard_loop()` (run 15252, 670 rows/67 counties, 96s) and `gold_standard_certify()` run per the parallel-fleet rule, confirming walton **CERTIFIED** on the official scoreboard.
- `gold_standard_campaign` row (id 5293) updated: `criteria_passed` = walton all-true, lee all-true-except-I, `exit_reason='timeout'`, `session_end_at` set.
- Certification notification fired via `public.fire_workflow_dispatch(...)` per standing COMMS authorization.

## Guardrail compliance

- No fabricated zoning standard, market value, case outcome, or parity classification anywhere this session.
- No PropertyOnion data ingested as a source anywhere; the 12 PropertyOnion-sourced `bid_decisions` rows cleaned up were a hygiene fix (real po_market_value used), not new PropertyOnion ingestion.
- `shard9_j_generator.py` (shared across 7 counties) read but not edited — both the walton (prior session) and lee (this session) ARV-floor fixes are county-scoped one-off scripts.
- `pencil_dod_evaluate_county` was not modified.
- Cron jobs 109/111/115 and the gold-standard-loop-* scoring jobs were not touched.

## Next session priorities

1. **lee I** (90.0%, needs 95%, 45-row residual): the tractable remainder is thin — condo/PUD common-element STRAPs and Sanibel T2/T3/T4 parcels return no ZONING attribute from ArcGIS at all (2 independent lookup rounds confirmed this is a real source gap, not a transform bug). Would need either an authenticated Lee Property Appraiser session or a different data source (e.g. condo master-association zoning records) to close fully.
2. **Fleet-wide `shard9_j_generator.py` guard**: add a `data_source != 'propertyonion' OR tier1_authoritative=true` filter so it stops generating fabricated-ARV `bid_decisions` rows for out-of-canon PropertyOnion case numbers across all 7 counties it serves. Pre-existing issue, not introduced this session, ~1000+ historical rows fleet-wide affected.
3. **walton residual 7 rows** (26CA000062, 25CA000044, 19CA000472, 25CA000142, 26CA000030, 25CA000531A, 2026-0125TD): does not block certification (walton is already 10/10 CERTIFIED), but remains a genuine documented gap if a future session finds a new lever (e.g. an authenticated RealForeclose/civitek session).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
