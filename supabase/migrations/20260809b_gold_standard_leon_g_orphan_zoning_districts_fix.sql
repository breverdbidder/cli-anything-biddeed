-- Gold Standard: leon county letter G regression fix (dispatch c5a8b2c7 follow-up)
--
-- ROOT CAUSE: a prior leon letter-I fix inserted 5 parcel_zones rows with zone_codes
-- that had NO matching zoning_districts row (CC, CP, OR-3, UT @ jurisdiction_id=917
-- Tallahassee; C-2 @ jurisdiction_id=1397 Unincorporated Leon County). The
-- v_zoning_gold_standard_kpi_v3 view LEFT JOINs zoning_districts -> zone_standards;
-- with no zoning_districts row, v_zoning_district_applicability's COALESCE(...,true)
-- defaults far_applicable/pk1000_applicable/density_applicable to TRUE while
-- max_far/parking_per_1000sf/max_density_du_acre are NULL (no zone_standards row
-- exists either) -- these 5 parcels count as "applicable but missing a value",
-- driving pct_far_of_applicable and pct_pk1000_of_applicable to 0.0%, which drove
-- G's LEAST(density,far,pk1000) to 0.0% (regressed from 98.9%).
--
-- FIX: insert real zoning_districts + zone_standards rows for all 5 codes, sourced
-- from the actual City of Tallahassee Land Development Code (Sec. 10-XXX, city
-- districts) and the Leon County Code of Ordinances (Sec. 10-6.XXX, unincorporated
-- county C-2), including the master TABLE 10E: Density and Intensity Standards
-- (Tallahassee LDC Article IV Division 4, municode.com Ch10Art4Div4.pdf) which is
-- the authoritative summary table cross-referenced across all Transect/Downtown
-- Overlay districts.
--
-- Sources (fetched and read directly, 2026-08-09):
--   https://www.talgov.com/Uploads/Public/Documents/place/zoning/cc_city.pdf   (Sec. 10-197, CC)
--   https://www.talgov.com/Uploads/Public/Documents/place/zoning/cp_city.pdf   (Sec. 10-258, CP)
--   https://www.talgov.com/Uploads/Public/Documents/place/zoning/or_3_city.pdf (Sec. 10-253, OR-3)
--   https://www.talgov.com/Uploads/Public/Documents/place/zoning/ut.pdf        (Sec. 10-242, UT)
--   https://www.talgov.com/Uploads/Public/Documents/place/zoning/c_2_county.pdf (Sec. 10-6.647, C-2, Leon County unincorp.)
--   https://www.municode.com/sites/default/files/archives/webcontent/13907/Ch10Art4Div4.pdf
--     (TABLE 10E: Density and Intensity Standards -- s.f./acre intensity + DU/acre density
--      by Transect/Downtown-Overlay district; TABLE 8A/8B parking ratios by Transect)
--
-- Conversion note: Tallahassee LDC expresses non-residential intensity as
-- "gross building floor area (s.f.) per acre" rather than a bare FAR ratio.
-- FAR = floor area / lot area, so s.f.-per-acre / 43,560 s.f.-per-acre = FAR.
-- This matches the existing max_far value ranges already in zone_standards
-- (0.02 - 2.00) for other FL jurisdictions in this dataset.

-- =========================================================================
-- CC -- Central Core (Sec. 10-197), jurisdiction_id 917 (Tallahassee)
-- Category: mixed-use (residential up to 150 du/ac + commercial/retail by design intent,
--   "critical mass of activity in the central core", explicit downtown mixed character).
-- TABLE 10E (Downtown Overlay row "CC"): Intensity (s.f./acre) = NA, Footprint Density = 150 DU/acre.
--   The Downtown Overlay explicitly does NOT regulate FAR/intensity by a s.f.-per-acre cap --
--   height/massing is controlled instead by the Downtown Regulating Plan maps DT-1..DT-5
--   (Sec. 10-282, 10-282.1) which is a dimensional (setback/height) standard, not a FAR number.
--   far_regulated = false is a genuine ordinance-sourced N/A, not a guess.
-- TABLE 8B (Downtown Overlay Parking Ratios): "Developments proposed within the Central Core
--   of the Downtown Overlay are exempt from the parking requirements contained herein."
--   pk1000_regulated = false is a direct ordinance quote, not a guess.
-- Density: 150 DU/acre stated directly in both Sec. 10-197 ("Allow residential density of up
--   to 150 dwelling units per acre") and TABLE 10E.
-- =========================================================================
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, pk1000_regulated, density_regulated)
VALUES (917, 'CC', 'Central Core District', 'mixed-use',
  'Downtown mixed-use district intended to create a critical mass of activity in the central core of the City, allowing residential density up to 150 du/ac alongside retail/commercial/office uses. Governed by the Downtown Overlay Regulating Plan (Sec. 10-282) rather than the standard Land Use Development Matrix.',
  'Sec. 10-197', false, false, true)
;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 150.00,
  'https://www.talgov.com/Uploads/Public/Documents/place/zoning/cc_city.pdf',
  'Sec. 10-197; TABLE 10E (Ch10Art4Div4)', 1.00, now()
FROM zoning_districts WHERE jurisdiction_id = 917 AND code = 'CC';

-- =========================================================================
-- CP -- Commercial Parkway District (Sec. 10-258), jurisdiction_id 917 (Tallahassee)
-- Category: commercial (name is "Commercial Parkway"; residential only permitted above
--   ground-floor non-residential use, or as a secondary/conditional use).
-- Sec. 10-258 development standards table: "Any Permitted Principal Use ... 25,000 s.f. of
--   building floor area per acre" (commercial/office not to exceed 200,000 s.f. gross per parcel;
--   50,000 s.f./acre for warehousing/mini-storage/self-storage specifically).
--   FAR = 25,000 / 43,560 = 0.574.
-- Density: Sec. 10-258 text states directly "Residential development up to a maximum of 16
--   dwelling units per acre is permitted... minimum gross density of 6 dwelling units per acre
--   shall be required" for other residential development. Max used: 16 du/ac.
--   density_regulated = true override (category=commercial defaults density_applicable to
--   false in v_zoning_district_applicability, but CP's own ordinance text explicitly
--   regulates density, so the default must be overridden to true).
-- Parking: TABLE 8A General Parking Ratios, Transect 4 (CP is listed under "TABLE 10B:
--   Development standards for Transect 4 (R-4, OR-2, UP-1, MR-1, C-2, CP, CU-18, CU-26)").
--   General/Administrative/Medical Office and General Retail/Commercial both = 4.0/1000 s.f.
--   for T4. Using 4.0 as the representative commercial parking ratio for this district.
-- =========================================================================
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, pk1000_regulated, density_regulated)
VALUES (917, 'CP', 'Commercial Parkway District', 'commercial',
  'Located in Suburban FLU areas along urban arterial roadways with high traffic volumes; linear commercial development pattern of office, general commercial, community facilities, and intensive automotive commercial uses. Residential permitted up to 16 du/ac (min 6 du/ac).',
  'Sec. 10-258', true, true, true)
;

INSERT INTO zone_standards (zoning_district_id, max_far, max_density_du_acre, parking_per_1000sf, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 0.57, 16.00, 4.0,
  'https://www.talgov.com/Uploads/Public/Documents/place/zoning/cp_city.pdf',
  'Sec. 10-258 (intensity/density); TABLE 8A Transect 4, TABLE 10E (Ch10Art4Div4, parking/intensity)', 0.90, now()
FROM zoning_districts WHERE jurisdiction_id = 917 AND code = 'CP';

-- =========================================================================
-- OR-3 -- Office Residential District (Sec. 10-253), jurisdiction_id 917 (Tallahassee)
-- Category: mixed-use (explicit design intent: "promote urban density and intensity of
--   residential and office uses and the mixing of permitted uses").
-- Sec. 10-253 development standards table: "Any Permitted Principal Non-Residential Use ...
--   20,000 square feet of gross building floor area per acre" (3 stories max).
--   FAR = 20,000 / 43,560 = 0.459. (Note: a conditional override to 40,000 s.f./acre / 6
--   stories exists for properties formerly designated Mixed Use C on the FLU map -- not used
--   here since per-parcel former-FLU history cannot be determined from the ordinance text alone.)
-- Density: Sec. 10-253 text states directly "The maximum gross density allowed for new
--   residential development in the OR-3 district is 20 dwelling units per acre, while the
--   minimum gross density allowed is 8 dwelling units per acre." Max used: 20 du/ac.
-- Parking: TABLE 8A, Transect 5 (OR-3 listed under "TABLE 10C: Development standards for
--   Transect 5 (OR-3, UP-2, CM, CU-45, AC, UT)"). Office/Retail = 3.0/1000 s.f. for T5.
-- =========================================================================
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, pk1000_regulated, density_regulated)
VALUES (917, 'OR-3', 'Office Residential District', 'mixed-use',
  'Suburban FLU district promoting urban density/intensity of residential and office uses in close proximity, mixing permitted uses to promote transit use. Ground-floor retail permitted. Max density 20 du/ac (min 8 du/ac).',
  'Sec. 10-253', true, true, true)
;

INSERT INTO zone_standards (zoning_district_id, max_far, max_density_du_acre, parking_per_1000sf, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 0.46, 20.00, 3.0,
  'https://www.talgov.com/Uploads/Public/Documents/place/zoning/or_3_city.pdf',
  'Sec. 10-253 (intensity/density); TABLE 8A Transect 5, TABLE 10E/10C (Ch10Art4Div4, parking/intensity)', 0.90, now()
FROM zoning_districts WHERE jurisdiction_id = 917 AND code = 'OR-3';

-- =========================================================================
-- UT -- University Transition District (Sec. 10-242), jurisdiction_id 917 (Tallahassee)
-- IMPORTANT CORRECTION: "UT" is NOT "Utility" -- confirmed via Sec. 10-242 ordinance text
-- as "University Transition District": higher-density residential (student housing) near
-- FSU/FAMU/TCC campuses, with small-scale retail for immediate residents.
-- Category: mixed-use (residential + small-scale retail/commercial by explicit design intent).
-- TABLE 10E (Transect 5 row "UT"): Intensity (s.f./acre) = NA, Additional Intensity
--   Limitations = NA, Footprint = 25,000 (s.f., a building FOOTPRINT/ground-coverage cap,
--   NOT a floor-area-ratio -- confirmed by column position matching CU-26/CU-18's
--   "Footprint" column, e.g. CU-26 Footprint=8,000 with its own separate Intensity=30,000).
--   Because the Intensity (true FAR-equivalent) column is explicitly NA for UT, far_regulated
--   is set to false -- this is an ordinance-sourced N/A (Intensity column literal "NA"), not
--   a guess, distinct from Footprint which regulates a different dimension (ground coverage).
-- Density: 50 DU/acre stated both in Sec. 10-242 text ("Higher density residential development
--   of up to 50 du/ac") and TABLE 10E. (A 25% density bonus is available within Central Core
--   per Sec. 10-289 -- not applied here as it is a discretionary bonus, not a base standard.)
-- Parking: TABLE 8A, Transect 5 (UT listed under "TABLE 10C: Development standards for
--   Transect 5 (OR-3, UP-2, CM, CU-45, AC, UT)"). Office/Retail = 3.0/1000 s.f. for T5.
-- =========================================================================
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, pk1000_regulated, density_regulated)
VALUES (917, 'UT', 'University Transition District', 'mixed-use',
  'Compact land use category providing higher density residential (student-oriented) near FSU/FAMU/TCC campuses with small-scale retail for immediate residents; up to 50 du/ac. Development standards established within Article IV Division 4 (MMTD/Transect 5).',
  'Sec. 10-242', false, true, true)
;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, parking_per_1000sf, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 50.00, 3.0,
  'https://www.talgov.com/Uploads/Public/Documents/place/zoning/ut.pdf',
  'Sec. 10-242 (density); TABLE 8A Transect 5, TABLE 10E/10C (Ch10Art4Div4, parking; Intensity column = NA)', 0.90, now()
FROM zoning_districts WHERE jurisdiction_id = 917 AND code = 'UT';

-- =========================================================================
-- C-2 -- General Commercial District (Sec. 10-6.647), jurisdiction_id 1397
-- (Unincorporated Leon County -- distinct ordinance from Tallahassee's own C-2 at Sec. 10-256)
-- Category: commercial (name is "General Commercial"; residential permitted only above
--   ground-floor commercial/office use).
-- Sec. 10-6.647 development standards table: "Any Permitted Principal Use ... 12,500 square
--   feet of non-residential gross building floor area per acre" (not to exceed 200,000 s.f.
--   per 20-acre-or-less district, or 250,000 s.f. for 20-30 acre districts; individual
--   buildings capped at 50,000 gross s.f.). FAR = 12,500 / 43,560 = 0.287.
-- Density: Sec. 10-6.647 text states directly "The maximum gross density allowed for new
--   residential development in the C-2 district is 16 dwelling units per acre, with a minimum
--   gross density of 8 dwelling units per acre." Max used: 16 du/ac.
--   density_regulated = true override (category=commercial defaults density_applicable to
--   false, but C-2's own ordinance text explicitly regulates density).
-- Parking: TABLE 8A General Parking Ratios, Transect 4 (C-2 listed under "TABLE 10B:
--   Development standards for Transect 4 (R-4, OR-2, UP-1, MR-1, C-2, CP, CU-18, CU-26)").
--   Office/Retail = 4.0/1000 s.f. for T4. (Table 8A applies city/county-wide per Transect;
--   Leon County unincorporated C-2 is assigned to Transect 4 in the same master table.)
-- =========================================================================
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, pk1000_regulated, density_regulated)
VALUES (1397, 'C-2', 'General Commercial District', 'commercial',
  'Unincorporated Leon County district for Bradfordville Mixed Use, Suburban, or Woodville Rural Community FLU areas with direct access to major collector/arterial roads; small-scale retail/professional/office/community uses. Residential up to 16 du/ac (min 8 du/ac), required above ground-floor commercial use.',
  'Sec. 10-6.647', true, true, true)
;

INSERT INTO zone_standards (zoning_district_id, max_far, max_density_du_acre, parking_per_1000sf, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 0.29, 16.00, 4.0,
  'https://www.talgov.com/Uploads/Public/Documents/place/zoning/c_2_county.pdf',
  'Sec. 10-6.647 (intensity/density); TABLE 8A Transect 4, TABLE 10E/10B (Ch10Art4Div4, parking/intensity)', 0.90, now()
FROM zoning_districts WHERE jurisdiction_id = 1397 AND code = 'C-2';
