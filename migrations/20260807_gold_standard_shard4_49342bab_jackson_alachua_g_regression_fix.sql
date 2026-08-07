INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated)
SELECT 1515, 'FLU-COMMERCIAL', 'Future Land Use: Commercial -- Jackson County FLUM FeatureServer, LAND_USE=Commercial. Same FLU schema as FLU-RES/FLU-AG2 (no FAR/parking figure exists in this FLU schema -- land-use-category regulation, not district-based bulk standards), hence far_regulated/pk1000_regulated explicitly false rather than fabricated.', 'commercial', false, false, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id=1515 AND code='FLU-COMMERCIAL');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated)
SELECT 1022, 'FLU-GRACEVILLE-RES', 'Future Land Use: Residential -- inferred from DOR_UC=001 (SFR) plus Jackson countywide FLUM naming precedent (FLU-SNEADS-AG, FLU-CAMPBELLTON-RES) for municipalities lacking dedicated zoning GIS; same FLU schema as county FLUM layers -- no FAR/parking figure exists, hence far_regulated/pk1000_regulated explicitly false rather than fabricated.', 'residential', false, false, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id=1022 AND code='FLU-GRACEVILLE-RES');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated)
SELECT 915, 'U3', 'Urban 3', 'residential', NULL, false, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id=915 AND code='U3');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated)
SELECT 915, 'RC', 'Residential Conservation', 'residential', NULL, false, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id=915 AND code='RC');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated)
SELECT 1404, 'R-1C', 'Residential Single Family (R-1C)', 'residential', NULL, NULL, NULL
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id=1404 AND code='R-1C');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated)
SELECT 891, 'R-3', 'Residential (R-3)', 'residential', NULL, NULL, NULL
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id=891 AND code='R-3');
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT 13680, 4, 'https://growth-management.alachuacounty.us/formsdocs/ULDC_Replacement_Pages_Oct_2018.pdf', 'Chapter 403 Art.3 Table 403.07.1 (R-1a or R-1c: 1-4 per acre; using max of range = 4)'
WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id=13680);
