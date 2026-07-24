-- SHARD-8 okaloosa (dispatch ac288257-fde4-4e26-a8d7-abb78447619f), G letter fix
--
-- CONTEXT: live pencil_dod_evaluate_county('okaloosa') at session start showed
-- 8/10 (A,B,C,D,E,F,H,J PASS; G FAIL detail "density=96.7 far=90.5 pk1000=60.0",
-- I FAIL detail "card_complete=54 of 57"), auctions_total=57 -- a materially
-- better baseline than the session brief's stale 4/10-with-2-auctions
-- description. Multiple prior same-day sessions (2026-07-19 shard3, 2026-07-24
-- shard9) had already done the Bid4Assets harvest, GIS parcel enrichment, and
-- bid_decisions backfill. This migration works the two letters still failing.
--
-- G ROOT CAUSE: v_zoning_gold_standard_kpi_v3 traced to exactly 2 parcel_zones
-- rows (out of 61 total okaloosa parcel_zones rows) whose (jurisdiction_id,
-- zone_code) has NO matching zoning_districts row at all:
--   id=843928  jurisdiction_id=1407 (Unincorporated Okaloosa County)  zone_code='SR'
--   id=843932  jurisdiction_id=923  (Destin)                          zone_code='MDR-V'
-- Because v_zoning_district_applicability LEFT JOINs zoning_districts and
-- defaults far_applicable/pk1000_applicable/density_applicable to TRUE via
-- COALESCE(...,true) when no district row exists, these 2 parcels count as
-- "applicable but missing" on density, FAR, AND pk1000 simultaneously --
-- exactly matching the shortfall: far denom=21 (19/21 filled -> 90.5%),
-- pk1000 denom=5 (3/5 filled -> 60.0%), density denom=61 (59/61 -> 96.7%).
-- Both source parcel_zones rows are real, GIS-sourced (source column:
-- 'okaloosa_gis:planning-development/zoning:25:shard9_run_wp4' and
-- 'okaloosa_gis:localgovernment/destin_energov:6:shard9_run_wp4' respectively)
-- from a prior same-shard session -- not fabricated by this session.
--
-- REAL SOURCES USED THIS SESSION (both fetched live and read in full via PDF
-- text extraction, not summarized/guessed):
--
-- 1. SR (Suburban Residential), Unincorporated Okaloosa County:
--    https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf
--    Sec 2.04.00-2.04.07, Table 2.4 "RESIDENTIAL (R-2) & SUBURBAN RESIDENTIAL
--    (SR) BULK REGULATIONS", p.2-19: SR shares the same density tiers as R-2
--    (single-family detached 6 du/ac, attached/duplex/triplex/quad/multi-family
--    16 du/ac -- district max = 16, following the same "district max = highest
--    permitted tier" convention already used for R-2/R-3/MU-1/MDR-V in this
--    county's existing zoning_districts rows). SR-specific intensity: 0.25 FAR,
--    60% ISC (higher than R-2's 0.10 FAR / 55% ISC -- SR explicitly allows all
--    C-1/C-2 permitted uses per Sec 2.04.05, hence the higher non-residential
--    intensity ceiling). Setbacks/height identical to R-2 (20' front, 7.5'/10'
--    side by unit type, 10' rear, 45' height, 20' frontage) per the same Table
--    2.4 columns. No per-1000sf parking ratio exists anywhere in the LDC for
--    residential districts -- Chapter 6 Sec 6.04.02 (parking requirements,
--    already researched in the companion 20260719h migration for this same
--    county) expresses ALL residential parking as spaces-per-dwelling-unit,
--    not per-1000sf. pk1000_regulated is set to false (SR is a Residential-
--    category district per its own zoning_districts.category classification),
--    matching the existing non-fabrication pattern already applied to every
--    other residential district in Okaloosa (R-1-N, R-1-S, R-2, RR all carry
--    pk1000_regulated=false for the identical reason).
--
-- 2. MDR-V (Medium Density Residential - Village), City of Destin:
--    https://www.cityofdestin.com/DocumentCenter/Home/View/80 (Zoning District
--    Factsheet: MDR-V, "Last Updated: October 18, 2024", excerpt from Destin
--    LDC 7.12.06/7.12.08). Table "Dimensional Requirements in MDR-V": Maximum
--    Density = 5.81 du/acre (1-unit tier) / 9.90 du/acre (2+-unit tier) -- the
--    higher 2+-unit tier (9.90) is used as max_density_du_acre, consistent with
--    the "max" semantics already applied to GRMU/TCMU in this same county's
--    existing zone_standards rows (20260719h migration). Maximum Floor Area
--    Ratio is explicitly "N/A" in the ordinance table itself -- MDR-V is a
--    residential-only district (permitted uses: single-family detached,
--    multi-family attached, guest house, accessory dwelling, SRO housing;
--    explicitly EXCLUDES all non-residential uses per the district's own
--    purpose statement) -- so FAR is genuinely inapplicable, not a missing-
--    data gap. far_regulated is set to false for MDR-V accordingly (same
--    non-fabrication pattern as pk1000_regulated=false elsewhere: the district
--    is correctly excluded from the FAR-applicable denominator rather than
--    counted as "applicable but missing"). No per-1000sf or per-unit parking
--    ratio is published on the factsheet -- pk1000_regulated set to false
--    (Residential category, no confirmed standard, same non-fabrication
--    pattern as MDR-V's FAR and as every other residential district in this
--    county). Setbacks: front 20', side 7.5', rear 10' (1-unit tier, "A/B"
--    footnote applies additional height-based setbacks for 2+ unit buildings
--    which are use-specific, not recorded as a single value here). Max height
--    35'/3 stories. Min open space 25%.
--
-- Both districts' zone_standards rows fill max_density_du_acre with a real,
-- cited, verified number. far_regulated/pk1000_regulated are set to false
-- ONLY where the primary source itself either says the standard is N/A
-- (MDR-V FAR) or where this county's own ordinance structurally does not
-- express residential parking per-1000sf (both districts' pk1000) -- these
-- are honesty corrections to the *applicability* flag, not fabricated
-- numeric values. SR DOES have a real FAR value (0.25) directly stated in
-- Table 2.4, so max_far is filled (not left NULL) for SR.

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 1407, 'SR', 'Suburban Residential (SR) District', 'Residential',
       'Medium density residential housing plus certain non-residential uses (all C-1 and C-2 permitted uses) that contribute to the comfort and convenience of the district. Must be located within the Urban Development Area Boundary with central water/sewer available. Okaloosa County LDC Table 2.4.',
       'Okaloosa County LDC Sec. 2.04.00-2.04.07, Table 2.4', true, true, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1407 AND code = 'SR');

INSERT INTO zone_standards (zoning_district_id, front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft, max_lot_coverage_pct, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 20, 10, 10, 45, 60, 0.25, 16.00,
       'https://myokaloosa.com/sites/default/files/users/gmuser/chapter2-LDC.pdf',
       'Sec. 2.04.07, Table 2.4 (RESIDENTIAL (R-2) & SUBURBAN RESIDENTIAL (SR) BULK REGULATIONS) -- SR intensity 0.25 FAR / 60% ISC; max density shown is the multi-family/attached ceiling (16 du/acre), single-family detached is lower (6 du/acre) but district max is the higher figure, consistent with existing R-2/R-3 convention in this county', 0.95
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 1407 AND zd.code = 'SR'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT j.id, 'MDR-V', 'Medium Density Residential - Village (MDR-V) District', 'Residential',
       'Permanent single-family detached or multi-family attached residential dwelling units. Explicitly excludes seasonal residential, commercial transient accommodations, and all non-residential uses. Destin LDC 7.12.06/7.12.08.',
       'Destin LDC Sec. 7.12.05-7.12.08 (Zoning District Factsheet: MDR-V, updated 2024-10-18)', false, true, false
FROM jurisdictions j
WHERE j.name = 'Destin' AND j.county = 'Okaloosa'
  AND NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = j.id AND code = 'MDR-V');

INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, min_lot_width_ft, min_lot_depth_ft, max_height_ft, front_setback_ft, side_setback_ft, rear_setback_ft, min_open_space_pct, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 7500, 70, 100, 35, 20, 7.5, 10, 25, 9.90,
       'https://www.cityofdestin.com/DocumentCenter/Home/View/80',
       'Zoning District Factsheet: MDR-V (Destin LDC 7.12.08), Last Updated 2024-10-18 -- max density shown is the 2+ dwelling-unit tier (9.90 du/acre); 1-unit tier is 5.81 du/acre. Maximum Floor Area Ratio is explicitly listed as "N/A" in the ordinance table (residential-only district, all non-residential uses expressly excluded) -- far_regulated set false accordingly, not a missing-data gap. No parking ratio published on this factsheet.', 0.95
FROM jurisdictions j
JOIN zoning_districts zd ON zd.jurisdiction_id = j.id AND zd.code = 'MDR-V'
WHERE j.name = 'Destin' AND j.county = 'Okaloosa'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = zd.id);

-- Expected result: pencil_dod_evaluate_county('okaloosa').G moves from
-- {"pass":false,"metric":60.0,"detail":"density=96.7 far=90.5 pk1000=60.0"}
-- to {"pass":true,"metric":100.0,...} since both previously-uncovered
-- parcel_zones rows now resolve to a real zoning_districts row with
-- far_applicable/pk1000_applicable/density_applicable correctly set (no
-- longer defaulting to the true-but-missing COALESCE fallback).
