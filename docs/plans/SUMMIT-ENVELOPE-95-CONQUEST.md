# SUMMIT DISPATCH: Brevard Envelope Conquest → 95%

**Date:** 2026-03-23
**Priority:** P0
**Owner:** Claude Code (autonomous)
**Escalation:** Telegram → Ariel only if blocked after 3 retries

---

## Objective

Bring ALL 11 Brevard envelopes to ≥95% parcel coverage. Current: 246,386/361,733 (68.1%). Target: 343,646/361,733 (95%).

**Gap: ~97,260 parcels across 7 envelopes.**

---

## Current State

| # | Envelope | Have | Need@95% | Gap | Status |
|---|----------|------|----------|-----|--------|
| 27 | unincorporated_27 | 37,016 | 37,478 | **462** | P0 |
| 25 | melbourne | 26,710 | 30,854 | **4,144** | P1 |
| 23 | rockledge | 11,597 | 18,871 | **7,274** | P2 |
| 30 | unincorporated_30 | 4,107 | 11,210 | **7,103** | P2 |
| 21 | titusville | 6,450 | 15,647 | **9,197** | P3 |
| 29 | palm_bay_29 | 42,496 | 56,791 | **14,295** | P3 |
| 22 | cocoa | 15,341 | 35,354 | **20,013** | P4 |
| 24 | cocoa_beach | 3,556 | 38,473 | **34,917** | P4-INVESTIGATE |
| 20 | satellite_beach | 3,789 | 3,778 | 0 | ✅ DONE |
| 26 | palm_bay | 35,739 | 35,436 | 0 | ✅ DONE |
| 28 | unincorporated_28 | 59,585 | 59,754 | 0 | ✅ DONE |

---

## Execution Order: Sequential P0 → P4

### PHASE 0: Investigation (Before Conquest)

**Task 0A — Cocoa Beach Parcel Audit**

Envelope 24 reports 40,498 total parcels but Cocoa Beach city only has ~10,843 parcels.

```yaml
investigate:
  - query: "SELECT COUNT(*), city FROM zoning_assignments WHERE envelope_id = 24 GROUP BY city"
  - query: "SELECT COUNT(*) FROM bcpao_parcels WHERE CITY = 'COCOA BEACH'"
  - check: Does envelope 24 include Cape Canaveral, Patrick SFB, unincorporated barrier island?
  - check: Are parcels double-counted across envelopes?
expected_outcome: Determine TRUE parcel universe for envelope 24
```

**Task 0B — Cocoa Beach GIS Endpoint Discovery**

Previous attempts: NOT_FOUND. No public zoning feature service.

```yaml
try_in_order:
  1_agol_search:
    url: "https://www.arcgis.com/sharing/rest/search?q=cocoa+beach+florida+zoning&f=json&num=20"
    pattern: Same approach that cracked Cocoa and Rockledge
  2_city_gis_portal:
    url: "https://www.cityofcocoabeach.com"
    search: GIS, maps, zoning map, interactive map
    tool: Firecrawl if needed
  3_brevard_county_flu:
    url: "https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0"
    note: County zoning layer has 10,096 features — may cover Cocoa Beach
    query: Point query sample Cocoa Beach parcel centroids against county layer
  4_use_code_extension:
    note: BCPAO USE_CODE mapping as last resort
    source: Previous USE_CODE→zone_code mapping table used for 90% benchmark
fallback: USE_CODE + county FLU overlay = likely sufficient for 95%
```

**Report investigation findings to Telegram before proceeding.**

---

### PHASE 1: P0 — unincorporated_27 (Gap: 462 parcels)

```yaml
strategy: Top-up query against county zoning layer
endpoint: https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0
method: BCPAO centroids → spatial intersect → Supabase upsert
batch_size: 500
expected_time: 15 minutes
success_criteria: 37,478+ parcels (≥95%)
```

---

### PHASE 2: P1 — melbourne (Gap: 4,144 parcels)

```yaml
strategy: Continue centroid queries against Melbourne GIS
known_issue: Melbourne has tile service only (tiles.arcgis.com), feature service needed
investigate_first:
  - Check if V5B conquest from Mar 17 completed Melbourne
  - Query Supabase for actual melbourne parcel_zones count
  - If feature service still missing, use county zoning layer + USE_CODE
endpoint_options:
  - tiles.arcgis.com Melbourne zoning (if feature service found)
  - County zoning layer (fallback)
  - USE_CODE mapping (last resort)
expected_time: 30-60 minutes
success_criteria: 30,854+ parcels (≥95%)
```

---

### PHASE 3: P2 — rockledge + unincorporated_30 (Gap: 14,377 parcels)

```yaml
rockledge:
  strategy: Resume centroid queries against Rockledge GIS
  endpoint: https://gis-rockledge.cityofrockledge.org/server/rest/services/Planning_Building_Public/FeatureServer/0
  note: Endpoint confirmed alive in Mar 17 session
  expected_time: 45 minutes

unincorporated_30:
  strategy: County zoning layer + multi-community extraction
  communities: Identify which communities fall in envelope 30
  endpoint: https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0
  expected_time: 45 minutes
```

---

### PHASE 4: P3 — titusville + palm_bay_29 (Gap: 23,492 parcels)

```yaml
titusville:
  strategy: Titusville GIS confirmed working
  endpoint: https://gis.titusville.com/.../CommunityDevelopment/MapServer/15
  zone_field: Zone_Code
  expected_time: 60 minutes

palm_bay_29:
  strategy: Palm Bay GIS (check if 503 resolved) + USE_CODE fallback
  endpoint: https://gis.palmbayflorida.org/arcgis/rest/services/GrowthManagement/Zoning/MapServer/0
  fallback: USE_CODE mapping (same approach as envelope 26 which hit 96%)
  expected_time: 90 minutes
```

---

### PHASE 5: P4 — cocoa + cocoa_beach (Gap: 54,930 parcels)

```yaml
cocoa:
  strategy: Resume Cocoa AGOL queries
  endpoint: https://services1.arcgis.com/Tex1uhbqnOZPx6qT/arcgis/rest/services/Public_View_Cocoa_Zoning_with_Split_Lots_June_2023_view/FeatureServer/1
  zone_field: Zoning
  known_issue: Only 14,773 parcels in zoning extent vs 29,882 total COCOA parcels
  approach: Query all in-extent parcels, USE_CODE for out-of-extent remainder
  expected_time: 90 minutes

cocoa_beach:
  strategy: Based on Phase 0 investigation results
  approach: TBD after Task 0A and 0B
  expected_time: 120 minutes (investigation + conquest)
```

---

## Infrastructure

```yaml
repos:
  primary: breverdbidder/cli-anything-biddeed
  scraper: breverdbidder/zonewise-scraper-v4

secrets_needed:
  - SUPABASE_URL
  - SUPABASE_SERVICE_KEY
  - TELEGRAM_BOT_TOKEN
  - TELEGRAM_CHAT_ID

monitoring:
  - Telegram updates after each envelope completes
  - Sentinel auto-healing if queries stall
  - Final summary table when all 11 at ≥95%

cost_estimate: $0 (spatial queries against free GIS endpoints + Supabase writes)
```

---

## Success Criteria

```yaml
done_when:
  - ALL 11 envelopes ≥ 95%
  - Final coverage table sent to Telegram
  - county_conquest_status table updated in Supabase
  - No envelope below 95% threshold
```

---

## Handoff

This spec goes to Claude Code via SUMMIT dispatch. Claude Code:
1. Loads TODO.md from GitHub
2. Adds these phases as tasks
3. Executes sequentially P0 → P4
4. Reports via Telegram at each phase completion
5. Posts final 11-envelope coverage table when done
