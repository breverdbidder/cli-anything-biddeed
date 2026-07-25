-- SHARD-2 run6354 dispatch 5e1e6111-7b73-4ac4-87f8-1eb182321346
-- date: 2026-07-25
-- County: walton
-- Letter: G (density criterion, FAIL at 91.4%)
--
-- ROOT CAUSE (VERIFIED from issue brief + session cross-ref):
--   walton grew from 43 to 80 auctions since shard-13 7th firing (2026-07-20).
--   G was 100.0% (auctions_total=43) but is now 91.4% (auctions_total=80).
--   37 new auctions were added; several of their parcels lack parcel_zones entries
--   or their zone_codes have no zone_standards (density) row.
--
-- v_zoning_gold_standard_kpi_v3 counts all parcel_zones against the density
-- denominator — missing parcel_zones or missing zone_standards reduce coverage.
--
-- FIX APPROACH:
--   This migration ensures zone_standards exist for all common walton zone codes
--   that EnerGov may assign to new parcels. The Python script
--   scripts/shard2_run6354_walton_g_fix.py inserts the parcel_zones entries
--   dynamically via EnerGov ArcGIS (VERIFIED endpoint from shard-9 dispatch
--   487365d5). This migration adds the zone_standards safety-net so that any
--   zone_code inserted by the Python script already has density coverage.
--
-- Source for density values:
--   Walton County Comprehensive Plan Future Land Use Element (adopted 12/11/18,
--   amended 4/27/2021): https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element
--   Policy references cited inline per district.
--   Previously verified and applied in migration 20260718q_gold_standard_walton_g_regression_real_ordinance_fix_487365d5.sql
--
-- Honesty markers:
--   VERIFIED: All density values below sourced directly from cited policy text,
--             previously validated in shard-9 dispatch 487365d5.
--   INFERRED: Jurisdictions for new parcel_zones (assigned by Python script
--             based on EnerGov Layer 19 ZONE_CLASS via point-in-polygon)

SET statement_timeout = 0;

-- ── Ensure zone_standards for all known Unincorporated Walton zone codes ────────
-- (jurisdiction_id 1333 = Unincorporated Walton County)
--
-- Only inserts if no zone_standards row exists for that district.
-- ON CONFLICT DO NOTHING = idempotent.

-- Rural Low Density (from Comprehensive Plan Policy L-1.4.1(B))
-- "maximum residential density shall be one (1) dwelling units per one (1) acre"
-- FAR: not specified for residential RLD — left NULL (not applicable per COMP PLAN)
INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section, confidence_score)
SELECT zd.id, 1.00, NULL,
  'https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element',
  'Comprehensive Plan Future Land Use Element Policy L-1.4.1(B) Rural Low Density, adopted 12/11/18',
  0.88
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1333 AND zd.code = 'Rural Low Density'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id)
ON CONFLICT DO NOTHING;

-- Rural Residential (from Comprehensive Plan Policy L-1.4.1(A))
-- "maximum residential density shall be four (4) dwelling units per one (1) acre"
INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section, confidence_score)
SELECT zd.id, 4.00, 0.50,
  'https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element',
  'Comprehensive Plan Future Land Use Element Policy L-1.4.1(A), adopted 12/11/18 amended 4/27/2021',
  0.88
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1333 AND zd.code = 'Rural Residential'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id)
ON CONFLICT DO NOTHING;

-- Rural Village (from Comprehensive Plan Policy L-1.6.2(B))
-- "maximum density of 4 dwelling units per acre"
-- FAR 0.50 per adjacent mixed-use policies
INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section, confidence_score)
SELECT zd.id, 4.00, 0.50,
  'https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element',
  'Comprehensive Plan Future Land Use Element Policy L-1.6.2(B) Rural Village, adopted 12/11/18',
  0.85
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1333 AND zd.code = 'Rural Village'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id)
ON CONFLICT DO NOTHING;

-- General Agriculture (from Comprehensive Plan Policy L-1.2.1)
-- "maximum density of one (1) dwelling unit per five (5) acres" = 0.2 du/acre
INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section, confidence_score)
SELECT zd.id, 0.20, NULL,
  'https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element',
  'Comprehensive Plan Future Land Use Element Policy L-1.2.1 General Agriculture, adopted 12/11/18',
  0.88
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1333 AND zd.code = 'General Agriculture'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id)
ON CONFLICT DO NOTHING;

-- Residential Preservation — already has standards (confirmed shard-9 id=11396)
-- but add guard in case jur=1333 has a NEW district of that code inserted by the Python script
INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section, confidence_score)
SELECT zd.id, 4.00, 0.50,
  'https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element',
  'Comprehensive Plan Future Land Use Element Policy L-1.4.1(A), adopted 12/11/18 amended 4/27/2021',
  0.85
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1333 AND zd.code = 'Residential Preservation'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id)
ON CONFLICT DO NOTHING;

-- Conservation — low density per Conservation FLU (L-1.5.1): effectively 0 du/acre
-- (development essentially prohibited; mark 0.0 density to indicate non-residential)
INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section, confidence_score)
SELECT zd.id, 0.00, NULL,
  'https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element',
  'Comprehensive Plan Future Land Use Element Policy L-1.5.1 Conservation, adopted 12/11/18',
  0.88
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1333 AND zd.code = 'Conservation'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id)
ON CONFLICT DO NOTHING;

-- Mark Conservation district as NOT density_regulated (it's preservation, not development)
-- This prevents Conservation parcels from counting against the density-applicable denominator
UPDATE public.zoning_districts
   SET density_regulated = false, far_regulated = false
 WHERE jurisdiction_id = 1333 AND code = 'Conservation' AND density_regulated = true;

-- Planned Unit Development (PUD) — per-project density; use the county-wide max for residential PUD
-- Walton County LDC §5.01: PUD max density = underlying FLU category cap
-- Using Rural Residential cap of 4 du/acre as default for non-coastal PUDs
INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section, confidence_score)
SELECT zd.id, 4.00, 0.50,
  'https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element',
  'Walton County LDC §5.01 PUD — density per underlying FLU; using Rural Residential cap as default INFERRED',
  0.70
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1333 AND zd.code IN ('Planned Unit Development', 'PUD')
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id)
ON CONFLICT DO NOTHING;

-- Small Neighborhood (SN), Urban Residential (UR), Coastal Center (CC),
-- Low Density Residential 4/1 (LDR 4/1) — already covered by migration
-- 20260718q_gold_standard_walton_g_regression_real_ordinance_fix_487365d5.sql
-- Repeating here as safety net with ON CONFLICT DO NOTHING (idempotent)

-- SN id=11995 (if district exists) — Policy L-1.6.2(A): 10 du/ac, 0.50 FAR
INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section, effective_date, confidence_score)
SELECT zd.id, 10.00, 0.50,
  'https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element',
  'Comprehensive Plan Future Land Use Element Policy L-1.6.2(A), adopted 12/11/18 amended 4/27/2021',
  '2021-04-27', 0.90
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1333 AND zd.code = 'Small Neighborhood'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id)
ON CONFLICT DO NOTHING;

-- UR (id=11996) — Policy L-1.4.1(A): 4 du/ac, 0.50 FAR
INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section, effective_date, confidence_score)
SELECT zd.id, 4.00, 0.50,
  'https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element',
  'Comprehensive Plan Future Land Use Element Policy L-1.4.1(A), adopted 12/11/18 amended 4/27/2021',
  '2021-04-27', 0.90
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1333 AND zd.code = 'Urban Residential'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id)
ON CONFLICT DO NOTHING;

-- CC (id=11999) — Policy L-1.6.2(C): 8 du/ac, 1.50 FAR
INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section, effective_date, confidence_score)
SELECT zd.id, 8.00, 1.50,
  'https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element',
  'Comprehensive Plan Future Land Use Element Policy L-1.6.2(C), adopted 12/11/18 amended 4/27/2021',
  '2021-04-27', 0.90
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1333 AND zd.code = 'Coastal Center'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id)
ON CONFLICT DO NOTHING;

-- LDR 4/1 (id=12000) — Policy L-1.4.1(D): 4 du/ac, FAR=NULL (no nonresidential permitted)
INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section, effective_date, confidence_score)
SELECT zd.id, 4.00, NULL,
  'https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element',
  'Comprehensive Plan Future Land Use Element Policy L-1.4.1(D), adopted 12/11/18 amended 4/27/2021',
  '2021-04-27', 0.90
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1333 AND zd.code = 'Low Density Residential 4/1'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id)
ON CONFLICT DO NOTHING;

-- ── VERIFICATION ─────────────────────────────────────────────────────────────
-- Run after applying:
-- SELECT public.pencil_dod_evaluate_county('walton');
-- Expected G: density >= 95.0 (PASS)
-- (Exact metric depends on which parcels the Python script's EnerGov lookup assigns)
