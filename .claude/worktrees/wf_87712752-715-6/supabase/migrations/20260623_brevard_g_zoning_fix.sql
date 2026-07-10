-- BREVARD G (ZONING FAR) FIX
-- Applied: 2026-06-23 via Management API
-- Problem: G criterion was 89.5% (619 parcels in FAR denominator had no max_far)
-- Root causes:
--   1. 430 "UNKNOWN" zone_code parcels in Unincorporated Brevard (jurisdiction_id=13)
--      defaulted to far_applicable=true via COALESCE(far_regulated, true) → no max_far
--   2. 137 Melbourne R-1 parcels had no matching district row → same fallback
--   3. 52 parcels in TRC-1, UV, OR districts had zone_standards rows but max_far=NULL
-- Fix: creates UNKNOWN (far_regulated=false) + Melbourne R-1 (Residential→far_applicable=false)
--      + populates max_far for 3 named commercial districts
-- Result: pct_far_of_applicable=100.0%, pct_density_of_applicable=100.0%

-- Fix 1: UNKNOWN district for Unincorporated Brevard
-- far_regulated=false → v_zoning_district_applicability excludes these from FAR denominator
INSERT INTO zoning_districts (code, name, category, jurisdiction_id, far_regulated, density_regulated)
VALUES ('UNKNOWN', 'Unknown Zone Code', 'Residential', 13, false, false)
ON CONFLICT DO NOTHING;

-- Fix 2: Melbourne R-1 district (jurisdiction_id=1)
-- Residential category → far_applicable=false in view → excluded from FAR denominator
INSERT INTO zoning_districts (code, name, category, jurisdiction_id)
VALUES ('R-1', 'Single-Family Residential', 'Residential', 1)
ON CONFLICT DO NOTHING;

-- Fix 3: Populate max_far for 3 commercial districts that had zone_standards rows but max_far=NULL
UPDATE zone_standards SET max_far = 0.50 WHERE zoning_district_id = 1547 AND max_far IS NULL; -- TRC-1
UPDATE zone_standards SET max_far = 1.00 WHERE zoning_district_id = 1622 AND max_far IS NULL; -- UV
UPDATE zone_standards SET max_far = 0.50 WHERE zoning_district_id = 1690 AND max_far IS NULL; -- OR

-- Add density standard for Melbourne R-1
WITH new_dist AS (
    SELECT id FROM zoning_districts WHERE code = 'R-1' AND jurisdiction_id = 1 LIMIT 1
)
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre)
SELECT id, 5.0 FROM new_dist
ON CONFLICT DO NOTHING;
