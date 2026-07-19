-- Manatee county criterion G — parking_per_1000sf backfill from real LDC ordinance text
-- Source: Manatee County LDC Chapter 10 (Transportation Management), Table 10-1/Table B Parking Ratios
-- https://www.mymanatee.org/media/docs/default-source/development-services-department-documents/development-services-department-documents/land-development-regulations/ldc-ch10-transportation-management-v53-comments.pdf
--
-- Districts updated (jurisdiction: county='Manatee', name='Unincorporated Manatee County'):
--   GC    (zoning_district_id 10894, zone_standards.id 3600): General Retail Sales Uses 1/250 GFA
--         (min 4 spaces, whichever greater) -> INFERRED principal-use mapping = 4.0 spaces/1000sf
--   NC-M  (zoning_district_id 11250, zone_standards.id 3987): Retail Sales, Neighborhood General
--         1/250 GFA -> INFERRED principal-use mapping = 4.0 spaces/1000sf
--   NC-S  (zoning_district_id 11251, zone_standards.id 3986): Retail Sales, Neighborhood General
--         1/250 GFA -> INFERRED principal-use mapping = 4.0 spaces/1000sf (same table row as NC-M;
--         districts differ only in max project size cap, not parking ratio)
--
-- Districts explicitly LEFT NULL (BLANK > WRONG — no single per-1000sf ratio in ordinance):
--   HM (Manufacturing - Heavy, zone_standards.id 3988): ordinance gives a two-tier formula
--       (1/250 sq ft gross office area + 1/1000 sq ft remaining GFA) with no fixed office/non-office
--       split — reducing to one number would require an unstated assumption. Left null.
--   LM (Manufacturing - Light, zone_standards.id 3602): same two-tier formula issue as HM. Left null.

UPDATE zone_standards SET parking_per_1000sf = 4 WHERE id = 3600; -- GC
UPDATE zone_standards SET parking_per_1000sf = 4 WHERE id = 3987; -- NC-M
UPDATE zone_standards SET parking_per_1000sf = 4 WHERE id = 3986; -- NC-S
