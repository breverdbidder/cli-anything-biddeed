#!/bin/bash
# ══════════════════════════════════════════════════════════════
# SUMMIT DISPATCH: MASSING DATA GAP CLOSURE
# Target: zone_standards fill rate 57% → 95%+ (Brevard)
# Stack: Firecrawl (primary) + Apify Playwright (fallback)
# Cost: $0 (existing credits + free tiers)
# Duration: 2 Claude Code sessions (~14 hours)
# ══════════════════════════════════════════════════════════════
#
# ⛔ BANNED: AgentQL / TinyFish — $312 surprise bill, "Bill to: null null"
#    NEVER import agentql. NEVER call api.agentql.com. PERMANENT.
#
# REPO: breverdbidder/zonewise-modal (existing scraping infra)
# DB: mocerqjnksmhcjzxrewo.supabase.co
# SRK: ends ...Tqp9nE (in GitHub secrets as SUPABASE_SERVICE_KEY)
#
# ══════════════════════════════════════════════════════════════
#
# CURRENT STATE (from live DB audit March 24, 2026):
#
#   TABLE: zone_standards (2,359 rows)
#   ┌────────────────────────┬───────┬────────┬──────────┐
#   │ FIELD                  │ FILLED│ TOTAL  │ FILL %   │
#   ├────────────────────────┼───────┼────────┼──────────┤
#   │ max_height_ft          │ 1,337 │ 2,359  │ 56.7%    │
#   │ front_setback_ft       │ 1,311 │ 2,359  │ 55.6%    │
#   │ side_setback_ft        │~1,311 │ 2,359  │ ~55.6%   │
#   │ rear_setback_ft        │~1,311 │ 2,359  │ ~55.6%   │
#   │ max_lot_coverage_pct   │   968 │ 2,359  │ 41.0%    │
#   │ max_far                │   440 │ 2,359  │ 18.7%    │
#   │ max_density_du_acre    │   707 │ 2,359  │ 30.0%    │
#   │ parking_per_unit       │    13 │ 2,359  │  0.6%    │
#   │ parking_per_1000sf     │     0 │ 2,359  │  0.0%    │
#   │ min_open_space_pct     │  ~118 │ 2,359  │ ~5.0%    │
#   └────────────────────────┴───────┴────────┴──────────┘
#
#   TABLE: zoning_districts (6,225 rows)
#   TABLE: permitted_uses (12,673 rows)
#   TABLE: zoning_assignments (351,469 Brevard parcels)
#   TABLE: sample_properties (351,424 Brevard w/ geometry)
#
# TARGET STATE:
#   max_height_ft      → 95%+
#   front/side/rear    → 95%+
#   max_lot_coverage   → 80%+
#   max_far            → 60%+ (many FL residential zones genuinely don't use FAR)
#   max_density_du_acre→ 70%+
#   parking_per_unit   → 80%+
#   parking_per_1000sf → 50%+
#
# ══════════════════════════════════════════════════════════════

set -euo pipefail

echo "🚀 SUMMIT DISPATCH: Massing Data Gap Closure"
echo "============================================="
echo ""
echo "⛔ AgentQL BANNED — using Firecrawl + Apify ONLY"
echo ""

# ─── PHASE 1: IDENTIFY BREVARD NULL ZONES (30 min) ───────────
#
# Query zone_standards JOIN zoning_districts
# WHERE jurisdiction is Brevard county
# AND max_height_ft IS NULL
#
# Expected: ~200-400 Brevard-specific zones with NULL controls
#
# SQL:
#   SELECT zd.id, zd.code, zd.name, zd.jurisdiction_id,
#          j.name as jurisdiction_name, j.municode_url
#   FROM zoning_districts zd
#   LEFT JOIN zone_standards zs ON zs.zoning_district_id = zd.id
#   LEFT JOIN zonewise_jurisdictions j ON j.id = zd.jurisdiction_id
#   WHERE zd.jurisdiction_id IN (
#     SELECT id FROM zonewise_jurisdictions
#     WHERE county = 'brevard'
#   )
#   AND (zs.max_height_ft IS NULL OR zs.front_setback_ft IS NULL)
#   ORDER BY j.name, zd.code;
#
# Group results by jurisdiction → generates Municode URL targets

# ─── PHASE 2: FIRECRAWL LLM EXTRACTION (4-6 hours) ──────────
#
# For each Brevard jurisdiction with NULL zone_standards:
#
# METHOD: Firecrawl /v1/scrape with extract mode
# This is PROVEN working — used for Melbourne, Malabar, Titusville
#
# FIRECRAWL_KEY: fc-fa112951a2564765a2d146302774ac9b
#
# REQUEST TEMPLATE:
# ```python
# import httpx
#
# def scrape_dimensional_standards(municode_url, zone_section_url):
#     resp = httpx.post(
#         "https://api.firecrawl.dev/v1/scrape",
#         headers={
#             "Authorization": "Bearer fc-fa112951a2564765a2d146302774ac9b",
#             "Content-Type": "application/json"
#         },
#         json={
#             "url": zone_section_url,
#             "formats": ["extract"],
#             "waitFor": 10000,
#             "timeout": 30000,
#             "extract": {
#                 "schema": {
#                     "type": "object",
#                     "properties": {
#                         "districts": {
#                             "type": "array",
#                             "items": {
#                                 "type": "object",
#                                 "properties": {
#                                     "district_code": {"type": "string"},
#                                     "district_name": {"type": "string"},
#                                     "max_height_ft": {"type": "number"},
#                                     "max_stories": {"type": "integer"},
#                                     "front_setback_ft": {"type": "number"},
#                                     "side_setback_ft": {"type": "number"},
#                                     "rear_setback_ft": {"type": "number"},
#                                     "corner_setback_ft": {"type": "number"},
#                                     "max_lot_coverage_pct": {"type": "number"},
#                                     "max_far": {"type": "number"},
#                                     "max_density_du_acre": {"type": "number"},
#                                     "min_lot_sqft": {"type": "number"},
#                                     "min_lot_width_ft": {"type": "number"},
#                                     "min_open_space_pct": {"type": "number"},
#                                     "parking_per_unit": {"type": "number"},
#                                     "parking_per_1000sf": {"type": "number"}
#                                 }
#                             }
#                         }
#                     }
#                 },
#                 "prompt": "Extract ALL zoning dimensional standards from this municipal code section. Look for dimensional tables with lot size, setbacks, height limits, FAR, lot coverage, density (dwelling units per acre), parking requirements, and open space. Convert all measurements to feet and square feet. Include every zoning district listed."
#             }
#         },
#         timeout=60
#     )
#     return resp.json()
# ```
#
# BREVARD JURISDICTION MUNICODE URLS (priority order):
#
# 1. Unincorporated Brevard (54 districts)
#    https://library.municode.com/fl/brevard_county
#    ZONING: Chapter 62, Article VI - Zoning Districts
#
# 2. Melbourne (largest city, ~40 districts)
#    https://library.municode.com/fl/melbourne
#    ZONING: Part III, Appendix B - Zoning
#
# 3. Palm Bay (78,660 parcels assigned)
#    https://library.municode.com/fl/palm_bay
#    ZONING: Chapter 185 - Zoning
#
# 4. Titusville (~40 districts)
#    https://library.municode.com/fl/titusville
#    ZONING: Chapter 28 - Zoning
#
# 5. Cocoa
#    https://library.municode.com/fl/cocoa
#
# 6. Rockledge
#    https://library.municode.com/fl/rockledge
#
# 7. Satellite Beach
#    https://library.municode.com/fl/satellite_beach
#
# 8. Indian Harbour Beach
#    https://library.municode.com/fl/indian_harbour_beach
#
# 9. Cape Canaveral
#    https://library.municode.com/fl/cape_canaveral
#
# 10. West Melbourne
#     https://library.municode.com/fl/west_melbourne
#
# 11-18: Malabar(DONE), Melbourne Beach, Melbourne Village,
#         Indialantic, Palm Shores, Grant-Valkaria, Mims area
#
# RATE LIMITING:
#   - 2 second delay between Firecrawl calls
#   - Max 30 calls per jurisdiction (most have 5-15 zoning sections)
#   - If rate limited: switch to Apify fallback

# ─── PHASE 3: APIFY FALLBACK (if Firecrawl rate-limited) ────
#
# Apify Playwright scraper — FREE $5/mo tier
# PROVEN on Malabar (13/13 districts extracted)
#
# ```python
# from apify_client import ApifyClient
#
# client = ApifyClient("apify_api_YOUR_TOKEN")  # from GitHub secrets
#
# def apify_scrape(url):
#     run = client.actor("apify/web-scraper").call(
#         run_input={
#             "startUrls": [{"url": url}],
#             "pageFunction": """
#                 async function pageFunction(context) {
#                     const { page, request } = context;
#                     await page.waitForTimeout(8000);
#                     const content = await page.content();
#                     return { url: request.url, html: content };
#                 }
#             """,
#             "proxyConfiguration": {"useApifyProxy": True},
#             "maxRequestsPerCrawl": 1
#         }
#     )
#     items = client.dataset(run["defaultDatasetId"]).list_items().items
#     return items[0]["html"] if items else None
# ```
#
# Then parse with BeautifulSoup + regex (existing code in
# zonewise-modal/src/extractors/phase_extractors.py)

# ─── PHASE 4: PARKING SPRINT (2-3 hours) ─────────────────────
#
# Parking tables are SEPARATE sections in Municode ordinances.
# They are highly structured — usually one big table per jurisdiction.
#
# Brevard County (unincorp): Chapter 62, Article X - Parking
# Melbourne: Appendix B, Article XX - Off-Street Parking
# Palm Bay: Chapter 185, Division 8 - Parking
#
# PARKING SCHEMA for Firecrawl extract:
# ```json
# {
#     "schema": {
#         "type": "object",
#         "properties": {
#             "parking_requirements": {
#                 "type": "array",
#                 "items": {
#                     "type": "object",
#                     "properties": {
#                         "use_type": {"type": "string"},
#                         "spaces_per_unit": {"type": "number"},
#                         "spaces_per_1000sf": {"type": "number"},
#                         "spaces_per_bedroom": {"type": "number"},
#                         "notes": {"type": "string"}
#                     }
#                 }
#             }
#         }
#     },
#     "prompt": "Extract ALL off-street parking requirements from this ordinance. For each land use type, extract the required number of parking spaces per unit, per 1000 sq ft, or per bedroom. Include residential (single family, duplex, multifamily, townhouse) and commercial (office, retail, restaurant, hotel) requirements."
# }
# ```
#
# MAPPING parking → zone_standards:
#   - Match use_type to permitted_uses.use_description
#   - Single Family → parking_per_unit (typically 2.0)
#   - Multifamily → parking_per_unit (typically 1.5-2.0)
#   - Commercial → parking_per_1000sf (typically 3.0-5.0)
#   - Where jurisdiction doesn't specify: use Brevard County default

# ─── PHASE 5: DERIVE MISSING VALUES (1 hour) ─────────────────
#
# Some fields can be COMPUTED rather than scraped:
#
# 1. max_stories (where NULL but max_height_ft exists):
#    UPDATE zone_standards
#    SET max_stories = FLOOR(max_height_ft / 11)
#    WHERE max_stories IS NULL AND max_height_ft IS NOT NULL;
#
# 2. max_far (for residential zones without explicit FAR):
#    -- In FL, residential density controls trump FAR
#    -- Derive: FAR ≈ (density_du_acre × avg_unit_sf) / 43560
#    -- avg_unit_sf: SF=1800, MF-Low=900, MF-Mid=750, MF-High=650
#    UPDATE zone_standards zs
#    SET max_far = ROUND(
#      (zs.max_density_du_acre * 900.0) / 43560.0, 2
#    )
#    WHERE zs.max_far IS NULL
#    AND zs.max_density_du_acre IS NOT NULL
#    AND zs.zoning_district_id IN (
#      SELECT id FROM zoning_districts
#      WHERE category IN ('residential', 'mixed-use')
#    );
#
# 3. Zone category classification (batch LLM):
#    SELECT id, code, name FROM zoning_districts
#    WHERE category = 'Uncategorized' OR category IS NULL;
#    -- Feed to DeepSeek V3.2 in batches of 100:
#    -- "Classify each zone: residential/commercial/industrial/mixed/agricultural/planned"
#    -- R-1, R-2, R-3 → residential
#    -- C-1, C-2, BU → commercial
#    -- M-1, I-1 → industrial
#    -- PUD, MXD → mixed-use
#    -- AG, A-1 → agricultural

# ─── PHASE 6: VALIDATION + NEVER-LIE AUDIT (30 min) ─────────
#
# After all phases, run fill rate audit and report EXACT numbers:
#
# ```sql
# SELECT
#   COUNT(*) as total,
#   COUNT(max_height_ft) as height_filled,
#   COUNT(front_setback_ft) as front_filled,
#   COUNT(side_setback_ft) as side_filled,
#   COUNT(rear_setback_ft) as rear_filled,
#   COUNT(max_lot_coverage_pct) as coverage_filled,
#   COUNT(max_far) as far_filled,
#   COUNT(max_density_du_acre) as density_filled,
#   COUNT(parking_per_unit) as parking_unit_filled,
#   COUNT(parking_per_1000sf) as parking_sf_filled,
#   COUNT(min_open_space_pct) as open_space_filled,
#   ROUND(COUNT(max_height_ft)::numeric / COUNT(*) * 100, 1) as height_pct,
#   ROUND(COUNT(front_setback_ft)::numeric / COUNT(*) * 100, 1) as setback_pct,
#   ROUND(COUNT(max_far)::numeric / COUNT(*) * 100, 1) as far_pct,
#   ROUND(COUNT(parking_per_unit)::numeric / COUNT(*) * 100, 1) as parking_pct
# FROM zone_standards;
# ```
#
# Send results to Telegram:
# "🏗️ MASSING DATA SPRINT COMPLETE
# Height: X% (was 57%)
# Setbacks: X% (was 56%)
# FAR: X% (was 19%)
# Coverage: X% (was 41%)
# Parking: X% (was 0.6%)
# Ready for 3D Massing Engine: YES/NO"

# ─── SUCCESS CRITERIA ─────────────────────────────────────────
#
# [ ] height + setbacks ≥ 95% for Brevard jurisdictions
# [ ] parking_per_unit ≥ 80% for Brevard jurisdictions
# [ ] max_far ≥ 60% (including derived values)
# [ ] Zone categories classified (0% "Uncategorized" for Brevard)
# [ ] NEVER-LIE: All reported numbers match actual DB counts
# [ ] Telegram summary sent with before/after comparison
# [ ] No AgentQL calls anywhere in codebase

echo "✅ Dispatch spec ready for Claude Code execution"
echo "Estimated: 2 sessions, ~14 hours total, $0 incremental cost"
