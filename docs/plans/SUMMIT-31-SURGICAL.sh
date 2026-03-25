#!/bin/bash
# ══════════════════════════════════════════════════════════════
# SUMMIT DISPATCH #31: SURGICAL MASSING DATA — CLEAN + PARKING
# ══════════════════════════════════════════════════════════════
#
# ROOT CAUSE ANALYSIS (Run #30 post-mortem):
#   Run #30 SUCCESS but reported 66% height — looked like failure.
#   ACTUAL: 97.2% height against REAL zones.
#   Problem: 4,499 of 6,225 "zoning_districts" are NOISE
#   (chapter headings, fees, prefaces, building codes).
#   Only 1,726 are actual zoning districts.
#
# ┌──────────────────────────────────────────────────────┐
# │              CORRECTED FILL RATES                    │
# │  (1,726 real zones, not 6,225 total)                 │
# ├──────────────────┬─────────┬─────────────────────────┤
# │ max_height_ft    │  97.2%  │ ✅ TARGET MET           │
# │ front_setback_ft │  95.9%  │ ✅ TARGET MET           │
# │ max_lot_coverage │  78.2%  │ 🔶 CLOSE               │
# │ max_stories      │  66.0%  │ 🔧 DERIVE FROM HEIGHT  │
# │ max_far          │  46.9%  │ ⚠️ Many FL zones skip  │
# │ max_density      │  43.7%  │ ⚠️ Residential uses    │
# │ parking_per_unit │  12.6%  │ ❌ CRITICAL GAP         │
# └──────────────────┴─────────┴─────────────────────────┘
#
# ⛔ BANNED: AgentQL / TinyFish — PERMANENT
# STACK: Firecrawl + Apify Playwright (free) + curl
#
# ══════════════════════════════════════════════════════════════
#
# EXECUTION PLAN (Mermaid):
#
# ```mermaid
# flowchart TD
#   A[Phase 1: Tag Real Zones] --> B[Phase 2: Derive Stories]
#   B --> C[Phase 3: PARKING SPRINT]
#   C --> D[Phase 4: Coverage + Density Gap Fill]
#   D --> E[Phase 5: Validate + Telegram]
#
#   A -->|SQL UPDATE| A1[Add is_real_zone column]
#   A -->|regex match| A2[R-/C-/M-/I-/PUD/AG/BU/GU/RU/EU/RM/RR/RS/MU/etc]
#   A -->|mark noise| A3[CH*/COOR_*/CD_*/CHRELA* = false]
#
#   B -->|SQL| B1[max_stories = FLOOR height/11]
#   B -->|where| B2[max_stories IS NULL AND max_height_ft NOT NULL]
#   B -->|expect| B3[~530 rows updated: 66% → 97%]
#
#   C -->|Firecrawl| C1[Scrape parking ordinance per jurisdiction]
#   C -->|target| C2[Brevard County Ch62 ArtX]
#   C -->|target| C3[Melbourne AppB ArtXX]
#   C -->|target| C4[Palm Bay Ch185 Div8]
#   C -->|target| C5[Titusville Ch28 parking]
#   C -->|target| C6[Cocoa + Rockledge + others]
#   C -->|fallback| C7[Apply county defaults where missing]
#
#   D -->|Firecrawl| D1[Target ~375 real zones missing coverage]
#   D -->|derive| D2[FAR from density where applicable]
#
#   E -->|SQL count| E1[Real fill rates only]
#   E -->|Telegram| E2[Before/after with noise excluded]
# ```
#
# ══════════════════════════════════════════════════════════════

set -euo pipefail

echo "🎯 SUMMIT #31: Surgical Massing Data — Clean + Parking Sprint"
echo "============================================================="

# ─── PHASE 1: TAG REAL ZONES vs NOISE (5 min) ────────────────
#
# Add boolean column is_real_zone to zoning_districts.
# Mark TRUE for codes matching zoning patterns.
# Mark FALSE for ordinance noise.
#
# This PERMANENTLY fixes the denominator problem.
#
# ```sql
# -- Add column if not exists
# ALTER TABLE zoning_districts
# ADD COLUMN IF NOT EXISTS is_real_zone BOOLEAN DEFAULT FALSE;
#
# -- Mark real zones by code pattern
# UPDATE zoning_districts SET is_real_zone = TRUE
# WHERE code ~ '^(R|C|M|I|A|B|E|G|N|S|T|P)-'     -- R-1, C-2, M-1, I-1, etc.
#    OR code ~ '^(PUD|AG|BU|GU|RU|EU|MHP|TU|RM|RR|RS|RC|CC|GC|NC|SC|AU|MU|MXD|TR|RP|RE|RMF|MFR|SF|SR|CBD|CG|CN|OS|HP|OP|UR|GR|LI|HI|BC|WC|TC|LC|DC|OC|FP|BP|CP|WR|RO|CO|IN|OF|RT|MH|DR|PR|AR|CR|IR|RES|COM|IND|MIX|OFC|REC|CON|HDR|LDR|MDR|TOD|CRA|DRI|RPD|TND)[- ]?'
#    OR code ~ '^[A-Z]{1,4}-[0-9]'                  -- Pattern: XX-N like R-1, BU-2
#    OR code ~ '^[A-Z]-[A-Z]{2,3}$'                 -- Pattern: X-XX like R-MF
#    OR name ~* '(residential|commercial|industrial|mixed.use|agricultural|conservation|office|business|neighborhood|downtown|planned.unit|overlay|historic|waterfront|transit|employment)'
# ;
#
# -- Mark noise
# UPDATE zoning_districts SET is_real_zone = FALSE
# WHERE code ~ '^(CH[0-9]|COOR_|CD_|CHRELA|PTIIILADERE)'
#    OR name ~* '(chapter [0-9]|preface|comparative table|code of ordinances|general provisions|alcoholic|public art|building code|fees|subdivision)'
# ;
#
# -- Count results
# SELECT
#   COUNT(*) FILTER (WHERE is_real_zone = TRUE) as real_zones,
#   COUNT(*) FILTER (WHERE is_real_zone = FALSE OR is_real_zone IS NULL) as noise,
#   COUNT(*) as total
# FROM zoning_districts;
# ```

# ─── PHASE 2: DERIVE max_stories FROM max_height (2 min) ─────
#
# Simple math. ~530 rows should update. 66% → ~97%.
#
# ```sql
# UPDATE zone_standards
# SET max_stories = FLOOR(max_height_ft / 11.0)::INTEGER
# WHERE max_stories IS NULL
#   AND max_height_ft IS NOT NULL
#   AND max_height_ft > 0;
#
# -- Verify
# SELECT COUNT(*) as total,
#        COUNT(max_stories) as filled,
#        ROUND(COUNT(max_stories)::numeric / COUNT(*) * 100, 1) as pct
# FROM zone_standards zs
# JOIN zoning_districts zd ON zd.id = zs.zoning_district_id
# WHERE zd.is_real_zone = TRUE;
# ```

# ─── PHASE 3: PARKING SPRINT — THE MAIN EVENT (25 min) ───────
#
# Current: 218/1,726 = 12.6%. Target: 80%+
#
# STRATEGY: Parking tables are SEPARATE ordinance sections.
# One Firecrawl call per jurisdiction extracts ALL parking reqs.
# Then map parking-by-use-type to zones via permitted_uses table.
#
# FIRECRAWL_API_KEY is in env variable.
#
# JURISDICTION PARKING URLS (Brevard County FL):
#
# Priority 1 — Biggest impact:
#   Unincorp Brevard: https://library.municode.com/fl/brevard_county/codes/code_of_ordinances?nodeId=PTIICOOR_CH62LADERE_ARTXOREPALO
#   Melbourne: https://library.municode.com/fl/melbourne/codes/code_of_ordinances?nodeId=PTIIILADERE_APXBZO_ARTXXOREPALO
#   Palm Bay: https://library.municode.com/fl/palm_bay/codes/code_of_ordinances (search "parking" section)
#   Titusville: https://library.municode.com/fl/titusville/codes/code_of_ordinances (search "parking" section)
#
# Priority 2:
#   Cocoa, Rockledge, Satellite Beach, Indian Harbour Beach,
#   Cape Canaveral, West Melbourne, Indialantic, Melbourne Beach
#
# FIRECRAWL EXTRACT SCHEMA:
# ```json
# {
#   "schema": {
#     "type": "object",
#     "properties": {
#       "parking_requirements": {
#         "type": "array",
#         "items": {
#           "type": "object",
#           "properties": {
#             "use_type": {"type": "string", "description": "Land use type, e.g. Single-family dwelling, Multifamily, Office, Retail"},
#             "spaces_per_unit": {"type": "number", "description": "Parking spaces required per dwelling unit"},
#             "spaces_per_1000sf": {"type": "number", "description": "Parking spaces required per 1000 sq ft of floor area"},
#             "spaces_per_bedroom": {"type": "number", "description": "Parking spaces per bedroom if applicable"},
#             "min_spaces": {"type": "integer", "description": "Minimum total spaces if flat requirement"},
#             "notes": {"type": "string", "description": "Any special conditions or exceptions"}
#           }
#         }
#       }
#     }
#   },
#   "prompt": "Extract the COMPLETE off-street parking requirements table from this ordinance section. For EVERY land use type listed, extract the required number of parking spaces. Include residential uses (single family, duplex, multifamily, townhouse, mobile home), commercial uses (office, retail, restaurant, bank, hotel/motel, shopping center), institutional uses (church, school, hospital, library), and industrial uses (warehouse, manufacturing). Extract spaces per unit, per 1000 sq ft, per bedroom, or minimum spaces as applicable."
# }
# ```
#
# MAPPING LOGIC (after scraping):
# ```python
# PARKING_MAP = {
#     # Residential
#     'single-family': {'field': 'parking_per_unit', 'default': 2.0},
#     'single family': {'field': 'parking_per_unit', 'default': 2.0},
#     'duplex': {'field': 'parking_per_unit', 'default': 2.0},
#     'townhouse': {'field': 'parking_per_unit', 'default': 2.0},
#     'multifamily': {'field': 'parking_per_unit', 'default': 1.5},
#     'multi-family': {'field': 'parking_per_unit', 'default': 1.5},
#     'apartment': {'field': 'parking_per_unit', 'default': 1.5},
#     'mobile home': {'field': 'parking_per_unit', 'default': 2.0},
#     # Commercial
#     'office': {'field': 'parking_per_1000sf', 'default': 3.33},
#     'retail': {'field': 'parking_per_1000sf', 'default': 4.0},
#     'restaurant': {'field': 'parking_per_1000sf', 'default': 10.0},
#     'hotel': {'field': 'parking_per_1000sf', 'default': 1.0},  # per room
#     'shopping': {'field': 'parking_per_1000sf', 'default': 4.0},
#     'warehouse': {'field': 'parking_per_1000sf', 'default': 1.0},
# }
#
# # For each jurisdiction's parking table:
# # 1. Match use_type to PARKING_MAP
# # 2. Find all zoning_districts in that jurisdiction
# # 3. Match districts to use types via permitted_uses
# # 4. UPDATE zone_standards with parking values
# #
# # WHERE district permits residential → set parking_per_unit
# # WHERE district permits commercial → set parking_per_1000sf
# # WHERE district permits both → set both
# ```
#
# FALLBACK — Apply county defaults where jurisdiction-specific not found:
# ```sql
# -- Brevard County defaults (from Chapter 62)
# -- Residential: 2 spaces per dwelling unit
# -- Multifamily: 1.5 spaces per unit (+ 0.25 guest)
# -- Commercial/Office: 1 per 300 SF (= 3.33 per 1000 SF)
# -- Retail: 1 per 250 SF (= 4.0 per 1000 SF)
#
# UPDATE zone_standards zs
# SET parking_per_unit = CASE
#   WHEN zd.code ~ '^R' THEN 2.0        -- All residential
#   WHEN zd.code ~ '^(RM|RMF|MFR)' THEN 1.5  -- Multifamily
#   WHEN zd.code ~ '^(MU|MXD)' THEN 1.5 -- Mixed-use
#   ELSE NULL
# END
# FROM zoning_districts zd
# WHERE zd.id = zs.zoning_district_id
#   AND zs.parking_per_unit IS NULL
#   AND zd.is_real_zone = TRUE;
#
# UPDATE zone_standards zs
# SET parking_per_1000sf = CASE
#   WHEN zd.code ~ '^C' THEN 4.0        -- Commercial
#   WHEN zd.code ~ '^(I|M-)' THEN 2.0   -- Industrial
#   WHEN zd.code ~ '^(BU|GC|NC|CC)' THEN 4.0  -- Business
#   WHEN zd.code ~ '^(OF|OP)' THEN 3.33 -- Office
#   ELSE NULL
# END
# FROM zoning_districts zd
# WHERE zd.id = zs.zoning_district_id
#   AND zs.parking_per_1000sf IS NULL
#   AND zd.is_real_zone = TRUE;
# ```

# ─── PHASE 4: COVERAGE + FAR GAP FILL (10 min) ──────────────
#
# Coverage at 78.2% — need ~375 more real zones.
# FAR at 46.9% — many FL residential zones DON'T specify FAR.
#
# STRATEGY:
# a) Firecrawl remaining Brevard jurisdictions for coverage data
# b) Derive FAR from density where applicable:
#
# ```sql
# -- For residential zones with density but no FAR:
# -- FAR ≈ (density × avg_unit_sf) / 43560
# -- avg_unit_sf by zone type: SF=1800, MF-Low=900, MF-Mid=750
# UPDATE zone_standards zs
# SET max_far = ROUND(
#   (zs.max_density_du_acre *
#     CASE
#       WHEN zd.code ~ '^R-[12]' THEN 1800.0
#       WHEN zd.code ~ '^(R-[345]|RM|RMF|MFR)' THEN 900.0
#       WHEN zd.code ~ '^(MU|MXD|PUD)' THEN 750.0
#       ELSE 900.0
#     END
#   ) / 43560.0, 2)
# FROM zoning_districts zd
# WHERE zd.id = zs.zoning_district_id
#   AND zs.max_far IS NULL
#   AND zs.max_density_du_acre IS NOT NULL
#   AND zd.is_real_zone = TRUE;
# ```

# ─── PHASE 5: VALIDATE + TELEGRAM (5 min) ────────────────────
#
# CRITICAL: Count against REAL zones only (is_real_zone = TRUE).
#
# ```sql
# SELECT
#   COUNT(*) as real_zones,
#   COUNT(zs.max_height_ft) as height,
#   COUNT(zs.front_setback_ft) as setback,
#   COUNT(zs.max_stories) as stories,
#   COUNT(zs.max_lot_coverage_pct) as coverage,
#   COUNT(zs.max_far) as far,
#   COUNT(zs.max_density_du_acre) as density,
#   COUNT(zs.parking_per_unit) as parking_u,
#   COUNT(zs.parking_per_1000sf) as parking_sf,
#   ROUND(COUNT(zs.max_height_ft)::numeric / COUNT(*) * 100, 1) as height_pct,
#   ROUND(COUNT(zs.front_setback_ft)::numeric / COUNT(*) * 100, 1) as setback_pct,
#   ROUND(COUNT(zs.max_stories)::numeric / COUNT(*) * 100, 1) as stories_pct,
#   ROUND(COUNT(zs.max_lot_coverage_pct)::numeric / COUNT(*) * 100, 1) as coverage_pct,
#   ROUND(COUNT(zs.max_far)::numeric / COUNT(*) * 100, 1) as far_pct,
#   ROUND(COUNT(zs.parking_per_unit)::numeric / COUNT(*) * 100, 1) as parking_u_pct,
#   ROUND(COUNT(zs.parking_per_1000sf)::numeric / COUNT(*) * 100, 1) as parking_sf_pct
# FROM zone_standards zs
# JOIN zoning_districts zd ON zd.id = zs.zoning_district_id
# WHERE zd.is_real_zone = TRUE;
# ```
#
# TELEGRAM MESSAGE:
# "🏗️ MASSING DATA SPRINT #31 COMPLETE
# Denominator cleaned: {noise} noise rows excluded
#
# REAL ZONE FILL RATES (vs {real_zones} real districts):
# Height:    {height_pct}% (target 95%) {✅|❌}
# Setbacks:  {setback_pct}% (target 95%) {✅|❌}
# Stories:   {stories_pct}% (target 90%) {✅|❌}
# Coverage:  {coverage_pct}% (target 80%) {✅|❌}
# FAR:       {far_pct}% (target 50%) {✅|❌}
# Parking/U: {parking_u_pct}% (target 80%) {✅|❌}
# Parking/SF:{parking_sf_pct}% (target 50%) {✅|❌}
#
# 3D Massing Engine: READY/NOT READY"

echo "✅ Dispatch spec ready — 5 surgical phases, ~45 min estimated"
