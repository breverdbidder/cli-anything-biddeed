# GOLD STANDARD SHARD-10 — glades + gilchrist — dispatch b88eb871

session: architect-20260718T160000

## Status board (dispatched brief state)

| County | Before | Target | Notes |
|---|---|---|---|
| glades | 8/10 | 8/10 | C/D structurally blocked — confirmed do-not-retry this session |
| gilchrist | 6/10 | 10/10 | 1 new row arrived after run2820 (was 10/10 on 2026-07-04) |

## Diagnosis

### glades (8/10) — STRUCTURAL BLOCK, NOT RETRIED

C/D = 0% for glades has been confirmed structurally blocked across **5 consecutive sessions**:
- shard7 run1113 (2026-06-27)
- shard9 bootstrap+purge
- shard2 ghost-success purge
- shard8 run3713 (2026-07-11): explicitly confirmed "no RealAuction/PropertyOnion coverage; in-person-only foreclosures"
- shard12 dispatch 68e27f69 (2026-07-12): re-confirmed, Wayback self-litmus ruled out via CDX API test

The dispatch brief itself states: "Recommend this stops being re-investigated every session absent a genuinely new idea — it is costing session time for a repeatedly-confirmed dead end."

**Glades C/D is NOT re-investigated this session. No new lever exists.**

### gilchrist (6/10) — REGRESSION FROM 10/10

Prior session run2820 (2026-07-04) achieved 10/10 for gilchrist:
- C: 80.0% → 100.0% (1 stray unmatched row fixed via AJAX re-harvest)
- D: same
- I: 100.0%
- J: 100.0%

Current brief shows 6/10 with C=83.3%, D=83.3%, I=83.3%, J=83.3% — exactly 5/6 for each.
This means **1 new auction row arrived after run2820** (6 total now vs 5 previously).
The new row needs: parity matching (C/D) + property card enrichment (I) + bid_decision (J).

## Fix shipped

### Script: `scripts/shard10_gilchrist_cd_i_j_fix_b88eb871.py`

Three-phase fix:

1. **C/D AJAX harvest** — harvests all unique auction dates from `gilchrist.realforeclose.com` and `gilchrist.realtaxdeed.com` using the proven `shard2_run2450_ajax_realforeclose_harvest.py` AJAX mechanism (verified working for 15+ counties this campaign). Exact case_number match → PATCH `parity_status=matched_clean`, `parity_source=tier1:shard10_b88eb871_ajax_harvest`.

2. **I FL DOR enrichment** — queries FL DOR statewide cadastral FeatureServer (same pattern as `gold_standard_shard8_glades_i_enrichment.py` and `shard9_run3645_sumter_i_parcel_enrichment.py`) for rows missing lat/lon/assessed_value/market_value. Gilchrist CO_NO=31, city allowlist: Trenton, Bell, Fanning Springs, etc. BLANK>WRONG: rejected if city/CO_NO not on allowlist.

3. **J bid_decisions** — idempotent Shapira Formula insert (same shape as union/sumter/glades J generators). `COUNTY_DEFAULT_ARV=$130,000` (rural N. Florida county; Gilchrist is small population ~17K). `ML_SCORE=0.52`, `LOCATION_SCORE=0.40`, `CONFIDENCE_SCORE=0.55`. Only inserts rows whose case_number is not already in `bid_decisions`.

### Workflow: `.github/workflows/gold-standard-shard10-gilchrist-b88eb871.yml`

One-shot `workflow_dispatch` — runs the fix script then verifies via `pencil_dod_evaluate_county`.

### Migration: `supabase/migrations/20260718_shard10_gilchrist_cdij_b88eb871.sql`

Documents the session; live writes via Supabase REST.

## Expected outcome

```
gilchrist: 6/10 → 10/10
  C: 83.3% → 100.0%
  D: 83.3% → 100.0%
  I: 83.3% → 100.0% (1 row enriched)
  J: 83.3% → 100.0% (1 new bid_decision inserted)

glades: 8/10 (unchanged — C/D structural block)
```

## SQL VERIFICATION

To be populated after workflow execution. Trigger via:

```
gh workflow run gold-standard-shard10-gilchrist-b88eb871.yml --repo breverdbidder/cli-anything-biddeed
```

Expected output:
```sql
SELECT public.pencil_dod_evaluate_county('gilchrist');
-- gilchrist: 10/10 (C=100.0, D=100.0, I=100.0, J=100.0)

SELECT public.pencil_dod_evaluate_county('glades');
-- glades: 8/10 (C=0.0 structural, D=0.0 structural — unchanged)
```

## Deviation log

- glades C/D not retried (per repeated prior session recommendation + 5-session confirmation). Any future attempt requires a genuinely new lever not yet identified.
- This is a GHA-runner session — script was written and wired; actual execution against live DB happens via the `workflow_dispatch` trigger. Execution receipt will be in the GHA run log.

## Ultraloop audit

Script inserts 4 rows to `gold_standard_ultraloop_audit` (one per letter C/D/I/J) with `dispatch_id=b88eb871-...`, `ultraloop_mode=fallback`, `survived=<post-fix pass result>`.

## Residual / next-session priorities

1. **glades OUA district** (2 parcels, `zoning_districts.id=11768`) — retry when Municode 403 / elaws.us 503 clear. Does not block G at current 96.7%, but would complete it.
2. **glades I/J ultraloop_audit rows** are stale (>7 days). Should be refreshed before glades reaches 10/10 shot (C/D blocker first).
3. **gilchrist**: if 10/10 confirmed, run `gold_standard_certify()` in the next session after two consecutive daily 07:30Z confirmations.
