# SUMMIT: BREVARD ENVELOPE CONQUEST V6
# Mission: Close ALL envelopes to 85%+ coverage
# NEVER-LIE RULE: No victory declared until DB proves it

## CURRENT STATE (verified 2026-03-27)
```yaml
targets:
  - id: 21_titusville
    current: 6450
    total: 16471
    pct: 39
    gap: 10021
    priority: HIGH
  - id: 22_cocoa
    current: 15341
    total: 37215
    pct: 41
    gap: 21874
    priority: HIGH
  - id: 23_rockledge
    current: 11597
    total: 19864
    pct: 58
    gap: 8267
    priority: MEDIUM
  - id: 24_cocoa_beach
    current: 3556
    total: 40498
    pct: 9
    gap: 36942
    priority: CRITICAL
  - id: 25_melbourne
    current: 26710
    total: 32478
    pct: 82
    gap: 5768
    priority: LOW (close)
  - id: 29_palm_bay_29
    current: 42496
    total: 59780
    pct: 71
    gap: 17284
    priority: HIGH
  - id: 30_unincorporated_30
    current: 4107
    total: 11800
    pct: 35
    gap: 7693
    priority: HIGH

safeguard: 85%
total_gap: 107849 parcels across 7 envelopes
```

## STRATEGY: 3-TRACK PARALLEL VIA MODAL

### Track 1: Municipal GIS Portal Discovery + Spatial Join
```yaml
approach: per-centroid query against city's own zoning GIS
targets: [titusville, cocoa, rockledge, cocoa_beach, melbourne]
method:
  1. Probe ArcGIS hub: arcgis.com/sharing/rest/search?q={city}+zoning+brevard
  2. If portal found → download zoning polygons → Shapely STRtree spatial join
  3. If no portal → Track 2 fallback
  4. CRS: ALWAYS verify source CRS before transform. Use pyproj, not hardcoded offsets.
  5. Melbourne: fix CRS 2881→3857 transform that lost 32K parcels last time
known_endpoints:
  titusville: gis.titusville.com/arcgis/rest/services/CommunityDevelopment/MapServer/15
  cocoa: discovered via arcgis search (Zoning field confirmed)
  melbourne: maps.mlbfl.org layer 109 (ZONE_ALL) — needs CRS fix
  rockledge: probe required
  cocoa_beach: probe required
```

### Track 2: BCPAO County Zoning Overlay Backfill
```yaml
approach: county-level zoning polygons for parcels missed by Track 1
targets: [unincorporated_30, any Track 1 gaps]
method:
  1. Load BCPAO zoning layer from gis.brevardfl.gov
  2. STRtree spatial join for all parcels without zone_code
  3. Only fills parcels NOT already matched by Track 1
  4. Zone codes from county = valid but lower quality than municipal
```

### Track 3: Palm Bay 29 Re-Conquest
```yaml
approach: per-centroid vs gis.palmbayflorida.org (proven method)
targets: [palm_bay_29]
method:
  1. Query Supabase for all palm_bay_29 parcel_ids WITHOUT zone_code
  2. Get centroids from BCPAO
  3. Per-centroid spatial query against Palm Bay GIS
  4. This worked for palm_bay_26 (96%) — same endpoint, different envelope
```

## EXECUTION RULES
```yaml
parallelism: Modal containers, 10 workers per track
cost_cap: $10 session max
verification:
  after_each_track: |
    SELECT envelope_id, 
           COUNT(DISTINCT parcel_id) as covered,
           (SELECT total FROM envelope_targets WHERE id = envelope_id) as total
    FROM zoning_assignments 
    WHERE envelope_id IN (21,22,23,24,25,29,30)
    GROUP BY envelope_id
  victory_condition: ALL envelopes >= 85%
  never_lie: |
    - No "conquered" until SELECT proves it
    - Report EXACT percentages from DB
    - If a track fails, report failure — don't mask it
    - Telegram updates with raw numbers only
```

## COMPLETION CRITERIA
```yaml
done_when:
  - ALL 7 yellow envelopes reach 85%+
  - Dedup verified (no duplicate parcel_ids per envelope)
  - Zone codes are REAL zoning codes, not USE_CODE descriptions
  - Final audit query run and results posted to Telegram
  - Supabase county_conquest_status table updated
```

## ANTI-PATTERNS (BANNED)
- Declaring victory from pipeline output without DB verification
- Counting USE_CODE descriptions as zone codes
- Inflating totals with duplicates
- Masking per-jurisdiction failures with aggregate numbers
- Celebrating before the SELECT confirms it
