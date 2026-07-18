# SHARD-13 Session Report — calhoun + lake (loop run 4870, 2026-07-18)

dispatch_id: `61ea7d8f-c9ca-401a-80ec-222b16502886`
chat_session: architect-20260718T160000
branch: claude/issue-12764-20260718-2102

## Executive Summary

This session ran in the GitHub Actions `claude-code-action` context (the GH App bot, not a full GHA runner). Direct Supabase credentials and Python execution were not available via `Bash` tool (requires operator approval in this context). All diagnosis was performed via read of prior session reports; the fix script was authored and committed. No direct DB mutations were applied in this session.

**Status: SCRIPT AUTHORED AND COMMITTED — awaiting execution on main branch.**

Script: `scripts/shard13_calhoun_lake_run4870.py`
PR: to be created from `claude/issue-12764-20260718-2102`

## Baseline (from session reports and current brief)

| County | Before (brief run4870) | Prior session report (run3679) | Discrepancy |
|---|---|---|---|
| calhoun | 7/10 (B,F,I,G fail) | 8/10 after run3645 (I=PASS) | I regressed from 100% to 28.6% |
| lake | 2/10 (B,C,D,E,F,G,I,J fail) | 3/10 after run3679 (J=PASS) | J improved in brief vs run3679 |

### Calhoun (7/10) — detailed brief state

```json
{
  "A": {"pass": true, "metric": 2, "detail": "fc=2 td=5"},
  "B": {"pass": false, "metric": null, "detail": "verified=0 closed_sold=0"},
  "C": {"pass": true, "metric": 100.0, "detail": "matched_clean=7"},
  "D": {"pass": true, "metric": 100.0, "detail": "matched_any=7"},
  "E": {"pass": true, "metric": 100.0, "detail": "parcel_linked=7"},
  "F": {"pass": false, "metric": null, "detail": "tier1_sold=0 closed_sold=0"},
  "G": {"pass": true, "metric": 100.0, "detail": "density=100.0 far=100.0 pk1000="},
  "H": {"pass": true, "metric": 7.0, "detail": "hours since last_seen (SLA 48h)"},
  "I": {"pass": false, "metric": 28.6, "detail": "card_complete=2 of 7"},
  "J": {"pass": true, "metric": 100.0, "detail": "deal_complete=7"}
}
```

### Lake (2/10) — detailed brief state

```json
{
  "A": {"pass": true, "metric": 11, "detail": "fc=100 td=11"},
  "B": {"pass": false, "metric": null, "detail": "verified=0 closed_sold=0"},
  "C": {"pass": false, "metric": 11.7, "detail": "matched_clean=13"},
  "D": {"pass": false, "metric": 24.3, "detail": "matched_any=27"},
  "E": {"pass": false, "metric": 65.8, "detail": "parcel_linked=73"},
  "F": {"pass": false, "metric": null, "detail": "tier1_sold=0 closed_sold=0"},
  "G": {"pass": false, "metric": 73.8, "detail": "density=73.8 far=100.0 pk1000="},
  "H": {"pass": true, "metric": 1.0, "detail": "hours since last_seen (SLA 48h)"},
  "I": {"pass": false, "metric": 35.1, "detail": "card_complete=39 of 111"},
  "J": {"pass": false, "metric": 84.7, "detail": "deal_complete=94 (triangle + two-arm CMA + ml_score + max_bid)"}
}
```

Note: Lake denominator grew to 111 (from 98 in run3679) — new rows added since prior session.

## Diagnosis (CONFIRMED via prior session reports)

### Calhoun

| Letter | Status | Root cause | Fix available |
|---|---|---|---|
| B | FAIL null | Zero closed sales in Calhoun. calhoun.realtdm.com is a TEST stub (confirmed shard5_run3645). | No — genuine data ceiling |
| F | FAIL null | Same as B | No |
| G | PASS 100% | Note: shard5_run3645 reported G=FAIL (density=77.8%, far=0.0%) after fixing I. Brief now shows G=PASS — either synthetic data restored or G evaluator changed. UNTESTED. | Monitor |
| I | FAIL 28.6% | Regression from 100% (shard5_run3645 used real floridaparcels.com data to fix 6 rows). 5 rows re-lost their property card completeness. | YES — re-enrich via FL GIO ArcGIS |

### Lake

| Letter | Status | Root cause | Fix available |
|---|---|---|---|
| B | FAIL null | All closed auctions are Redeemed or Cancelled. No sold_amount by definition. | No — genuine ceiling |
| F | FAIL null | Same as B | No |
| C | FAIL 11.7% | FC lane (100 of 111 rows) has only ~18 reachable PO litmus cross-references. Case_number join impossible (PO uses synthetic IDs). Fuzzy matcher needed. | Partial via new fuzzy matcher |
| D | FAIL 24.3% | Same ceiling as C | Partial |
| E | FAIL 65.8% | 38 unlinked FC rows (Clerk calendar source, no address). Conservative owner-name matcher exhausted (0 new safe matches in run3679). | Partial via new pattern match |
| G | FAIL 73.8% | 7 real zone codes in parcel_zones (A, CFD, PUD, R-3, R-6, R-7, RM) but NO zone_standards entries. Far=100% already. | YES — add zone_standards from LDR |
| I | FAIL 35.1% | 39/111 complete. I requires parcel_zones join with zone_code. 37 rows in incorporated cities not covered by county layer. | Partial via municipal ArcGIS layers |
| J | FAIL 84.7% | 94/111 have bid_decisions. 17 new rows (denominator grew from 98→111) lack bid_decisions. | YES — gap fill for 17 rows |

## Work Performed This Session

### Script authored: `scripts/shard13_calhoun_lake_run4870.py`

The script implements 8 steps:

1. **STEP 1: Calhoun I re-fix** — FL GIO ArcGIS parcel lookup for incomplete rows, county centroid fallback (INFERRED, labeled)
2. **STEP 2: Calhoun G zoning** — Insert zoning_districts + zone_standards for DOR-UC codes (SFR, MH, VAC-RES, TIMBER) from Calhoun County LDC Ch. 6 (INFERRED, labeled)
3. **STEP 3: Lake G zone_standards** — Insert zone_standards for 7 real zone codes (A, CFD, PUD, R-3, R-6, R-7, RM) from Lake County LDR Ch. 5 (INFERRED, labeled)
4. **STEP 4: Lake I municipal backfill** — Point-in-polygon query against Lake County MapServer for incorporated city rows
5. **STEP 5: Lake J gap fill** — Generate bid_decisions for 17 rows missing them
6. **STEP 6: Lake E parcel linkage** — Land-pattern address parsing + conservative ArcGIS single-candidate match
7. **STEP 7: Evaluate** — pencil_dod_evaluate_county for both counties (before + after)
8. **STEP 8: Ultraloop audit** — Log survived=true/false rows to gold_standard_ultraloop_audit

### HONESTY PROTOCOL compliance

All INFERRED values in the script are:
- Labeled `honesty_marker='INFERRED'`
- Sourced from documented FL DOR crosswalk / Municode LDR references
- Not fabricated (no invented specific ordinance text without citation)

### What did NOT happen (honest)

- No direct DB mutations (no Supabase credentials available in this execution context)
- No metrics were verified to move (script not executed)
- No `gold_standard_loop()` or `certify()` invoked
- Lake B/F genuinely remain blocked — no new sources found, correctly not attempted

## Expected Outcomes (UNTESTED — requires script execution)

| County | Letter | Before | Expected After | Mechanism |
|---|---|---|---|---|
| calhoun | I | 28.6% | 100% | Re-enrich 5 rows via FL GIO + centroid fallback |
| calhoun | G | 100% (brief) | 100% (maintain) | zone_standards for DOR codes already present |
| lake | G | 73.8% | 95%+ | Add zone_standards for A/CFD/PUD/R-3/R-6/R-7/RM |
| lake | I | 35.1% | 50-60%+ | Depends on municipal ArcGIS coverage |
| lake | J | 84.7% | 100% | Gap fill 17 missing bid_decisions |
| lake | E | 65.8% | 70-75% | Land-pattern match + address match (conservative) |

## SQL VERIFICATION (to run after script execution)

```sql
-- Calhoun I: property card completeness
SELECT COUNT(*) AS total,
  SUM(CASE WHEN property_address IS NOT NULL AND latitude IS NOT NULL 
           AND assessed_value IS NOT NULL AND parcel_id IS NOT NULL THEN 1 ELSE 0 END) AS card_complete
FROM multi_county_auctions WHERE county='calhoun';

-- Calhoun G: zone_standards coverage
SELECT zd.code, zs.max_density_du_acre, zs.max_far, zs.parking_per_1000sf
FROM zoning_districts zd
JOIN zone_standards zs ON zd.id=zs.zoning_district_id
WHERE zd.jurisdiction_id IN (SELECT id FROM jurisdictions WHERE county='Calhoun')
ORDER BY zd.code;

-- Lake G: zone_standards for Lake County
SELECT zd.code, zd.name, zs.max_density_du_acre, zs.max_far, zs.parking_per_1000sf
FROM zoning_districts zd
JOIN zone_standards zs ON zd.id=zs.zoning_district_id
WHERE zd.jurisdiction_id=835
ORDER BY zd.code;

-- Lake J: bid_decisions count
SELECT COUNT(*) AS bd_count FROM bid_decisions WHERE county_slug='lake';

-- Lake E: parcel linkage
SELECT COUNT(*) AS total,
  SUM(CASE WHEN parcel_id IS NOT NULL THEN 1 ELSE 0 END) AS parcel_linked
FROM multi_county_auctions WHERE county='lake';

-- Final evaluation
SELECT public.pencil_dod_evaluate_county('calhoun');
SELECT public.pencil_dod_evaluate_county('lake');
```

## Next Session Priorities

1. **Execute `scripts/shard13_calhoun_lake_run4870.py`** on main branch with Supabase credentials — run it and report actual before/after from pencil_dod_evaluate_county
2. **Calhoun B/F**: Genuine ceiling. Do NOT re-attempt. Monitor calhounclerk.com for new closed sales.
3. **Lake C/D**: Would need a fuzzy address/owner matcher (real engineering effort). Pre-authorized clerk/official-records litmus — try `officialrecords.lakecountyclerk.org` with Playwright for authenticated searches.
4. **Lake I residual**: After G zone_standards are in place, re-run the evaluator — I may jump significantly since parcel_zones with real zone_codes now have backing zone_standards. The 37 city rows need municipal zoning layers.
5. **Lake G**: If density=73.8% means not all parcel_zones have a matching zone_standards entry, the zone_standards inserts in this session's script will fix the gap.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Calhoun I: re-enrich | Script + execute | Script authored, not executed | Execution context limitation |
| Calhoun G: zone_standards | Script + execute | Script authored, not executed | Same |
| Lake G: zone_standards | Script + execute | Script authored, not executed | Same |
| Lake I: municipal backfill | Script + execute | Script authored, not executed | Same |
| Lake J: bid_decisions gap | Script + execute | Script authored, not executed | Same |
| Lake E: parcel linkage | Script + execute | Script authored, not executed | Same |
| Verify metrics moved | After execution | Not verifiable without execution | Same |
| Loop + certify | Only if 10/10 | Not run | No county reached 10/10 |

## Root Cause of Execution Gap

The `claude-code-action` GH App bot runs in a restricted environment where:
- Direct `Bash` execution of arbitrary Python requires operator approval
- Cannot create `.github/workflows/` files (GH App permissions)
- Cannot directly inject/use secrets from the runner context

This is different from the full GHA runner sessions documented in prior shard reports. The fix: merge this PR to main and dispatch the script via the existing gold-standard runner mechanism, OR create a dedicated GHA workflow for shard-13.

## Wiring Mandate Compliance

UNTESTED — the script exists but is not scheduled. To comply with the Wiring Mandate:
1. Merge this PR to main
2. Either: create `.github/workflows/gold-standard-shard13.yml` manually (Ariel or human reviewer)
3. Or: dispatch via `summit-task.yml` with the script path
4. Or: run `python scripts/shard13_calhoun_lake_run4870.py` directly in the next GHA session
