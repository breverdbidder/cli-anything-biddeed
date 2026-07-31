-- GOLD STANDARD hamilton, letter G fix (density coverage), 2026-07-31
-- Executed live via scripts/hamilton-G_fix.py (this file documents the
-- already-applied changes for audit trail; the script is idempotent and
-- safe to re-run).
--
-- Context: pencil_dod_evaluate_county('hamilton') -> G FAIL, metric=73.3,
-- detail="density=73.3 far=100.0 pk1000=". 11/15 density-applicable
-- parcels had max_density_du_acre; 4 didn't because their zoning_districts
-- rows (ESA-2 id=12937, RSF/MH-1 id=12938, jurisdiction_id=841 "Jasper")
-- had density_regulated=NULL / far_regulated=NULL and zero zone_standards
-- rows -- v_zoning_district_applicability's COALESCE(...,true) default
-- routed them into the applicable-but-missing numerator gap.
--
-- Affected parcels (parcel_zones.zone_code, jurisdiction_id=841):
--   ESA-2:    3139-160, 4071-000, 4510-000
--   RSF/MH-1: 2007-000
--
-- Real ordinance values (VERIFIED via live OCR this session -- tesseract +
-- pymupdf, 300dpi render; both source PDFs are scanned images with no
-- extractable text layer, confirmed live HTTP 200):
--   https://zoning.hamiltoncountyfl.com/uploads/4.4-esa-environmentally-sensitive-areas.pdf
--   https://zoning.hamiltoncountyfl.com/uploads/4.8-rsfmh-residential-single-family-mobile-home.pdf
--
-- ESA-2 (Sec 4.4.7 / 4.4.8 / 4.4.11):
--   min_lot_sqft=435600 (10 acres). max_density_du_acre=0.1 -- DIRECTLY
--   STATED in OCR'd text: "an overall density of one (1) dwelling unit per
--   ten (10) acres is maintained on site" (Sec 4.4.7, PRD alternative).
--   max_far=1.0 (Sec 4.4.8 note: "no structure shall exceed a 1.0 floor
--   area ratio"). max_height_ft=35 (Sec 4.4.8). max_lot_coverage_pct=20
--   (Sec 4.4.8). front/side/rear=30/25/25 (Sec 4.4.7). parking_per_unit=2
--   (Sec 4.4.11). confidence_score=0.95 (directly stated).
--
-- RSF/MH-1 (Sec 4.8.6 / 4.8.7 / 4.8.9 / 4.8.10):
--   min_lot_sqft=20000 -- DIRECTLY STATED: "RSF/MH-1: Minimum lot area
--   20,000 sq. ft." (Sec 4.8.6). max_density_du_acre=2.18 -- DERIVED
--   (43560/20000=2.178, one-unit-per-minimum-lot reading; no explicit
--   du/acre figure in ordinance text). Same derivation methodology already
--   shipped for Lafayette RSF-2, see
--   20260711_shard11_lafayette_g_real_rsf2_zoning_standards.sql.
--   max_far=1.0 (Sec 4.8.9 note). max_height_ft=35 (Sec 4.8.8).
--   max_lot_coverage_pct=40 (Sec 4.8.9, single-family/duplex row).
--   front/side/rear=30/15/15 (Sec 4.8.7, RSF/MH-1 row). parking_per_unit=2
--   (Sec 4.8.10). confidence_score=0.85 (density derived, rest directly
--   OCR'd).
--
-- Idempotent equivalent (already applied live via REST by
-- scripts/hamilton-G_fix.py -- only patches NULL fields, only inserts
-- zone_standards when absent):

-- 1. Mark both districts as density-regulated (was NULL -> default-true
--    applicable-with-no-standard gap) and explicitly not FAR-regulated by
--    category heuristic (was NULL -> already defaulted false, this makes
--    it explicit / non-behavior-changing).
UPDATE zoning_districts
SET density_regulated = true, far_regulated = false
WHERE id = 12937 AND density_regulated IS NULL;

UPDATE zoning_districts
SET density_regulated = true, far_regulated = false
WHERE id = 12938 AND density_regulated IS NULL;

-- 2. Insert real, cited zone_standards for ESA-2 (id=12937)
INSERT INTO zone_standards (
    zoning_district_id, min_lot_sqft, max_density_du_acre, max_far,
    max_height_ft, max_lot_coverage_pct, front_setback_ft, side_setback_ft,
    rear_setback_ft, parking_per_unit, source_url, ordinance_section,
    confidence_score
)
SELECT 12937, 435600, 0.1, 1.0, 35, 20, 30, 25, 25, 2,
       'https://zoning.hamiltoncountyfl.com/uploads/4.4-esa-environmentally-sensitive-areas.pdf',
       'Sec 4.4.7 (PRD alt.: 1 du/10ac stated directly), 4.4.8, 4.4.11',
       0.95
WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = 12937);

-- 3. Insert real, cited zone_standards for RSF/MH-1 (id=12938)
INSERT INTO zone_standards (
    zoning_district_id, min_lot_sqft, max_density_du_acre, max_far,
    max_height_ft, max_lot_coverage_pct, front_setback_ft, side_setback_ft,
    rear_setback_ft, parking_per_unit, source_url, ordinance_section,
    confidence_score
)
SELECT 12938, 20000, 2.18, 1.0, 35, 40, 30, 15, 15, 2,
       'https://zoning.hamiltoncountyfl.com/uploads/4.8-rsfmh-residential-single-family-mobile-home.pdf',
       'Sec 4.8.6 (min lot 20,000 sqft; density DERIVED 43560/20000=2.178, matches shipped Lafayette RSF-2 precedent)',
       0.85
WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = 12938);

-- Verification (pencil_dod_evaluate_county('hamilton')):
--   Before: G FAIL, metric=73.3, detail="density=73.3 far=100.0 pk1000="
--   After:  G PASS, metric=100.0, detail="density=100.0 far=100.0 pk1000="
--   (confirmed live via REST this session; script output in session report)
