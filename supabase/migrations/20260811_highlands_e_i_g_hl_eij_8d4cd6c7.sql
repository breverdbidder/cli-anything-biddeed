-- Gold Standard workstream hl_EIJ, dispatch 8d4cd6c7-e51a-4a0d-a8da-6995f13bad43
-- County: highlands. Letters: E (parcel linkage), I (card completeness),
-- G (zoning FAR/density/PK1000 coverage — regression guard for the I fix).
--
-- Idempotent record of the zoning_districts / zone_standards rows required
-- so that the 29 parcels backfilled by scripts/highlands_e_parcel_linkage.py
-- and scripts/highlands_i_zone_backfill.py (real zone_code values pulled
-- live from https://gis.highlandsfl.gov/server/rest/services/Layers/Zoning/
-- MapServer/0) don't regress letter G. Without these rows the new zone
-- codes join to NULL zoning_districts/zone_standards and count as
-- "applicable but missing standards" in v_zoning_gold_standard_kpi_v3,
-- which is exactly the self-inflicted regression a prior session's
-- migration (20260723170500_shard8_gadsden_highlands_e_i_g_close_740368a6.sql)
-- already warned about and fixed once before.
--
-- Sources (all live, fetched this session):
--   Highlands County Land Development Regulations, Chapter 12
--   https://cms2.revize.com/revize/highlandscountyfl/highlandscounty/departments/engineering/uploads/Chapter_12_Land_Development_Regulations.pdf
--     Section 12.05.210 R-1A residential district: min lot 10,000 sq ft -> 43,560/10,000 = 4.36 du/acre
--       (matches the pre-existing 918/R-1A and 1654/R1/R1A rows' precedent value already in this table)
--     Section 12.05.211 R-1 residential district: "same as R-1A" -> same 4.36 du/acre basis
--     Section 12.05.213 R-3 multiple-family district: FUD variant (R-3-FUD) density set
--       case-by-case at P&Z/BCC public hearing per Sec 12.05.29x FUD language
--       ("Maximum density per acre in this district shall be determined by
--       the FUD at the public hearings by the P&Z and the BCC") -> no fixed
--       ordinance density exists; marked density_regulated=false (genuinely
--       not applicable / no fixed standard), not left NULL-defaulting to
--       counted-but-missing.
--     Section 12.05.220 M-1 mobile home subdivisions district: min lot
--       5,000 sq ft (central sewer/water) -> 43,560/5,000 = 8.71 du/acre
--   Avon Park (jurisdiction_id 955): the county-appraiser ArcGIS zoning
--     layer exposes 'AP R1' / 'AP R1A' / 'AP C2' codes for parcels inside
--     Avon Park's municipal boundary, but Avon Park's own municipal zoning
--     ordinance was not reachable this session (avonpark.cc timed out; no
--     Municode chapter located in the session budget). Rather than fabricate
--     an Avon Park density figure, R1/R1A/M1S for jurisdiction 955 are
--     inserted with regulated flags explicitly set to NOT applicable
--     (far/pk1000/density = false) so they are correctly excluded from the
--     G-letter applicable-parcel denominator instead of silently counting
--     as "applicable but no standard" against it. This is an honest partial:
--     if a future session finds Avon Park's real ordinance, these 3 rows
--     should be updated with real values.

-- ── 918 (Sebring): R1A (dash-free variant), R3FUD ──────────────────────────
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 918, 'R1A', 'R-1A Residential (dash-free ZON code variant)', 'residential', '12.05.210', false, true, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 918 AND code = 'R1A');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 918, 'R3FUD', 'R-3 Multiple-Family, Flexible Unit Development overlay', 'residential', '12.05.213 / FUD', false, false, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 918 AND code = 'R3FUD');

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, min_lot_sqft, source_url, ordinance_section)
SELECT d.id, 4.36, 10000,
       'https://cms2.revize.com/revize/highlandscountyfl/highlandscounty/departments/engineering/uploads/Chapter_12_Land_Development_Regulations.pdf',
       '12.05.210'
FROM zoning_districts d
WHERE d.jurisdiction_id = 918 AND d.code = 'R1A'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);

-- ── 1654 (unincorporated Highlands County): M1 ─────────────────────────────
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 1654, 'M1', 'M-1 Mobile Home Subdivisions District', 'residential', '12.05.220', false, true, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1654 AND code = 'M1');

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, min_lot_sqft, source_url, ordinance_section)
SELECT d.id, 8.71, 5000,
       'https://cms2.revize.com/revize/highlandscountyfl/highlandscounty/departments/engineering/uploads/Chapter_12_Land_Development_Regulations.pdf',
       '12.05.220'
FROM zoning_districts d
WHERE d.jurisdiction_id = 1654 AND d.code = 'M1'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);

-- ── 955 (Avon Park): R1, R1A, M1S — no independently verified Avon Park
--    ordinance source found this session; marked not-applicable rather than
--    fabricated, so they are excluded (not miscounted) from G's denominator.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 955, 'R1', 'Residential (Avon Park GIS zoning layer, ZON=''AP R1'') — Avon Park municipal ordinance not independently verified this session', 'residential', NULL, false, false, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 955 AND code = 'R1');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 955, 'R1A', 'Residential (Avon Park GIS zoning layer, ZON=''AP R1A'') — Avon Park municipal ordinance not independently verified this session', 'residential', NULL, false, false, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 955 AND code = 'R1A');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 955, 'M1S', 'Mobile Home / Residential Subdivision (Avon Park GIS zoning layer, ZON=''AP M1S'' pattern) — Avon Park municipal ordinance not independently verified this session', 'residential', NULL, false, false, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 955 AND code = 'M1S');

-- ── 840 (Lake Placid): plain R1 (existing rows are R-1-PD / R1-PD variants
--    only; ZON layer returns bare 'R1' for some Lake Placid parcels) ───────
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 840, 'R1', 'Residential (Lake Placid GIS zoning layer, bare ZON=''R1'') — Lake Placid municipal ordinance not independently verified this session', 'residential', NULL, false, false, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 840 AND code = 'R1');
