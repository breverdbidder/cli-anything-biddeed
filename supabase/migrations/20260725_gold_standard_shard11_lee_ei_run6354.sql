-- Gold Standard SHARD-11 lee — E+I fix, dispatch 03ff9ae3-9a64-4179-8345-d6b129a0ed83, run 6354.
-- Session: architect-20260725T080000
--
-- Current state (brief, run 6354):
--   E=88.5% [parcel_linked=285/322]   target >=95% (need 306+)
--   I=83.2% [card_complete=268/322]   target >=95% (need 306+)
--
-- Strategy (pure-SQL path using fl_parcels for Lee co_no=46):
--   1. Diagnostic — print current gap sizes.
--   2. Backfill lat/lng + assessed_value from fl_parcels for rows with parcel_id
--      that are missing geo/value data.
--   3. Insert parcel_zones from fl_parcels where (jid, zone_code) exists in
--      zoning_districts (G regression guard -- never insert unknown codes).
--   4. E-gap address linkage: for rows with parcel_id=NULL but have property_address,
--      try exact uppercase match against fl_parcels.site_addr (unique matches only).
--   5. Insert parcel_zones for newly E-linked rows (same guard).
--
-- Lee County jurisdiction IDs:
--   630 = Lee County Unincorporated, 815 = Cape Coral, 914 = Bonita Springs,
--   912 = Fort Myers Beach, 942 = Sanibel, 929 = Fort Myers (city)
--
-- G regression guard: only insert parcel_zones where (jurisdiction_id, zone_code)
-- exists in zoning_districts. This is the critical invariant from all prior Lee sessions.

SET statement_timeout = 0;

DO $$
DECLARE
  v_total         INTEGER;
  v_e_gap         INTEGER;
  v_i_gap_pz      INTEGER;
  v_i_gap_geo     INTEGER;
  v_i_gap_val     INTEGER;
  v_geo_updated   INTEGER;
  v_pz_inserted   INTEGER;
  v_e_linked      INTEGER;
  v_e_pz_inserted INTEGER;
BEGIN

-- ── Step 1: Diagnostic ────────────────────────────────────────────────────────

  SELECT COUNT(*) INTO v_total
  FROM multi_county_auctions
  WHERE county = 'lee'
    AND (data_source IS NULL OR data_source <> 'propertyonion');

  SELECT COUNT(*) INTO v_e_gap
  FROM multi_county_auctions
  WHERE county = 'lee'
    AND (data_source IS NULL OR data_source <> 'propertyonion')
    AND (parcel_id IS NULL
         OR parcel_id IN ('MULTIPLE PARCEL', 'MULTIPLE')
         OR LOWER(parcel_id) = 'property appraiser');

  SELECT COUNT(*) INTO v_i_gap_pz
  FROM multi_county_auctions mca
  WHERE mca.county = 'lee'
    AND (mca.data_source IS NULL OR mca.data_source <> 'propertyonion')
    AND mca.parcel_id IS NOT NULL
    AND mca.parcel_id ~ '\d'
    AND LOWER(mca.parcel_id) NOT IN ('property appraiser', 'multiple parcel', 'multiple')
    AND NOT EXISTS (
      SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = mca.parcel_id
    );

  SELECT COUNT(*) INTO v_i_gap_geo
  FROM multi_county_auctions
  WHERE county = 'lee'
    AND (data_source IS NULL OR data_source <> 'propertyonion')
    AND parcel_id IS NOT NULL AND parcel_id ~ '\d'
    AND LOWER(parcel_id) NOT IN ('property appraiser', 'multiple parcel', 'multiple')
    AND (latitude IS NULL OR longitude IS NULL);

  SELECT COUNT(*) INTO v_i_gap_val
  FROM multi_county_auctions
  WHERE county = 'lee'
    AND (data_source IS NULL OR data_source <> 'propertyonion')
    AND parcel_id IS NOT NULL AND parcel_id ~ '\d'
    AND LOWER(parcel_id) NOT IN ('property appraiser', 'multiple parcel', 'multiple')
    AND assessed_value IS NULL AND market_value IS NULL;

  RAISE NOTICE '[DIAGNOSTIC] Lee in-scope rows: %', v_total;
  RAISE NOTICE '[DIAGNOSTIC] E gap (no real parcel_id): %', v_e_gap;
  RAISE NOTICE '[DIAGNOSTIC] I gap - needs parcel_zones: %', v_i_gap_pz;
  RAISE NOTICE '[DIAGNOSTIC] I gap - needs geo (lat/lng): %', v_i_gap_geo;
  RAISE NOTICE '[DIAGNOSTIC] I gap - needs value: %', v_i_gap_val;

-- ── Step 2: Backfill geo/value from fl_parcels (pin = parcel_id exact match) ──

  UPDATE multi_county_auctions mca
  SET
    latitude       = COALESCE(mca.latitude, fp.centroid_lat),
    longitude      = COALESCE(mca.longitude, COALESCE(fp.centroid_lng, fp.centroid_lon)),
    assessed_value = CASE WHEN mca.assessed_value IS NULL
                          THEN COALESCE(fp.val_assessed, fp.val_market)
                          ELSE mca.assessed_value END
  FROM fl_parcels fp
  WHERE mca.county = 'lee'
    AND (mca.data_source IS NULL OR mca.data_source <> 'propertyonion')
    AND mca.parcel_id IS NOT NULL
    AND mca.parcel_id ~ '\d'
    AND LOWER(mca.parcel_id) NOT IN ('property appraiser', 'multiple parcel', 'multiple')
    AND fp.pin = mca.parcel_id
    AND (mca.latitude IS NULL OR mca.longitude IS NULL OR mca.assessed_value IS NULL)
    AND (fp.centroid_lat IS NOT NULL OR fp.val_assessed IS NOT NULL OR fp.val_market IS NOT NULL);

  GET DIAGNOSTICS v_geo_updated = ROW_COUNT;
  RAISE NOTICE '[STEP 2] Geo/value updated from fl_parcels: % rows', v_geo_updated;

-- ── Step 3: Insert parcel_zones from fl_parcels (G regression guard applied) ──

  INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
  SELECT DISTINCT ON (mca.parcel_id)
    mca.parcel_id,
    CASE
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%north fort myers%'   THEN 630
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%fort myers shores%'  THEN 630
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%alva%'               THEN 630
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%bokeelia%'           THEN 630
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%lehigh acres%'       THEN 630
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%cape coral%'         THEN 815
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%bonita springs%'     THEN 914
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%estero%'             THEN 630
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%fort myers beach%'   THEN 912
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%sanibel%'            THEN 942
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%captiva%'            THEN 630
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%fort myers%'         THEN 929
      ELSE 630
    END                   AS jurisdiction_id,
    fp.zoning_code        AS zone_code,
    fp.zoning_code        AS zone_name,
    'shard11_run6354_fl_parcels_20260725' AS source
  FROM multi_county_auctions mca
  JOIN fl_parcels fp ON fp.pin = mca.parcel_id
  WHERE mca.county = 'lee'
    AND (mca.data_source IS NULL OR mca.data_source <> 'propertyonion')
    AND mca.parcel_id IS NOT NULL
    AND mca.parcel_id ~ '\d'
    AND LOWER(mca.parcel_id) NOT IN ('property appraiser', 'multiple parcel', 'multiple')
    AND fp.zoning_code IS NOT NULL AND fp.zoning_code <> ''
    AND NOT EXISTS (SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = mca.parcel_id)
    -- G regression guard: only insert if (jid, zone_code) is already known
    AND EXISTS (
      SELECT 1 FROM zoning_districts zd
      WHERE zd.jurisdiction_id = CASE
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%north fort myers%'   THEN 630
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%fort myers shores%'  THEN 630
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%alva%'               THEN 630
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%bokeelia%'           THEN 630
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%lehigh acres%'       THEN 630
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%cape coral%'         THEN 815
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%bonita springs%'     THEN 914
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%estero%'             THEN 630
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%fort myers beach%'   THEN 912
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%sanibel%'            THEN 942
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%captiva%'            THEN 630
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%fort myers%'         THEN 929
        ELSE 630
      END
      AND zd.code = fp.zoning_code
    )
  ON CONFLICT DO NOTHING;

  GET DIAGNOSTICS v_pz_inserted = ROW_COUNT;
  RAISE NOTICE '[STEP 3] parcel_zones inserted (fl_parcels STRAP match, known codes only): % rows', v_pz_inserted;

-- ── Step 4: E-gap — address linkage from fl_parcels ───────────────────────────

  -- Backfill parcel_id from exact uppercase address match in fl_parcels
  -- Only apply when the match is unique (1 parcel per address) to avoid wrong linkage.
  WITH e_gap_rows AS (
    SELECT mca.id, UPPER(TRIM(mca.property_address)) AS addr_upper
    FROM multi_county_auctions mca
    WHERE mca.county = 'lee'
      AND (mca.data_source IS NULL OR mca.data_source <> 'propertyonion')
      AND (mca.parcel_id IS NULL
           OR mca.parcel_id IN ('MULTIPLE PARCEL', 'MULTIPLE')
           OR LOWER(mca.parcel_id) = 'property appraiser')
      AND mca.property_address IS NOT NULL
      AND LENGTH(TRIM(mca.property_address)) > 5
  ),
  fl_addr_candidates AS (
    SELECT
      e.id AS mca_id,
      fp.pin AS matched_parcel_id,
      fp.centroid_lat AS fp_lat,
      COALESCE(fp.centroid_lng, fp.centroid_lon) AS fp_lng,
      fp.val_assessed AS fp_assessed,
      COUNT(*) OVER (PARTITION BY e.id) AS match_count
    FROM e_gap_rows e
    JOIN fl_parcels fp ON UPPER(TRIM(fp.site_addr)) = e.addr_upper
  )
  UPDATE multi_county_auctions mca
  SET
    parcel_id      = fac.matched_parcel_id,
    latitude       = COALESCE(mca.latitude, fac.fp_lat),
    longitude      = COALESCE(mca.longitude, fac.fp_lng),
    assessed_value = COALESCE(mca.assessed_value, fac.fp_assessed)
  FROM fl_addr_candidates fac
  WHERE mca.id = fac.mca_id
    AND fac.match_count = 1;  -- unique match only

  GET DIAGNOSTICS v_e_linked = ROW_COUNT;
  RAISE NOTICE '[STEP 4] E-gap rows linked via address match: % rows', v_e_linked;

-- ── Step 5: Insert parcel_zones for E-gap rows newly linked in step 4 ─────────

  INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
  SELECT DISTINCT ON (mca.parcel_id)
    mca.parcel_id,
    CASE
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%north fort myers%'   THEN 630
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%fort myers shores%'  THEN 630
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%alva%'               THEN 630
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%bokeelia%'           THEN 630
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%lehigh acres%'       THEN 630
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%cape coral%'         THEN 815
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%bonita springs%'     THEN 914
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%estero%'             THEN 630
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%fort myers beach%'   THEN 912
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%sanibel%'            THEN 942
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%captiva%'            THEN 630
      WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%fort myers%'         THEN 929
      ELSE 630
    END                        AS jurisdiction_id,
    fp.zoning_code             AS zone_code,
    fp.zoning_code             AS zone_name,
    'shard11_run6354_fl_parcels_addr_20260725' AS source
  FROM multi_county_auctions mca
  JOIN fl_parcels fp ON fp.pin = mca.parcel_id
  WHERE mca.county = 'lee'
    AND (mca.data_source IS NULL OR mca.data_source <> 'propertyonion')
    AND mca.parcel_id IS NOT NULL AND mca.parcel_id ~ '\d'
    AND LOWER(mca.parcel_id) NOT IN ('property appraiser', 'multiple parcel', 'multiple')
    AND fp.zoning_code IS NOT NULL AND fp.zoning_code <> ''
    AND NOT EXISTS (SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = mca.parcel_id)
    AND EXISTS (
      SELECT 1 FROM zoning_districts zd
      WHERE zd.jurisdiction_id = CASE
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%north fort myers%'   THEN 630
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%fort myers shores%'  THEN 630
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%alva%'               THEN 630
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%bokeelia%'           THEN 630
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%lehigh acres%'       THEN 630
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%cape coral%'         THEN 815
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%bonita springs%'     THEN 914
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%estero%'             THEN 630
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%fort myers beach%'   THEN 912
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%sanibel%'            THEN 942
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%captiva%'            THEN 630
        WHEN LOWER(COALESCE(fp.site_city, '')) LIKE '%fort myers%'         THEN 929
        ELSE 630
      END
      AND zd.code = fp.zoning_code
    )
  ON CONFLICT DO NOTHING;

  GET DIAGNOSTICS v_e_pz_inserted = ROW_COUNT;
  RAISE NOTICE '[STEP 5] parcel_zones inserted for E-gap addr-linked rows: % rows', v_e_pz_inserted;

-- ── Step 6: Final state ───────────────────────────────────────────────────────

  RAISE NOTICE '[SUMMARY] geo_updated=% pz_inserted=% e_linked=% e_pz_inserted=%',
    v_geo_updated, v_pz_inserted, v_e_linked, v_e_pz_inserted;

END;
$$;

-- ── Verification query (run after commit) ─────────────────────────────────────

SELECT
  'lee_scope_total'        AS metric,
  COUNT(*)::TEXT           AS value
FROM multi_county_auctions
WHERE county = 'lee'
  AND (data_source IS NULL OR data_source <> 'propertyonion')

UNION ALL

SELECT
  'e_gap_remaining'        AS metric,
  COUNT(*)::TEXT           AS value
FROM multi_county_auctions
WHERE county = 'lee'
  AND (data_source IS NULL OR data_source <> 'propertyonion')
  AND (parcel_id IS NULL
       OR parcel_id IN ('MULTIPLE PARCEL', 'MULTIPLE')
       OR LOWER(parcel_id) = 'property appraiser')

UNION ALL

SELECT
  'pz_gap_remaining'       AS metric,
  COUNT(*)::TEXT           AS value
FROM multi_county_auctions mca
WHERE mca.county = 'lee'
  AND (mca.data_source IS NULL OR mca.data_source <> 'propertyonion')
  AND mca.parcel_id IS NOT NULL
  AND mca.parcel_id ~ '\d'
  AND LOWER(mca.parcel_id) NOT IN ('property appraiser', 'multiple parcel', 'multiple')
  AND NOT EXISTS (SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = mca.parcel_id)

UNION ALL

SELECT
  'parcel_zones_lee_total' AS metric,
  COUNT(*)::TEXT           AS value
FROM parcel_zones
WHERE jurisdiction_id IN (630, 815, 914, 912, 929, 942)

ORDER BY metric;

-- ### SQL VERIFICATION
-- SELECT public.pencil_dod_evaluate_county('lee');
-- Timestamp: 2026-07-25 UTC
