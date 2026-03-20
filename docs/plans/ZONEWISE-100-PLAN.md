# ZONEWISE COMPLETION PLAN — Brevard 100% + Uniform Format

**Date:** 2026-03-20
**Author:** Claude AI Architect
**Executor:** Claude Code via SUMMIT dispatch
**Repo:** breverdbidder/cli-anything-biddeed

---

## CURRENT STATE (DB-Verified)

| Metric | Value |
|--------|-------|
| sample_properties (BCPAO) | 351,424 |
| zoning_assignments | 327,882 |
| Coverage | 93.3% |
| Gap | 23,542 parcels |

### Jurisdiction Comparison (BCPAO vs Zoning)

| Jurisdiction | BCPAO | Zoning | Delta | Status |
|-------------|-------|--------|-------|--------|
| Palm Bay | 78,697 | 78,660 | -37 | ✅ DONE |
| Melbourne | 62,134 | 51,508 | **-10,626** | ❌ GAP |
| Cocoa | 29,882 | 29,885 | +3 | ✅ DONE |
| Titusville | 21,995 | 28,126 | +6,131 | ⚠️ OVER |
| Rockledge | 17,869 | 17,873 | +4 | ✅ DONE |
| Cocoa Beach | 10,843 | 10,840 | -3 | ✅ DONE |
| West Melbourne | 10,365 | 11,331 | +966 | ⚠️ OVER |
| Satellite Beach | 8,524 | 8,525 | +1 | ✅ DONE |
| Cape Canaveral | 7,355 | 7,356 | +1 | ✅ DONE |
| Melbourne Beach | 7,337 | 7,337 | 0 | ✅ DONE |
| Indialantic | 5,205 | 5,207 | +2 | ✅ DONE |
| Indian Harbour Beach | 4,496 | 4,494 | -2 | ✅ DONE |
| Grant-Valkaria | 3,065 | 3,067 | +2 | ✅ DONE |
| Malabar | 1,430 | 1,431 | +1 | ✅ DONE |
| Melbourne Village | 1,001 | 318 | **-683** | ❌ GAP |
| Palm Shores | 433 | 433 | 0 | ✅ DONE |
| Unincorp. Brevard | 80,793 | 61,490* | **-19,303** | ❌ GAP |

*Unincorporated is fragmented across 6 jurisdiction values: `unincorporated` (29,397), `merritt_island` (20,335), `mims` (4,955), `barefoot_bay` (4,880), `micco` (1,897), `fellsmere` (26)

---

## PROBLEMS TO FIX

### P1: INCORPORATED GAPS (11,309 parcels)
1. **Melbourne: 10,626 missing** — GIS endpoint alive at `maps.mlbfl.org` (113K records). Previous `melbourne_fill_final.py` matched 51,508. Remaining parcels likely failed TaxAcct match. Need spatial join fallback.
2. **Melbourne Village: 683 missing** — No municipal GIS. Use USE_CODE crosswalk from BCPAO `sample_properties.use_code`.

### P2: UNINCORPORATED GAP (19,303 parcels)
- BCPAO has 80,793 unincorporated parcels
- Zoning has 61,490 across 6 sub-jurisdiction values
- No single GIS source for unincorporated Brevard zoning
- **Approach:** USE_CODE crosswalk for remaining 19,303

### P3: JURISDICTION FRAGMENTATION (22 values → 17 canonical)
Current zoning_assignments has 22 distinct jurisdiction values. BCPAO uses 17 canonical names. Need normalization:

| Current Value | Canonical BCPAO Name |
|--------------|---------------------|
| `unincorporated` | `unincorporated_brevard` |
| `merritt_island` | `unincorporated_brevard` |
| `mims` | `unincorporated_brevard` |
| `barefoot_bay` | `unincorporated_brevard` |
| `micco` | `unincorporated_brevard` |
| `fellsmere` | `unincorporated_brevard` |
| All others | Keep as-is (already match) |

### P4: OVER-COUNTED JURISDICTIONS
- **Titusville: +6,131 over BCPAO** — Likely includes Mims parcels or duplicates
- **West Melbourne: +966 over BCPAO** — Likely includes neighboring parcels from GIS overlap

### P5: ZONE CODE QUALITY
- Melbourne Village has USE descriptions as zone_codes (e.g., "TWO RESIDENTIAL UNITS - NOT ATTACHED")
- These should be normalized to standard codes (e.g., "R-2", "MFR") or at minimum flagged with `zone_source: "use_code_crosswalk"`

---

## EXECUTION PLAN (4 Phases)

### Phase 1: Melbourne Gap Fill (10,626 parcels)
**Script:** `scripts/melbourne_gap_fill_v2.py`
**Workflow:** `summit-melbourne-gap-v2.yml`

Algorithm:
1. Query `sample_properties` for Melbourne parcels (`jurisdiction_id=1`)
2. LEFT JOIN against `zoning_assignments` on `parcel_id`
3. Get list of parcel_ids with NO zoning match
4. For each missing parcel:
   a. Look up `tax_account` from `sample_properties`
   b. Query Melbourne GIS by TaxAcct (existing approach)
   c. If no GIS match: query by lat/lon spatial proximity (centroid from sample_properties.geometry)
   d. If still no match: USE_CODE crosswalk fallback
5. Upsert to `zoning_assignments` with `zone_source` field:
   - `"melbourne_gis"` for GIS matches
   - `"spatial_join"` for lat/lon matches  
   - `"use_code_crosswalk"` for fallback

**Since we can't do SQL JOINs via REST API, approach:**
1. Fetch all Melbourne parcel_ids from `sample_properties` (62,134)
2. Fetch all Melbourne parcel_ids from `zoning_assignments` (51,508)
3. Python set difference = missing parcel_ids
4. Process missing in batches

### Phase 2: Melbourne Village + Unincorporated Fill (19,986 parcels)
**Script:** `scripts/usecode_gap_fill_final.py`
**Workflow:** `summit-usecode-final.yml`

Algorithm:
1. Same set-difference approach for Melbourne Village (683) and unincorporated (19,303)
2. For each missing parcel_id:
   a. Get `use_code` from `sample_properties`
   b. Map via USE_CODE_MAP (already exists in `summit_gap_closer.py`)
   c. Upsert with `zone_source: "use_code_crosswalk"`

### Phase 3: Jurisdiction Normalization (SQL)
**Script:** `scripts/normalize_jurisdictions.py`
**Workflow:** `summit-normalize-jurisdictions.yml`

SQL operations via Supabase REST:
```sql
-- Merge sub-communities into unincorporated_brevard
UPDATE zoning_assignments 
SET jurisdiction = 'unincorporated_brevard'
WHERE jurisdiction IN ('unincorporated', 'merritt_island', 'mims', 'barefoot_bay', 'micco', 'fellsmere');

-- Add zone_source column if not exists
ALTER TABLE zoning_assignments ADD COLUMN IF NOT EXISTS zone_source TEXT;

-- Add zone_confidence column if not exists  
ALTER TABLE zoning_assignments ADD COLUMN IF NOT EXISTS zone_confidence TEXT;
```

### Phase 4: Dedup + Validate
**Script:** `scripts/dedup_and_validate.py`
**Workflow:** `summit-dedup-validate.yml`

1. Find duplicate parcel_ids in zoning_assignments
2. For duplicates: keep the entry with best zone_source priority (melbourne_gis > spatial > use_code_crosswalk)
3. For over-counted jurisdictions (Titusville, West Melbourne): identify parcel_ids NOT in sample_properties for that jurisdiction → either reassign or delete
4. Final COUNT(*) validation:
   - `zoning_assignments` should equal `sample_properties` (351,424)
   - Each jurisdiction count should match BCPAO ±5

---

## VERIFICATION QUERIES (NEVER-LIE COMPLIANCE)

After each phase, run and report:
```sql
-- Total coverage
SELECT COUNT(*) as total_zoning, 
       (SELECT COUNT(*) FROM sample_properties) as total_bcpao,
       ROUND(COUNT(*)::numeric / (SELECT COUNT(*) FROM sample_properties) * 100, 1) as pct
FROM zoning_assignments;

-- Per-jurisdiction comparison
SELECT sp.jurisdiction_name, sp.parcel_count as bcpao, 
       COALESCE(za.cnt, 0) as zoning,
       sp.parcel_count - COALESCE(za.cnt, 0) as gap
FROM (SELECT jurisdiction_id, jurisdiction_name, COUNT(*) as parcel_count 
      FROM sample_properties GROUP BY 1,2) sp
LEFT JOIN (SELECT jurisdiction, COUNT(*) as cnt 
           FROM zoning_assignments GROUP BY 1) za 
ON lower(replace(sp.jurisdiction_name, ' ', '_')) = za.jurisdiction
ORDER BY gap DESC;
```

---

## DISPATCH ORDER

1. `summit-melbourne-gap-v2.yml` (dispatch_event)
2. Wait for completion → verify Melbourne = 62,134
3. `summit-usecode-final.yml` (dispatch_event)
4. Wait → verify Melbourne Village = 1,001, unincorporated total = 80,793
5. `summit-normalize-jurisdictions.yml` (dispatch_event)
6. Wait → verify 17 canonical jurisdictions
7. `summit-dedup-validate.yml` (dispatch_event)
8. Final report: all jurisdictions match ±5 of BCPAO

---

## CONSTRAINTS

- **$10/session MAX** — All scripts use Supabase REST + Melbourne GIS (both free)
- **No Gemini/LLM calls needed** — Pure data operations
- **No Firecrawl needed** — Using existing GIS endpoint + USE_CODE crosswalk
- **Existing secrets available** — SUPABASE_URL, SUPABASE_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
- **NEVER-LIE:** Every phase MUST report COUNT(*) before AND after

---

## FILES TO CREATE

| File | Purpose |
|------|---------|
| `scripts/melbourne_gap_fill_v2.py` | Phase 1: Melbourne 10,626 gap |
| `scripts/usecode_gap_fill_final.py` | Phase 2: Melbourne Village + Unincorporated |
| `scripts/normalize_jurisdictions.py` | Phase 3: 22→17 jurisdiction names |
| `scripts/dedup_and_validate.py` | Phase 4: Dedup + final validation |
| `.github/workflows/summit-zonewise-100.yml` | Master workflow dispatching all 4 phases |
| `docs/plans/ZONEWISE-100-PLAN.md` | This plan (committed to repo) |
