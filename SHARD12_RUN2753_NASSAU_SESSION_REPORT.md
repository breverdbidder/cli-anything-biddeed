# SHARD-12 run2753 Session Report — nassau, levy, gulf, franklin

dispatch_id: `a50b350f-3b98-4150-9a19-36775fb6ecbd`
chat_session: `architect-20260704T000000`
Method: ULTRALOOP protocol — one Workflow (`wf_d4b782ff-f35`) running an independent adversarial refuter against a suspected nassau B/F fabrication, then fanning 4 per-county forensics agents + 4 independent adversarial refuters across the shard's failing letters. 13 `gold_standard_ultraloop_audit` rows logged under the dispatch_id above.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Nassau C (82.4%→95%) | Diagnose + fix | Diagnosed 6 matched_divergent rows (stale auction_status/date vs PropertyOnion); a proposed 5-row relabel to matched_clean was independently **REFUTED** (PO corroboration is an unaudited JSON blob, no live verification columns) and NOT applied. Genuinely blocked pending an authenticated RealForeclose rescrape (confirmed: anonymous WebFetch → HTTP 403). | No fix shipped — correctly withheld |
| Nassau B/F | Not flagged as failing (brief reported both 100% PASS) | ULTRALOOP found both PASSes rested on a fabricated flat `sold_amount=150000` placeholder on 27/34 rows — self-documented in `migrations/20260625_shard4_run581_gold_standard.sql` as an arbitrary default. Reverted live. | Unplanned but mandatory per Honesty Protocol — the most important finding of the session |
| Nassau parity_source incident | N/A | The first revert patch also overwrote `parity_source`, which the live evaluator requires to start with `tier1%` for C/D — this silently broke C (82.4%→20.6%) and D (100%→20.6%) as an unintended side effect. Caught immediately by re-running the evaluator, corrected live in the same session. | Self-inflicted regression, self-caught, self-corrected within minutes — disclosed in full below |
| Levy C/D (0%→95%) | Diagnose + fix | Confirmed genuinely blocked: PropertyOnion has zero Levy County coverage, and `taxsmart_levyclerk_com` is our only/primary source (not a second independent leg). No relabeling proposed. | None — honest BLOCKED verdict |
| Gulf C/D (43.8%→95%) | Diagnose + fix | Confirmed genuinely blocked: 6 of 9 non-matched rows are `shard5_bootstrap` synthetic placeholders (identical lat/long, identical assessed_value across "different" parcels); 3 are unresolved "Address On File" rows. No relabeling proposed. | None — honest BLOCKED verdict |
| Gulf I (93.8%→95%) | Diagnose + fix | Found the exact failing row: `parcel_id='Property Appraiser'` (a literal UI-scrape artifact) on case `232024CC000157CCAXMX`. An already-committed migration (`supabase/migrations/20260702_shard4_gulf_property_appraiser_cleanup.sql`) already contained the correct, previously-vetted fix — but it had never been executed against the live DB. Executed it live. | Fixed — real gain, zero new fabrication (reused an already-reviewed convention) |
| Franklin B/C/D/E/F/I (all failing) | Diagnose + fix | B/C/D/F confirmed structurally blocked and honest: 7/9 auctions are `scheduled` for dates after today (2026-07-04), 1 `redeemed`, 1 `cancelled` — zero auctions have actually resulted in a sale to verify. E/I have one real fixable gap each (1 missing parcel_id; all 9 missing geo/value) but require a working Franklin GIS/appraiser endpoint not reachable this session (qpublic → HTTP 403, no confirmed FL GIO ArcGIS URL). No values fabricated. | None — honest BLOCKED/UNKNOWN verdict |

## Deviation log

**The single largest finding: nassau's B and F were not actually passing.** The brief reported nassau 9/10 with B=100%/F=100%. Live investigation found 27 of 34 `multi_county_auctions` rows carried an identical `sold_amount=150000` — including 6 rows dated *after* today (auctions that have not yet occurred) and 8 `cancelled` rows (no sale occurred). The source is self-documented in `migrations/20260625_shard4_run581_gold_standard.sql`: `-- nassau: use opening_bid or default 150000 (no amount data at all)`. The same constant was propagated into 5 `tax_deed_outcomes` and 22 `foreclosure_outcomes` rows under data_source labels that sound authoritative (`nassau_realtaxdeed_official`, `nassau_realforeclose_official`, `nassau_mca_official`) but all share the identical `winning_bid=150000.0`. An independent adversarial refuter, given only the claim (not my analysis), ran its own live queries and returned **SURVIVES** — same anti-pattern class as the santa_rosa (`203b7fe0`) and pasco (`d92b5a33`) B/F reverts earlier in this campaign. Reverted live: `scripts/shard12_run2753_nassau_bf_fabrication_revert.py`.

**Self-inflicted regression, disclosed in full:** the first version of the revert patch also set `parity_source` to a new non-`tier1`-prefixed tag on the same 27 rows. The live `pencil_dod_evaluate_county` function (read via the Supabase Management API's `pg_get_functiondef` — the copy in `supabase/migrations/20260702_shard3_pencil_dod_f_scope_fix.sql` was stale relative to production) requires `parity_status='matched_clean' AND parity_source LIKE 'tier1%'` for C, and the matched_divergent equivalent for D. Overwriting `parity_source` dropped nassau C from 82.4%→20.6% and D from 100%→20.6% as an unrelated side effect — a clobber of the exact kind commit `25fafcd5` ("guard run_cd_parity() against clobbering tier1_ parity labels") had already flagged as a known gotcha in this codebase. Caught by re-running the evaluator immediately after the patch (three consecutive stable reads all showed the drop, ruling out a transient read). Corrected live by restoring a `tier1`-prefixed `parity_source` tag on the 27 rows. **Full honesty on a limitation:** the exact original per-row `parity_source` values (`tier1_official_platform_open_auction_parcel` / `tier1_official_platform_parcel` / `tier1_foreclosure_outcome` / `tier1_matched_clean_bootstrap`) could not be recovered row-by-row — no audit history was captured before the overwrite. A single disclosed placeholder tag, `tier1_bf_fabrication_revert_shard12_20260704_original_source_not_recoverable`, was used instead of guessing a specific historical method name. C/D were verified restored to their exact pre-incident values (82.4% / 100.0%) after the correction — see before/after below.

Gulf I's fix was **not** new work: a prior session (`SHARD4_RUN2346_SESSION_REPORT.md`, `supabase/migrations/20260702_shard4_gulf_property_appraiser_cleanup.sql`) had already root-caused this exact row and written the correct SQL, but per the SHIP GATE mandate ("Execute, not just commit... files-only commits = WIP, never SHIPPED") it was never actually run against the live database. This session executed it — no new fabrication risk, since the fix reuses an already-independently-reviewed synthetic-ID convention already accepted for two sibling cases.

## Verification evidence — before/after (`pencil_dod_evaluate_county`, live)

**nassau** — 9/10 (fabricated) → honest 7/10:
```
BEFORE: B verified=27/27 (100.0%) PASS [FABRICATED]  | F tier1_sold=27/27 (100.0%) PASS [FABRICATED]
        C matched_clean=28/34 (82.4%) FAIL | D matched_any=34/34 (100.0%) PASS
AFTER:  B verified=0/0 (null) FAIL | F tier1_sold=0/0 (null) FAIL
        C matched_clean=28/34 (82.4%) FAIL [unchanged, restored after self-inflicted dip] | D matched_any=34/34 (100.0%) PASS [unchanged, restored]
Unaffected: A PASS(5) | E 97.1% PASS | G 100% PASS | H 0.1h PASS | I 97.1% PASS | J 100% PASS
```

**levy** — 8/10, unchanged (A,B,E,F,G,H,I,J pass; C,D fail, confirmed genuinely blocked):
```
C matched_clean=0/32 (0.0%) FAIL | D matched_any=0/32 (0.0%) FAIL — no genuine second independent source exists
```

**gulf** — 7/10 → 8/10 (I fixed):
```
BEFORE: I card_complete=15/16 (93.8%) FAIL
AFTER:  I card_complete=16/16 (100.0%) PASS
Unchanged: C matched_clean=7/16 (43.8%) FAIL | D matched_any=7/16 (43.8%) FAIL — confirmed genuinely blocked (synthetic bootstrap placeholders)
```

**franklin** — 4/10, unchanged (A,G,H,J pass; B,C,D,E,F,I fail, confirmed genuinely blocked/unknown):
```
B verified=0/0 (null) FAIL | C 0.0% FAIL | D 0.0% FAIL | E parcel_linked=8/9 (88.9%) FAIL | F tier1_sold=0/0 (null) FAIL | I card_complete=0/9 (0.0%) FAIL
All confirmed structural: 7/9 auctions scheduled for dates after 2026-07-04 (haven't occurred), 1 redeemed, 1 cancelled — zero resulted sales exist to verify.
```

13 `gold_standard_ultraloop_audit` rows logged this session under dispatch_id `a50b350f-3b98-4150-9a19-36775fb6ecbd` (12 `survived=true`, 1 `survived=false` — the refuted nassau C relabel proposal, logged not discarded per protocol).

## Carry-forward items (flagged, not attempted — out of this session's scope)

1. **Nassau C**: 6 rows (5 addressable + 1 with no PO corroboration at all) need a real authenticated RealForeclose rescrape of nassau.realforeclose.com (anonymous fetch returns HTTP 403) to resolve stale `auction_status`/`auction_date` values against the actual outcome. Highest-leverage next step for nassau.
2. **Nassau fleet-wide flag**: `migrations/20260625_shard4_run581_gold_standard.sql` documents the same `default 150000` pattern was applied to a shard covering **holmes, marion, nassau, walton** — only nassau was in this session's scope to fix. Flagging holmes/marion/walton for whichever shard owns them next; not fixed here.
3. **Levy C/D**: needs a genuinely independent second source (e.g., a Levy County Property Appraiser sale-record feed) before any parity claim is possible — PropertyOnion does not cover this county.
4. **Gulf C/D**: 6 `shard5_bootstrap` rows need a real Gulf Clerk foreclosure/tax-deed re-scrape to replace synthetic parcel IDs (`GULF-FC/TD-PARCEL-000X`); 3 "Address On File" rows need the realforeclose scraper re-run to resolve actual street addresses.
5. **Franklin E/I**: needs a confirmed-working Franklin County GIS/property-appraiser endpoint (qpublic.net returned HTTP 403 to automated fetch this session; no FL GIO ArcGIS REST endpoint for Franklin was verified reachable). 1 parcel_id and all 9 rows' geo/value fields are blocked on this.
6. Did **not** run `gold_standard_loop()`/`gold_standard_certify()` per PARALLEL-FLEET RULES (could not confirm no other shard session was mid-flight); reported via per-county `pencil_dod_evaluate_county` only, as instructed.
