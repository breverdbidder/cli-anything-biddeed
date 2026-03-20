# ZONEWISE 67-COUNTY EXPANSION — Claude Code Handoff

**Date:** 2026-03-20
**Author:** Claude AI Architect (Opus session)
**Executor:** Claude Code autonomous sessions
**Priority:** P0 — Brevard 100% → Orange + Duval ingestion → Dashboard on zonewise.ai

---

## STRATEGIC DECISIONS (LOCKED)

1. **Dashboard location:** zonewise.ai (zonewise-web repo, Vercel Pro prj_EaXgEO6WDoSpCeLhuCemtbPr6e8E)
2. **Data strategy:** HYBRID — All three sources combined:
   - FL GIO Statewide Cadastral API (10.8M parcels, DOR_UC baseline for ALL 67)
   - County-specific GIS endpoints (real zoning codes, high confidence)
   - Firecrawl→Gemini→Claude waterfall (for municipalities without GIS)
3. **Data structure:** Mirror Brevard's proven `zoning_assignments` + `sample_properties` schema with `co_no` column
4. **Next counties:** Orange (CO_NO=48) + Duval (CO_NO=16) after Brevard hits 100%
5. **Brand:** House brand mandatory — Navy #1E3A5F, Orange #F59E0B, Inter font, bg #020617

---

## PHASE 0: BREVARD 100% COMPLETION (23,542 gap)

### Already committed to cli-anything-biddeed:
- `docs/plans/ZONEWISE-100-PLAN.md` — Full gap analysis
- `migrations/20260320_multi_county_schema.sql` — Multi-county schema
- `scripts/ingest_county.py` — FL GIO ingestion pipeline
- `.github/workflows/summit-ingest-county.yml` — GHA dispatch

### Tasks (execute in order):

#### 0A: Run multi-county migration
```bash
# Execute migration against Supabase
psql "$DATABASE_URL" -f migrations/20260320_multi_county_schema.sql
```
This creates: `fl_counties` (67 rows), `county_conquest_status`, `county_jurisdictions`, adds `co_no`/`zone_source`/`dor_uc` columns to `zoning_assignments`.

#### 0B: Melbourne Gap Fill (10,626 parcels)
**Script:** `scripts/melbourne_gap_fill_v2.py` (CREATE THIS)

Algorithm:
1. Fetch all Melbourne `parcel_id` from `sample_properties` WHERE `jurisdiction_id=1` (62,134)
2. Fetch all Melbourne `parcel_id` from `zoning_assignments` WHERE `jurisdiction=melbourne` (51,508)
3. Python set difference → ~10,626 missing parcel_ids
4. For each missing parcel:
   - Query Melbourne GIS: `https://maps.mlbfl.org/services/rest/services/AGOL/CommunityDevelopmentViewer_AGOL/MapServer/128`
   - Match by TaxAcct field
   - If no match: USE_CODE crosswalk fallback from `sample_properties.use_code`
5. Upsert to `zoning_assignments` with `zone_source='melbourne_gis'` or `'use_code_crosswalk'`
6. Report COUNT(*) before and after (NEVER-LIE)

**GIS endpoint confirmed alive:** 113,070 records, fields: TaxAcct, ZONE_ALL

#### 0C: Melbourne Village + Unincorporated Fill (19,986 parcels)
**Script:** `scripts/usecode_gap_fill_final.py` (CREATE THIS)

Algorithm:
1. Same set-difference for Melbourne Village (683 gap) and unincorporated subcommunities (19,303 gap)
2. Map `sample_properties.use_code` → zone_code via DOR_UC_MAP (already in `summit_gap_closer.py`)
3. Upsert with `zone_source='use_code_crosswalk'`

#### 0D: Jurisdiction Normalization
**Script:** `scripts/normalize_jurisdictions.py` (CREATE THIS)

```python
# Merge 6 sub-communities → unincorporated_brevard
REMAP = {
    'unincorporated': 'unincorporated_brevard',
    'merritt_island': 'unincorporated_brevard',
    'mims': 'unincorporated_brevard',
    'barefoot_bay': 'unincorporated_brevard',
    'micco': 'unincorporated_brevard',
    'fellsmere': 'unincorporated_brevard',
}
# Batch PATCH via Supabase REST for each old jurisdiction value
```

Result: 22 jurisdiction values → 17 canonical (matching BCPAO's `count_by_jurisdiction` RPC)

#### 0E: Dedup + Validate
**Script:** `scripts/dedup_and_validate.py` (CREATE THIS)

1. Find duplicate parcel_ids: keep best `zone_source` (gis > spatial > use_code_crosswalk)
2. Fix Titusville over-count (+6,131): identify parcel_ids not in `sample_properties` for that jurisdiction
3. Fix West Melbourne over-count (+966): same approach
4. Final validation: `zoning_assignments COUNT(*)` should match `sample_properties COUNT(*)` ±50

### 0F: Populate Brevard county_jurisdictions
After normalization, populate `county_jurisdictions` table for Brevard with final counts from both tables.

### Verification (MANDATORY — NEVER-LIE):
```sql
SELECT 'zoning_assignments' as tbl, COUNT(*) FROM zoning_assignments WHERE co_no = 5
UNION ALL
SELECT 'sample_properties', COUNT(*) FROM sample_properties WHERE co_no = 5;
```

---

## PHASE 1: DASHBOARD ON ZONEWISE.AI

### Architecture
The dashboard is a new page in `zonewise-web` (Next.js on Vercel Pro).

#### Files to create in zonewise-web:
```
app/conquest/page.tsx          — Main conquest dashboard page
app/conquest/[county]/page.tsx — County detail view (dynamic route)
components/conquest/           — Dashboard components
  CountyGrid.tsx
  CountyDetail.tsx
  JurisdictionTable.tsx
  StatsCard.tsx
  ConquestProgress.tsx
lib/conquest.ts                — Supabase queries for conquest data
```

#### Data flow:
```
Supabase (fl_counties + county_conquest_status + county_jurisdictions)
  ↓ Server-side fetch (Next.js RSC)
  ↓ 
Conquest Dashboard (zonewise.ai/conquest)
  ├── Statewide overview (67 county grid)
  ├── County drill-down (jurisdiction table)
  └── Real-time stats from DB
```

#### Key queries:
```typescript
// Statewide overview
const { data } = await supabase.rpc('get_county_dashboard')

// County detail
const { data } = await supabase.rpc('get_county_dashboard', { p_co_no: 48 })

// Live jurisdiction counts
const { count } = await supabase
  .from('zoning_assignments')
  .select('*', { count: 'exact', head: true })
  .eq('co_no', 48)
```

#### Brand compliance:
- Navy #1E3A5F primary
- Orange #F59E0B accent/CTA
- Background #020617 (slate-950)
- Font: Inter (already in zonewise-web globals.css)
- Follow BRAND_COLORS.md

#### Reference implementation:
The React artifact `/mnt/user-data/outputs/zonewise-67-dashboard.jsx` contains the full component logic, color system, county data, and interaction patterns. Port this to Next.js/TypeScript with server-side data fetching replacing the hardcoded arrays.

---

## PHASE 2: ORANGE + DUVAL INGESTION

### Orange County (CO_NO=48, Orlando metro, ~1.4M pop)
**Property Appraiser:** https://www.ocpafl.org
**Known GIS:** Orange County has a robust GIS portal

Steps:
1. Run `python ingest_county.py --county 48 --full` (DOR baseline)
2. Discover Orange County municipal GIS endpoints
3. Run Firecrawl→Gemini→Claude for municipalities without GIS
4. Upgrade `zone_confidence` from 'low' to 'high' as real zoning is matched

### Duval County (CO_NO=16, Jacksonville, ~1M pop)  
**Property Appraiser:** https://www.coj.net/departments/property-appraiser
**Known GIS:** Jacksonville has consolidated city-county government

Steps:
1. Run `python ingest_county.py --county 16 --full` (DOR baseline)
2. Jacksonville is consolidated → single GIS source for all parcels
3. Should be faster than Brevard (fewer jurisdictions)

### GHA workflow:
Already deployed: `summit-ingest-county.yml` — dispatch with county slug + mode (count/full)

---

## PHASE 3: SCALE TO 67

### Pipeline architecture (per county):
```
┌─────────────────────────────────────────────────┐
│ Stage 1: DOR Baseline (automated, $0)           │
│  FL GIO API → sample_properties + zoning_assign │
│  zone_source: 'dor_use_code'                    │
│  zone_confidence: 'low'                         │
├─────────────────────────────────────────────────┤
│ Stage 2: Municipal GIS Discovery (semi-auto)    │
│  Discover county/city ArcGIS endpoints          │
│  Map GIS fields → zone_code                     │
│  zone_source: 'gis'                             │
│  zone_confidence: 'high'                        │
├─────────────────────────────────────────────────┤
│ Stage 3: Firecrawl Upgrade (automated, $)       │
│  Firecrawl → Gemini Flash → Claude Sonnet       │
│  For municipalities without GIS                  │
│  zone_source: 'firecrawl'                       │
│  zone_confidence: 'medium'                      │
├─────────────────────────────────────────────────┤
│ Stage 4: Validation + Dashboard Update          │
│  COUNT(*) verification                           │
│  Refresh county_conquest_status                  │
│  Dashboard auto-updates from Supabase            │
└─────────────────────────────────────────────────┘
```

### Cost model:
- Stage 1: $0 (FL GIO API is free, Supabase on existing plan)
- Stage 2: $0 (county GIS endpoints are free public APIs)
- Stage 3: ~$1-5/county (Firecrawl + Gemini Flash)
- Total 67 counties: ~$100-300 one-time

### Parallel execution:
- Stage 1 can run for ALL 67 counties immediately
- Stage 2 requires per-county GIS discovery (prioritize by population)
- Stage 3 runs on-demand for gaps

---

## FILES ALREADY COMMITTED TO cli-anything-biddeed

| File | SHA | Purpose |
|------|-----|---------|
| `docs/plans/ZONEWISE-100-PLAN.md` | ec38960843 | Brevard completion plan |
| `docs/plans/ZONEWISE-67-EXPANSION.md` | THIS FILE | Multi-county expansion |
| `migrations/20260320_multi_county_schema.sql` | 9c5c6a7504 | DB migration (67 counties) |
| `scripts/ingest_county.py` | ea24b63fc0 | FL GIO ingestion pipeline |
| `.github/workflows/summit-ingest-county.yml` | 0daaa189dd | GHA dispatch workflow |

## FILES TO CREATE (Claude Code)

| File | Repo | Purpose |
|------|------|---------|
| `scripts/melbourne_gap_fill_v2.py` | cli-anything-biddeed | Phase 0B |
| `scripts/usecode_gap_fill_final.py` | cli-anything-biddeed | Phase 0C |
| `scripts/normalize_jurisdictions.py` | cli-anything-biddeed | Phase 0D |
| `scripts/dedup_and_validate.py` | cli-anything-biddeed | Phase 0E |
| `app/conquest/page.tsx` | zonewise-web | Dashboard page |
| `app/conquest/[county]/page.tsx` | zonewise-web | County detail |
| `components/conquest/*.tsx` | zonewise-web | UI components |
| `lib/conquest.ts` | zonewise-web | Data queries |

---

## EXECUTION ORDER FOR CLAUDE CODE

```
Session 1 (cli-anything-biddeed): Brevard 100%
  1. Run migration
  2. Execute Phase 0B-0E scripts
  3. Verify with COUNT(*)
  4. Push all scripts

Session 2 (zonewise-web): Dashboard
  1. Create conquest pages + components
  2. Wire to Supabase
  3. Deploy via existing deploy-prod workflow
  4. Verify at zonewise.ai/conquest

Session 3 (cli-anything-biddeed): Orange + Duval
  1. Dispatch ingest_county for Orange (count first, then full)
  2. Dispatch ingest_county for Duval
  3. Discover GIS endpoints for both counties
  4. Upgrade zone_confidence with real GIS data
```

---

## CONSTRAINTS

- **$10/session MAX** — All scripts use free APIs (FL GIO, county GIS, Supabase)
- **NEVER-LIE:** Every script MUST report COUNT(*) before AND after
- **ZERO-HITL:** No manual tasks for Ariel
- **HOUSE BRAND:** Navy/Orange/Inter on all dashboard UI
- **INFRA SSOT:** zonewise-web prj_EaXgEO6WDoSpCeLhuCemtbPr6e8E only
- **TODO.md Protocol:** Check TODO.md before each task
