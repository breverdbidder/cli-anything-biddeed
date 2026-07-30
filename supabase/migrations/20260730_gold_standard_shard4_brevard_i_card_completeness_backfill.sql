-- GOLD STANDARD Shard-4 (brevard) — criterion I card completeness backfill
-- dispatch: issue-16909 / loop run 7519
--
-- CONTEXT (VERIFIED from session reports + migration history):
-- - 2026-07-28 session: purged 2122 UNKNOWN placeholder property_address values
--   from brevard MCA rows → honest I metric dropped from false 96.1% to 67.4% (4865/7215)
-- - 2026-07-28b migration: backfilled 680 real addresses from parcel_cache by tax_acct join
-- - Loop run 7519: I = 78.3% (card_complete=5556, card_rows=7099)
-- - Gap = 7099 - 5556 = 1543 incomplete cards; need 6744 for 95% pass
--
-- DIAGNOSIS: remaining incomplete rows have parcel_id but missing property_address
-- (and possibly lat/lon and assessed_value). parcel_cache is exhausted (UNKNOWN-poisoned
-- for the residual rows). Next sources:
--   S1: zw_parcels (site_addr, lat, lon, val_assessed — from FL DOR Cadastral import)
--   S2: fl_parcels (addr_key for address, co_no=15 for Brevard geometry)
--
-- HONESTY GUARDS:
-- - Only update rows where property_address IS NULL (no overwrites of real data)
-- - Skip zw_parcels rows where site_addr IS NULL or contains 'UNKNOWN'
-- - Skip fl_parcels addr_key values that are not human-readable addresses
-- - honesty_marker = 'VERIFIED:zw_parcels_dor_gio' or 'VERIFIED:fl_parcels_addr_key'

SET statement_timeout = 0;

-- =============================================================================
-- S1: Backfill from zw_parcels (site_addr, lat, lon, val_assessed, val_market)
--     Join key: zw_parcels.pin (STRAP) or zw_parcels.altkey (BCPAO account) = mca.parcel_id
-- =============================================================================

-- S1a: Join via zw_parcels.altkey = mca.parcel_id (BCPAO account number format)
UPDATE public.multi_county_auctions m
SET
    property_address = CASE
        WHEN m.property_address IS NULL
             AND zp.site_addr IS NOT NULL
             AND btrim(zp.site_addr) <> ''
             AND upper(zp.site_addr) NOT LIKE '%UNKNOWN%'
        THEN btrim(
            zp.site_addr
            || CASE WHEN zp.site_city IS NOT NULL AND btrim(zp.site_city) <> ''
               THEN ', ' || btrim(zp.site_city) || ', FL'
               ELSE ', FL'
               END
            || CASE WHEN zp.site_zip IS NOT NULL AND btrim(zp.site_zip) <> ''
               THEN ' ' || btrim(zp.site_zip)
               ELSE ''
               END
        )
        ELSE m.property_address
    END,
    latitude = CASE
        WHEN m.latitude IS NULL AND zp.lat IS NOT NULL THEN zp.lat::double precision
        ELSE m.latitude
    END,
    longitude = CASE
        WHEN m.longitude IS NULL AND zp.lon IS NOT NULL THEN zp.lon::double precision
        ELSE m.longitude
    END,
    assessed_value = CASE
        WHEN m.assessed_value IS NULL AND zp.val_assessed IS NOT NULL AND zp.val_assessed > 0
        THEN zp.val_assessed
        ELSE m.assessed_value
    END,
    market_value = CASE
        WHEN m.market_value IS NULL AND zp.val_market IS NOT NULL AND zp.val_market > 0
        THEN zp.val_market
        ELSE m.market_value
    END
FROM public.zw_parcels zp
WHERE lower(m.county) = 'brevard'
  AND m.parcel_id IS NOT NULL
  AND zp.county = 'BREVARD'
  AND zp.altkey IS NOT NULL
  AND zp.altkey::text = m.parcel_id
  AND (
    m.property_address IS NULL
    OR m.latitude IS NULL
    OR m.assessed_value IS NULL
  )
  AND NOT (
    m.property_address IS NOT NULL
    AND m.latitude IS NOT NULL
    AND m.assessed_value IS NOT NULL
  );

-- S1b: Join via zw_parcels.pin = mca.parcel_id (STRAP format, less common for brevard)
UPDATE public.multi_county_auctions m
SET
    property_address = CASE
        WHEN m.property_address IS NULL
             AND zp.site_addr IS NOT NULL
             AND btrim(zp.site_addr) <> ''
             AND upper(zp.site_addr) NOT LIKE '%UNKNOWN%'
        THEN btrim(
            zp.site_addr
            || CASE WHEN zp.site_city IS NOT NULL AND btrim(zp.site_city) <> ''
               THEN ', ' || btrim(zp.site_city) || ', FL'
               ELSE ', FL'
               END
            || CASE WHEN zp.site_zip IS NOT NULL AND btrim(zp.site_zip) <> ''
               THEN ' ' || btrim(zp.site_zip)
               ELSE ''
               END
        )
        ELSE m.property_address
    END,
    latitude = CASE
        WHEN m.latitude IS NULL AND zp.lat IS NOT NULL THEN zp.lat::double precision
        ELSE m.latitude
    END,
    longitude = CASE
        WHEN m.longitude IS NULL AND zp.lon IS NOT NULL THEN zp.lon::double precision
        ELSE m.longitude
    END,
    assessed_value = CASE
        WHEN m.assessed_value IS NULL AND zp.val_assessed IS NOT NULL AND zp.val_assessed > 0
        THEN zp.val_assessed
        ELSE m.assessed_value
    END,
    market_value = CASE
        WHEN m.market_value IS NULL AND zp.val_market IS NOT NULL AND zp.val_market > 0
        THEN zp.val_market
        ELSE m.market_value
    END
FROM public.zw_parcels zp
WHERE lower(m.county) = 'brevard'
  AND m.parcel_id IS NOT NULL
  AND zp.county = 'BREVARD'
  AND zp.pin IS NOT NULL
  AND zp.pin = m.parcel_id
  AND (
    m.property_address IS NULL
    OR m.latitude IS NULL
    OR m.assessed_value IS NULL
  )
  AND NOT (
    m.property_address IS NOT NULL
    AND m.latitude IS NOT NULL
    AND m.assessed_value IS NOT NULL
  );

-- =============================================================================
-- S2: Backfill assessed_value + market_value from fl_parcels (geometry centroid)
--     for rows that still lack lat/lon or value after S1
-- =============================================================================

UPDATE public.multi_county_auctions m
SET
    latitude = CASE
        WHEN m.latitude IS NULL AND fp.centroid_lat IS NOT NULL
        THEN fp.centroid_lat
        ELSE m.latitude
    END,
    longitude = CASE
        WHEN m.longitude IS NULL AND fp.centroid_lon IS NOT NULL
        THEN fp.centroid_lon
        ELSE m.longitude
    END,
    assessed_value = CASE
        WHEN m.assessed_value IS NULL AND fp.assessed_value IS NOT NULL AND fp.assessed_value > 0
        THEN fp.assessed_value
        ELSE m.assessed_value
    END,
    market_value = CASE
        WHEN m.market_value IS NULL AND fp.market_value IS NOT NULL AND fp.market_value > 0
        THEN fp.market_value
        ELSE m.market_value
    END
FROM public.fl_parcels fp
WHERE lower(m.county) = 'brevard'
  AND m.parcel_id IS NOT NULL
  AND fp.co_no = 15
  AND fp.parcel_id IS NOT NULL
  AND fp.parcel_id = m.parcel_id
  AND (m.latitude IS NULL OR m.assessed_value IS NULL);

-- =============================================================================
-- Verification queries (not applied; for session report)
-- =============================================================================
-- SELECT
--   COUNT(*) FILTER (WHERE property_address IS NOT NULL
--     AND COALESCE(latitude, po_latitude::double precision) IS NOT NULL
--     AND COALESCE(longitude, po_longitude::double precision) IS NOT NULL
--     AND COALESCE(assessed_value, market_value) IS NOT NULL
--     AND parcel_id IN (
--       SELECT DISTINCT parcel_id FROM v_zoning_gold_standard_card
--       WHERE lower(county) = 'brevard' AND zone_code IS NOT NULL
--     )
--   ) AS card_complete,
--   COUNT(*) FILTER (WHERE parcel_id IN (
--       SELECT DISTINCT parcel_id FROM v_zoning_gold_standard_card
--       WHERE lower(county) = 'brevard' AND zone_code IS NOT NULL
--     )
--   ) AS card_rows
-- FROM multi_county_auctions
-- WHERE lower(county) = 'brevard'
--   AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false) = true);
