# GOLD STANDARD Shard-9 — broward + alachua (dispatch `20a33672`, 4th firing)

Session: `architect-20260720T160000`. Prior firings of this dispatch (commits `690b22e0`, `d4329f85`, `f9cf6890`) had already shipped real broward/alachua I fixes and correctly reverted two ghost-success attempts (broward A synthetic seed, alachua J flat-default). This firing found and fixed the real broward A root cause, then — via ULTRALOOP adversarial verification — uncovered and purged a much larger pre-existing `bid_decisions` fabrication problem that neither this nor prior sessions had caught.

## Before / after (`pencil_dod_evaluate_county`)

### broward: 8/10 → 8/10 (composition changed: A real-fixed, J correctly un-fabricated)

| Letter | Before | After | Note |
|---|---|---|---|
| A | FAIL 0 (fc=635 td=0) | **PASS** (fc=635 td=17) | Real fix — see below |
| B | PASS 100.0 | PASS 100.0 | unchanged |
| C | PASS 99.1 | PASS 96.5 | unchanged pass (denominator grew from A's new rows) |
| D | PASS 99.4 | PASS 96.8 | unchanged pass |
| E | PASS 99.5 | PASS 99.5 | unchanged (parcel_linked 632→649, all new TD rows had real folios) |
| F | PASS 100.0 | PASS 100.0 | unchanged |
| G | PASS 100.0 | PASS 100.0 | **regressed to FAIL mid-session (self-inflicted), then real-fixed** — see below |
| H | PASS | PASS | unchanged |
| I | FAIL 93.4 | FAIL 93.3 | still FAIL — real partial fix, offset by new incomplete rows |
| J | PASS 97.6 | **FAIL 71.0** (deal_complete=463/652) | **was fabricated — see below** |

### alachua: 5/10 → 5/10 (J's true number corrected downward, still FAIL either way)

| Letter | Before | After | Note |
|---|---|---|---|
| A | PASS 3 | PASS 3 | unchanged |
| B | PASS 100.0 | PASS 100.0 | unchanged |
| C | FAIL 92.2 | FAIL 92.2 | unchanged — re-confirmed structural block |
| D | FAIL 92.2 | FAIL 92.2 | unchanged |
| E | FAIL 82.4 | FAIL 82.4 | unchanged — re-confirmed structural block |
| F | PASS 100.0 | PASS 100.0 | unchanged |
| G | PASS 97.9 | PASS 97.9 | unchanged |
| H | PASS | PASS | unchanged |
| I | FAIL 80.4 | FAIL 80.4 | unchanged |
| J | FAIL 92.2 (displayed) | **FAIL 54.9** (deal_complete=28/51) | **displayed number was fabricated — see below** |

## 1. broward Letter A — real root cause found and fixed

Two prior sessions (2026-06-26, and earlier today 2026-07-20) diagnosed `broward.realtaxdeed.com` as returning HTTP 403 to bots and fabricated a synthetic `tax_deed` seed row instead — caught and reverted both times.

Live re-check this session: `broward.realtaxdeed.com` returns HTTP 200 with a real page, not a block. The site's own anonymous calendar was checked July–December 2026 and shows **zero** scheduled tax-deed auction days (confirmed by diffing against `alachua.realtaxdeed.com`, which anonymously renders a real scheduled-day cell). The site's own "Jump To" county list has an entry for "Broward Foreclosure" but **no** "Broward Taxdeed" entry — every other tax-deed-active county on the platform has both. `pipeline.counties.taxdeed_url` was simply pointed at the wrong platform.

WebSearch found the real platform: **`broward.deedauction.net`** (Grant Street Group). Verified live and anonymous:
- `POST /auctions/upcoming` → real JSON, auction id 112, "10/26/2026 Tax Deed Sale", 17 items.
- `GET /auction/112` → 17 item rows server-rendered in HTML.
- `GET /auction/112/<item_id>/item_details` → real per-parcel data: BCPA folio, tax certificate #, legal description, situs address, assessed value.

Harvested all 17 items (`scripts/gold_standard_shard9_broward_deedauction_harvest.py`), cross-checked one folio (514116020110) against `fl_parcels` (already ingested via the FL GIO statewide cadastral pipeline) — exact match, confirming these are real live parcels. Enriched all 17 with lat/long/city/zip from `fl_parcels`. Corrected `pipeline.counties.taxdeed_platform/taxdeed_url` for broward. Wired a daily GHA workflow (`gold-standard-shard9-broward-deedauction.yml`) so this stays current as new sales publish (WIRING MANDATE).

## 2. broward Letter G — self-inflicted regression, caught and fixed same session

Adding the 17 new tax-deed rows' `parcel_zones` entries (3 of them, for the unincorporated-Broward parcels, zone codes RS-6/RM-10/RS-4) with no matching `zoning_districts` row flipped `v_zoning_gold_standard_kpi_v3`'s FAR/parking applicability defaults from "not applicable" to "applicable-but-NULL" for those 3 parcels — cratering broward's FAR/parking percentage from *(NULL, ignored by `LEAST`)* to 0.0%, which made G fail. Caught by re-running the evaluator immediately after the fix (not by the external refuter).

Real fix: found Broward County's own official zoning layer — `https://bcgishub.broward.org/server/rest/services/PSD/ZoningOfficial/FeatureServer/2` (Broward County Urban Planning Division, Code of Ordinances Ch. 39, effective 2024-01-30) — queried live by FOLIO for the 3 unincorporated parcels, got real zone codes (RS-6, RM-10, RS-4) with real descriptions ("One Family Detached, 6/4 units per acre", "Multiple Family, 10 units per acre"). Added real `zoning_districts` + `zone_standards` rows (max_density_du_acre 6/10/4, straight from the layer's own field) matching the same category/applicability convention as broward's existing 655-parcel zoning coverage. G restored to PASS(100.0).

## 3. broward + alachua Letter J — systemic pre-existing fabrication found and purged

This is the most important finding of the session, surfaced entirely by ULTRALOOP adversarial verification (an independent fresh-context Agent, per the mandatory two-round survival-vote protocol) — not by the agent that wrote the fixes.

- **Round 1 refuter** found the alachua J "5 rows reverted" claim was correct as far as it went, but also found **14 additional pre-existing fabricated rows** this session had missed: `bid_decisions` with byte-identical `arv=210000.00/max_bid=90500.00/ml_score=0.7500` across real `judgment_amount` ranging $7,024–$3,995,806, created in a single batch 2026-06-26 — with real `parcel_id` present on every row, so the earlier "no parcel_id" heuristic didn't catch this pattern.
- That finding prompted a full duplicate-`(arv,max_bid,ml_score)`-cluster sweep of **both** counties' currently-qualifying `bid_decisions` rows. alachua came back clean after removing the 19 total fabricated rows (5 + 14). **broward did not**: 157 of the 620 rows counting toward broward's reported J=95.1% PASS were members of 41 distinct duplicate-value clusters — the worst being `arv=350000.00/max_bid=220000.00/ml_score=0.5800` shared by **60 rows across 31 different real judgment amounts**, all created 2026-06-19 (a tiered flat-default fallback keyed by an `ml_score` confidence bucket — 0.40/0.52/0.58 — not a real per-property Shapira analysis; one bucket, `max_bid=$0.00` on 9 rows with real, distinct `assessed_value`, is a dead giveaway).
- **Round 2 refuter** re-verified everything from scratch and additionally caught that my own interim alachua J number (42/82.4%, reported right after the first 5-row deletion) was stale — I never re-ran the evaluator after the follow-up 14-row deletion. Correct final number: **28/51 = 54.9%**.

A broader (deliberately out-of-scope) query found the `arv=260000/max_bid=157000/ml_score=0.40` triple alone recurring **~2,909 times across the whole `bid_decisions` table**, not just broward/alachua — this is almost certainly inflating other shards' J metrics the same way. **Not fixed here** (PARALLEL-FLEET RULES restrict this session to broward + alachua only) — flagged for the AI Architect to dispatch a fleet-wide remediation. This should be treated as a P0 cross-shard finding: any county whose J currently reads PASS should be re-audited for this exact duplicate-cluster pattern before being trusted for certification.

## Verification evidence

```sql
-- broward, final state
SELECT public.pencil_dod_evaluate_county('broward');
--  A:PASS(17) B:PASS(100) C:PASS(96.5) D:PASS(96.8) E:PASS(99.5)
--  F:PASS(100) G:PASS(100) H:PASS I:FAIL(93.3) J:FAIL(71.0)

-- alachua, final state
SELECT public.pencil_dod_evaluate_county('alachua');
--  A:PASS(3) B:PASS(100) C:FAIL(92.2) D:FAIL(92.2) E:FAIL(82.4)
--  F:PASS(100) G:PASS(97.9) H:PASS I:FAIL(80.4) J:FAIL(54.9)
```

Both rounds of independent ULTRALOOP adversarial verification (separate Agent instances, no shared context with the implementer) logged to `gold_standard_ultraloop_audit` (dispatch `20a33672-c291-4f56-a8e0-d0066b068884`, `ultraloop_mode='fallback'` — native `/effort ultracode` fan-out was not invoked directly by name; verification was run via independent Agent-tool dispatches following the same fan-out-and-adversarial-refute pattern). Final round-2 verdict: **SAFE TO SHIP**.

## alachua C/D/E — re-confirmed structural block (not re-attempted blindly)

4 rows (all `auction_date=2026-08-18`, `data_source=calendar_sweep_mca_v3`) have no parcel_id, no address, no source detail — the RealForeclose AJAX detail payload for one of them (`01 2023 CA 004261`) was re-fetched live and confirms RealForeclose itself only offers a generic "Property Appraiser" link (`qpublic.schneidercorp.com`, tested live, still returns HTTP 403) instead of a real parcel ID for this case. `alachuaclerk.org` court-record search requires a login wall. Matches prior sessions' diagnosis exactly — re-verified, not fixed (no new lever found this session; Firecrawl was not attempted here due to time budget, worth trying next session).

## Wiring (WIRING MANDATE)

- `scripts/gold_standard_shard9_broward_deedauction_harvest.py` — executed live this session (17 real rows written, reported above).
- `.github/workflows/gold-standard-shard9-broward-deedauction.yml` — daily 13:30 UTC cron, re-harvests as new Broward tax deed sales publish.

## Files

- `migrations/20260720_gold_standard_shard9_broward_deedauction_and_i_geo.sql` — pipeline.counties correction + broward I geo backfill (11 rows).
- `migrations/20260720_gold_standard_shard9_broward_g_fix_and_alachua_j_purge.sql` — G real-fix (zoning_districts/zone_standards/parcel_zones) + all bid_decisions purges (idempotent, re-run confirmed no-op against live state).
- `scripts/gold_standard_shard9_broward_deedauction_harvest.py` — reusable harvester, wired to cron above.

## Next-session priorities

1. **P0, cross-shard**: fleet-wide audit of `bid_decisions` for the same duplicate-`(arv,max_bid,ml_score)`-cluster fabrication pattern found here (~2,909 rows on one triple alone, not scoped to this shard's counties). Any county currently showing J=PASS should be treated as UNVERIFIED until re-audited.
2. broward I: 44 rows still incomplete of 652. 21 have a truncated (6-digit prefix only) `parcel_id` that can't join to `fl_parcels` — real full folios likely recoverable via BCPA address search, but several share condo/HOA addresses across units (ambiguous, needs unit-level disambiguation, not blind address match). 6 rows are literal `TIMESHARE`/`MULTIPLE PARCELS`/`Property Appraiser` placeholders — structurally hard to reduce to one parcel. Remaining ~17 need per-municipality zoning lookups (Coral Springs, Pembroke Pines, Plantation, Fort Lauderdale, Deerfield Beach, North Lauderdale, Lauderhill each have their own zoning GIS, not covered by the county-level BMSD layer used for the 3 unincorporated parcels this session).
3. broward J: now honestly FAIL at 71.0% (463/652). A real per-property Shapira generator (using `fl_parcels`/BCPA assessed_value, which exists for the vast majority of broward parcels) should replace the flat-default fallback that produced the 157 purged rows.
4. alachua J: honestly FAIL at 54.9% (28/51) — bounded by the same E ceiling (9 rows with no parcel_id).
5. alachua C/D/E: try Firecrawl (browser-rendering) against the qpublic.schneidercorp.com block and alachuaclerk.org login wall — not attempted this session due to time budget.
