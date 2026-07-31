# Gold Standard Shard-10: sarasota + columbia (dispatch 44c8ac10)

Session: 2026-07-31, `architect-20260731T000000`. ULTRALOOP mode: **fallback** (manual Task/Workflow fan-out — 6 diagnose→fix→verify pipelines, 18 agents total, one independent adversarial refuter per claim). No row logged to `gold_standard_ultraloop_audit` — direct DB write access (psql/DDL) was unavailable from this session's sandbox (see Environment Note below), so audit rows could not be inserted; this report is the evidence trail instead.

## Environment note (read before trusting any "applied" claim below)

Direct `psql` to the Supabase pooler failed from this session for both `aws-0-us-west-2` and `aws-0-us-east-1` regions, and for the direct `db.<ref>.supabase.co` host, all with `$SUPABASE_DB_PASSWORD` from the environment (`password authentication failed` / `tenant not found`). This blocks raw SQL DDL. **REST API (PostgREST) read/write with the service-role key works fine** and is what all fixes below actually used. Nothing requiring `CREATE`/`ALTER TABLE` was applied live this session — where that was the only path (sarasota G), the session correctly stopped short rather than fabricate an "applied" migration.

## Brief snapshot vs. live reality (important drift caught this session)

The dispatch brief's sarasota numbers (9/10, only G failing) were **stale**. Live `pencil_dod_evaluate_county('sarasota')` at session start showed **5/10** (auctions_total grew 187→365 between the brief snapshot and now, diluting C/D/I/J below the 95% threshold). Work was scoped to the live state, not the brief.

## Before → After (live RPC, pasted verbatim)

### sarasota — 5/10 → **6/10**

| Letter | Before | After | Change |
|---|---|---|---|
| A | PASS fc=111 td=254 | PASS (unchanged) | – |
| B | PASS 98.3 (verified=119 closed_sold=121) | PASS 98.5 (verified=131 closed_sold=133) | moved (side effect of C/D outcome scrape) |
| C | FAIL 91.8 (matched_clean=335) | FAIL 94.5 (matched_clean=345) | improved, still fails |
| D | FAIL 91.8 (matched_any=335) | FAIL 94.5 (matched_any=345) | improved, still fails |
| E | PASS 96.2 | PASS (unchanged) | – |
| F | PASS 98.3 | PASS 98.5 | moved (same outcome scrape) |
| G | FAIL 54.5 (density=91.4 far=95.4 pk1000=54.5) | FAIL 50.0 (density=91.5 far=95.0 pk1000=50.0) | **drifted down** — side effect of the I-letter fix adding 14 new `parcel_zones` rows that shifted G's denominator; not a regression from a passing state, G failed both before and after |
| H | PASS | PASS | – |
| I | FAIL 91.2 (card_complete=333/365) | **PASS 95.1 (card_complete=347/365)** | ✅ **flipped to PASS** |
| J | FAIL 93.4 (deal_complete=341, later found to be ghost-success — see below) | FAIL 94.0 (deal_complete=343, real comps) | improved, still fails, but now honest |

### columbia — 6/10 → 6/10 (no letters moved — every gap confirmed structural, not fixed)

| Letter | Before | After |
|---|---|---|
| A | FAIL fc=15 td=0 | unchanged |
| B | FAIL verified=0 closed_sold=0 (metric null) | unchanged |
| F | FAIL tier1_sold=0 closed_sold=0 (metric null) | unchanged |
| I | FAIL card_complete=14/15 | unchanged |

## What was actually done, per letter

**sarasota I → PASS (verified survives adversarial refutation).** 14 of 15 flagged rows had a real ArcGIS match on `ags3.scgov.net` (Sarasota's ParcelProperty FeatureServer); house-number-verified against our `property_address`, backfilled `latitude/longitude/market_value` via REST PATCH. The metric did **not** move after that alone — the agent caught that `card_complete`'s predicate also requires a `parcel_zones` row, which all 14 lacked. It found a real, previously-unused zoning layer set on the same ArcGIS host (`CountyZoning` + per-city layers for North Port/Sarasota/Venice), ran point-in-polygon queries, and inserted 14 real `parcel_zones` rows. RPC re-run twice, stable at 347/365 = 95.1%. One row (a condo unit, parcel `2028103031`) has no match in the source layer and was correctly left unfixed rather than fabricated — residual 18/365 incomplete rows remain (17 pre-existing structurally-blocked + the condo).

**sarasota J — ghost-success caught and replaced with real data (still FAIL, but now honest).** The diagnosis found the existing 341 `bid_decisions` rows were fabricated: `arv` = `assessed_value` verbatim on all 341, `factors.cma_resale/arv` fixed at exactly 1.0000, `factors.cma_distressed/arv` fixed at exactly 0.8000, and only 4 distinct `ml_score` values across 341 rows. This is a textbook ghost-success pattern this campaign's SHIP GATE rule exists to catch. The session purged all 341 rows and rebuilt real per-property comps from `fl_parcels` (DOR cadastral data — not PropertyOnion), bucketed by (zip, dor_uc), using real sold-comp percentiles (p25/p75) for 342 of 365 qualifying properties; 343 rows written (5 properties had <3 comps and were left out rather than fabricated). Post-write fingerprint check: 0/343 `arv==assessed_value` matches (was 341/341), 55 distinct `ml_score` values (was 4). Metric moved 93.4%→94.0% — still fails 95%, reported plainly. Committed as `6a2450d9` (pushed this session).

**sarasota C/D — real progress, but the fix agent's residual narrative was wrong and does not survive adversarial check.** Outcome scrapers (pre-existing, not new) were re-run: 10 new `foreclosure_outcomes` + 2 new `tax_deed_outcomes` rows, 131 `multi_county_auctions` rows patched with `sold_amount`/`sold_amount_captured_at`. Metric moved 91.8%→94.5% (still FAIL). **However**: the fix's honesty_note claimed the remaining 20-row residual was "a clean, fully-explained ceiling" of 12 redeemed tax-deed rows + 8 near-term upcoming foreclosure rows. The refuter's direct re-query found only **1** upcoming foreclosure row in that date range, not 8, and that the true county-wide pool of unmatched foreclosure rows is **1,119** (dating back to 2018) — nothing resembling a clean, small residual. The 12-redeemed-tax-deed-rows half of the claim did check out. **Do not trust the "clean ceiling" characterization from this session; the real residual is large and unexplained.**

**sarasota G — correctly not fixed.** `zone_standards` and `permitted_uses` have zero rows (not null-valued rows) for all 4 blocking Sarasota zoning districts (CN, PID, CT, DTC). Live ordinance research (Zoneomics, county code) confirms these are use-type-keyed parking ordinances with no district-level `parking_per_1000sf` value in the source at all — this may be a metric-definition problem, not a missing-data problem. This is the **2nd county** (after bay, dispatch `9f070f2b`) to hit this identical wall. Recommend the fleet-wide policy decision already flagged in `a9f1f24f`: either exclude use-type-only jurisdictions from `pk1000_applicable`, or approve a disclosed default judgment-call mapping. Not something a single session should decide unilaterally. See `migrations/20260731_gold_standard_shard10_sarasota_g_dispatch44c8ac10.sql` (documentation-only, no SQL executed).

**columbia A/B/F — confirmed structural, not a bug.** All 15 columbia rows are `sale_type=foreclosure`, `auction_status=upcoming`; zero are tax-deed, zero have reached a closed/sold outcome yet. A needs a genuinely new tax-deed scraper lane for columbia (not present in this session's scope — flagged for a future session, not attempted half-built). B/F cannot be measured until cases actually close; this is a maturity gap, not a data defect. `columbiaclerk.com` and `realtaxdeed.com` both returned HTTP 403 (Cloudflare-gated) when probed for a tax-deed source.

**columbia I — confirmed structural.** The one incomplete row (`357 SW AMIEL CT`, parcel `04023-000`) sits inside Fort White town limits (independently confirmed via live point-in-polygon query against the county's own `Ft_White_Limits` layer), but Columbia County's zoning GIS has no dedicated Fort White zoning layer — the county's `Zoning_Atlas` layer returns zero features at this parcel's coordinates. Structurally unlinkable with current data sources.

## Adversarial verification summary (ULTRALOOP fallback mode)

| Claim | Survived independent refutation? |
|---|---|
| columbia A/B/F no-action | ✅ survived |
| columbia I no-action | ✅ survived |
| sarasota G no-action | ❌ did not survive as stated — the file's "no drift" line was stale by the time of refutation (corrected in this session before commit; see file) |
| sarasota C/D partial fix | ❌ did not survive as stated — core DB writes and metric movement are real and verified, but the residual-composition narrative (8 upcoming rows) was refuted (actual: 1) |
| sarasota I fix | ✅ survived, full PASS confirmed 3x live |
| sarasota J fix | ✅ survived, ghost-success purge and real-comp replacement fully confirmed |

Two of six claims did not survive as originally stated. Both non-survivals were narrative/interpretive overreach on top of real, verified underlying data work — not fabricated data. Both have been corrected in this report and in the committed file. Per this campaign's Honesty Protocol, VERIFIED-tagged claims that don't reproduce carry a 3x penalty; flagging that explicitly here rather than smoothing it over.

## Verification protocol executed

- `pencil_dod_evaluate_county('sarasota')` and `('columbia')` queried live before, during (per-fix), and after (pasted above, UTC 2026-07-31).
- Did **not** run `gold_standard_loop()` or `gold_standard_certify()` — other shards may be mid-flight per PARALLEL-FLEET RULES; per-county evaluator only.
- No cron jobs (109/111/115/gold-standard-loop-*) touched.
- PropertyOnion was not used as a data source anywhere in this session (litmus-only, confirmed in each fix).

## Residual / next-session priorities

1. **sarasota G**: needs the fleet-wide policy call on use-type-keyed parking ordinances (2nd county hitting this, after bay) — not a scraping task.
2. **sarasota C/D**: real residual is ~1,119 unmatched foreclosure rows county-wide, far larger and messier than previously believed. Needs real parity-audit work, not a quick backfill.
3. **sarasota J**: 22 auctions still lack sufficient real comps (<3 sold comps in bucket) — needs either a wider comp-search radius/time window or acceptance of a smaller reliable set.
4. **columbia A**: needs a new tax-deed lane/scraper for columbia (clerk site is Cloudflare-gated — may need a different auction platform, undetermined this session).
5. **columbia B/F**: will resolve naturally as upcoming auctions close and outcomes get scraped — no action needed until then.
6. **columbia I**: structurally blocked pending a Fort White zoning data source (none found this session).

## SQL VERIFICATION

```
-- sarasota, 2026-07-31 (post-fix, 3rd re-run for stability):
SELECT public.pencil_dod_evaluate_county('sarasota');
-- A=PASS(111) B=PASS(98.5) C=FAIL(94.5) D=FAIL(94.5) E=PASS(96.2) F=PASS(98.5)
-- G=FAIL(50.0) H=PASS(0.1) I=PASS(95.1) J=FAIL(94.0)  auctions_total=365  -- 6/10

-- columbia, 2026-07-31:
SELECT public.pencil_dod_evaluate_county('columbia');
-- A=FAIL(0) B=FAIL(null) C=PASS(100.0) D=PASS(100.0) E=PASS(100.0) F=FAIL(null)
-- G=PASS(100.0) H=PASS(15.7) I=FAIL(93.3) J=PASS(100.0)  auctions_total=15  -- 6/10
```
