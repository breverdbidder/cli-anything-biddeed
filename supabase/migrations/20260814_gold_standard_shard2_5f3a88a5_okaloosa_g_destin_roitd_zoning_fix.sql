-- Gold Standard shard-2 (dispatch 5f3a88a5-19bc-4d64-a3b6-fba1e561f75b, loop run 11435)
-- County: okaloosa. Letter: G (zoning coverage, min(density,FAR,pk1000) >= 95%).
--
-- SELF-INFLICTED REGRESSION, CAUGHT AND FIXED SAME SESSION:
-- The okaloosa I-fix (see 20260814_gold_standard_shard2_5f3a88a5_okaloosa_i_card_completeness.sql,
-- landed earlier this session) linked case 2025-CA-003304-C to parcel 00-2S-22-1125-0000-0490
-- via okgis.myokaloosa.com and inserted a parcel_zones row with zone_code='ROI-TD'
-- (Destin, jurisdiction_id=923). No zoning_districts row existed for 'ROI-TD' at that time,
-- so v_zoning_gold_standard_kpi_v3's COALESCE(a.far_applicable/pk1000_applicable/density_applicable, true)
-- fallback counted this parcel as "applicable, standard NULL" on ALL THREE dimensions at once.
-- G dropped from PASS 97.1% (density=97.1 far=100.0 pk1000=100.0) to FAIL 80.0%
-- (density=94.4 far=96.2 pk1000=80.0) as a direct result -- a real regression, not a
-- pre-existing gap. Per campaign mandate ("any regression = P0"), fixed in this same session
-- rather than left for a future one.
--
-- FIX: fetched the real primary-source City of Destin Zoning District Factsheet for ROI-TD
-- (https://www.cityofdestin.com/DocumentCenter/View/84/ROI-TD, official cityofdestin.com
-- government domain, "Last Updated: October 18, 2024", excerpted from LDC 7.12.08). Confirmed
-- via pdftotext extraction of the live PDF (WebFetch's HTML converter cannot parse this PDF;
-- had to fall back to downloading + pdftotext -layout):
--   - Dimensional Requirements table, "Maximum Density (units per acre)": 9.00 (1-dwelling-unit
--     tier) / 12.00 (2+ dwelling-unit tier). Used 12.00 (the higher permitted tier).
--   - "Maximum Floor Area Ratio": N/A for BOTH tiers -- an explicit, ordinance-stated
--     non-applicability, not a missing-data gap.
--   - No parking-per-1000sf (or any parking) line item appears anywhere in the district's
--     dimensional table.
--
-- CATEGORIZATION JUDGMENT (adversarially verified, see gold_standard_ultraloop_audit,
-- county_slug=okaloosa, letter=G, this session): far_regulated=false and pk1000_regulated=false
-- are NOT a cherry-pick to force a pass -- all 5 pre-existing Destin zoning_districts rows
-- (CBR id=12969, GRMU id=12085, HDR id=13292, MDR-V id=12641, TCMU id=12086, all created
-- 2026-07-19..31, weeks before this session) already carry pk1000_regulated=false, and none
-- of them have a max_far value regulated by a uniform table either (HDR/MDR-V have
-- far_regulated=NULL which the applicability view's category-fallback already resolves to
-- not-applicable for a Residential-category district). This fix extends an already-established
-- jurisdiction-wide pattern to a 6th Destin district, using that same district's own
-- ordinance text as the basis, rather than inventing a new policy.
--
-- RESULT (live, pencil_dod_evaluate_county('okaloosa'), adversarially verified survived=true):
--   G: FAIL 80.0 (density=94.4 far=96.2 pk1000=80.0) -> PASS 95.8 (density=95.8 far=100.0 pk1000=100.0)
--   okaloosa: 9/10 -> 10/10 (all of A-J now PASS)
--
-- Statements below are DML reflecting the live write already made via the Supabase Management
-- API SQL endpoint during this session. This file is the audit trail, not the execution
-- mechanism (the write already landed live before this file was authored).

INSERT INTO zoning_districts (id, code, name, jurisdiction_id, category, far_regulated, pk1000_regulated, density_regulated)
VALUES (
  14080,
  'ROI-TD',
  'Residential, Office & Institutional - Tourist Development (ROI-TD) District',
  923,
  'Mixed-Use',
  false,
  false,
  true
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO zone_standards (id, zoning_district_id, max_far, max_density_du_acre, parking_per_1000sf, source_url, ordinance_section, confidence_score, scraped_at)
VALUES (
  6267,
  14080,
  NULL,
  12.00,
  NULL,
  'https://www.cityofdestin.com/DocumentCenter/View/84/ROI-TD',
  'Destin LDC 7.12.08 ROI-TD Zoning District Factsheet (Last Updated Oct 18 2024), Dimensional Requirements table: Maximum Density (units per acre) 2+ dwelling-unit column = 12.00 (1-dwelling-unit-per-lot tier is 9.00, lower tier not used here); Maximum Floor Area Ratio = N/A for both columns (confirmed not regulated by FAR in this district); no parking-per-1000sf line item present in the dimensional table (consistent with the pattern already established for every other Destin district in this DB: CBR/GRMU/HDR/MDR-V/TCMU all have pk1000_regulated=false)',
  0.9,
  now()
)
ON CONFLICT (id) DO NOTHING;
