-- Gold Standard shard-3 volusia G fix (dispatch 8c78a8df, loop run 7519, 3rd firing)
--
-- ROOT CAUSE: parcel_zones row for parcel_id=533801110032 (jurisdiction_id=938,
-- Daytona Beach) stores zone_code='M1' (no hyphen), which does not match the
-- existing zoning_districts row code='M-1' ("Local Industry", id=6536, every
-- other Daytona Beach industrial code in this dataset -- M-1/M-3/M-4/M-5 -- is
-- stored hyphenated). The join in v_zoning_gold_standard_kpi_v3 therefore fails
-- for this one parcel, defaulting far_applicable/pk1000_applicable to true with
-- NULL values, which is what dragged pct_far_of_applicable to 83.3% (5/6) and
-- pct_pk1000_of_applicable to 92.3% (12/13) -- volusia's only G blocker
-- (density already passes at 96.8%).
--
-- FIX, adversarially verified this session (2 independent researchers +
-- 1 independent re-fetch adjudicator, all confirmed live against
-- api.municode.com jobId=492952 productId=13509):
--   1. Normalize the one mis-coded parcel_zones row to the real district code.
--   2. Populate zone_standards.max_far=1.0 for M-1 (Local Industry), quoted
--      verbatim from Daytona Beach LDC Sec. 4.4.B.3 "Intensity and Dimensional
--      Standards": "Floor area ratio (FAR), maximum | 1.0".
--   3. Mark pk1000_regulated=false for M-1: Daytona Beach's LDC does NOT set a
--      parking minimum per zoning district (Sec. 4.4.B.4 explicitly defers to
--      "development standards in Article 6"). Article 6 Table 6.2.C.1 sets
--      parking by USE TYPE city-wide, and the dominant formula for M-1's core
--      industrial-services/manufacturing/warehouse uses is a compound "1.5 per
--      1,000 sf + 3.5 per 1,000 sf of office or retail area" -- not a single
--      per-1,000sf number. Forcing a single blended value would misrepresent
--      the ordinance (both researchers explicitly flagged this as a
--      fabrication risk). pk1000_regulated=false follows the exact precedent
--      already set for MFR-40 (id=6529) in this same jurisdiction, where
--      per-unit/non-per-1000sf parking was likewise marked not-applicable
--      rather than force-fit into the per-1000sf field.
--
-- NET EFFECT: far_applicable_parcels stays 6, now 6/6 populated (100%);
-- pk1000_applicable_parcels drops 13->12 (this parcel becomes not-applicable),
-- 12/12 populated (100%). density already 96.8% (unaffected, still PASS).
-- G = LEAST(density,far,pk1000) should move from 83.3 -> >=95.

BEGIN;

-- 1. Normalize the mis-coded zone_code to match the real published district code.
UPDATE parcel_zones
   SET zone_code = 'M-1'
 WHERE parcel_id = '533801110032'
   AND jurisdiction_id = 938
   AND zone_code = 'M1';

-- 2/3. Real ordinance values for zoning_districts.id=6536 ("M-1", "Local Industry", Daytona Beach).
UPDATE zoning_districts
   SET far_regulated = true,
       pk1000_regulated = false,
       ordinance_section = 'ADVERSARIALLY VERIFIED 2026-07-30 (2 independent researchers + 1 independent adjudicator re-fetch): api.municode.com/CodesContent?jobId=492952&nodeId=DABELADECO_ART4ZODI_S4.4INBAZODI&productId=13509 (Daytona Beach LDC Sec. 4.4.B.3, "Local Industry (M-1)" Intensity and Dimensional Standards table): "Floor area ratio (FAR), maximum 1.0". Sec. 4.4.B.4 "Development Standards" explicitly defers parking to Article 6 (no per-district override). Article 6 Sec. 6.2 Table 6.2.C.1 (node DABELADECO_ART6DEST_S6.2OREPALO) sets parking by use type city-wide; M-1''s core Industrial Services/Manufacturing & Production/Warehouse & Freight Movement uses share a compound formula "1.5 per 1,000 sf + 3.5 per 1,000 sf of office or retail area", not a single per-1,000sf figure -- pk1000_regulated=false to avoid fabricating a blended number, matching the MFR-40 (id=6529) precedent in this same jurisdiction.'
 WHERE id = 6536;

INSERT INTO zone_standards (zoning_district_id, max_far)
VALUES (6536, 1.0)
ON CONFLICT (zoning_district_id) DO UPDATE SET max_far = EXCLUDED.max_far;

COMMIT;
