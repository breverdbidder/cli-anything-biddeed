-- Gold Standard shard-1 (dispatch 95d2d8fc-cb62-4ba1-a58b-7e1134cf00cf): st_lucie letter G fix.
--
-- IDEMPOTENT RECORD of live PostgREST writes already applied this session
-- (direct psql unreachable from this sandbox -- documented long-standing
-- constraint; writes made via PATCH/POST to zoning_districts/zone_standards).
--
-- BASELINE (live pencil_dod_evaluate_county('st_lucie'), start of session):
--   "G": {"pass": false, "detail": "density=91.0 far=0.0 pk1000=0.0", "metric": 0.0}
--
-- ═══════════════════════════════════════════════════════════════════════
-- DIAGNOSIS (schema first, per task instructions -- prior session's
-- "jurisdiction_id column" assumption on zone_standards was wrong; the real
-- FK is zone_standards.zoning_district_id -> zoning_districts.id, and
-- zoning_districts.jurisdiction_id is the actual county-linkage column)
-- ═══════════════════════════════════════════════════════════════════════
--
-- Confirmed schema live: zone_standards has NO jurisdiction_id column.
-- The chain is: multi_county_auctions -> parcel_zones (parcel_id,
-- jurisdiction_id, zone_code) -> zoning_districts (jurisdiction_id, code) ->
-- zone_standards (zoning_district_id FK to zoning_districts.id).
--
-- Sized the gap: all 27 zoning_districts rows across st_lucie's 4
-- jurisdictions (1400 unincorporated, 971 Fort Pierce, 953 Port St Lucie,
-- 1128 St Lucie Village -- which has ZERO districts, unaffected here) have
-- max_far/parking_per_1000sf = NULL in zone_standards, with NO exception --
-- this confirms the task's substrate-gap hypothesis for those two columns.
-- BUT this is NOT why G scored 0.0%. The true driver, found by reading
-- v_zoning_gold_standard_kpi_v3 (the actual view behind the G metric, not
-- the raw card fill-rate and not v_zoning_district_applicability, which
-- already correctly showed far_applicable=false/pk1000_applicable=false for
-- every one of the 27 known districts):
--
--   far_applicable_parcels: 2, pct_far_of_applicable: 0.0
--
-- The denominator was a real, non-zero 2 -- not the ~235 rows a naive
-- "NULL far_regulated defaults to applicable" read would suggest (that
-- theory was tested live this session by explicitly setting far_regulated=
-- false on 8 districts whose flag had been left NULL by prior sessions
-- -- R-1/953 id=10798 [213 card rows alone], R-3/971, RS-3/RM-9/RM-5/RMH-5
-- /1400, RM-5/RM-8/953 -- and produced ZERO movement in G, disproving it;
-- those 8 flag-sets are harmless/correct hygiene but were not the lever).
--
-- Root cause, confirmed by diffing the card view's distinct (jurisdiction_id,
-- zone_code) pairs against zoning_districts: TWO zone codes present in
-- parcel_zones/the card view had NO zoning_districts row AT ALL:
--   (953, 'RS-1') -- parcel 113913, zone_name "SINGLE-FAMILY RESIDENTIAL"
--   (953, 'RM-11') -- parcel 118013, zone_name "MULTIPLE FAMILY RESIDENTIAL"
-- Both were inserted into parcel_zones by yesterday's
-- 20260827_gold_standard_shard11_stlucie_i_zoning_substrate_gap.sql (letter
-- I fix, source='st_lucie_psl_re_parcels_web_arcgis_propertyid_20260827')
-- but that session never created the corresponding zoning_districts rows.
-- With no zoning_districts row to carry an explicit far_regulated=false
-- override, the KPI view's applicability heuristic defaulted BOTH to
-- "far/pk1000 applicable, no standard on file" -- exactly the same class of
-- self-inflicted regression already documented multiple times in this
-- campco (RMH-5 20260730c, R-2/RS-4 20260719_shard11_2nd, 12 districts
-- 20260815_shard3). This is the real, confirmed, non-fabricated lever.
--
-- ═══════════════════════════════════════════════════════════════════════
-- FIX 1: RS-1 and RM-11 (953, Port St Lucie) -- create the missing
-- zoning_districts rows with real ordinance-sourced far/parking-not-
-- applicable flags and real density standards.
-- ═══════════════════════════════════════════════════════════════════════
--
-- Both confirmed live this session via WebFetch of Port St Lucie Code of
-- Ordinances Title XV Ch. 158 Art. V (portstlucie.elaws.us), the same
-- source already used and cited for this jurisdiction's RS-2/RM-5 rows in
-- prior sessions:
--   Sec. 158.072 (RS-1, Single-Family Residential): "Fifteen thousand
--     (15,000) square feet and a minimum width of seventy-five (75) feet"
--     minimum lot; no FAR figure; parking "As set forth in section
--     158.221" (per-garage-configuration table, NOT per-1000sf -- same
--     158.221 already independently confirmed for the R-1/RS-2 siblings).
--   Sec. 158.079 (RM-11, Multiple-Family Residential): "maximum gross
--     project density of eleven (11) dwelling units per acre"; "Maximum
--     Building Coverage. Thirty-five (35) percent, provided that the
--     maximum impervious surface does not exceed fifty (50) percent"; no
--     FAR figure; parking same 158.221 reference as RS-1.
--
-- RS-1 density derived by the same method already used for this
-- jurisdiction's RS-2 (43560/10000=4.36 du/ac, on file since 2026-07-19):
-- 43560 / 15000 = 2.904 du/ac.

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, pk1000_regulated, density_regulated)
VALUES
  (953, 'RS-1',  'Single-Family Residential Zoning District (RS-1)',   'residential', 'Port St. Lucie Code of Ordinances Sec. 158.072', false, false, true),
  (953, 'RM-11', 'Multiple-Family Residential Zoning District (RM-11)', 'residential', 'Port St. Lucie Code of Ordinances Sec. 158.079', false, false, true)
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, min_lot_width_ft, max_density_du_acre, source_url, ordinance_section)
SELECT d.id, 15000, 75.0, 2.904,
       'http://portstlucie.elaws.us/code/coor_titlexv_ch158_artv_sec158.072',
       'Port St. Lucie Code Sec. 158.072 - RS-1 Single-Family Residential (min lot 15,000sf/75ft; density derived 43560/15000)'
FROM zoning_districts d WHERE d.jurisdiction_id = 953 AND d.code = 'RS-1'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_lot_coverage_pct, max_impervious_pct, source_url, ordinance_section)
SELECT d.id, 11.0, 35.0, 50.0,
       'http://portstlucie.elaws.us/code/coor_titlexv_ch158_artv_sec158.079',
       'Port St. Lucie Code Sec. 158.079 - RM-11 Multiple-Family Residential (max gross project density 11 du/acre; max bldg coverage 35%, max impervious 50%)'
FROM zoning_districts d WHERE d.jurisdiction_id = 953 AND d.code = 'RM-11'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);

-- RESULT after fix 1 (live v_zoning_gold_standard_kpi_v3, verified):
--   far_applicable_parcels: 2 -> 0, pct_far_of_applicable: 0.0 -> null (correctly blank/NA)
--   pk1000_applicable_parcels: 2 -> 0, pct_pk1000_of_applicable: 0.0 -> null
--   G: far=0.0/pk1000=0.0/metric=0.0 FAIL -> far=blank/pk1000=blank, density-only
--      metric=92.5 FAIL (density alone still short of 95%)

-- ═══════════════════════════════════════════════════════════════════════
-- FIX 2: density-only headroom -- 2 more real, sourced density values to
-- close the remaining ~2.5pp gap (92.5% -> 95%+ needed).
-- ═══════════════════════════════════════════════════════════════════════
--
-- RM-8 (953, Port St Lucie), highest remaining leverage after RS-1/RM-11:
-- Sec. 158.078 confirmed live (same elaws source, same Article V sequence
-- as RM-5=158.077/RM-11=158.079): "maximum gross project density of eight
-- (8) dwelling units per acre" for multiple-family dwellings.
UPDATE zoning_districts
SET density_regulated = true,
    ordinance_section = 'Port St. Lucie Code of Ordinances Sec. 158.078'
WHERE jurisdiction_id = 953 AND code = 'RM-8'
  AND density_regulated IS DISTINCT FROM true;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT d.id, 8.0,
       'http://portstlucie.elaws.us/code/coor_titlexv_ch158_artv_sec158.078',
       'Port St. Lucie Code Sec. 158.078 - RM-8 Multiple-Family Residential (max gross project density 8 du/acre)'
FROM zoning_districts d WHERE d.jurisdiction_id = 953 AND d.code = 'RM-8'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);

-- R-1 (971, Fort Pierce): Fort Pierce Code of Ordinances Sec. 125-191(a),
-- confirmed live via the Zoneomics ordinance mirror (same source already
-- used and cited for this jurisdiction's R-3 row): "primarily intended to
-- provide for areas of single-family dwellings with an average net density
-- of less than four units per acre." Recorded as 4.0 du/ac max, consistent
-- with how this jurisdiction's R-2 "less than five units per acre" was
-- already recorded as 5.0 in the 20260719 migration (regulatory ceiling,
-- not a rounded guess), and internally consistent with the existing R-2=5/
-- R-3=6/R-4=10 progression on file for Fort Pierce.
UPDATE zoning_districts
SET density_regulated = true,
    ordinance_section = 'Fort Pierce Code of Ordinances Sec. 125-191(a)'
WHERE jurisdiction_id = 971 AND code = 'R-1'
  AND density_regulated IS DISTINCT FROM true;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT d.id, 4.0,
       'https://www.zoneomics.com/code/fort-pierce-FL/chapter_4',
       'Fort Pierce Code of Ordinances Sec. 125-191(a) - R-1 Single Family Low Density Zone (average net density less than 4 units/acre)'
FROM zoning_districts d WHERE d.jurisdiction_id = 971 AND d.code = 'R-1'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);

-- ═══════════════════════════════════════════════════════════════════════
-- INCIDENTAL HYGIENE (tested, harmless, did not move G -- kept because it
-- is correct and matches the already-documented sibling districts in the
-- same jurisdictions, all of which already carry far_regulated=false):
-- ═══════════════════════════════════════════════════════════════════════
-- 8 residential districts had far_regulated left NULL (not explicit false)
-- by prior sessions while their pk1000_regulated was already correctly set
-- false. Set far_regulated=false explicitly for consistency with siblings
-- (R-2/971, RS-4/1400, R-4/971, C-3/971, I-1/971, CG/953, etc. all already
-- false). Verified this made ZERO difference to G's metric (confirms
-- v_zoning_gold_standard_kpi_v3, not v_zoning_district_applicability, is
-- what actually drives the pencil_dod_evaluate_county G score -- useful
-- for future sessions debugging this letter).
UPDATE zoning_districts SET far_regulated = false
WHERE id IN (10798, 14091, 14095, 13111, 14087, 12930, 14094, 13490)
  AND far_regulated IS NULL;

-- ═══════════════════════════════════════════════════════════════════════
-- RESULT (verified live via pencil_dod_evaluate_county('st_lucie'), 2026-08-28)
-- ═══════════════════════════════════════════════════════════════════════
-- G:  density=91.0 far=0.0 pk1000=0.0 metric=0.0  FAIL
--  -> density=92.5 far=blank pk1000=blank metric=92.5 (after Fix 1)  FAIL
--  -> density=93.2 (after RM-8)  FAIL
--  -> density=95.5 far=blank pk1000=blank metric=95.5 (after Fort Pierce R-1)  PASS
--
-- Full county re-check, same session, confirms no regressions:
-- A=PASS(122) B=PASS(100.0) C=FAIL(80.7, unchanged, out of scope)
-- D=PASS(100.0) E=PASS(97.2) F=PASS(100.0) G=PASS(95.5) H=PASS(0.0)
-- I=PASS(96.4) J=PASS(100.0). auctions_total=249, unchanged.
--
-- Residual: st_lucie's zone_standards table still has zero rows anywhere
-- with a real max_far value (the task's literal "max_far/parking wholesale
-- NULL" observation is TRUE and remains true after this fix) -- but it is
-- now honestly reflected as 0 applicable/0 NA (blank), not 0/N-applicable
-- (0.0% fail), because every commercial/industrial district that could
-- plausibly be FAR-regulated already carries a real, ordinance-researched
-- far_regulated=false (Fort Pierce C-3/I-1, Port St Lucie CG/CS/WI/MPUD,
-- unincorporated IL -- all previously confirmed via Zoneomics/elaws mirrors
-- as genuinely having no FAR figure in the code). If a future session finds
-- a St Lucie commercial/industrial district that DOES have a real FAR or
-- parking-per-1000sf figure in its ordinance, sourcing it would strengthen
-- G's evidentiary basis (currently PASS on density alone with far/pk1000
-- both at "0 applicable"), but is not required to hold the current pass.
SELECT 1;
