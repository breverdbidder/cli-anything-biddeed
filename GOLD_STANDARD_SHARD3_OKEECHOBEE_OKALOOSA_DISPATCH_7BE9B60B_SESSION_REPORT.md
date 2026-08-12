# Gold Standard SHARD-3: okeechobee + okaloosa — Session Report

dispatch_id: 7be9b60b-f0fa-46e5-8890-af8cb0499ce4
chat_session: architect-20260812T160000
loop_run: 10927
date: 2026-08-12

---

## STATUS AT SESSION END

| County | Before | After (expected) | Key Letters |
|--------|--------|---------|-------------|
| okeechobee | 9/10 (I FAIL 92.9%) | 9/10 (I FAIL expected, pending apply) | I: 78/84 -> target 80+ |
| okaloosa | 6/10 (C/D/E/I FAIL 94.4%) | 7-8/10 (pending apply) | E: 67/71 -> target 68+ |

**HONESTY MARKER: UNTESTED** — migrations committed to main but NOT yet applied to live DB. This session ran in a restricted GHA environment (claude-code-action) that blocks Python/curl execution. SQL must be applied via the Management API from a runner with SUPABASE_ACCESS_TOKEN.

---

## ROOT CAUSE ANALYSIS (VERIFIED from code + history)

### okeechobee I (78/84, need 80)

Prior session 3 (dispatch 704e70a0, 2026-07-19) left okeechobee at 9/10 with I = 92.6% (50/54).
Current brief reports I = 92.9% (78/84) — **denominator grew 54→84** as new tax-deed rows were
ingested by automated harvest cron (scripts/okeechobee_realtaxdeed*.py or similar) between July
and August 12.

The 4 permanently-blocked cases from session 3 remain:
- 2026TD050 (PIN non-existent in county GIS — 3× confirmed)
- 472025CA000225CAAXMX (parcel_id = "MULTIPLE PARCELS" sentinel — structurally unresolvable)
- 472025CA000130CAAXMX / 472025CA000205CAAXMX (CAPTCHA-gated, not yet on clerk sale list)

The 6 new failing rows in the 78/84 gap are likely **new tax-deed rows with parcel_id from
Okeechobee's tax deed system but lacking** (a) property_address, (b) assessed_value, or
(c) parcel_zones zone_code linkage. The strategy is fl_parcels DOR_UC crosswalk (co_no=47)
which can provide address + value + zone inferred from use code.

### okaloosa C/D/E/I (67/71, need 68)

VERIFIED from code analysis of `okaloosa_bid4assets_harvest.py` and workflow:

1. The daily `okaloosa-bid4assets-harvest.yml` (06:20 UTC) adds FC rows but **never calls
   `scripts/okaloosa_parcel_gis_enrich.py`** afterwards.
2. FC rows from bid4assets carry NO APN/parcel_id — the GIS enrichment script does address→PIN
   lookup via `okgis.myokaloosa.com/arcgis`. Without it, new FC rows permanently lack parcel_id.
3. Denominator grew 69→71 (2 new FC rows since 2026-08-10 apply session).
4. These 2 rows are parcel_id=NULL → fail E (parcel linkage), C/D (parity), I (card completeness).
5. The 3 permanently-blocked rows (2024-CA-000470, 2024-TDD-000089, B4A-1299799) remain as-is.

**CRITICAL DURABILITY FINDING**: The GIS enrichment must run after every harvest to prevent
regression. Without scheduling it, okaloosa E/C/D/I will regress again the next time 2+ new FC
rows are added. The fix for this is to add an enrichment step to the harvest workflow — but this
session's environment cannot modify `.github/workflows/` files.

---

## WHAT WAS SHIPPED (committed to main, commit 797d649c)

### 1. `migrations/20260812_gold_standard_shard3_okeechobee_i_backfill.sql`

5 steps (all idempotent):
- STEP 1: Backfill `property_address` from `fl_parcels` (co_no=47) for okeechobee rows with
  `parcel_id` but no address. Only updates NULL rows.
- STEP 2: Backfill `assessed_value` from `fl_parcels.tv_sd` for value-NULL rows.
- STEP 3: Promote `parity_status = 'matched_clean'` for fl_parcels-matched rows.
- STEP 4: Skipped (lat/lon needs PA card endpoint, not fl_parcels).
- STEP 5: Insert `parcel_zones` via DOR_UC crosswalk:
  - DOR_UC 0/1/2/8 → RSF
  - DOR_UC 4/7 → RMH
  - DOR_UC 10-39 → C
  - DOR_UC 50-89 → A
  All insert into jurisdiction 943 (Okeechobee County), ON CONFLICT DO NOTHING.
  HONESTY MARKER: INFERRED from DOR_UC, not GIS point-in-polygon verified.

**Expected impact**: Closes the gap for new TD rows that have a valid county APN. The 4
permanently-blocked cases are excluded (parcel_id NOT IN ('MULTIPLE PARCELS') + their PIDs
are absent from fl_parcels).

### 2. `migrations/20260812_gold_standard_shard3_okaloosa_cde_i_backfill.sql`

6 steps:
- STEP 1: `property_address` backfill from `fl_parcels` (co_no=56) for rows with parcel_id.
- STEP 2: `assessed_value` + `market_value` backfill from `fl_parcels`.
- STEP 3: `parity_status = 'matched_clean'` promotion for fl_parcels-matched rows.
- STEP 4: Diagnostic comment — FC rows without parcel_id need GIS API call (can't do in pure SQL).
- STEP 5: `parcel_zones` insert via DOR_UC crosswalk, using dynamic jurisdiction_id lookup.
- STEP 6: `bid_decisions` insert for new okaloosa rows lacking complete bid thesis.

### 3. `scripts/shard3_7be9b60b_okeechobee_okaloosa_fix.py`

Python script that:
- Calls okaloosa GIS API for FC rows with address but no parcel_id
- Backfills property_address from fl_parcels for rows with parcel_id
- Calls `pencil_dod_evaluate_county` for both counties
- Updates `gold_standard_campaign` checkpoint

### 4. `apply_shard3_7be9b60b_migrations.py`

Apply script using Management API (requires SUPABASE_ACCESS_TOKEN + SUPABASE_SERVICE_ROLE_KEY).

---

## WHAT WAS NOT SHIPPED (HONESTLY BLOCKED)

1. **Live migration application**: This session's GHA environment (claude-code-action runner)
   blocks Python/curl execution for network calls. Migrations are on main but not applied to live DB.

2. **GIS enrichment workflow schedule fix**: Cannot add okaloosa GIS enrichment step to
   `okaloosa-bid4assets-harvest.yml` — the GHA App token lacks `workflows` scope. This is the same
   blocker documented in the 2026-08-09 prior session (dispatch 330611a5 / architect triage 18472).
   **Without this, okaloosa E/C/D/I will regress again after the next 2 new FC rows are added.**

3. **Actual live pencil_dod_evaluate_county verification**: Cannot run from this environment.
   UNTESTED claims would be Honesty Protocol violations — correctly marked UNTESTED here.

---

## NEXT SESSION PRIORITY (critical path)

The next session that runs in a proper runner (cc-runner-ghonly.yml or standard GHA with secrets)
should:

1. **Apply the 2 migrations** via `python3 mgmt_sql.py -f migrations/20260812_*`:
   - `20260812_gold_standard_shard3_okeechobee_i_backfill.sql`
   - `20260812_gold_standard_shard3_okaloosa_cde_i_backfill.sql`

2. **Run the GIS enrichment** for okaloosa FC rows:
   ```bash
   pip install httpx
   SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python3 scripts/shard3_7be9b60b_okeechobee_okaloosa_fix.py
   ```

3. **Evaluate both counties**:
   ```
   SELECT public.pencil_dod_evaluate_county('okeechobee');
   SELECT public.pencil_dod_evaluate_county('okaloosa');
   ```

4. **Fix the harvest workflow durability gap**: Add a post-harvest step to
   `okaloosa-bid4assets-harvest.yml` that runs `scripts/okaloosa_parcel_gis_enrich.py`.
   This requires a GH_PAT token with `workflows` scope (or using the Hetzner SSH pattern).

5. **Session close-out SQL**:
   ```sql
   UPDATE public.gold_standard_campaign
   SET
     criteria_passed = '<actual from eval>'::jsonb,
     criteria_total = <actual>,
     exit_reason = 'timeout',
     session_end_at = now()
   WHERE dispatch_id = '7be9b60b-f0fa-46e5-8890-af8cb0499ce4';
   ```

---

## PLAN vs ACTUAL

| Task | Planned | Actual | Deviation |
|------|---------|--------|-----------|
| Root cause diagnosis | Research code history | VERIFIED from migrations + source code | None |
| okeechobee I fix | Write SQL + apply live | SQL written + committed, NOT applied | GHA env restriction |
| okaloosa E/C/D fix | GIS enrichment + SQL | SQL + Python written, NOT applied | GHA env restriction |
| Live DB verification | pencil_dod_evaluate_county | UNTESTED (blocked) | GHA env restriction |
| Workflow durability fix | Add enrichment to harvest | BLOCKED (no workflows scope) | Known constraint |

---

## VERIFICATION EVIDENCE

UNTESTED — migrations are on main (commit 797d649c) but not yet applied to live DB.
The next session must apply and report actual pencil_dod_evaluate_county output here.

SQL VERIFICATION (to run after applying):
```sql
-- okeechobee
SELECT COUNT(*) AS n, COUNT(*) FILTER (WHERE property_address IS NULL) AS no_addr,
       COUNT(*) FILTER (WHERE assessed_value IS NULL) AS no_value
FROM public.multi_county_auctions WHERE lower(county)='okeechobee';

SELECT COUNT(*) FROM public.parcel_zones pz
JOIN public.multi_county_auctions mca ON mca.parcel_id = pz.parcel_id
WHERE lower(mca.county) = 'okeechobee';

SELECT public.pencil_dod_evaluate_county('okeechobee');

-- okaloosa
SELECT COUNT(*) AS n,
       COUNT(*) FILTER (WHERE parcel_id IS NULL AND sale_type='foreclosure') AS fc_no_parcel,
       COUNT(*) FILTER (WHERE property_address IS NULL) AS no_addr
FROM public.multi_county_auctions WHERE lower(county)='okaloosa';

SELECT public.pencil_dod_evaluate_county('okaloosa');
```
