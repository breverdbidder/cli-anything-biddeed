-- Shard-9: okaloosa G density bifurcation fix (2026-07-24)
--
-- CONTEXT: The 2026-07-19 G-fix migration
-- (20260719h_gtm22j_shard3_okaloosa_g_real_ordinance_zone_standards.sql)
-- left density=NULL for R-1 and MU in Unincorporated Okaloosa County (id=1407)
-- because the LDC specifies TWO values depending on parcel location:
--   R-1: 4 du/acre north of Eglin AFB encroachment boundary
--        5 du/acre south of Eglin AFB encroachment boundary
--   MU:  25 du/acre inside the Urban Development Area Boundary (UDAB)
--        4 du/acre outside UDAB
-- This left G at density=75.6% (FAIL, needs >=95%).
--
-- SOURCE: Okaloosa County LDC (Land Development Code):
--   R-1: Table 2.3 (Sec. 2.03.06), 4 du/acre north / 5 south of Eglin AFB
--   MU:  Table 2.6 (Sec. 2.07.07), 25 inside UDAB / 4 outside UDAB
--   Source URL: https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf
--
-- STRATEGY: Create four sub-district codes in zoning_districts:
--   R-1-N: north of Eglin AFB → density=4 du/acre
--   R-1-S: south of Eglin AFB → density=5 du/acre
--   MU-IN: inside UDAB → density=25 du/acre
--   MU-OUT: outside UDAB → density=4 du/acre
--
-- Per-parcel GIS resolution is handled by:
--   scripts/okaloosa_g_density_bifurcation_fix.py
--   (queries Eglin AFB/UDAB boundary layers on okgis.myokaloosa.com
--    to classify each parcel's lat/lon into the correct sub-district)
--
-- This migration creates the sub-district and zone_standards rows;
-- the Python script updates parcel_zones to point to the correct sub-district.
--
-- Note: parcel_zones.zone_code is updated from 'R-1'→'R-1-N'/'R-1-S'
-- and 'MU'→'MU-IN'/'MU-OUT' by the Python script. The original 'R-1' and
-- 'MU' zoning_districts rows (with NULL density) are NOT deleted because
-- future new parcels may be assigned these codes by the zoning substrate
-- script before this bifurcation fix runs — the fix is idempotent and
-- re-runs cleanly.

-- -------------------------------------------------------------------------
-- R-1 sub-districts
-- -------------------------------------------------------------------------
INSERT INTO zoning_districts (
    jurisdiction_id, code, name, category, description,
    ordinance_section, far_regulated, density_regulated, pk1000_regulated
)
SELECT
    1407,
    'R-1-N',
    'Residential-1 North of Eglin AFB (Unincorporated Okaloosa)',
    'Residential',
    'Single-family residential north of Eglin AFB encroachment boundary. Max density 4 du/acre per Okaloosa County LDC Table 2.3 (northern density tier). Created by shard-9 density bifurcation fix 2026-07-24.',
    'Okaloosa County LDC Sec. 2.03.06, Table 2.3 (north of Eglin AFB encroachment boundary: 4 du/acre)',
    true, true, false
WHERE NOT EXISTS (
    SELECT 1 FROM zoning_districts
    WHERE jurisdiction_id = 1407 AND code = 'R-1-N'
);

INSERT INTO zoning_districts (
    jurisdiction_id, code, name, category, description,
    ordinance_section, far_regulated, density_regulated, pk1000_regulated
)
SELECT
    1407,
    'R-1-S',
    'Residential-1 South of Eglin AFB (Unincorporated Okaloosa)',
    'Residential',
    'Single-family residential south of Eglin AFB encroachment boundary. Max density 5 du/acre per Okaloosa County LDC Table 2.3 (southern density tier). Created by shard-9 density bifurcation fix 2026-07-24.',
    'Okaloosa County LDC Sec. 2.03.06, Table 2.3 (south of Eglin AFB encroachment boundary: 5 du/acre)',
    true, true, false
WHERE NOT EXISTS (
    SELECT 1 FROM zoning_districts
    WHERE jurisdiction_id = 1407 AND code = 'R-1-S'
);

-- -------------------------------------------------------------------------
-- MU sub-districts
-- -------------------------------------------------------------------------
INSERT INTO zoning_districts (
    jurisdiction_id, code, name, category, description,
    ordinance_section, far_regulated, density_regulated, pk1000_regulated
)
SELECT
    1407,
    'MU-IN',
    'Mixed Use Inside UDAB (Unincorporated Okaloosa)',
    'Mixed-Use',
    'Mixed use inside the Urban Development Area Boundary. Max density 25 du/acre per Okaloosa County LDC Table 2.6. Created by shard-9 density bifurcation fix 2026-07-24.',
    'Okaloosa County LDC Sec. 2.07.07, Table 2.6 (inside UDAB: 25 du/acre)',
    true, true, false
WHERE NOT EXISTS (
    SELECT 1 FROM zoning_districts
    WHERE jurisdiction_id = 1407 AND code = 'MU-IN'
);

INSERT INTO zoning_districts (
    jurisdiction_id, code, name, category, description,
    ordinance_section, far_regulated, density_regulated, pk1000_regulated
)
SELECT
    1407,
    'MU-OUT',
    'Mixed Use Outside UDAB (Unincorporated Okaloosa)',
    'Mixed-Use',
    'Mixed use outside the Urban Development Area Boundary. Max density 4 du/acre per Okaloosa County LDC Table 2.6. Created by shard-9 density bifurcation fix 2026-07-24.',
    'Okaloosa County LDC Sec. 2.07.07, Table 2.6 (outside UDAB: 4 du/acre)',
    true, true, false
WHERE NOT EXISTS (
    SELECT 1 FROM zoning_districts
    WHERE jurisdiction_id = 1407 AND code = 'MU-OUT'
);

-- -------------------------------------------------------------------------
-- zone_standards for all four sub-districts
-- -------------------------------------------------------------------------
INSERT INTO zone_standards (
    zoning_district_id, max_density_du_acre, max_far,
    source_url, ordinance_section, confidence_score
)
SELECT zd.id, 4.0, 0.10,
    'https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf',
    'Sec. 2.03.06, Table 2.3 (RESIDENTIAL-1 BULK REGULATIONS, north of Eglin AFB: 4 du/acre)',
    0.95
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 1407 AND zd.code = 'R-1-N'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

INSERT INTO zone_standards (
    zoning_district_id, max_density_du_acre, max_far,
    source_url, ordinance_section, confidence_score
)
SELECT zd.id, 5.0, 0.10,
    'https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf',
    'Sec. 2.03.06, Table 2.3 (RESIDENTIAL-1 BULK REGULATIONS, south of Eglin AFB: 5 du/acre)',
    0.95
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 1407 AND zd.code = 'R-1-S'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

INSERT INTO zone_standards (
    zoning_district_id, max_density_du_acre, max_far,
    source_url, ordinance_section, confidence_score
)
SELECT zd.id, 25.0, 2.00,
    'https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf',
    'Sec. 2.07.07, Table 2.6 (BULK REGULATIONS FOR MU DISTRICTS, inside UDAB: 25 du/acre)',
    0.95
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 1407 AND zd.code = 'MU-IN'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

INSERT INTO zone_standards (
    zoning_district_id, max_density_du_acre, max_far,
    source_url, ordinance_section, confidence_score
)
SELECT zd.id, 4.0, 2.00,
    'https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf',
    'Sec. 2.07.07, Table 2.6 (BULK REGULATIONS FOR MU DISTRICTS, outside UDAB: 4 du/acre)',
    0.95
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 1407 AND zd.code = 'MU-OUT'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);
