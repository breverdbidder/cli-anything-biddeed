# Gold Standard Shard-4 Issue #18319 — Session Report

**Dispatch:** `1338ab5d-c22a-43be-876f-887fb75417e7`
**Session:** `architect-20260807T080000`
**Loop run:** 9488
**Counties:** sarasota, seminole, pasco, suwannee, hendry
**Mode:** Fallback ultraloop (REST API via GHA workflow)

## Entry State (from brief)

| County | Score | Failing |
|--------|-------|---------|
| sarasota | 9/10 | G (pk1000=90) |
| seminole | 8/10 | G (pk1000=88.9), I (94.9%) |
| pasco | 7/10 | C/D (84.4%), I (82.9%) |
| suwannee | 6/10 | B/F (null), I (74.3%), J (0) |
| hendry | 5/10 | C/D/E/I/J (all 64.4%) |

## Diagnosis

### sarasota G — STRUCTURAL BLOCKER (4th+ session)

**VERIFIED** (multiple prior sessions, most recently dispatch 44c8ac10 2026-07-31):
- Sarasota County Sec. 124-120(g)(2) regulates parking by USE TYPE, not district
- 4 blocking districts (CN, PID, CT, DTC): ZERO `zone_standards` rows exist
- 3 of 5 blocking parcels are vacant/unaddressed → no use-type signal
- Source URLs: HTTP 503/404/403 across all ordinance sources

**Action: NONE.** Fleet-wide policy decision required from Ariel:
- (a) Exclude use-type-only jurisdictions from `pk1000_applicable`
- (b) Approve modal use-type proxy with `confidence_score < 1.0`

### seminole G — PUD-RES fix

**Root cause** (from dispatch ccb82791 2nd firing report, 2026-08-07):
- 3 new `parcel_zones` inserts (Sanford, Altamonte Springs, unincorporated) added last session
- Altamonte Springs insert used zone_code `PUD-RES` which has no `zoning_districts` row
- `v_zoning_gold_standard_kpi_v3` counts unmatched zone_code as "applicable with no standard" → G fails

**Fix:** Create `zoning_districts` row for PUD-RES in Altamonte Springs jurisdiction, classified as `far_regulated=false, density_regulated=false, pk1000_regulated=false` (per-development-agreement, same treatment as Venice PUD, Clay BFPUD).

### seminole I — 1 row gap

**Root cause** (from prior session report):
- Need 131/137 (95%). Currently 130/137 (94.9%).
- 5 rows: garbage/synthetic/null parcel_ids (untouchable without fabrication)
- 2 rows: Seminole GIS hosts unreachable (network timeouts in prior session)

**Fix:** Re-harvest NULL parity rows via RealForeclose/RealTaxDeed AJAX to backfill any missing parcel_id, property_address, assessed_value from the live auction platform.

### pasco C/D + I — New auction surge

**Root cause:** ~70 new auctions added since the 2026-07-23 fix (which brought pasco to 10/10).
- Prior: 257 total → Current: 327 total
- Gap: ~51 rows without parity (C/D), ~56 rows without card completeness (I)

**Fix:** Re-run proven scripts:
- `shard_pasco_cd_i_fix.py` (foreclosure lane, RealForeclose AJAX)
- `shard_pasco_cd_taxdeed_fix.py` (tax deed lane, RealTaxDeed AJAX)
- Plus parcel enrichment for rows missing `parcel_id` via FL GIO ArcGIS

### suwannee B/F — STRUCTURAL BLOCKER (6th+ session)

**VERIFIED** (dispatch 6fe5726b 2026-07-25, 6th+ consecutive session):
- 0 closed foreclosure sales exist
- Courthouse-steps FC: no electronic records
- Civitek OCRS (myfloridacounty.com/orisearch/61): Cloudflare Turnstile CAPTCHA
- Cases 4666/4667 confirmed Redeemed, 25-CA-197 has no electronic listing

**Action: NONE for B/F.** Wait for actual sales or CAPTCHA-bypass authorization.

### suwannee I/J — New auction surge

**Root cause:** ~21 new tax deed auctions (td=35 vs 14 in prior session).
- New rows likely lack parcel_id, assessed_value, bid_decisions

**Fix:** RealTaxDeed harvest for NULL parity rows + assessed_value-based bid_decisions for newly-linked parcels.

### hendry C/D/E/I/J — New auction surge

**Root cause:** ~21 new auctions (59 total vs 38 in prior session, dispatch bebd50e5 2nd firing which had hendry at 9/10).
- All 5 failing letters at 38/59 = 64.4% → exactly the 38 old rows pass, 21 new rows lack everything

**Fix:**
- E: Parcel linkage via Hendry ArcGIS (`services7.arcgis.com/8l7Qq5t0CPLAJwJK`)
  - `/Hendry_County_Parcels/FeatureServer/0` (LOCADD address match)
  - `/Zoning/FeatureServer/1` (PARCELNO → Current_Zo)
- C/D: RealForeclose/RealTaxDeed AJAX parity harvest
- I: Follows from E (parcel_id + zone_code needed for card_complete)
- J: bid_decisions for newly-linked rows with assessed_value (INFERRED proxy)

**Note on Hendry F:** Prior session (bebd50e5 2nd) confirmed F oscillates due to race condition with `scrape-realauction-county.yml`. Case 25-100 appears on both a results-report page (sold $7,100 on 2026-07-16) AND still listed on the preview page. Do NOT force-patch auction_status — will be overwritten immediately by the next scraper run. F resolves when Hendry delists the case from their preview calendar.

## Session Artifacts

- `scripts/gold_standard_shard4_18319_executor.py` — Main executor
- `.github/workflows/gold-standard-shard4-18319.yml` — GHA workflow (manual trigger)
- `migrations/20260807_gold_standard_shard4_18319_sarasota_seminole_pasco_suwannee_hendry.sql` — Provenance

## Execution

All DML executed via `gold-standard-shard4-18319.yml` workflow (triggered after this commit).

Expected outcomes:
- pasco C/D: +51 matched_clean rows → 327/327 = 100% (if new rows are live on RealForeclose/RealTaxDeed)
- pasco I: +56 card_complete rows (from parity harvest bringing parcel_id/address/value)
- seminole G: PUD-RES removed from denominator → G recovery toward prior 97.9%
- seminole I: +1-3 rows from parity harvest → 131-133/137 (PASS threshold at 131)
- hendry E/I/C/D: +21 linked rows → 59/59 = 100% (if Hendry ArcGIS responds)
- hendry J + suwannee J: bid_decisions for newly-linked rows
- suwannee I: +21 enriched from RealTaxDeed + PA lookup

## Honesty Protocol Tags

- sarasota G blocker: **VERIFIED** (4th consecutive session confirming identical root cause)
- suwannee B/F blocker: **VERIFIED** (6th+ consecutive session)
- pasco/seminole/hendry root cause (new auctions): **INFERRED** from entry metrics vs prior session counts
- hendry F oscillation: **INFERRED** (process-of-elimination, prior session INFERRED)
- Expected outcomes from executor: **UNTESTED** (GHA not yet run at report time)

## SQL VERIFICATION (to be pasted after GHA completes)

```sql
-- Run via pencil_dod_evaluate_county per PARALLEL-FLEET RULES
SELECT public.pencil_dod_evaluate_county('sarasota');
SELECT public.pencil_dod_evaluate_county('seminole');
SELECT public.pencil_dod_evaluate_county('pasco');
SELECT public.pencil_dod_evaluate_county('suwannee');
SELECT public.pencil_dod_evaluate_county('hendry');

SELECT letter, county_slug, claim, survived, created_at
FROM public.gold_standard_ultraloop_audit
WHERE dispatch_id = '1338ab5d-c22a-43be-876f-887fb75417e7'
ORDER BY created_at DESC;
```

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|------|---------|--------|-----------|
| sarasota G | Fix pk1000 | Documented blocker (requires Ariel policy decision) | Policy blocker, 4th session confirming |
| seminole G | Add PUD-RES zone_standards | Executor deploys fix via GHA | None |
| seminole I | Add 1+ parcel row | Parity harvest via GHA | None |
| pasco C/D | Re-run parity scripts | Executor re-harvests NULL+mca_only | None |
| pasco I | Parcel enrichment | FL GIO ArcGIS via executor | None |
| suwannee B/F | Fix outcomes | Documented blocker (courthouse-steps) | Structural, 6th session confirming |
| suwannee I/J | Enrich new auctions | RealTaxDeed + bid_decisions via executor | None |
| hendry E/I/C/D/J | Parcel linkage | Hendry ArcGIS + parity harvest via executor | None |

## Next Session Priorities

1. **Hendry F**: Resolve case 25-100 oscillation (confirm with Hendry clerk whether 2026-07-30 re-listing is a stale preview page or a genuine re-notice; if stale, request Hendry's platform team to update)
2. **sarasota G**: Awaiting fleet policy decision from Ariel (pk1000 use-type-keyed ordinance)
3. **seminole I**: If still short at 130-131/137 after harvest, investigate the 2 network-timeout rows from prior session via fresh GIS probe
4. **pasco C/D**: If still below 95% after harvest, check for newly-added rows that postdate the harvest window
5. **suwannee B/F**: No action until (a) actual sale closes, (b) CAPTCHA bypass authorized, or (c) manual clerk records request approved
