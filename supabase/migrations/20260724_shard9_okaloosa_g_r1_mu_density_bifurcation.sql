-- Gold Standard shard-9, dispatch f8de10ec-e7af-4ac2-9af7-6b7dd80c3809
-- WORK-PACKAGE 5: okaloosa G (zoning gold standard) -- R-1 / MU density bifurcation
--
-- BACKGROUND: an earlier unmerged session (scripts/shard4_run5668_okaloosa_cei_g_fix.py,
-- and landed migration 20260719h_gtm22j_shard3_okaloosa_g_real_ordinance_zone_standards.sql)
-- hypothesized that Unincorporated Okaloosa County's R-1 and MU zoning districts have
-- max_density_du_acre split by geography, and left max_density_du_acre NULL for both
-- districts (zoning_districts.id 12081 R-1, id 12083 MU) rather than fabricate a single
-- value. That hypothesis was NEVER independently verified against ordinance text.
--
-- THIS SESSION verified it directly against the primary source PDF
-- (https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf, downloaded
-- and text-extracted 2026-07-24):
--
--   Sec. 2.03.06, Table 2.3 (RESIDENTIAL - 1 BULK REGULATIONS), p.2-17:
--     "MAXIMUM DENSITY
--      North of Eglin AFB    no more than 4 dwellings/acre
--      South of Eglin AFB    no more than 5 dwellings/acre"
--
--   Sec. 2.07.07, Table 2.6 (BULK REGULATIONS FOR MU DISTRICTS), p.2-24/2-25:
--     "MAXIMUM DENSITY
--      Inside Urban Development Area Boundary (UDAB)      No more than 25 dwellings/acre
--      Outside UDAB or Rural Community                    No more than 4 dwellings/acre"
--
-- CONFIRMED: the bifurcation is real, not a fabricated hypothesis. Both district codes
-- genuinely have two different max-density values keyed on parcel geography.
--
-- RESOLUTION METHOD (per-parcel, not guessed):
--   MU (5 gap parcels): point-in-polygon against Okaloosa County GIS "Urban Development
--     Boundary" layer (okgis.myokaloosa.com/arcgis/rest/services/Planning-Development/
--     Zoning/MapServer/12, 16 polygon features, real county-published UDAB geometry).
--     Query run 2026-07-24, esriSpatialRelIntersects, inSR/outSR=4326:
--       18-3N-23-1800-0000-013B  -> INSIDE UDAB  (668 Mayo Trail, Crestview)
--       32-3N-23-303D-0000-0110  -> INSIDE UDAB  (Browning Ct, Crestview)
--       15-3N-24-0000-0067-0000  -> OUTSIDE UDAB (1886 Wadsworth Rd, Baker)
--       224N23000000370000      -> OUTSIDE UDAB (6287 Bethany Dr, Crestview)
--       261S22100000000190      -> OUTSIDE UDAB (4411 Sonoma Cir, Niceville)
--
--   R-1 (9 gap parcels): the county GIS has no single queryable "north/south of Eglin
--     AFB" line layer (Planning-Development/Zoning MapServer layers 6 "Eglin Enchroachment
--     Zone" and 7 "Eglin Enchroachment Zone Density Limits" are a DIFFERENT, narrower
--     noise-compatibility corridor -- extent lat 30.6405-30.7286 -- that does not contain
--     any of the 9 gap parcels and is not the ordinance's plain-language "north/south of
--     Eglin AFB" reference). Instead used the authoritative DoD-sourced Eglin AFB
--     reservation boundary polygon (ArcGIS: services.arcgis.com/hRUr1F8lE8Jq2uJo/ArcGIS/
--     rest/services/milbases/FeatureServer/0, SITE_NAME='Eglin AFB', DISDI/OSD source,
--     28-ring multipolygon, main ring 12,966 vertices). For each parcel: cast a vertical
--     ray at the parcel's own longitude, find where it crosses the Eglin polygon boundary,
--     and classify north/south of that crossing band; cross-checked with a full even-odd
--     point-in-ring test and with the parcel_id's own PLSS Township digit (Florida
--     Township numbering: N townships lie north of the base line, S townships south --
--     Eglin's main reservation sits in the 1N-2N band). All 9 parcels resolved
--     unambiguously and every method agreed:
--       06-3N-24-1000-0000-0080  -> NORTH (Twp 3N, 1509 Long Needle Ct)
--       12-3N-24-1101-000F-0080  -> NORTH (Twp 3N, 5225 Moore Loop)
--       26-4N-23-0000-0008-0020  -> NORTH (Twp 4N, Tupelo St)
--       01-2S-24-0790-000K-0190  -> SOUTH (Twp 2S, 23 Woodham Ave)
--       02-2S-24-0502-000B-0110  -> SOUTH (Twp 2S, 800 Bradford Dr)
--       02-2S-24-213B-000E-0050  -> SOUTH (Twp 2S, 409 Ed St)
--       10-2S-24-3020-000A-0570  -> SOUTH (Twp 2S, 155 Homewood Dr)
--       102S243030000D0310       -> SOUTH (Twp 2S, 201 Pawnee Cir)
--       24-1S-22-223B-000E-0200  -> SOUTH (Twp 1S, ~440ft south of Eglin boundary,
--                                    1486 Cat Mar Rd, Niceville/Bluewater Bay area)
--
-- SCHEMA NOTE: zoning_districts/zone_standards store one density value per
-- (jurisdiction_id, code) pair -- there is no per-parcel override column, and adding one
-- would require the shared v_zoning_gold_standard_kpi_v3 / v_zoning_gold_standard_card
-- views (used by every county, not just okaloosa) to be taught to read it. Rather than
-- touch those shared views, this migration uses the EXISTING extensibility point the
-- pipeline already relies on: distinct zone_code values that resolve to distinct
-- zoning_districts rows. Two new codes per bifurcated district (R-1-N / R-1-S,
-- MU-IN / MU-OUT), each with correct district-specific density (all other bulk figures
-- -- FAR, setbacks, height, lot coverage -- copied unchanged from the existing R-1/MU
-- rows, since Table 2.3 / Table 2.6 only bifurcate MAXIMUM DENSITY, nothing else). The 14
-- gap parcel_zones rows are repointed to the correct new code. This is additive-only,
-- does not touch shared view logic, and does not affect any other county.

-- ---------------------------------------------------------------------------------------
-- 1) New zoning_districts rows: R-1-N, R-1-S, MU-IN, MU-OUT (jurisdiction_id=1407)
-- ---------------------------------------------------------------------------------------

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 1407, 'R-1-N', 'Residential - 1 (R-1) District -- North of Eglin AFB', 'Residential',
       'Single-family detached residential. Max density 4 du/acre (north-of-Eglin-AFB tier). Okaloosa County LDC Table 2.3. Zone-code split from R-1 to express the ordinance''s geography-bifurcated density; all other bulk standards identical to R-1.',
       'Okaloosa County LDC Sec. 2.03.06, Table 2.3', true, true, null
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1407 AND code = 'R-1-N');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 1407, 'R-1-S', 'Residential - 1 (R-1) District -- South of Eglin AFB', 'Residential',
       'Single-family detached residential. Max density 5 du/acre (south-of-Eglin-AFB tier). Okaloosa County LDC Table 2.3. Zone-code split from R-1 to express the ordinance''s geography-bifurcated density; all other bulk standards identical to R-1.',
       'Okaloosa County LDC Sec. 2.03.06, Table 2.3', true, true, null
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1407 AND code = 'R-1-S');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 1407, 'MU-IN', 'Mixed Use (MU) District -- Inside UDAB', 'Mixed-Use',
       'Mix of residential and non-residential uses. Max density 25 du/acre (inside Urban Development Area Boundary tier). Okaloosa County LDC Table 2.6. Zone-code split from MU to express the ordinance''s geography-bifurcated density; all other bulk standards identical to MU.',
       'Okaloosa County LDC Sec. 2.07.07, Table 2.6', true, true, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1407 AND code = 'MU-IN');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 1407, 'MU-OUT', 'Mixed Use (MU) District -- Outside UDAB / Rural Community', 'Mixed-Use',
       'Mix of residential and non-residential uses. Max density 4 du/acre (outside UDAB / rural community tier). Okaloosa County LDC Table 2.6. Zone-code split from MU to express the ordinance''s geography-bifurcated density; all other bulk standards identical to MU.',
       'Okaloosa County LDC Sec. 2.07.07, Table 2.6', true, true, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1407 AND code = 'MU-OUT');

-- ---------------------------------------------------------------------------------------
-- 2) zone_standards for the 4 new districts -- clone existing R-1 (id 12081) / MU (id
--    12083) bulk figures (FAR, setbacks, height, lot coverage all unbifurcated per
--    ordinance text), only max_density_du_acre differs.
-- ---------------------------------------------------------------------------------------

INSERT INTO zone_standards (zoning_district_id, front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft, max_lot_coverage_pct, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 20, 10, 10, 45, 55, 0.10, 4.00,
       'https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf',
       'Sec. 2.03.06, Table 2.3 (RESIDENTIAL - 1 BULK REGULATIONS) -- "North of Eglin AFB: no more than 4 dwellings/acre"', 0.95
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 1407 AND zd.code = 'R-1-N'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

INSERT INTO zone_standards (zoning_district_id, front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft, max_lot_coverage_pct, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 20, 10, 10, 45, 55, 0.10, 5.00,
       'https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf',
       'Sec. 2.03.06, Table 2.3 (RESIDENTIAL - 1 BULK REGULATIONS) -- "South of Eglin AFB: no more than 5 dwellings/acre"', 0.95
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 1407 AND zd.code = 'R-1-S'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

INSERT INTO zone_standards (zoning_district_id, front_setback_ft, side_setback_ft, rear_setback_ft, max_lot_coverage_pct, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 20, 5, 10, 75, 2.00, 25.00,
       'https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf',
       'Sec. 2.07.07, Table 2.6 (BULK REGULATIONS FOR MU DISTRICTS) -- "Inside Urban Development Area Boundary (UDAB): No more than 25 dwellings/acre"', 0.95
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 1407 AND zd.code = 'MU-IN'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

INSERT INTO zone_standards (zoning_district_id, front_setback_ft, side_setback_ft, rear_setback_ft, max_lot_coverage_pct, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 20, 10, 10, 75, 2.00, 4.00,
       'https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf',
       'Sec. 2.07.07, Table 2.6 (BULK REGULATIONS FOR MU DISTRICTS) -- "Outside UDAB or Rural Community: No more than 4 dwellings/acre"', 0.95
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 1407 AND zd.code = 'MU-OUT'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

-- ---------------------------------------------------------------------------------------
-- 3) Repoint the 14 gap parcel_zones rows to their resolved code (Unincorporated Okaloosa
--    County, jurisdiction_id=1407 only -- scoped narrowly by parcel_id, touches no other
--    county's rows).
-- ---------------------------------------------------------------------------------------

UPDATE parcel_zones SET zone_code = 'R-1-S'
WHERE jurisdiction_id = 1407 AND zone_code = 'R-1'
  AND parcel_id IN (
    '01-2S-24-0790-000K-0190', '02-2S-24-0502-000B-0110', '02-2S-24-213B-000E-0050',
    '10-2S-24-3020-000A-0570', '102S243030000D0310', '24-1S-22-223B-000E-0200'
  );

UPDATE parcel_zones SET zone_code = 'R-1-N'
WHERE jurisdiction_id = 1407 AND zone_code = 'R-1'
  AND parcel_id IN (
    '06-3N-24-1000-0000-0080', '12-3N-24-1101-000F-0080', '26-4N-23-0000-0008-0020'
  );

UPDATE parcel_zones SET zone_code = 'MU-IN'
WHERE jurisdiction_id = 1407 AND zone_code = 'MU'
  AND parcel_id IN (
    '18-3N-23-1800-0000-013B', '32-3N-23-303D-0000-0110'
  );

UPDATE parcel_zones SET zone_code = 'MU-OUT'
WHERE jurisdiction_id = 1407 AND zone_code = 'MU'
  AND parcel_id IN (
    '15-3N-24-0000-0067-0000', '224N23000000370000', '261S22100000000190'
  );
