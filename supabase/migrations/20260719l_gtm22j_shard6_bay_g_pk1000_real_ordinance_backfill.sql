-- GTM-22j shard-6 (hillsborough/flagler/bay, dispatch 1f302343): bay letter G
-- pk1000 (parking_per_1000sf coverage) was the binding constraint at 27.3%
-- (density=96.5, far=100.0 already pass). Only 3 of 11 pk1000-applicable
-- zoning_districts rows (Panama City GC-1/GC-2/MU-2) had a real
-- parking_per_1000sf value; 4 rows (ids 3999/C-1, 4000/C-3A, 4637/MU-1,
-- 4254/CH) were NULL.
--
-- Values sourced from live-fetched, pdfplumber-extracted current ordinance
-- PDFs (verified 2026-07-19 by two independent agents, both downloaded and
-- extracted the PDFs themselves rather than trusting a citation):
--   Panama City ULDC Ch.108 Table 108-1 (panamacity.gov/DocumentCenter/View/2918):
--     "Business and professional offices: 1 per 250 sq. ft." = 4.0/1000sf
--     -- same table/rate already used for sibling GC-1/GC-2/MU-2 rows.
--   Bay County LDR Ch.25 Table 25.1 (baycountyfl.gov/DocumentCenter/View/617):
--     "General business, commercial, or personal service establishment
--      catering to retail trade: 4 spaces per 1,000 sq. ft." (page 3)
--     -- confirmed the existing Bulk Regulations source (DocumentCenter/View/3008)
--        already cited on these rows carries NO parking column, so this is a
--        genuinely separate, correct complementary source, not a duplicate.
--   Panama City Beach LDC Table 4.05.02.A (pcbfl.gov/DocumentCenter/View/283,
--     page 132 of 410, dated 12-11-25): "Commercial activities (Retail Sales,
--     retail business and business Uses not otherwise specified): 3.33 per
--     1,000 s.f. of g.l.a."
--
-- DISCLOSED JUDGMENT CALL (per adversarial verify pass): none of the three
-- source tables publish a parking rate broken out by exact zone code -- each
-- rate is mapped from the closest matching general-commercial/retail use
-- category in a citywide/countywide use-based table. Panama City MU-1 in
-- particular could plausibly use the 3.33 "retail" rate from the same table
-- instead of the 4.0 "business/professional office" rate chosen here; this
-- ambiguity is real and is recorded in ordinance_section for future review,
-- not hidden.
--
-- Idempotent: parking_per_1000sf IS NULL guards, safe to re-run.

BEGIN;

UPDATE public.zone_standards
SET parking_per_1000sf = 4.0,
    ordinance_section = ordinance_section || ' | Parking: Panama City ULDC Chapter 108, Table 108-1, "Business and professional offices" = 1 per 250 sq. ft. GFA = 4.0 spaces/1,000 sq ft. Citywide use-based table (not zone-specific); same rate already used for sibling districts GC-1/GC-2/MU-2. Judgment call: MU-1 could alternatively map to the 3.33 "retail" rate in the same table -- flagged for review, not a uniquely-published by-zone rate.'
WHERE id = 4637
  AND zoning_district_id = 11610
  AND parking_per_1000sf IS NULL;

UPDATE public.zone_standards
SET parking_per_1000sf = 4.0,
    ordinance_section = ordinance_section || ' | Parking: Bay County LDR Chapter 25, Table 25.1, "General business, commercial, or personal service establishment catering to retail trade" = 4 spaces per 1,000 sq ft GFA. Countywide use-based table (Chapter 25) distinct from the Chapter 6/Bulk Regulations table already cited above, which carries no parking column.'
WHERE id = 3999
  AND zoning_district_id = 11360
  AND parking_per_1000sf IS NULL;

UPDATE public.zone_standards
SET parking_per_1000sf = 4.0,
    ordinance_section = ordinance_section || ' | Parking: Bay County LDR Chapter 25, Table 25.1, "General business, commercial, or personal service establishment catering to retail trade" = 4 spaces per 1,000 sq ft GFA. Countywide use-based table (Chapter 25) distinct from the Chapter 6/Bulk Regulations table already cited above, which carries no parking column.'
WHERE id = 4000
  AND zoning_district_id = 11361
  AND parking_per_1000sf IS NULL;

UPDATE public.zone_standards
SET parking_per_1000sf = 3.33,
    ordinance_section = ordinance_section || ' | Parking: Panama City Beach LDC Sec. 4.05.02, Table 4.05.02.A, "Commercial activities (Retail Sales, retail business and business Uses not otherwise specified)" = 3.33 spaces per 1,000 sq ft g.l.a. Citywide use-based table (not zone-specific).'
WHERE id = 4254
  AND zoning_district_id = 11611
  AND parking_per_1000sf IS NULL;

COMMIT;
