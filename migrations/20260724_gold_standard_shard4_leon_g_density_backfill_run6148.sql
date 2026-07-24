-- GOLD STANDARD shard-4 (leon/glades/walton), loop run 6148, dispatch 0fc2eae2.
-- County: leon. Letter G density backfill -- closes the gap opened by the
-- previous migration in this run (20260724_..._g_regression_fix_run6148.sql),
-- which correctly classified MR-1/R-3(x2)/RP-2/UF as category='residential'
-- (fixing FAR/parking N/A status) but left max_density_du_acre NULL, dropping
-- G's density dimension from 98.7% to 90.5% (needed >=95%).
--
-- Real ordinance values, each independently verified live this session by
-- fetching the actual talgov.com Land Development Code PDF and reading the
-- cited section text (not guessed, not inferred from a neighboring code):
--   MR-1 (Tallahassee, jur 917): Sec. 10-250 -- "maximum gross density
--     allowed for new residential development in the MR-1 district is 20
--     dwelling units per acre" -- mr_1_city.pdf
--   R-3  (Tallahassee, jur 917): Sec. 10-246 -- "maximum gross density
--     allowed for new residential development in the R-3 district is 8
--     dwelling units per acre" -- r_3_city.pdf
--   R-3  (Unincorporated, jur 1397): Sec. 10-6.637 -- identical 8 du/acre
--     cap under the county code section -- r_3_county.pdf
--   RP-2 (Tallahassee, jur 917): Sec. 10-6.617(3)(b) -- "prohibiting
--     densities in excess of six (6.0) dwelling units per acre" -- rp2a.pdf
--   UF   (Unincorporated, jur 1397): Sec. 10-163(a) -- "low-density
--     residential development of no greater than one unit on three acres"
--     = 1/3 = 0.33 du/acre (base, non-clustered figure) -- uf.pdf
--
-- Expected effect: density_applicable_parcels unchanged (179), numerator
-- +15 (all 5 newly-classified codes' parcels now carry a real value),
-- pct_density_of_applicable 90.5% -> ~98.9%, G PASS.

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT id, 20.00,
  'https://www.talgov.com/Uploads/Public/Documents/place/zoning/mr_1_city.pdf', 'Sec. 10-250'
FROM zoning_districts WHERE jurisdiction_id = 917 AND code = 'MR-1'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zoning_districts.id);

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT id, 8.00,
  'https://www.talgov.com/Uploads/Public/Documents/place/zoning/r_3_city.pdf', 'Sec. 10-246'
FROM zoning_districts WHERE jurisdiction_id = 917 AND code = 'R-3'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zoning_districts.id);

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT id, 8.00,
  'https://www.talgov.com/Uploads/Public/Documents/place/zoning/r_3_county.pdf', 'Sec. 10-6.637'
FROM zoning_districts WHERE jurisdiction_id = 1397 AND code = 'R-3'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zoning_districts.id);

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT id, 6.00,
  'https://www.talgov.com/Uploads/Public/Documents/place/zoning/rp2a.pdf', 'Sec. 10-6.617(3)(b)'
FROM zoning_districts WHERE jurisdiction_id = 917 AND code = 'RP-2'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zoning_districts.id);

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT id, 0.33,
  'https://www.talgov.com/Uploads/Public/Documents/place/zoning/uf.pdf', 'Sec. 10-163(a)'
FROM zoning_districts WHERE jurisdiction_id = 1397 AND code = 'UF'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zoning_districts.id);
