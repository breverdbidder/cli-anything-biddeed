# SHARD-9 run3645 — walton / escambia / santa_rosa / liberty

dispatch_id: bf7aeb04-5c58-403a-969d-957b767c6d25
chat_session: architect-20260710T160000
mode: ULTRALOOP fallback (manual Workflow-tool fan-out, not native `/effort ultracode`)

## Scoreboard: plan vs actual

| County | Before | After | Delta |
|---|---|---|---|
| walton | 9/10 (I fail) | **10/10** | +1, all 10 letters PASS |
| escambia | 7/10 (C,D,I fail) | 7/10 (C,D,G fail) | net 0 count, but I fixed for real (78.5%→98.5%); G newly/honestly fails (see below) |
| santa_rosa | 6/10 (B,E,F,I fail) | 7/10 (B,F,I fail) | +1 (E fixed) |
| liberty | 3/10 | 3/10 | unchanged — re-confirmed exhausted blocker, not idled on |

## What actually shipped (commits on origin/main)

- `e55a74d2` — walton I: 81.1%→97.3% (30→36 of 37). Real EnerGov ArcGIS FeatureServer point-in-polygon zoning + geo backfill for 6 of 7 gap rows (7th, case 26CA000030, has zero scrapable fields on walton.realforeclose.com — left null, genuinely blocked).
- `ce677a37` — santa_rosa E: 92.1%→96.1% (70→73 of 76) via realforeclose_aids + fl_parcels (co_no=67) cross-matched address/parcel linkage; I geocode assist via US Census Geocoder for one row. 4 of 6 original gap rows unaddressable (no property address ever scraped) — left null.
- (no commit, SQL-only) — escambia I: 78.5%→98.5% (260→326 of 331) via 65 new real parcel_zones rows sourced from maps.escpa.org live ArcGIS (parcel geometry + zoning layers), independently reproduced by the refuter via its own shoelace-centroid + EPSG:2883→WGS84 reprojection.
- `3aa697db` — escambia G partial remediation: corrected zoning_districts 7187 (R-NC) / 7188 (C-1) / 7191 (C-3) applicability flags (far_regulated=false where the real Pensacola LDC Ch. 12-3 genuinely has no FAR standard for these codes — verified by downloading and full-text-searching the actual ordinance PDF, zero occurrences of "FAR"/"density"). Did NOT fabricate values for the gap. G still fails (see below).
- (no commit, SQL-only) — walton G full remediation: sourced real density/FAR/impervious/open-space figures from Walton LDC Chapter 2 (5 sections, word-for-word cited) for the 5 new Rural-designation codes + confirmed DeFuniak Springs' own ArcGIS FeatureServer zoning for the 6th parcel and normalized it to walton's existing 'A' (Agriculture) district code rather than inventing a new one. **G restored 100.0%→100.0% (no net regression survives).**

Every item above went through an independent adversarial-refuter pass (separate agent, told to default skeptical) before being logged to `gold_standard_ultraloop_audit`. All 8 build claims survived refutation (`survived=true`); no false-positive claims were filtered out this session.

## Deviation: a self-inflicted P0 regression, caught and mostly fixed same-session

The escambia_I and walton_I fixes each added real parcel_zones rows for parcels in zoning districts that had never been ordinance-backfilled for density/FAR/parking. This flipped criterion **G** from a previously-PASSing 100% (on a near-empty, mostly-null denominator) to a newly-visible, honest failure once those parcels became "applicable." This is exactly the class of regression CLAUDE.md flags as P0 ("RECONCILE all prior PASSes — any regression = P0"). We did not ship the I-gain and move on; we ran a second, tightly-scoped Build+Verify round same session to fix it with real ordinance data:

- **walton: fully recovered.** G is back at 100.0% PASS — confirmed by the refuter independently downloading the Walton LDC PDF and word-for-word matching all 5 cited sections, plus independently querying DeFuniak Springs' own ArcGIS layer for the 6th parcel.
- **escambia: partially recovered, still FAIL.** The far/density applicability flags for R-NC/C-1/C-3 were corrected (no fabricated numbers), but a separate, larger, pre-existing gap remains: `parking_per_1000sf` (pk1000) is genuinely uncovered for the newly-added parcels and is not something this session's narrow fix addressed. Live: `G FAIL metric=0.0 [density=84.2 far=0.0 pk1000=0.0]`. **This is disclosed as an open item for a future session, not claimed as fixed.**

## Residual fabrication flags found (pre-existing, NOT from this session, NOT touched)

- Escambia `jurisdiction_id=1151` zoning_districts.name literally reads `"Single Family Residential (Shard9 Synthetic)"` with 261 parcel_zones rows — dated 2026-06-24, weeks before this session. Left untouched (out of scope) but flagged here for a future purge/audit, matching this campaign's pattern of prior ghost-success (charlotte, desoto, hendry, etc.).
- Walton's pre-existing 27 parcel_zones rows (before this session) were labeled `source='shard4_run581_v2/walton_synthetic'` with garbage parcel_ids like `'TIMESHARE'` and `'Property Appraiser'` — a blanket R-1 fabrication from an earlier session. Also left untouched (out of scope for the I/G fix, which only touched the 6+7 new rows) but flagged for a future session.

## Genuinely blocked (confirmed live this session, not idled on without evidence)

- **escambia C/D (77.0%/77.0%, need 95%)**: the 76 unmatched rows are all real future tax-deed auction dates (2026-08-05 through 2026-12-02). Independently re-harvested escambia.realtaxdeed.com's live AJAX calendar — 301 real case numbers exist for those 5 dates, **zero** overlap with our 76. The site genuinely does not publish these specific cases yet (or under different numbering) — not a matcher bug. Re-check closer to each sale date.
- **santa_rosa B/F (null/null)**: 44 auctions already past their auction_date sit with `auction_status='upcoming'` and no sold_amount. `scripts/county_outcome_harvester.py` was run against santarosa.realforeclose.com/realtaxdeed.com and correctly wrote zero rows — RealForeclose login/access failed, so nothing was fabricated. **Genuinely blocked on scraper access, not on missing effort.** Real opportunity remains for a future session with working RealAuction credentials.
- **santa_rosa I (71.1%, need 95%)**: parcel_zones coverage for santa_rosa only exists for Gulf Breeze (77 rows) — confirmed via direct query. Broader santa_rosa zoning ingestion is a substrate-build task, same class as the historical duval/brevard G gaps.
- **liberty (3/10, unchanged)**: re-confirmed fresh this session — A (no tax-deed lane, libertyclerk.com explicitly lists none, RealAuction platforms return 403), B/F (sole case's auction_date 2026-07-21 is still 11 days future), C/D (nothing to match against), G/I (Bristol jurisdiction has zero real zoning data). All re-logged to `gold_standard_ultraloop_audit` with fresh survived=true evidence to keep the certify gate's 7-day freshness window current. Correctly not re-litigated at length — a prior session (dispatch 121fa7c3) had already exhausted this county.

## SQL VERIFICATION (fresh live pull, this comment)

Query: `SELECT public.pencil_dod_evaluate_county(p_county) FOR county IN ('walton','escambia','santa_rosa','liberty')`
Timestamp: 2026-07-10T17:09Z (UTC)

```
walton: 10/10 — A PASS(6) B PASS(100.0) C PASS(100.0) D PASS(100.0) E PASS(97.3)
        F PASS(100.0) G PASS(100.0) H PASS(1.3) I PASS(97.3) J PASS(100.0)

escambia: 7/10 — A PASS(34) B PASS(100.0) C FAIL(77.0) D FAIL(77.0) E PASS(99.7)
        F PASS(100.0) G FAIL(0.0) H PASS(1.3) I PASS(98.5) J PASS(100.0)

santa_rosa: 7/10 — A PASS(22) B FAIL(null) C PASS(100.0) D PASS(100.0) E PASS(96.1)
        F FAIL(null) G PASS(100.0) H PASS(0.6) I FAIL(71.1) J PASS(100.0)

liberty: 3/10 — A FAIL(0) B FAIL(null) C FAIL(0.0) D FAIL(0.0) E PASS(100.0)
        F FAIL(null) G FAIL(null) H PASS(5.2) I FAIL(0.0) J PASS(100.0)
```

`gold_standard_ultraloop_audit`: 8 build rows + 8 refuter rows inserted this session across the 4 counties, all `survived=true`, `dispatch_id='bf7aeb04-5c58-403a-969d-957b767c6d25'`, `ultraloop_mode='fallback'`.

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not** run mid-session — other shards were concurrently pushing (23 commits from other shard sessions landed on origin/main during this session's runtime, none conflicting with our county-scoped work).

## Verification evidence (Evidence-Before-Claims)

Every claim above was independently re-derived by a second agent that did not write the fix: re-ran `pencil_dod_evaluate_county` fresh, re-fetched primary sources (ArcGIS FeatureServers, ordinance PDFs, Census Geocoder) rather than trusting citations, checked for the repo's documented fabrication anti-patterns (placeholder-coordinate clusters, mechanically-derived parcel_ids, PropertyOnion masquerading, denominator gaming), and confirmed claimed git commits actually exist on origin/main. Two verify agents found and disclosed minor provenance-description imprecisions (santa_rosa: one parcel's linkage credit misattributed to realforeclose_aids vs the actual fl_parcels address match; walton: 'AG' GIS code normalized to existing 'A' district) — neither invalidated the underlying claim.

## Next session should pick up

1. escambia G — source real `parking_per_1000sf` standards for the Pensacola LDC districts still missing them (or confirm genuinely N/A via applicability flag, not a guess).
2. escambia C/D — re-check the 76 future tax-deed cases closer to their sale dates (2026-08-05 is the nearest).
3. santa_rosa B/F — fix RealForeclose/RealTaxDeed authenticated access for santa_rosa, then re-run `county_outcome_harvester.py` against the 44 past-due auctions.
4. santa_rosa I / broader zoning substrate — santa_rosa parcel_zones coverage is Gulf Breeze-only; needs the same substrate-build treatment as brevard/duval G work.
5. Flag for a dedicated fabrication-purge pass: escambia jurisdiction 1151 ("Shard9 Synthetic") and walton's pre-existing 27 `walton_synthetic` rows.
