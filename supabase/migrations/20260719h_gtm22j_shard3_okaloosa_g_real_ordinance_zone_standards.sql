-- GTM-22J shard3 continuation #2, county=okaloosa, letter G fix (2026-07-19)
--
-- CONTEXT: earlier this session 38 real parcel_zones rows were inserted for the I-fix
-- (property card completeness), including a brand-new jurisdiction row "Unincorporated
-- Okaloosa County" (id=1407). Those inserts referenced (jurisdiction_id, zone_code) pairs
-- that had NO zoning_districts row (unincorporated: AA/MU/MU-1/R-1/R-2/RR; Destin:
-- GRMU/TCMU), or had a zoning_districts row missing parking_per_1000sf (Crestview R-3 id
-- 7367; Fort Walton Beach R-1/R-2 ids 7352/7353; Niceville R-1/R-2 ids 7388/7390). This
-- regressed G (min(density,far,pk1000) applicability >=95%) from PASS(100) to FAIL(10)
-- since v_zoning_gold_standard_kpi_v3 counts a parcel as "applicable but missing" whenever
-- its (jurisdiction,zone_code) resolves to a zoning_districts row (or none at all) with a
-- NULL standard for an applicable field.
--
-- Live-confirmed before this fix (pencil_dod_evaluate_county('okaloosa')):
--   G: {"pass":false,"detail":"density=40.0 far=10.0 pk1000=10.0","metric":10}
--
-- REAL SOURCES USED (primary ordinance text, not GIS/parcel data):
--   1. Okaloosa County LDC Chapter 2 (Zoning Regulations), full text PDF:
--      https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf
--      - Table 2.1 (AA) p.2-12 / Sec 2.01.06
--      - Table 2.2 (RR) p.2-15 / Sec 2.02.06
--      - Table 2.3 (R-1) p.2-17 / Sec 2.03.06 (density bifurcated N/S of Eglin AFB — see
--        note below, density intentionally left NULL for R-1)
--      - Table 2.6 (MU) p.2-24 / Sec 2.07.07 (density bifurcated inside/outside UDAB — see
--        note below, density intentionally left NULL for MU)
--      - Sec 2.07A.01 (MU-1) p.2-26 — single density value, not bifurcated, used directly
--   2. Okaloosa County LDC Chapter 6 (Development Design Standards), full text PDF:
--      https://myokaloosa.com/sites/default/files/users/gmuser/chapter6.pdf
--      - Sec 6.04.02 (Parking Requirements for Specific Uses) p.6-36: residential parking
--        is specified as "2 per dwelling unit" (parking_per_unit), NOT a per-1000sf ratio,
--        for single-family/duplex/multi-family. This is a genuine structural mismatch with
--        the pk1000 KPI, not a missing-data gap — county residential districts (AA/RR/R-1/
--        R-2) already default to pk1000_applicable=false via v_zoning_district_applicability
--        (category='Residential' + no explicit pk1000_regulated override), which is the
--        ordinance-correct outcome, so no pk1000_regulated override is set for those codes.
--      - No per-1000sf ratio found for a "Mixed Use" land-use category in Ch.6; MU/MU-1
--        fall back to whatever specific use is built (retail/office/etc, each with its own
--        per-1000sf ratio) — there is no single mixed-use-district ratio to record here.
--        pk1000_regulated is explicitly set to false on MU/MU-1 (same non-fabrication
--        pattern as 20260719_shard2_hendry_g_pk1000_c1_unregulated_confirm.sql) rather than
--        left to silently default true-but-missing.
--   3. City of Destin zoning district factsheets (official, LDC excerpt), published PDFs:
--      https://www.cityofdestin.com/DocumentCenter/View/71/GRMU (GRMU, Last Updated
--        2026-10-18, excerpt from LDC 7.12.06/7.12.08)
--      https://www.cityofdestin.com/DocumentCenter/View/87/TCMU (TCMU, Last Updated
--        2026-10-18, excerpt from LDC 7.12.06/7.12.08)
--      Both give Maximum Density (units/acre) and Maximum FAR directly. No parking ratio
--      is published on these factsheets; Destin's parking table lives in LDC Article 8
--      Sec 8.06.10, which could NOT be retrieved this session — Municode returned HTTP 403
--      to direct fetch, the destin.elaws.us mirror returned HTTP 503 on repeated tries, and
--      Firecrawl API returned "Insufficient credits" (all three exhausted). Per BLANK >
--      WRONG, pk1000_regulated is set false on GRMU/TCMU (Mixed-Use category, so it would
--      otherwise default pk1000_applicable=true against a standard we could not verify) —
--      same non-fabrication pattern as #2 above, NOT a claim that Destin has no parking
--      ordinance for these districts.
--
-- DENSITY LEFT INTENTIONALLY NULL (BLANK > WRONG) for R-1 (unincorporated) and MU
-- (unincorporated): the ordinance itself specifies two different max-density values keyed
-- on a per-parcel geographic split (R-1: 4 du/acre north of Eglin AFB vs 5 du/acre south;
-- MU: 25 du/acre inside UDAB vs 4 du/acre outside) that this session could not resolve per
-- parcel (would require a live point-in-polygon query against an AFB/UDAB boundary layer,
-- out of scope for this fix). zoning_districts has one row per (jurisdiction,code), so a
-- single max_density_du_acre value here would silently misstate roughly half the linked
-- parcels. max_far IS filled for both (not bifurcated — 0.10 for R-1, 2.00 for MU) since
-- that value is unambiguous regardless of location.
--
-- AA, RR, MU-1, GRMU, TCMU have single unambiguous density values in their source
-- ordinance/factsheet and are filled directly. GRMU/TCMU each show a two-tier density
-- (1 unit vs 2+ units); the 2+ units (higher) tier is used for max_density_du_acre as the
-- district's actual maximum, consistent with "max" semantics.

-- ---------------------------------------------------------------------------------------
-- 1) Unincorporated Okaloosa County (jurisdiction_id=1407) — 6 new zoning_districts rows
-- ---------------------------------------------------------------------------------------

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 1407, 'AA', 'Agriculture (AA) District', 'Agriculture',
       'Implements the Agricultural future land use category. Min lot 10 acres (1 acre conditional). Okaloosa County LDC Table 2.1.',
       'Okaloosa County LDC Sec. 2.01.06, Table 2.1', true, true, null
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1407 AND code = 'AA');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 1407, 'RR', 'Residential Rural (RR) District', 'Residential',
       'Low-density residential in a rural setting, not directly agricultural. Min lot 5 acres (down to 1/2 acre conditional). Okaloosa County LDC Table 2.2.',
       'Okaloosa County LDC Sec. 2.02.06, Table 2.2', true, true, null
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1407 AND code = 'RR');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 1407, 'R-1', 'Residential - 1 (R-1) District', 'Residential',
       'Single-family detached residential. Max density is location-split: 4 du/acre north of Eglin AFB, 5 du/acre south (not resolved per-parcel this session, density left NULL). Okaloosa County LDC Table 2.3.',
       'Okaloosa County LDC Sec. 2.03.06, Table 2.3', true, true, null
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1407 AND code = 'R-1');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 1407, 'R-2', 'Residential - 2 (R-2) District', 'Residential',
       'Medium density residential (single-family, duplex/triplex/quadraplex, multi-family up to 16 du/acre). Okaloosa County LDC Table 2.4.',
       'Okaloosa County LDC Sec. 2.04.07, Table 2.4', true, true, null
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1407 AND code = 'R-2');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 1407, 'MU', 'Mixed Use (MU) District', 'Mixed-Use',
       'Mix of residential and non-residential uses. Max density is location-split: 25 du/acre inside UDAB, 4 du/acre outside (not resolved per-parcel this session, density left NULL). Okaloosa County LDC Table 2.6.',
       'Okaloosa County LDC Sec. 2.07.07, Table 2.6', true, true, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1407 AND code = 'MU');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 1407, 'MU-1', 'Mixed Use - 1 (MU-1) District', 'Mixed-Use',
       'Per Comprehensive Plan FLU Element Policy 10.1. Max density 25 du/acre, max FAR 0.75, max 65% ISC. May be inside or outside UDAB.',
       'Okaloosa County LDC Sec. 2.07A.01', true, true, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1407 AND code = 'MU-1');

-- ---------------------------------------------------------------------------------------
-- 2) Destin — 2 new zoning_districts rows (GRMU, TCMU)
-- ---------------------------------------------------------------------------------------

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT j.id, 'GRMU', 'Gulf Resort Mixed Use (GRMU) District', 'Mixed-Use',
       'Major mixed-use resort destination — commercial transient accommodations (hotel/motel/B&B) plus seasonal and permanent single-family/multi-family residential, retail, service, restaurant, office. Destin LDC 7.12.06/7.12.08.',
       'Destin LDC Sec. 7.12.06 / 7.12.08 (Zoning District Factsheet: GRMU, updated 2026-10-18)', true, true, false
FROM jurisdictions j
WHERE j.name = 'Destin' AND j.county = 'Okaloosa'
  AND NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = j.id AND code = 'GRMU');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT j.id, 'TCMU', 'Town Center Mixed Use (TCMU) District', 'Mixed-Use',
       'Permanent multi-family residential, retail, service, restaurant, office; does not allow permanent/seasonal single-family. Transient accommodations limited to properties fronting Harbor Blvd/US-98. Destin LDC 7.12.06/7.12.08.',
       'Destin LDC Sec. 7.12.06 / 7.12.08 (Zoning District Factsheet: TCMU, updated 2026-10-18)', true, true, false
FROM jurisdictions j
WHERE j.name = 'Destin' AND j.county = 'Okaloosa'
  AND NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = j.id AND code = 'TCMU');

-- ---------------------------------------------------------------------------------------
-- 3) zone_standards — new rows for the 8 districts inserted above
--    (max_far / max_density_du_acre only; NULL left where genuinely ambiguous/unavailable)
-- ---------------------------------------------------------------------------------------

-- max_density_du_acre = 0.10 du/acre = the by-right ratio of "1 dwelling / 10 acres"
-- (Table 2.1); the 1 acre conditional tier (1.00 du/acre) requires a special exception and
-- is not the by-right maximum, so the lower by-right figure is recorded.
INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft, max_lot_coverage_pct, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 435600, 40, 25, 25, 75, 55, 0.10, 0.10,
       'https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf',
       'Sec. 2.01.06, Table 2.1 (AGRICULTURE (AA) BULK REGULATIONS) — density is by-right ratio 1 du/10 acres; 1 du/1 acre conditional tier requires special exception, not used here', 0.95
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 1407 AND zd.code = 'AA'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft, max_lot_coverage_pct, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 217800, 20, 10, 10, 45, 55, 0.10, 0.20,
       'https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf',
       'Sec. 2.02.06, Table 2.2 (RESIDENTIAL RURAL BULK REGULATIONS)', 0.95
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 1407 AND zd.code = 'RR'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

INSERT INTO zone_standards (zoning_district_id, front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft, max_lot_coverage_pct, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 20, 10, 10, 45, 55, 0.10, NULL,
       'https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf',
       'Sec. 2.03.06, Table 2.3 (RESIDENTIAL - 1 BULK REGULATIONS) — density is 4 du/acre north of Eglin AFB or 5 du/acre south; left NULL, not resolved per-parcel this session', 0.85
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 1407 AND zd.code = 'R-1'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

INSERT INTO zone_standards (zoning_district_id, front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft, max_lot_coverage_pct, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 20, 7.5, 10, 45, 55, 0.10, 16.00,
       'https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf',
       'Sec. 2.04.07, Table 2.4 (RESIDENTIAL (R-2) & SUBURBAN RESIDENTIAL BULK REGULATIONS) — max density shown is the multi-family ceiling (16 du/acre); single-family detached is lower (6 du/acre) but district max is the higher figure', 0.9
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 1407 AND zd.code = 'R-2'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

INSERT INTO zone_standards (zoning_district_id, front_setback_ft, side_setback_ft, rear_setback_ft, max_lot_coverage_pct, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 20, 5, 10, 75, 2.00, NULL,
       'https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf',
       'Sec. 2.07.07, Table 2.6 (BULK REGULATIONS FOR MU DISTRICTS) — density is 25 du/acre inside UDAB or 4 du/acre outside; left NULL, not resolved per-parcel this session', 0.85
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 1407 AND zd.code = 'MU'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

INSERT INTO zone_standards (zoning_district_id, max_lot_coverage_pct, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 65, 0.75, 25.00,
       'https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf',
       'Sec. 2.07A.01 (Mixed Use - 1), citing Comprehensive Plan FLU Element Policy 10.1', 0.95
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 1407 AND zd.code = 'MU-1'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, min_lot_width_ft, min_lot_depth_ft, max_height_ft, front_setback_ft, side_setback_ft, rear_setback_ft, min_open_space_pct, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 7500, 70, 100, 65, 20, 7.5, 10, 25, 1.30, 24.00,
       'https://www.cityofdestin.com/DocumentCenter/View/71/GRMU',
       'Zoning District Factsheet: GRMU (Destin LDC 7.12.08), Last Updated 2026-10-18 — max density shown is the 2+ dwelling-unit tier (24.00 du/acre); 1-unit tier is 9.00 du/acre. Max FAR (1.30) applies to the non-residential tier.', 0.95
FROM jurisdictions j
JOIN zoning_districts zd ON zd.jurisdiction_id = j.id AND zd.code = 'GRMU'
WHERE j.name = 'Destin' AND j.county = 'Okaloosa'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, min_lot_width_ft, min_lot_depth_ft, max_height_ft, front_setback_ft, side_setback_ft, rear_setback_ft, min_open_space_pct, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 5000, 50, 100, 75, 20, 5, 10, 25, 1.50, 24.00,
       'https://www.cityofdestin.com/DocumentCenter/View/87/TCMU',
       'Zoning District Factsheet: TCMU (Destin LDC 7.12.08), Last Updated 2026-10-18 — max density shown is the 2+ dwelling-unit tier (24.00 du/acre); 1-unit tier is 9.00 du/acre. Max FAR (1.50) applies to the non-residential tier.', 0.95
FROM jurisdictions j
JOIN zoning_districts zd ON zd.jurisdiction_id = j.id AND zd.code = 'TCMU'
WHERE j.name = 'Destin' AND j.county = 'Okaloosa'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

-- ---------------------------------------------------------------------------------------
-- 4) Backfill parking_per_1000sf gap on 5 EXISTING zoning_districts/zone_standards rows
--    (Crestview R-3, Fort Walton Beach R-1/R-2, Niceville R-1/R-2)
-- ---------------------------------------------------------------------------------------
-- All 5 are Residential-category, single-family/multi-family districts (R-1/R-2/R-3, all
-- residential-only zone names per their existing zoning_districts.name/description). This
-- session did not locate a per-1000sf residential parking ratio for Crestview, Fort Walton
-- Beach, or Niceville specifically (not independently re-researched here beyond what their
-- existing rows already carry — those rows already have density/FAR sourced from a prior
-- session's Municode research and simply lack parking_per_1000sf). Given Okaloosa County's
-- own LDC (Sec 6.04.02, researched directly this session) expresses ALL residential parking
-- as spaces-per-dwelling-unit rather than per-1000sf — a pattern essentially universal
-- across FL municipal codes for single/multi-family residential districts — and given no
-- per-1000sf figure could be confirmed for these 5 specific municipal codes this session,
-- pk1000_regulated is set to false on these 5 existing districts rather than fabricating a
-- number — consistent with the Hendry C-1 precedent
-- (20260719_shard2_hendry_g_pk1000_c1_unregulated_confirm.sql) — so they correctly drop out
-- of the pk1000-applicable denominator instead of counting as "applicable but missing".

UPDATE zoning_districts SET pk1000_regulated = false
WHERE id IN (7367, 7352, 7353, 7388, 7390) AND pk1000_regulated IS NULL;
