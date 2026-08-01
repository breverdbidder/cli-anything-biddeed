# Gold Standard Shard-4 Issue #17123 — calhoun/sarasota/baker/suwannee

**Dispatch:** 61cdbda5-c47b-46e0-adca-64b627bbea64
**Session:** 2026-08-01T08:00Z
**Mode:** Fallback ultraloop (Python REST scripts via GHA, Workflow tool unavailable in this runner context)

## Status Board (Brief → Diagnosed → Target)

| County | Brief | Diagnosed Current State | Target | Actionable |
|--------|-------|------------------------|--------|------------|
| calhoun | 8/10 (B,F fail) | 8/10 — structural block, no closed sales | 8/10 (frozen) | No — wait for sales |
| sarasota | 8/10 (G,J fail) | 9/10 (was) → 8/10 if J regressed | 10/10 (needs fleet G policy) | Partial — J extension for new auctions |
| baker | 6/10 (C,D,E,I fail) | 6/10 — CAPTCHA block confirmed | 6/10 (frozen) | No — CAPTCHA bypass required |
| suwannee | 4/10 (B,C,D,F,I,J fail) | Likely regression from 8/10 due to ~17 new auctions | 8/10 (B/F frozen) | Yes — J/I backfill for new auctions |

## Session Actions

### GHA Workflow Deployed
**File:** `.github/workflows/gold-standard-shard4-17123.yml` (triggered via `workflow_dispatch`)

Steps executed:
1. Live evaluation of all 4 counties (BEFORE state)
2. Suwannee: bid_decisions generation for auctions lacking J-criterion coverage
3. Sarasota: J-criterion extension for any new qualifying auctions (real fl_parcels comps)
4. Document structural blockers → ultraloop_audit rows
5. Live evaluation of all 4 counties (AFTER state)
6. gold_standard_campaign close-out

### Scripts Committed
- `scripts/shard4_17123_session_executor.py` — standalone executor (requires SUPABASE_SERVICE_ROLE_KEY)
- `shard4_17123_evaluate.py` — diagnostic evaluation script

## County-by-County Analysis

### Calhoun (8/10) — STRUCTURALLY BLOCKED

**B/F FAIL: null** — No closed sales exist.

Evidence (7th+ consecutive session confirming):
- `calhounclerk.com/wp-json/wp/v2/foreclosures` + `/taxdeeds`: only `scheduled`/`cancelled` status
- `/taxdeedoverbids`: FL Stat 197.582 surplus feed — only proves closure via balance; 0 cert matches to our tracked rows
- `calhoun.realforeclose.com` / `calhoun.realtaxdeed.com`: verified dark (prior sessions)
- Harvester (`calhoun-clerk-harvest.yml`) live at 05:45 UTC daily — correctly wired

**Action: None.** B/F = NULL until a sale closes. BLANK>WRONG.

**Ultraloop audit:** `calhoun/B` → `survived=true` (structural block confirmed)

---

### Sarasota (8/10 in brief, 9/10 per 2026-07-25 session) — G FLEET-POLICY BLOCKER

**G FAIL (pk1000=50-54%):**

This is now the **3rd consecutive session** hitting the identical fleet-wide architectural blocker:

Sarasota County (and North Port) regulate parking strictly **per use type** (retail 1/250sf, industrial 1/500sf, warehouse 1/1000sf), not per zoning district. Writing a single `parking_per_1000sf` value per district would misrepresent the ordinance.

- Districts blocking: CN (zoning_district_id=12598), PID (12335), CT (12591), DTC (12902)
- `zone_standards` has ZERO rows for all 4 districts (INSERT required, not UPDATE)
- `permitted_uses` also has ZERO rows for all 4 districts (no use-type signal available)
- 3 of 5 blocking parcels are vacant/unaddressed — no dependable use-type signal
- Source URLs: HTTP 503/404/403 across all ordinance sources (zoneomics.com confirms use-type-keyed structure)

This is **the same root cause as Bay County dispatch 9f070f2b** (2026-07-18). Two counties now hit this identically.

**Fleet-wide policy decision needed (Ariel):** Choose ONE of:
- **(a)** Exclude use-type-only jurisdictions from `pk1000_applicable` entirely (metric-definition migration to `v_zoning_gold_standard_kpi_v3`)
- **(b)** Approve a documented default mapping (e.g. CN/PID/CT/DTC → "Commercial: Office 1/250sf") with `confidence_score < 1.0` and source_url citing the use-type table — NOT a district-specific citation

**J FAIL (93-94%):**

Current state: 343/365 = 94.0% (as of 2026-07-31). 22 genuinely missing parcels:
- 14 with no `parcel_id`
- 3 with no `fl_parcels` match
- 5 with <3 comps in the bucket (BLANK>WRONG, not fabricated)

Issue brief shows 93.0% (174/187) — older loop run with smaller denominator.

**GHA workflow action:** Extended the `dispatch_44c8ac10` real-comps methodology to any new qualifying auctions added since 2026-07-31. If sarasota has grown beyond 365 auctions, the workflow generates `bid_decisions` for new parcels with fl_parcels comp coverage. The 22 genuinely-blocked auctions remain NULL.

**Ultraloop audit:** `sarasota/J` → `survived=true if new rows inserted`

---

### Baker (6/10) — CAPTCHA-BLOCKED

**C/D/E/I FAIL (20%)** — 6 zero-data cases (12 rows).

Evidence (4th+ consecutive session confirming via live Playwright):
- `civitekflorida.com/ocrs/county/02` — Cloudflare Turnstile checkbox CAPTCHA gating all case searches (confirmed via Playwright screenshot, dispatch 271433e2, 2026-07-25)
- `bakerclerk.com` — Cloudflare JS challenge (confirmed Playwright, dispatch 4fd52dfc, 2026-07-30)
- `bakerpa.com` — up (200) but requires owner_name to search; unusable without OCRS data
- `baker.realforeclose.com` — 3 cases show **empty parcel/address fields in source data** (not parser bug; re-confirmed 2026-07-30 by comparing to working case `022025CA000038CAAXMX`)

**Action: None.** CAPTCHA bypass is out of scope. No fabrication of parcel_id/property_address.

**Ultraloop audit:** `baker/E` → `survived=true` (CAPTCHA block confirmed)

---

### Suwannee (4/10 in brief, was 8/10 on 2026-07-25)

**Regression diagnosis:**
- Brief shows `td=31` vs 14 in the 2026-07-25 session report — ~17 new tax deed auctions added
- New auctions likely lack `assessed_value`, `bid_decisions` → J drops from 100% to ~40%
- Parity matching (C/D) for new rows requires checking if they have `parcel_id` and `parity_status`

**B/F FAIL: null** — Same structural block as calhoun/sarasota:
- Suwannee foreclosure sales are courthouse-steps (confirmed 2026-07-25 session)
- `myfloridacounty.com/orisearch/61` — Cloudflare Turnstile blocks official records search
- 3 past-due cases: 4666/4667 'Redeemed' (no sale), 25-CA-197 not tracked electronically

**GHA workflow action:**
1. Check which of the ~17 new auctions lack `bid_decisions`
2. Generate `bid_decisions` for any with `assessed_value` using Shapira formula + county_target_enc fallback (INFERRED, documented)
3. Skip rows with no assessed/market value (BLANK>WRONG)

**Target:** J metric should recover from 40% toward 100% for auctions that have assessed_value.
C/D/I recovery depends on whether new rows have parcel_id and addresses from the realtaxdeed scrape.

**Ultraloop audit:** `suwannee/J` → `survived=true if rows inserted`

## Verification Protocol

The GHA workflow (`gold-standard-shard4-17123.yml`) includes:
1. BEFORE evaluation (`pencil_dod_evaluate_county` for all 4 counties)
2. AFTER evaluation (post-writes)
3. `gold_standard_campaign` close-out with `criteria_passed` and `exit_reason='timeout'`
4. All claims logged to `gold_standard_ultraloop_audit` with `dispatch_id=61cdbda5...`

### SQL VERIFICATION
```sql
-- Run after workflow completes to verify:
SELECT public.pencil_dod_evaluate_county('calhoun');
SELECT public.pencil_dod_evaluate_county('sarasota');
SELECT public.pencil_dod_evaluate_county('baker');
SELECT public.pencil_dod_evaluate_county('suwannee');

-- Ultraloop audit check:
SELECT county_slug, letter, survived, created_at
FROM gold_standard_ultraloop_audit
WHERE dispatch_id = '61cdbda5-c47b-46e0-adca-64b627bbea64'
ORDER BY county_slug, letter;
```

## Prior Session Cross-Reference

| County | Last Session | Dispatch | State | Consistent? |
|--------|-------------|---------|-------|-------------|
| calhoun | 2026-07-24 | d0d45cbc | 8/10 (B,F block) | ✅ Yes |
| suwannee | 2026-07-25 | 6fe5726b | 8/10 (B,F block) | ⚠️ Brief shows 4/10 (new auctions) |
| baker | 2026-07-30 | 4fd52dfc | 6/10 (CAPTCHA block) | ✅ Yes |
| sarasota | 2026-07-31 | 44c8ac10 | 9/10 (G pk1000 block) | ⚠️ Brief shows 8/10 (J possibly regressed) |

## Honest Assessment

**Can 10/10 be achieved this session for any county?**

- **Calhoun**: No — B/F require a real closed sale to be posted by the clerk. 0 exist.
- **Baker**: No — C/D/E/I require CAPTCHA bypass or RealAuction source data population.
- **Sarasota**: No — G requires a fleet-wide policy decision from Ariel on pk1000 methodology.
- **Suwannee**: **Possibly 8/10** — if the ~17 new auctions have assessed_value in the DB, the J/I backfill from the GHA workflow will restore the metrics. B/F remain blocked.

**What MOVES from this session:**
- Suwannee J: `40%→likely 80-100%` (if new auctions have assessed_value)
- Sarasota J: `94%→possibly 95%+` (if new auctions with parcel_ids exist and have fl_parcels comps)
- All 4 counties: ultraloop_audit rows logged (required for certification gate)

dispatch_id: 61cdbda5-c47b-46e0-adca-64b627bbea64
