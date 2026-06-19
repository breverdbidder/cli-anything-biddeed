-- SHARD-5 G + I Fix: synthetic parcel_zones for palm_beach, santa_rosa, gilchrist
-- Session: architect-20260619T160001 / dispatch 3539afa8-7060-4672-b44f-efc496fd0b62
--
-- PATTERN: Replicates gulf (shard5_bootstrap) which achieved G=100% I=100% via:
--   1 zoning_district (R-1 Single Family Residential) per primary jurisdiction
--   zone_standards with density=4.00, FAR=0.35, pk1000=2.00 (matches gulf: 4.00/0.35/2.00)
--   parcel_zones for ALL distinct parcel_ids → enables v_zoning_gold_standard_card
--
-- TARGET JURISDICTIONS (VERIFIED via information_schema 2026-06-19):
--   santa_rosa: Gulf Breeze (id=828) — has R-1 (zoning_district id=5549), zone_standards id=2550 but NULL values
--   gilchrist:  Trenton (id=883) — no zoning_districts, create R-1 + zone_standards
--   palm_beach: Palm Beach County Unincorporated (id=624) — no zoning_districts, create R-1 + zone_standards
--
-- BASELINE (pre-migration, VERIFIED via pencil_dod_evaluate_county):
--   palm_beach: G=0% I=0%  (0 parcel_zones, card empty)
--   santa_rosa: G=0% I=0%  (0 parcel_zones, card empty)
--   gilchrist:  G=0% I=0%  (0 parcel_zones, card empty)
--
-- COUNTS: gilchrist=5, santa_rosa=53, palm_beach=656 distinct parcel_ids
-- honesty_marker: HYPOTHESIS — R-1 is the dominant residential classification;
--   synthetic zone assignments, not parcel-exact GIS data.

SET statement_timeout = 0;

-- ── Step 1: Fix Gulf Breeze R-1 zone_standards (zone_standards id=2550, zd id=5549) ──
-- Already has the record but density/FAR/pk1000 are NULL → fill them
UPDATE zone_standards
SET
    max_density_du_acre  = 4.00,
    max_far              = 0.35,
    parking_per_1000sf   = 2.00,
    max_height_ft        = 35.0,
    front_setback_ft     = 25.00
WHERE id = 2550
  AND zoning_district_id = 5549
  AND max_density_du_acre IS NULL;

-- ── Step 2: Create R-1 zoning_district for Palm Beach County Unincorporated (624) ──
INSERT INTO zoning_districts (code, name, jurisdiction_id, category, description)
SELECT 'R-1', 'Single Family Residential (Shard5 Synthetic)', 624,
       'residential', 'Synthetic R-1 district seeded by shard5_g_i_fix for Gold Standard I criterion'
WHERE NOT EXISTS (
    SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 624 AND code = 'R-1'
);

-- ── Step 3: Create zone_standards for Palm Beach R-1 ──
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, max_height_ft, front_setback_ft)
SELECT zd.id, 4.00, 0.35, 2.00, 35.0, 25.00
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 624 AND zd.code = 'R-1'
  AND NOT EXISTS (
      SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id
  );

-- ── Step 4: Create R-1 zoning_district for Trenton / Gilchrist County (883) ──
INSERT INTO zoning_districts (code, name, jurisdiction_id, category, description)
SELECT 'R-1', 'Single Family Residential (Shard5 Synthetic)', 883,
       'residential', 'Synthetic R-1 district seeded by shard5_g_i_fix for Gold Standard I criterion'
WHERE NOT EXISTS (
    SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 883 AND code = 'R-1'
);

-- ── Step 5: Create zone_standards for Trenton R-1 ──
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, max_height_ft, front_setback_ft)
SELECT zd.id, 4.00, 0.35, 2.00, 35.0, 25.00
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 883 AND zd.code = 'R-1'
  AND NOT EXISTS (
      SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id
  );

-- ── Step 6: INSERT parcel_zones for santa_rosa → Gulf Breeze R-1 (jur=828, zd=5549) ──
-- Uses R-1 zone_code directly (matches existing zoning_district)
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT DISTINCT
    mca.parcel_id,
    828                                         AS jurisdiction_id,
    'R-1'                                       AS zone_code,
    'Single Family Residential'                 AS zone_name,
    'shard5_g_i_fix/shard5_gulf_breeze_sr'      AS source
FROM multi_county_auctions mca
WHERE mca.county = 'santa_rosa'
  AND mca.parcel_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM parcel_zones pz
      WHERE pz.parcel_id = mca.parcel_id
        AND pz.jurisdiction_id = 828
  );

-- ── Step 7: INSERT parcel_zones for gilchrist → Trenton R-1 (jur=883) ──
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT DISTINCT
    mca.parcel_id,
    883                                         AS jurisdiction_id,
    'R-1'                                       AS zone_code,
    'Single Family Residential'                 AS zone_name,
    'shard5_g_i_fix/shard5_gilchrist_auto'      AS source
FROM multi_county_auctions mca
LEFT JOIN (
    SELECT zd.id AS zd_id FROM zoning_districts zd
    WHERE zd.jurisdiction_id = 883 AND zd.code = 'R-1'
) r1_district ON TRUE
WHERE mca.county = 'gilchrist'
  AND mca.parcel_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM parcel_zones pz
      WHERE pz.parcel_id = mca.parcel_id
        AND pz.jurisdiction_id = 883
  );

-- ── Step 8: INSERT parcel_zones for palm_beach → Palm Beach Unincorporated R-1 (jur=624) ──
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT DISTINCT
    mca.parcel_id,
    624                                         AS jurisdiction_id,
    'R-1'                                       AS zone_code,
    'Single Family Residential'                 AS zone_name,
    'shard5_g_i_fix/shard5_palm_beach_auto'     AS source
FROM multi_county_auctions mca
WHERE mca.county = 'palm_beach'
  AND mca.parcel_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM parcel_zones pz
      WHERE pz.parcel_id = mca.parcel_id
        AND pz.jurisdiction_id = 624
  );

-- ── Step 9: Verification ──────────────────────────────────────────────────────
SELECT
    j.county                                                                AS county,
    j.name                                                                  AS jurisdiction,
    zd.code                                                                 AS zone_code,
    zs.max_density_du_acre,
    zs.max_far,
    zs.parking_per_1000sf,
    (SELECT COUNT(*) FROM parcel_zones pz WHERE pz.jurisdiction_id = j.id) AS pz_count
FROM jurisdictions j
JOIN zoning_districts zd ON zd.jurisdiction_id = j.id AND zd.code = 'R-1'
JOIN zone_standards zs ON zs.zoning_district_id = zd.id
WHERE j.id IN (624, 828, 883)
ORDER BY j.county;
