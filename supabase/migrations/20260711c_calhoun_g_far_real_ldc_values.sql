-- Calhoun County G (zoning FAR/parking): real Calhoun County Land Development Code
-- FAR values for the 4 DOR-use-code zone_code labels (MH, SFR, TIMBER, VAC-RES) that
-- carry the 6 far/pk1000-applicable calhoun parcels (ingested 2026-07-10 from
-- dor_use_code:floridaparcels.com — these are DOR use-code crosswalk labels, NOT
-- actual Calhoun municipal zoning district codes; Calhoun's real land use districts
-- per its Comprehensive Plan / LDC are R, M-RR, M-UF, I, A, R-O, C, PUD, P, H, W).
--
-- SOURCE 1 (LDC): "Calhoun County, Florida Land Development Code", adopted
--   October 19, 2021. Downloaded from
--   https://www.calhouncountyfl.gov/uploads/2023/03/land-development-code-03-2023.pdf
--   Article IV, Table 4-C "Maximum Floor Area Ratios" (page IV-8 per doc pagination):
--     Land Use District   Floor Area Ratio
--     Residential          0.7
--     Commercial           1.0
--     Industrial           1.0
--     Conservation         0.25
--     Public               1.0
--     Historic             1.0
--   Article VI, Table (Density Restrictions - Unincorporated Calhoun County,
--   1991-2001, page VI-3 per doc pagination) gives the Comprehensive-Plan-sourced
--   figures actually used for the R and A land use districts:
--     R    Highest Permitted Density 2:1 (2 units/acre)   FAR .80   ISR NA
--     A    Highest Permitted Density 1:10                 FAR .50   ISR NA
--   (Two FAR figures for "Residential" appear in this document -- 0.7 in Article
--   IV Table 4-C and 0.80 in the Article VI/Table 4-B Comprehensive Plan table --
--   this is a genuine internal inconsistency in the county's own adopted code. We
--   use the more specific per-land-use-district Comprehensive Plan table (0.80 for
--   R, 0.50 for A) since it is the table explicitly cross-referenced by density
--   restrictions and is repeated identically in two places in the document
--   (Article IV Table 4-B and Article VI density table), while the 0.7 "Residential"
--   figure in Table 4-C appears only once and does not match either repetition of
--   the other table. This choice is flagged for orchestrator review.)
--
-- SOURCE 2 (Land Classifications / Allowable Uses, county planning dept handout):
--   https://www.calhouncountyfl.gov/uploads/2024/04/land-classification-allowable-uses.pdf
--   This document (R Residential, M-RR, M-UF, A-Agriculture sections) documents
--   setbacks, max height, max impervious lot coverage, min building sqft, and max
--   commercial-structure-sqft caps for each district -- it does NOT mention FAR or
--   any parking-per-1000sf standard anywhere in its 5 pages.
--
-- PARKING (parking_per_1000sf): Calhoun's LDC (Article IX, Table 9C "Parking Space
--   Requirements") ties parking to bedrooms for Residential ("1 space per bedroom")
--   and to gross floor area per 100/200/350/400/1000 sqft ONLY for named commercial/
--   institutional use categories (restaurants, car repair, wholesale sales, open air
--   markets, etc). There is NO parking-per-1000sf standard anywhere in the LDC for
--   Residential, Agriculture, Mobile Home, Timberland, or Vacant Residential land
--   uses -- the closest analog (1 space/bedroom) is a per-unit, not per-1000sf,
--   metric and converting it would require guessing an average bedroom size per
--   dwelling, which HARD GUARDRAILS forbid. parking_per_1000sf is therefore left
--   NULL for all 4 rows below -- this is a genuine, honest ordinance gap, not an
--   oversight. G will remain failing (LEAST(density,far,pk1000) requires all three
--   to be non-NULL-percentage-passing; pk1000_of_applicable stays NULL/0 because no
--   real value exists to cite).
--
-- MH  = DOR use code label for mobile-home-classed parcels -> conceptually Calhoun's
--       R (Residential) district per LDC 6.02.14 "Special Requirements for Mobile
--       Homes" (mobile/manufactured homes are permitted within Residential and other
--       districts, not a separate FAR category) -> FAR 0.80 (R district)
-- SFR = DOR use code label for single-family-residential-classed parcels ->
--       Calhoun's R (Residential) district -> FAR 0.80
-- TIMBER = DOR use code label for timberland-classed parcels -> Calhoun's A
--       (Agriculture) district ("Agriculture...includes mainly timberlands" per
--       LDC Section 6.02.06) -> FAR 0.50
-- VAC-RES = DOR use code label for vacant-residential-classed parcels -> Calhoun's
--       R (Residential) district (vacant land within a residential-use-coded
--       parcel; governed by the same district standards until developed) -> FAR 0.80

BEGIN;

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, created_at)
VALUES
  (922, 'MH', 'Mobile Home (DOR use-code crosswalk -> Calhoun R Residential district)', 'residential',
   'DOR use-code label from floridaparcels.com ingestion (2026-07-10). Not a distinct Calhoun LDC district; mobile/manufactured homes are permitted within the R Residential district per LDC Section 6.02.14. FAR sourced from Calhoun County LDC (adopted 2021-10-19) Article VI density table for the R district.',
   'Article VI (Land Use Districts), R Residential density table; Article IV Table 4-B', now()),
  (922, 'SFR', 'Single Family Residential (DOR use-code crosswalk -> Calhoun R Residential district)', 'residential',
   'DOR use-code label from floridaparcels.com ingestion (2026-07-10). Maps to Calhoun LDC R Residential district. FAR sourced from Calhoun County LDC (adopted 2021-10-19) Article VI density table for the R district.',
   'Article VI (Land Use Districts), R Residential density table; Article IV Table 4-B', now()),
  (922, 'TIMBER', 'Timberland (DOR use-code crosswalk -> Calhoun A Agriculture district)', 'agricultural',
   'DOR use-code label from floridaparcels.com ingestion (2026-07-10). Maps to Calhoun LDC A Agriculture district ("Agriculture...includes mainly timberlands" per LDC Section 6.02.06). FAR sourced from Calhoun County LDC (adopted 2021-10-19) Article VI density table for the A district.',
   'Article VI (Land Use Districts), Section 6.02.06 Agriculture; Article IV Table 4-B', now()),
  (922, 'VAC-RES', 'Vacant Residential (DOR use-code crosswalk -> Calhoun R Residential district)', 'residential',
   'DOR use-code label from floridaparcels.com ingestion (2026-07-10). Maps to Calhoun LDC R Residential district (vacant land, governed by R district standards). FAR sourced from Calhoun County LDC (adopted 2021-10-19) Article VI density table for the R district.',
   'Article VI (Land Use Districts), R Residential density table; Article IV Table 4-B', now())
ON CONFLICT DO NOTHING;

-- Populate real, citable FAR (max_far) from the Calhoun County LDC Article VI
-- density table (repeated identically in Article IV Table 4-B). max_density_du_acre
-- and parking_per_1000sf are left NULL: density for these DOR-derived rows is
-- already independently satisfied for the parcels via other means (this migration
-- targets G's FAR/parking gap specifically, not density), and no real
-- parking-per-1000sf ordinance value exists to cite (see comment block above).
INSERT INTO zone_standards (zoning_district_id, max_far, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 0.80,
       'https://www.calhouncountyfl.gov/uploads/2023/03/land-development-code-03-2023.pdf',
       'Article VI Density Restrictions table (R Residential row); Article IV Table 4-B',
       0.75, now()
FROM zoning_districts WHERE jurisdiction_id=922 AND code IN ('MH','SFR','VAC-RES')
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_far, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 0.50,
       'https://www.calhouncountyfl.gov/uploads/2023/03/land-development-code-03-2023.pdf',
       'Article VI Density Restrictions table (A Agriculture row); Article IV Table 4-B',
       0.75, now()
FROM zoning_districts WHERE jurisdiction_id=922 AND code = 'TIMBER'
ON CONFLICT DO NOTHING;

COMMIT;
