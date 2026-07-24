-- GOLD STANDARD shard-4 (leon/glades/walton), loop run 6148, dispatch 0fc2eae2.
-- County: leon. Letter G regression fix (self-caused by this session's I fix).
--
-- ROOT CAUSE (verified live 2026-07-24): the I-fix script in this session
-- (gold_standard_shard4_leon_i_zoning_backfill_run6148.py +
-- _parcel_layer_finish_run6148.py) inserted parcel_zones rows for 7 new
-- zone_codes that had no matching zoning_districts row: CC, MR-1, R-3 (both
-- jurisdictions), RP-2, UF, C-2. v_zoning_gold_standard_kpi_v3's applicability
-- CTE defaults far_applicable/pk1000_applicable/density_applicable to TRUE
-- when the zoning_districts join is NULL (COALESCE(a.far_applicable, true)).
-- This flipped far_applicable_parcels from 0 -> 17 with zero of them carrying
-- a max_far value, dropping G's FAR dimension from N/A to 0.0% and taking G
-- from PASS (98.7) to FAIL (0.0) same session -- a self-inflicted regression,
-- caught before shipping via a live G re-check after the I fix.
--
-- FIX, following the exact convention already used for leon's existing
-- classified districts (R-1, RP-1, RP, R, CU-26, CU-45 -- see zone_standards
-- source_url talgov.com PDFs / shard11_run3679_leon_zoning_real): classify
-- each new code by its REAL name, independently verified live against the
-- Leon County TLC_OverlayZoning_D_WM ArcGIS layer's own ZONING/ZONED domain
-- values (intervector.leoncountyfl.gov) -- not guessed:
--   MR-1 = "Medium Density Residential"                    -> residential
--   R-3  = "Single Detached, Attached and Two Family Residential" -> residential
--   RP-2 = "Residential Preservation-2" (same family as existing RP-1/RP)     -> residential
--   UF   = "Urban Fringe" (confirmed via live talgov.com/.../zoning/uf.pdf)   -> residential
-- category='residential' with far_regulated/pk1000_regulated left NULL
-- reproduces the exact fallback the view already uses successfully for
-- R-1/RP-1/RP/R/CU-26/CU-45: category not in (commercial,industrial,mixed-use)
-- => far_applicable=false, pk1000_applicable=false, density_applicable=true.
-- No numeric standards are fabricated -- only a verified category label.
--
-- CC ("Central Core", 1 parcel, case 2025 CA 001874, jurisdiction 917) and
-- C-2 ("General Commercial", 1 parcel, case 26-0028, jurisdiction 1397) are
-- genuinely commercial districts where FAR IS ordinance-regulated in
-- Tallahassee/Leon's LDC, and no real max_far value could be sourced this
-- session (talgov.com PDF lookup returned 404 for both cc.pdf and c-2.pdf --
-- filename pattern does not hold for these two codes). Per HONESTY PROTOCOL,
-- fabricating a FAR value is banned. These 2 parcel_zones rows are reverted
-- (deleted) rather than left half-classified -- they return to their prior
-- honest "not yet zoned" state. I's card_complete cushion (182/189, 96.3%)
-- absorbs the 2-row loss (180/189 = 95.2%, still PASS). Left open for a
-- future session with real Chapter 10 LDC Central Core / C-2 FAR figures.

DELETE FROM parcel_zones
WHERE jurisdiction_id = 917 AND zone_code = 'CC'
  AND source LIKE 'tlcgis%shard4-run6148%';

DELETE FROM parcel_zones
WHERE jurisdiction_id = 1397 AND zone_code = 'C-2'
  AND source LIKE 'tlcgis%shard4-run6148%';

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, description)
VALUES
  (917, 'MR-1', 'Medium Density Residential', 'residential', NULL,
   'leon_tlc_gis_domain_verified:shard4-run6148'),
  (917, 'R-3', 'Single Detached, Attached and Two Family Residential', 'residential', NULL,
   'leon_tlc_gis_domain_verified:shard4-run6148'),
  (1397, 'R-3', 'Single Detached, Attached and Two Family Residential', 'residential', NULL,
   'leon_tlc_gis_domain_verified:shard4-run6148'),
  (917, 'RP-2', 'Residential Preservation-2', 'residential', NULL,
   'leon_tlc_gis_domain_verified:shard4-run6148'),
  (1397, 'UF', 'Urban Fringe', 'residential', NULL,
   'leon_talgov_pdf_verified:shard4-run6148:https://www.talgov.com/Uploads/Public/Documents/place/zoning/uf.pdf')
ON CONFLICT DO NOTHING;
