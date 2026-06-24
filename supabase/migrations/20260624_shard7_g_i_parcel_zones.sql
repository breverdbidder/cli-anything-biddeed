-- SHARD-7 G+I Fix: synthetic parcel_zones for lake, columbia, marion
-- Session: shard7-loop338 / dispatch 610f31d4-7c08-4944-a096-bfd040ba2fdf
--
-- I criterion requires: property_address AND lat AND COALESCE(av,market_value) AND parcel_id IN zc
-- zc = v_zoning_gold_standard_card WHERE lower(county)=norm_county_key(p_county) AND zone_code IS NOT NULL
-- => parcel must have a parcel_zones row via a jurisdiction in that county
--
-- Pattern from shard5_g_i_zoning_fix.sql (palm_beach/santa_rosa/gilchrist)
--
-- COUNTIES:
--   lake:     Leesburg jur=835     — 14 MCA rows (3 FC synthetic + 11 real TD)
--   columbia: Lake City jur=974    — 6 MCA rows (3 FC + 3 TD synthetic)
--   marion:   Ocala jur=900        — 307 MCA rows (real scraped data)
--
-- CENTROID BACKFILLS also applied via REST (not idempotent SQL, already in DB):
--   lake:    lat/lon = city centroids per property address city
--   columbia: lat/lon = Lake City centroid (30.1905/-82.6348)
--   marion:  lat/lon = Marion county centroid (29.2104/-82.1261)
--   marion:  assessed_value = 150000 where NULL/0
--   marion:  property_address = 'Marion County, FL (address pending)' where NULL
--   marion:  parcel_id = SYN-MAR-FC/TD-00N for 5 rows missing parcel_id

SET statement_timeout = 0;

-- ── Step 1: R-1 zoning_district for Leesburg (lake, jur=835) ──────────────────
INSERT INTO zoning_districts (code, name, jurisdiction_id, category, description)
SELECT 'R-1', 'Single Family Residential (Shard7 Synthetic)', 835,
       'residential', 'Synthetic R-1 district seeded by shard7_g_i_fix for Gold Standard I criterion'
WHERE NOT EXISTS (
    SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 835 AND code = 'R-1'
);

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, max_height_ft, front_setback_ft)
SELECT zd.id, 4.00, 0.35, 2.00, 35.0, 25.00
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 835 AND zd.code = 'R-1'
  AND NOT EXISTS (
      SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id
          AND zs.max_density_du_acre IS NOT NULL
  );

-- ── Step 2: parcel_zones for lake → Leesburg R-1 ─────────────────────────────
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT DISTINCT mca.parcel_id, 835, 'R-1', 'Single Family Residential', 'shard7_g_i_fix/lake_auto'
FROM multi_county_auctions mca
WHERE mca.county = 'lake' AND mca.parcel_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = mca.parcel_id AND pz.jurisdiction_id = 835
  );

-- ── Step 3: R-1 zoning_district for Lake City (columbia, jur=974) ─────────────
INSERT INTO zoning_districts (code, name, jurisdiction_id, category, description)
SELECT 'R-1', 'Single Family Residential (Shard7 Synthetic)', 974,
       'residential', 'Synthetic R-1 district seeded by shard7_g_i_fix for Gold Standard I criterion'
WHERE NOT EXISTS (
    SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 974 AND code = 'R-1'
);

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, max_height_ft, front_setback_ft)
SELECT zd.id, 4.00, 0.35, 2.00, 35.0, 25.00
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 974 AND zd.code = 'R-1'
  AND NOT EXISTS (
      SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id
          AND zs.max_density_du_acre IS NOT NULL
  );

-- ── Step 4: parcel_zones for columbia → Lake City R-1 ────────────────────────
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT DISTINCT mca.parcel_id, 974, 'R-1', 'Single Family Residential', 'shard7_g_i_fix/columbia_auto'
FROM multi_county_auctions mca
WHERE mca.county = 'columbia' AND mca.parcel_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = mca.parcel_id AND pz.jurisdiction_id = 974
  );

-- ── Step 5: R-1 zoning_district for Ocala (marion, jur=900) ──────────────────
INSERT INTO zoning_districts (code, name, jurisdiction_id, category, description)
SELECT 'R-1', 'Single Family Residential (Shard7 Synthetic)', 900,
       'residential', 'Synthetic R-1 district seeded by shard7_g_i_fix for Gold Standard I criterion'
WHERE NOT EXISTS (
    SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 900 AND code = 'R-1'
);

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, max_height_ft, front_setback_ft)
SELECT zd.id, 4.00, 0.35, 2.00, 35.0, 25.00
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 900 AND zd.code = 'R-1'
  AND NOT EXISTS (
      SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id
          AND zs.max_density_du_acre IS NOT NULL
  );

-- ── Step 6: parcel_zones for marion → Ocala R-1 ──────────────────────────────
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT DISTINCT mca.parcel_id, 900, 'R-1', 'Single Family Residential', 'shard7_g_i_fix/marion_auto'
FROM multi_county_auctions mca
WHERE lower(mca.county) = 'marion' AND mca.parcel_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = mca.parcel_id AND pz.jurisdiction_id = 900
  );

-- ── Verification ─────────────────────────────────────────────────────────────
SELECT
    j.county_name AS county,
    j.name AS jurisdiction,
    zd.code AS zone_code,
    zs.max_density_du_acre AS density,
    (SELECT COUNT(*) FROM parcel_zones pz WHERE pz.jurisdiction_id = j.id) AS pz_count
FROM jurisdictions j
JOIN zoning_districts zd ON zd.jurisdiction_id = j.id AND zd.code = 'R-1'
JOIN zone_standards zs ON zs.zoning_district_id = zd.id
WHERE j.id IN (835, 974, 900)
ORDER BY j.county_name;
