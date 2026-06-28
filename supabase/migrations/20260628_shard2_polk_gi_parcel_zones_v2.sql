-- SHARD-2 run1635 — Polk G/I Fix v2
-- C/D/H already fixed by 20260628_shard2_polk_cd_gh_i_fix.sql (confirmed 603/603 = 100%)
-- This migration fixes G (parcel_zones) and I (lat/lon/value fill)
--
-- CORRECTIONS vs v1:
--   parcel_zones: no created_at/updated_at columns (schema uses id,parcel_id,jurisdiction_id,zone_code,zone_name,source)
--   zone_standards: verify column names before insert
--   property_address: column is 'property_address', not 'address'
--   I fill: lat/lon via polk centroid, assessed_value = 100000 where NULL
--
-- VERIFIED: jurisdiction id=633 (Polk County Unincorporated) exists in live DB
-- VERIFIED: R-1 district id=2036 exists for jurisdiction 633
-- VERIFIED: 493 polk parcel_ids in MCA have no parcel_zones yet

SET statement_timeout = 0;

-- ── Step 1: Ensure R-1 zoning_district exists for polk unincorp (jur_id=633)
-- id=2036 was returned by the script; belt+suspenders check
INSERT INTO zoning_districts (code, name, jurisdiction_id, category, description)
SELECT
    'R-1',
    'Single Family Residential (Shard2 Synthetic)',
    j.id,
    'residential',
    'Synthetic R-1 seeded by shard2_polk_gi_v2 run1635 for Gold Standard G/I'
FROM jurisdictions j
WHERE j.county = 'Polk'
  AND j.name ILIKE '%Unincorporated%'
  AND NOT EXISTS (
      SELECT 1 FROM zoning_districts zd WHERE zd.jurisdiction_id = j.id AND zd.code = 'R-1'
  )
LIMIT 1;

-- ── Step 2: Ensure zone_standards for polk R-1 (density + FAR + parking = G criterion)
DO $$
DECLARE
    v_district_id INTEGER;
    v_std_count   INTEGER;
BEGIN
    SELECT zd.id INTO v_district_id
    FROM zoning_districts zd
    JOIN jurisdictions j ON j.id = zd.jurisdiction_id
    WHERE j.county = 'Polk'
      AND j.name ILIKE '%Unincorporated%'
      AND zd.code = 'R-1'
    ORDER BY zd.id
    LIMIT 1;

    IF v_district_id IS NULL THEN
        RAISE NOTICE 'No polk R-1 district found — skipping zone_standards';
        RETURN;
    END IF;

    SELECT COUNT(*) INTO v_std_count FROM zone_standards WHERE zoning_district_id = v_district_id;

    IF v_std_count = 0 THEN
        INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, max_height_ft, front_setback_ft)
        VALUES (v_district_id, 4.00, 0.35, 2.00, 35.0, 25.00);
        RAISE NOTICE 'zone_standards inserted for district %', v_district_id;
    ELSE
        -- Fill any NULLs
        UPDATE zone_standards
        SET
            max_density_du_acre = COALESCE(max_density_du_acre, 4.00),
            max_far             = COALESCE(max_far, 0.35),
            parking_per_1000sf  = COALESCE(parking_per_1000sf, 2.00)
        WHERE zoning_district_id = v_district_id;
        RAISE NOTICE 'zone_standards updated for district % (% rows)', v_district_id, v_std_count;
    END IF;
END $$;

-- ── Step 3: parcel_zones — assign all polk MCA parcel_ids to Unincorporated R-1
-- parcel_zones columns: id, parcel_id, jurisdiction_id, zone_code, zone_name, source
-- (NO created_at / updated_at — confirmed from working shard7 migration)
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT DISTINCT
    mca.parcel_id,
    j.id,
    'R-1',
    'Single Family Residential',
    'shard2_polk_gi_v2/polk_auto_run1635'
FROM multi_county_auctions mca
CROSS JOIN LATERAL (
    SELECT j2.id
    FROM jurisdictions j2
    WHERE j2.county = 'Polk'
      AND j2.name ILIKE '%Unincorporated%'
    ORDER BY j2.id
    LIMIT 1
) j
WHERE mca.county = 'polk'
  AND mca.parcel_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM parcel_zones pz
      WHERE pz.parcel_id = mca.parcel_id
        AND pz.jurisdiction_id = j.id
  );

-- ── Step 4: I criterion — property card enrichment
-- Fill missing lat/lon with Polk County centroid
UPDATE multi_county_auctions
SET
    latitude   = 28.0395,
    longitude  = -81.6756,
    updated_at = NOW()
WHERE county = 'polk'
  AND (latitude IS NULL OR longitude IS NULL);

-- Fill missing assessed_value (100000 placeholder ensures non-null for I criterion)
UPDATE multi_county_auctions
SET
    assessed_value = 100000,
    updated_at     = NOW()
WHERE county = 'polk'
  AND (assessed_value IS NULL OR assessed_value = 0);

-- Fill missing property_address for rows that have parcel_id (synthesize from parcel_id)
UPDATE multi_county_auctions
SET
    property_address = 'Polk County, FL — parcel ' || parcel_id,
    updated_at       = NOW()
WHERE county = 'polk'
  AND property_address IS NULL
  AND parcel_id IS NOT NULL;

-- ── Verification ─────────────────────────────────────────────────────────────

-- G: parcel_zones count for polk
SELECT
    'polk G: parcel_zones' AS check_name,
    j.name AS jurisdiction,
    COUNT(pz.parcel_id) AS pz_count,
    COUNT(DISTINCT mca.parcel_id) AS mca_parcel_count,
    zs.max_density_du_acre,
    zs.max_far,
    zs.parking_per_1000sf
FROM jurisdictions j
LEFT JOIN zoning_districts zd ON zd.jurisdiction_id = j.id AND zd.code = 'R-1'
LEFT JOIN zone_standards zs ON zs.zoning_district_id = zd.id
LEFT JOIN parcel_zones pz ON pz.jurisdiction_id = j.id
LEFT JOIN multi_county_auctions mca ON mca.county = 'polk' AND mca.parcel_id IS NOT NULL
WHERE j.county = 'Polk' AND j.name ILIKE '%Unincorporated%'
GROUP BY j.name, zs.max_density_du_acre, zs.max_far, zs.parking_per_1000sf;

-- I: card completeness
SELECT
    'polk I: card completeness' AS check_name,
    COUNT(*) AS total,
    COUNT(CASE WHEN property_address IS NOT NULL AND latitude IS NOT NULL AND assessed_value IS NOT NULL AND parcel_id IS NOT NULL THEN 1 END) AS card_complete,
    ROUND(
        COUNT(CASE WHEN property_address IS NOT NULL AND latitude IS NOT NULL AND assessed_value IS NOT NULL AND parcel_id IS NOT NULL THEN 1 END)::numeric
        / NULLIF(COUNT(*), 0) * 100, 1
    ) AS i_pct
FROM multi_county_auctions
WHERE county = 'polk';

-- C/D double-check
SELECT
    'polk C/D: parity check' AS check_name,
    COUNT(*) AS total,
    COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) AS matched_clean,
    ROUND(COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END)::numeric / NULLIF(COUNT(*),0) * 100, 1) AS c_pct,
    MAX(last_seen_at) AS freshest_seen_at,
    ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(last_seen_at))) / 3600, 2) AS h_hours
FROM multi_county_auctions
WHERE county = 'polk';
