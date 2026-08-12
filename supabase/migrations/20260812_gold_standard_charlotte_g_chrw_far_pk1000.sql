-- Gold Standard charlotte-G (FIX phase, dispatch charlotte-G)
--
-- Root cause: of charlotte's 158 gold-standard-card parcels, only 2 are
-- FAR/pk1000-"applicable" under v_zoning_district_applicability's default
-- category formula (commercial/industrial/mixed-use, non-PUD). Both belong
-- to zoning district CHRW ("Charlotte Harbor Riverwalk (Mixed Use)",
-- zoning_districts.id=13810, jurisdiction_id=813, category='mixed-use').
-- That district has zero rows in zone_standards (max_far, parking_per_1000sf
-- both NULL) and far_regulated/pk1000_regulated overrides both NULL, so the
-- view falls through to the mixed-use default of TRUE for both applicability
-- flags. Neither metric has a real value to satisfy, so both parcels fail
-- both metrics -> pct_far_of_applicable=0.0, pct_pk1000_of_applicable=0.0.
--
-- Verified live (2026-08-12) before this migration:
--   pencil_dod_evaluate_county('charlotte').G = {pass:false, detail:"density=87.3 far=0.0 pk1000=0.0", metric:0.0}
--   zoning_districts id=13810: far_regulated=NULL, pk1000_regulated=NULL, category='mixed-use'
--   zone_standards: no row for zoning_district_id=13810
--
-- Real Charlotte County ordinance research (Sec. 3-9-47 "Charlotte Harbor
-- Community Development Code," charlottecounty-fl.elaws.us, cross-checked
-- against the county's own zoning-map legend PDF confirming CHRW is a
-- genuine district):
--   - CHRW's development-standards table regulates bulk via max density =
--     24 units/acre, max height = 35 ft, max lot coverage = 80%, min lot
--     12,000 sq ft. It contains NO FAR row/column at all (full-text search
--     of the section for "FAR"/"floor area ratio"/"intensity" returns zero
--     hits, confirmed via two independent fetches).
--   - Off-street parking for CHRW is not a district-specific fixed ratio;
--     it defers to the general Sec. 3-9-79 schedule, which for "Retail
--     Sales and Services, Business Services, Professional Services,
--     Clinics and Medical Laboratories" (the closest catch-all commercial
--     category applicable to a mixed-use riverwalk district) is
--     1 space / 200 sq ft = 5 spaces/1,000 sq ft.
--
-- far_regulated=false for CHRW mirrors the existing precedent already set
-- for CG (Commercial General) in this same jurisdiction (id=13397,
-- jurisdiction_id=813, far_regulated=false, pk1000_regulated=false) --
-- same jurisdiction, same real-ordinance-driven "not FAR-regulated" finding.
--
-- Expected live effect after this migration:
--   far_applicable_parcels: 2 -> 0 (CHRW excluded from FAR denominator;
--     zero-denominator convention treats this as N/A/pass, matching CG).
--   pk1000_applicable_parcels: stays 2, both now backed by a real
--     parking_per_1000sf=5.0 value -> pct_pk1000_of_applicable 0.0 -> 100.0.
--   G still gated on density=87.3 (separate, larger-magnitude gap, not in
--   scope of this migration -- tracked as a distinct task).
--
-- SAFETY: additive INSERT (one row, keyed by zoning_district_id=13810 which
-- currently has no zone_standards row) + single-column UPDATE on one
-- existing zoning_districts row. Does not touch the view, cron jobs, or any
-- other county's data.

INSERT INTO zone_standards (
    zoning_district_id,
    max_density_du_acre,
    max_height_ft,
    max_lot_coverage_pct,
    min_lot_sqft,
    parking_per_1000sf,
    source_url,
    ordinance_section
)
SELECT
    13810,
    24.0,
    35,
    80.0,
    12000,
    5.0,
    'https://charlottecounty-fl.elaws.us/code/coor_ptiii_ch3-9_artii_sec3-9-47',
    'Sec. 3-9-47 (CHRW district standards) / Sec. 3-9-79 (parking schedule)'
WHERE NOT EXISTS (
    SELECT 1 FROM zone_standards WHERE zoning_district_id = 13810
);

UPDATE zoning_districts
   SET far_regulated = false,
       ordinance_section = COALESCE(ordinance_section, 'Sec. 3-9-47')
 WHERE id = 13810 AND code = 'CHRW' AND jurisdiction_id = 813;
