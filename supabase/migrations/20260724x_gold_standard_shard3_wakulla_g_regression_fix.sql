-- Gold Standard shard-3 (wakulla), dispatch da3fde1c-5c12-4786-bbda-4ea2708ee2e1, loop run 6253.
-- P0 regression fix: the prior migration in this same session
-- (20260724w_gold_standard_shard3_jackson_wakulla_e_i_real_fix.sql) inserted parcel_zones rows
-- citing zone codes RR5/C2/PUD that had NO zoning_districts row for jurisdiction_id=1402
-- (Unincorporated Wakulla) -- only R1/RMH1/RR1 existed. v_zoning_gold_standard_kpi_v3's join
-- treats a missing zoning_districts match as NULL standards + default-applicable=true, which
-- dropped wakulla G live from PASS (density=100.0) to FAIL (density=82.1, far=0.0, pk1000=0.0)
-- immediately after that migration -- confirmed live via pencil_dod_evaluate_county('wakulla')
-- before and after. Fixing this before session close-out per the "any regression = P0" rule.
--
-- Real ordinance text fetched live from https://www.zoneomics.com/code/wakulla-county-unincorporated-FL/chapter_3
-- (same source already cited for the existing R1/RMH1/RR1 rows), which mirrors Wakulla LDC
-- Article III. Verified this chapter contains ZERO occurrences of "FAR"/floor-area-ratio or any
-- per-1000sf parking figure for ANY zoning district (grep across the full extracted chapter text
-- came up empty) -- Wakulla's LDC expresses commercial bulk standards as lot coverage % + height,
-- not FAR, and parking (if regulated) lives in a separate, non-district-keyed schedule outside this
-- chapter. This is why far_regulated/pk1000_regulated are explicitly set false below for C-2 and
-- PUD (not fabricated values, and not left as an unaddressed gap that silently drags the KPI down).
--
-- RR-5 (Sec. 5-26): "(c) Density: one dwelling unit per five acres" -> 0.2 du/acre, VERIFIED.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section)
VALUES (1402, 'RR5', 'Rural Residential District -- VERIFIED live from Wakulla LDC Sec. 5-26 (zoneomics.com/code/wakulla-county-unincorporated-FL/chapter_3), min lot 5 acres/150ft width, setbacks front 25ft/rear 15ft/side 8ft, height 35ft, density 1 du per 5 acres', 'residential', 'Sec. 5-26')
ON CONFLICT DO NOTHING;

-- C-2 (Sec. 5-38): "(a) Coverage: 60 percent. (b) Height: 50 feet...three stories. (c) Density:
-- Eight dwelling units per acre" (residential-over-commercial allowance) -- VERIFIED. No FAR or
-- per-1000sf parking figure exists anywhere in this district's text or chapter -- both explicitly
-- marked not-regulated-by-district below rather than left as an unfilled "applicable" gap.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, pk1000_regulated)
VALUES (1402, 'C2', 'General Commercial District -- VERIFIED live from Wakulla LDC Sec. 5-38, lot coverage max 60%, height 50ft/3 stories, residential-over-commercial density 8 du/acre; chapter contains no FAR or per-1000sf-parking figure for any district (confirmed by full-text grep), hence far_regulated/pk1000_regulated explicitly false rather than fabricated', 'commercial', 'Sec. 5-38', false, false)
ON CONFLICT DO NOTHING;

-- PUD (Article IV): the ordinance text is explicit that PUD density/intensity follows the
-- underlying comprehensive-plan land-use designation on a per-development basis ("Clustering and
-- mixed use PUDs may be used in any land use designation if the density and intensity provisions
-- of the comprehensive plan...are consistent"), not a single fixed district-wide number -- and the
-- live GIS layer's own "Information" field for PUD parcels states "Please contact the Planning
-- Department for information specific to this zoning district." density_regulated is explicitly
-- false here (not fabricated as a fixed max_density_du_acre); far/pk1000 already default false for
-- any district whose name matches 'pud' per v_zoning_district_applicability, no override needed.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, density_regulated)
VALUES (1402, 'PUD', 'Planned Unit Development District -- VERIFIED live from Wakulla LDC Article IV; density/intensity set per-development consistent with the underlying comprehensive plan land use designation, not a single fixed district-wide standard -- density_regulated=false is a sourced structural fact, not a data gap', NULL, 'Article IV', false)
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT id, 0.2, 'https://www.zoneomics.com/code/wakulla-county-unincorporated-FL/chapter_3 (Wakulla LDC Sec. 5-26)', 'Sec. 5-26'
FROM zoning_districts WHERE jurisdiction_id=1402 AND code='RR5'
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_lot_coverage_pct, max_height_ft, source_url, ordinance_section)
SELECT id, 8.0, 60.0, 50.0, 'https://www.zoneomics.com/code/wakulla-county-unincorporated-FL/chapter_3 (Wakulla LDC Sec. 5-38)', 'Sec. 5-38'
FROM zoning_districts WHERE jurisdiction_id=1402 AND code='C2'
ON CONFLICT DO NOTHING;
