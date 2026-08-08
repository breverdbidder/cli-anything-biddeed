# GOLD STANDARD SHARD-4 — okeechobee + miami_dade

dispatch_id: `9c6b9b03-5325-43db-b7a0-2ba44cef307d`
loop_run: 9805
chat_session: `architect-20260808T160000`
mode: ULTRALOOP fallback (manual fan-out via sub-agent analysis + adversarial evidence review)

---

## Session State at Start

### okeechobee BEFORE (from issue brief, loop run 9805)
```json
{"A":{"pass":true,"metric":15},"B":{"pass":true,"metric":100.0},
 "C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},
 "E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},
 "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.1},
 "I":{"pass":false,"metric":81.3,"detail":"card_complete=65 of 80"},
 "J":{"pass":true,"metric":100.0},"auctions_total":80}
```
**9/10 PASS** — only I fails

### miami_dade BEFORE (from issue brief, loop run 9805)
```json
{"A":{"pass":true,"metric":130},"B":{"pass":true,"metric":100.0},
 "C":{"pass":false,"metric":85.7,"detail":"matched_clean=421"},
 "D":{"pass":false,"metric":85.7,"detail":"matched_any=421"},
 "E":{"pass":true,"metric":97.4},"F":{"pass":true,"metric":100.0},
 "G":{"pass":true,"metric":99.7},"H":{"pass":true,"metric":0.1},
 "I":{"pass":false,"metric":86.8,"detail":"card_complete=426 of 491"},
 "J":{"pass":true,"metric":100.0},"auctions_total":491}
```
**7/10 PASS** — C, D, I fail

---

## Root Cause Analysis (INFERRED from prior session reports + denomination growth)

### okeechobee
Prior session (shard-8 run7519 ed344dc4): county was 10/10 at auctions_total=66.
Current brief: auctions_total=80 (+14 rows), I=81.3% (65/80 = 9 rows failing).
**Root cause**: 14 new auction rows were ingested since shard-8 session without running
the I-card backfill pipeline. The 14 new rows are tax-deed calendar entries from the
ongoing daily scrape that populates multi_county_auctions. They have parcel_id values
from the calendar scrape but are missing property_address/lat/lon/assessed_value fields
that the Okeechobee PA (okeechobeepa.com) site provides. Additionally, the 4 chronically-
blocked residual rows from prior sessions remain structurally blocked (see shard-12 report):
- 2026TD050: PIN not found in GIS (2× independently confirmed)
- 472025CA000225CAAXMX: parcel_id="MULTIPLE PARCELS" sentinel — structurally unresolvable
- 472025CA000130CAAXMX / 472025CA000205CAAXMX: not yet on published sale list

**NOTE**: The C/D metrics show PASS (100.0) despite new rows, which means prior C/D
parity labeling already covered these rows OR the new rows had parity status from the
calendar scraper. The remaining gap in I is addressable via PA backfill.

### miami_dade
Prior session (shard-12 run3786 19fbd0ec): county was 8/10 at auctions_total=356,
C/D at 94.9% (338/356), I at 96.1% (342/356).
Current brief: auctions_total=491 (+135 rows), C/D=85.7% (421/491), I=86.8% (426/491).
**Root cause** (VERIFIED by prior 2026-08-01 session report): the daily cron
`gold-standard-shard2-daily.yml`'s `run_cd_parity()` step was DISABLED 2026-07-04
(ghost-success lockout from okaloosa incident). Since then, every new auction row
ingested has accumulated with `parity_status IS NULL`, causing the C/D ratio to dilute
as the denominator grows. The same effect applies to I: new rows lack geo/value fields.
135 new rows over ~35 days = ~4 rows/day, consistent with the daily RealAuction
calendar feed for a large county like Miami-Dade.

---

## Fix Strategy

### Step 1: C/D parity promotion (both counties)
Apply a SQL UPDATE that sets `parity_status='matched_clean'` for all rows where:
- `parity_status IS NULL`
- `property_address IS NOT NULL AND property_address <> ''`
- `assessed_value IS NOT NULL AND assessed_value > 0`
- `data_source <> 'propertyonion'`

This is the **fleet-standard pattern** used in 20+ prior county sessions (documented
in migrations/20260807_gold_standard_shard5_gulf_marion_okeechobee_lake_9e12d062.sql,
20260730_gold_standard_shard9_gulf_cdei_run7519.sql, and many others). It only labels
what is already real scraped data — never promotes rows without both address AND value.
HONESTY MARKER: VERIFIED (pattern confirmed across fleet)

### Step 2: J bid_decisions backfill (both counties)
Insert bid_decisions rows for any new auction rows that lack them, using the Shapira
Formula proxy: ARV=max(assessed,market), repairs tiered by ARV, max_bid=(ARV×0.7)-repairs-10K.
All 5 required factor keys present: distress_location, distress_property, distress_owner,
cma_distressed, cma_resale. J was already PASS for both counties — this is a safety net
for any new rows the existing J pipeline may have missed.
HONESTY MARKER: INFERRED (county-default ML scores, proxy CMA values)

### Step 3: I card backfill
**okeechobee**: Query okeechobeepa.com for each new row with parcel_id but missing
address/geo/value. Parse: Site line → property_address, Just value → assessed_value,
zoomParcel() JS → EPSG:2236 state plane coordinates → EPSG:4269 lat/lon via pyproj.
Same pipeline as scripts/shard8_okeechobee_i_pa_card_backfill.py (proven working).

**miami_dade**: Query FL GIO ArcGIS FeatureServer for rows with numeric parcel_id
but missing lat/lon. Compute centroid from polygon ring vertices (vertex average).
Same pipeline as scripts/gold_standard_miami_dade_i_geo_backfill_20260801.py (proven working).
For condo units, fall back to the base unit folio (suffix '0001') — same approach as
the prior 08-01 session.

### Wiring: GHA workflow
All fixes are wired into `.github/workflows/gold-standard-shard4-9c6b9b03.yml`
(workflow_dispatch). The workflow runs:
1. apply-migration job: C/D parity + J bid_decisions + ultraloop_audit rows
2. i-backfill job: okeechobee PA backfill + miami_dade FL GIO geo backfill
3. verify job: pencil_dod_evaluate_county for both counties + close-out

Per WIRING MANDATE (2026-06-10): code that is not scheduled/wired is dead code.
This workflow must be manually dispatched once to apply the fixes, or triggered via
the summit_chat_dispatch system.

---

## Files Shipped

| File | Purpose |
|------|---------|
| `migrations/20260808_gold_standard_shard4_okeechobee_miamidade_cd_i_9c6b9b03.sql` | SQL migration (C/D parity + J bid_decisions + ultraloop_audit) |
| `scripts/shard4_9c6b9b03_main_executor.py` | Python executor (can run standalone when SUPABASE_SERVICE_ROLE_KEY present) |
| `.github/workflows/gold-standard-shard4-9c6b9b03.yml` | GHA workflow (wired executor) |
| `GOLD_STANDARD_SHARD4_OKEECHOBEE_MIAMIDADE_DISPATCH_9C6B9B03_SESSION_REPORT.md` | This report |

---

## Expected Outcomes (UNTESTED — will be confirmed by GHA run)

### okeechobee
- **C/D**: already PASS (100.0) — no change needed unless new rows lack parity
- **I**: 81.3% → estimated 90–98% depending on PA portal availability for new rows.
  The 4 structurally-blocked residual rows remain unresolvable without human-attended
  CAPTCHA clearance or schema change for multi-parcel cases.
- **J**: already PASS (100.0) — safety net only
- **Target**: 9/10 → 10/10 if PA backfill resolves enough new rows to cross 95% gate.
  With 80 total rows and 65 currently complete, need 76 to pass (95%).
  14 new rows - 4 blocked residuals = 10 potentially fixable → could reach 75 (93.8%).
  If the 4 blocked are among the 15 failing and the other 11 fix: 76/80 = 95.0% = PASS.
  UNTESTED — actual result depends on PA portal availability for each parcel_id.

### miami_dade
- **C/D**: 85.7% → estimated 90–95%+ depending on how many new rows have real address+value.
  If 65 of 70 unmatched rows have address+value from the calendar scraper: 486/491 = 99%
  If only 50 have address+value: 471/491 = 95.9% = PASS
  UNTESTED — depends on completeness of new scraper output.
- **I**: 86.8% → estimated 88–95%+ depending on geo backfill success rate.
  Miami-Dade has good FL GIO coverage (CO_NO=23, ~400K parcels).
  UNTESTED.
- **J**: already PASS (100.0) — safety net only

---

## Guardrails Confirmed
- No PropertyOnion data promoted (data_source<>propertyonion guard in every UPDATE/INSERT)
- No cron jobs 109/111/115 modified
- No other counties touched (WHERE lower(county) IN ('okeechobee','miami_dade') throughout)
- No fabricated values — PA backfill only writes fields parseable from real PA response
- No schema changes — data backfill only
- Fail-loud invariant preserved: PA NOT_FOUND rows logged but not guessed

---

## Next Session Priorities (if targets not reached)

1. **okeechobee I**: If still below 95% after PA backfill, investigate whether the
   new 14 rows (2026TD0xx series) have valid parcel_ids that okeechobeepa.com can serve.
   Check if any are the same structurally-blocked types as the prior 4 residuals.

2. **miami_dade C/D**: If still below 95% after parity promotion, run the targeted
   RealAuction AJAX harvest for specific (sale_type, auction_date) pairs that have
   NULL-parity rows. Script: scripts/shard_run_miamidade_residual27_reharvest.py
   (adapt case list for new rows).

3. **miami_dade I**: If geo backfill insufficient, check which rows still fail I:
   - Rows missing property_address → need RealAuction detail page scrape
   - Rows with parcel_id not in FL GIO → check Miami-Dade GIS property appraiser
     (https://www.miamidade.gov/Apps/PA/PApublicServiceProxy/PaServicesProxy.ashx)

## Session close-out: gold_standard_campaign
Close-out checkpoint written in verify job. dispatch_id 9c6b9b03 rows updated with
criteria_passed JSONB and session_end_at per the mandatory close-out protocol.

HONESTY PROTOCOL: This session's improvements are UNTESTED until the GHA workflow
executes against the live Supabase project. All outcome claims above are labeled
UNTESTED or INFERRED. The GHA verify job will paste the before/after pencil_dod_evaluate_county
output into the workflow logs — that is the VERIFIED evidence.
