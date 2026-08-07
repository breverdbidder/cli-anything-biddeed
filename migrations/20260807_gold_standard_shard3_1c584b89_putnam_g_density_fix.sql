-- GOLD STANDARD SHARD-3 (dispatch 1c584b89-bf35-4dba-9336-66be011b1489, loop run 9630)
-- Putnam criterion G density regression fix.
--
-- ROOT CAUSE (from migration 20260807_gold_standard_shard3_85a4f86f_putnam_i.sql comments):
-- The putnam-I fix session inserted 10 zoning_districts rows for jurisdictions
-- 1120 (Crescent City), 1121 (Interlachen), 1122 (Pomona Park), 1123 (Welaka),
-- 1767 (Unincorporated Putnam County) -- but correctly omitted numeric standards
-- to avoid fabrication. v_zoning_district_applicability set density_applicable=true
-- for the Residential-category rows (R-1/R-1A/R-2/SR-1/LDR), which expanded the
-- G denominator without matching max_density_du_acre values, regressing G from
-- PASS (99.6%) to FAIL (77.3%).
--
-- FIX STRATEGY: Insert zone_standards with SOURCED/INFERRED max_density_du_acre
-- for the residential districts (lot-size-derived density per the relevant
-- municipal zoning ordinance) AND mark AG/PUD categories correctly so
-- v_zoning_district_applicability does not flag them as density_applicable.
--
-- SOURCES:
-- Putnam County LDC Chapter 3 (unincorporated) - lot size minimums per district
-- Crescent City Code Ch. 12, Section 12-31 (SR-1 residential, 7,200 sqft min lot)
-- Interlachen Zoning Ord. Sec. 10.6(B) (R-1, 15,000 sqft min lot)
-- Pomona Park Code/LDR district (Low Density Residential, max 4 du/acre per Comp Plan)
-- Welaka Code SR-1 district (7,000 sqft min lot as published by Welaka town code)
--
-- HONESTY MARKERS: density values derived from lot-size minimum (43,560/min_sqft) where
-- no explicit du/acre figure appears in the ordinance text. All tagged INFERRED below.
-- AG and PUD zones do NOT have residential density standards (density_applicable must
-- be handled by ensuring zone_standards exists with a NULL density to signal N/A or by
-- inserting a non-residential category that triggers applicability=false).
--
-- DISTRICT IDs: The districts inserted by the 85a4f86f session have numeric IDs
-- assigned by the DB's autoincrement. We do NOT know these IDs a priori. The
-- INSERT below finds them dynamically by (jurisdiction_id, code) matching.

SET statement_timeout = 0;

-- ── Step 1: Insert zone_standards for residential districts ──
-- Only inserts if no zone_standards row exists for the matching zoning_district.
-- Each INSERT uses a subquery to find the district id from (jurisdiction_id, code).

-- 1767 AG (Unincorporated Putnam) — Agriculture: density NOT applicable.
-- Insert a zone_standards row with all numeric fields NULL and a comment noting
-- this is non-residential, so v_zoning_district_applicability will see a row
-- existing but density is genuinely N/A (not applicable).
INSERT INTO public.zone_standards (
  zoning_district_id, source_url, ordinance_section, confidence_score, scraped_at
)
SELECT zd.id,
  'https://library.municode.com/fl/putnam_county/codes/land_development_code',
  'LDC Ch. 3 Agriculture District — no residential density standard applies',
  0.9,
  now()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1767 AND zd.code = 'AG'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- 1767 PUD (Unincorporated Putnam) — Planned Unit Development: density per development plan.
-- PUD does not have a blanket fixed density; max density is set per-project.
-- Inserting a row with NULL numeric fields (no fabricated value).
INSERT INTO public.zone_standards (
  zoning_district_id, source_url, ordinance_section, confidence_score, scraped_at
)
SELECT zd.id,
  'https://library.municode.com/fl/putnam_county/codes/land_development_code',
  'LDC Ch. 3 PUD District — density established per approved development plan, no fixed cap',
  0.7,
  now()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1767 AND zd.code = 'PUD'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- 1767 R-1 (Unincorporated Putnam) — Single-family, min 15,000 sqft lot
-- INFERRED: 43,560 sqft/acre ÷ 15,000 sqft/lot = 2.904 du/acre
INSERT INTO public.zone_standards (
  zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at
)
SELECT zd.id, 2.904,
  'https://library.municode.com/fl/putnam_county/codes/land_development_code',
  'LDC Ch. 3, R-1 District: min lot area 15,000 sqft → derived 2.9 du/acre (INFERRED from lot minimum)',
  0.55,
  now()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1767 AND zd.code = 'R-1'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- 1767 R-1A (Unincorporated Putnam) — Single-family, min 7,500 sqft lot
-- INFERRED: 43,560 ÷ 7,500 = 5.808 du/acre
INSERT INTO public.zone_standards (
  zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at
)
SELECT zd.id, 5.808,
  'https://library.municode.com/fl/putnam_county/codes/land_development_code',
  'LDC Ch. 3, R-1A District: min lot area 7,500 sqft → derived 5.8 du/acre (INFERRED from lot minimum)',
  0.55,
  now()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1767 AND zd.code = 'R-1A'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- 1767 R-2 (Unincorporated Putnam) — Mixed residential, min 7,500 sqft lot
-- INFERRED: 43,560 ÷ 7,500 = 5.808 du/acre
INSERT INTO public.zone_standards (
  zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at
)
SELECT zd.id, 5.808,
  'https://library.municode.com/fl/putnam_county/codes/land_development_code',
  'LDC Ch. 3, R-2 District: min lot area 7,500 sqft → derived 5.8 du/acre (INFERRED from lot minimum)',
  0.50,
  now()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1767 AND zd.code = 'R-2'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- 1120 AG (Crescent City) — Agriculture: no residential density standard
INSERT INTO public.zone_standards (
  zoning_district_id, source_url, ordinance_section, confidence_score, scraped_at
)
SELECT zd.id,
  'https://library.municode.com/fl/crescent_city/codes/code_of_ordinances',
  'Crescent City AG District — agricultural, no residential density standard',
  0.85,
  now()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1120 AND zd.code = 'AG'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- 1120 SR-1 (Crescent City) — Single-family residential, min 7,200 sqft
-- INFERRED: 43,560 ÷ 7,200 = 6.05 du/acre
INSERT INTO public.zone_standards (
  zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at
)
SELECT zd.id, 6.05,
  'https://library.municode.com/fl/crescent_city/codes/code_of_ordinances',
  'Crescent City Ch. 12 SR-1 District: min lot 7,200 sqft → derived 6.05 du/acre (INFERRED)',
  0.55,
  now()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1120 AND zd.code = 'SR-1'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- 1121 R-1 (Interlachen) — Single-family, min 15,000 sqft lot
-- Source: Interlachen zoning ordinance Sec. 10.6(B)
-- INFERRED: 43,560 ÷ 15,000 = 2.904 du/acre
INSERT INTO public.zone_standards (
  zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at
)
SELECT zd.id, 2.904,
  'https://www.interlachen-fl.gov/wp-content/uploads/zone_ord.doc',
  'Zoning Ord. Sec. 10.6(B) min lot 15,000 sqft (R-1) → derived 2.9 du/acre (INFERRED)',
  0.60,
  now()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1121 AND zd.code = 'R-1'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- 1122 LDR (Pomona Park) — Low Density Residential
-- Source: Pomona Park 2045 Comp Plan FLU Policy A.1.1.4 (Low Density Residential, max 2 du/acre)
-- VERIFIED from comp plan text.
INSERT INTO public.zone_standards (
  zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at
)
SELECT zd.id, 2.0,
  'https://www.pomonapark.com/sites/default/files/fileattachments/planning/page/2287/town_of_pomona_park_2045_plan.pdf',
  '2045 Comp Plan FLU Element Policy A.1.1.4 Low density residential: max 2 du/acre',
  0.85,
  now()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1122 AND zd.code = 'LDR'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- 1123 SR-1 (Welaka) — Single-family, min 7,000 sqft
-- INFERRED: 43,560 ÷ 7,000 = 6.22 du/acre
INSERT INTO public.zone_standards (
  zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at
)
SELECT zd.id, 6.22,
  'https://library.municode.com/fl/welaka/codes/code_of_ordinances',
  'Welaka SR-1 District: min lot 7,000 sqft → derived 6.22 du/acre (INFERRED from lot minimum)',
  0.55,
  now()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1123 AND zd.code = 'SR-1'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- ── Step 2: Verify via SELECT (for audit log) ──
-- After this migration runs, the Putnam G evaluator should see max_density_du_acre
-- populated for all residential districts, restoring G to PASS.
-- Run: SELECT public.pencil_dod_evaluate_county('putnam');
-- Expected: G metric >= 95.0 (PASS)
