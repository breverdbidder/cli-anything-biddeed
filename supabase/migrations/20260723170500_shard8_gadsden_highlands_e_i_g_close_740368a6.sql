-- Gold Standard SHARD-8: gadsden + highlands, dispatch 740368a6, 2nd firing
-- Idempotent record of live fixes already applied via Management API SQL executor
-- during this session. Re-running is safe (all statements are idempotent).

-- ── HIGHLANDS C/D: PostgREST NULL-exclusion bug fix ────────────────────────
-- parity_status=not.eq.matched_clean silently excludes rows where
-- parity_status IS NULL (SQL 3-valued logic), so 10 already-complete rows
-- (real parcel_id + property_address) never got promoted by the litmus
-- fallback phase of scripts/shard8_run6046_highlands_cdij_fix.py.
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard8_run6046_litmus_fallback_nullfix:740368a6-0e19-4bb8-8a89-8670cfbd03e6',
    parity_checked_at = now()
WHERE county = 'highlands'
  AND parity_status IS NULL
  AND (parcel_id IS NOT NULL OR property_address IS NOT NULL);

-- ── HIGHLANDS I: real GIS zoning backfill (48 parcels) ──────────────────────
-- Source: live Highlands County ArcGIS Server, gis.highlandsfl.gov/server/
-- rest/services/Layers/Zoning/MapServer/0, joined on STRAP_NUM field.
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
VALUES
  ('C-04-34-28-100-1660-0310', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-04-34-28-100-1780-0310', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-04-34-28-110-1830-0330', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-04-34-28-110-1890-0570', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-04-34-28-110-1900-0240', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-04-34-28-110-1900-0460', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-04-34-28-110-1920-0390', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-04-34-28-110-2070-0320', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-20-36-30-100-0220-0070', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-21-34-29-060-0000-1430', 918, 'M1S', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-020-0390-0030', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-050-0480-0180', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-050-0510-0210', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-050-0530-0220', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-050-0540-0180', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-050-0560-0040', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-060-0550-0090', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-070-0680-0030', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-070-0870-0140', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-080-0570-0180', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-080-0690-0160', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-080-0710-0070', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-080-0750-0080', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-080-0890-0310', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-080-0890-0360', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-080-0890-0390', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-090-0740-0070', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-090-0770-0080', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-090-0800-0090', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-090-0810-0060', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-090-0820-0150', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-110-1040-0190', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-120-0960-0300', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-160-1680-0190', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-191-1830-0150', 918, 'B1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-191-1830-0200', 918, 'B1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-191-1830-0260', 918, 'B1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-191-1840-0210', 918, 'B1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-191-1840-0240', 918, 'B1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-191-1960-0200', 918, 'B1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-191-1960-0450', 918, 'B1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-191-1960-0670', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-22-37-30-400-0060-0040', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-24-35-28-030-0040-0110', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-24-35-28-040-0040-0070', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-24-35-28-101-009A-0380', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-24-35-28-120-0090-0010', 918, 'R3', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6'),
  ('C-35-34-28-021-0060-0180', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:740368a6')
ON CONFLICT DO NOTHING;

-- ── HIGHLANDS G: real ordinance standards for the new codes (fixes a self-
-- inflicted regression: adding B1/R3/M1S parcel_zones above without matching
-- zoning_districts/zone_standards rows crashed v_zoning_gold_standard_kpi_v3
-- far/pk1000 to 0%. Values sourced from Highlands County LDR, ord. 21-22-28).
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 918, 'B1', 'B-1 Neighborhood Business District', 'commercial', '12.05.240(I)', true, false, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 918 AND code = 'B1');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 918, 'R3', 'R-3 Multiple-Family Dwelling Including Motel and Hotel District', 'residential', '12.05.213(G)', false, true, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 918 AND code = 'R3');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 918, 'M1S', 'M-1-S Mobile Home and Residential Subdivisions District', 'residential', '12.05.221', false, true, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 918 AND code = 'M1S');

INSERT INTO zone_standards (zoning_district_id, max_far, max_height_ft, source_url, ordinance_section)
SELECT id, 0.8, 50,
  'https://cms2.revize.com/revize/highlandscountyfl/departments/development_services/planning/LDRS%20thru%20Ord%2021-22-28%20(6-21-22)%20ADA.pdf',
  '12.05.240(I)'
FROM zoning_districts d
WHERE d.jurisdiction_id = 918 AND d.code = 'B1'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_height_ft, source_url, ordinance_section)
SELECT id, 12, 150,
  'https://cms2.revize.com/revize/highlandscountyfl/departments/development_services/planning/LDRS%20thru%20Ord%2021-22-28%20(6-21-22)%20ADA.pdf',
  '12.05.213(G)'
FROM zoning_districts d
WHERE d.jurisdiction_id = 918 AND d.code = 'R3'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);
-- M1S: no zone_standards row inserted — ordinance density value not located
-- (honest gap per BLANK>WRONG, affects only 1 parcel, does not block G >=95%).

-- ── GADSDEN E: two blocked cases resolved with documentary evidence ────────
-- 25000901CA: recorded warranty deed (OR Bk949 Pg570) OCR-matched OR Bk317
-- Pg772 legal description to this parcel (disambiguated from 2 candidates).
UPDATE multi_county_auctions
SET parcel_id = '3-26-2N-5W-0000-00424-0500',
    latitude = 30.537212, longitude = -84.7039906,
    updated_at = now()
WHERE county = 'gadsden' AND case_number = '25000901CA' AND parcel_id IS NULL;

-- 25000942CA: CourtScribe Final Judgment + Certificate of Title confirmed
-- real property at 1029 Joe Adams Rd, Quincy FL; cross-matched to fl_parcels
-- by owner name (WOODS VIELLA) + exact address.
UPDATE multi_county_auctions
SET parcel_id = '3-19-2N-3W-1559-00000-0030',
    property_address = '1029 Joe Adams Rd, Quincy, FL 32351',
    latitude = 30.5569477, longitude = -84.5755808,
    assessed_value = 114613,
    updated_at = now()
WHERE county = 'gadsden' AND case_number = '25000942CA' AND parcel_id IS NULL;
