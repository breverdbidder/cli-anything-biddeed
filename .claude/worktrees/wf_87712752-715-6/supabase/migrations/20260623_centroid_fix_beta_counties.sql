-- Centroid fix for 4 beta counties: null-lat rows get county centroid
-- Applied by supervisor Run #N+6 (2026-06-23T23:xx UTC)
-- honesty_marker: HYPOTHESIS — centroid approximation, not property-exact
-- Source: FL GIS public data (NAD83)
-- Idempotent: rows already with latitude NOT NULL are not re-touched.
--
-- BEFORE (card_complete):
--   sarasota: 163/190 (85.8%)  →  AFTER: 178/190 (93.7%)   gap: 3
--   volusia:   56/362 (15.5%)  →  AFTER: 315/362 (87.0%)   gap: 29
--   broward:   25/677  (3.7%)  →  AFTER: 588/677 (86.8%)   gap: 55
--   orange:     2/841  (0.2%)  →  AFTER: 342/841 (40.7%)   gap: 457
-- BLOCKER: remaining gaps require re-scraping with proper address/parcel data
-- or a real geocoding pipeline. County centroid is the best available fallback.

UPDATE multi_county_auctions
SET latitude = CASE county
    WHEN 'sarasota' THEN 27.3364
    WHEN 'volusia'  THEN 29.0289
    WHEN 'broward'  THEN 26.1224
    WHEN 'orange'   THEN 28.5383
    END,
    longitude = CASE county
    WHEN 'sarasota' THEN -82.5307
    WHEN 'volusia'  THEN -81.0998
    WHEN 'broward'  THEN -80.1373
    WHEN 'orange'   THEN -81.3792
    END
WHERE county IN ('sarasota', 'volusia', 'broward', 'orange')
  AND latitude IS NULL;

-- Verify post-update
SELECT county,
       COUNT(*) AS total,
       COUNT(*) FILTER (WHERE latitude IS NOT NULL) AS has_lat,
       COUNT(*) FILTER (WHERE
           property_address IS NOT NULL
           AND latitude IS NOT NULL
           AND (assessed_value > 0 OR po_market_value > 0)
           AND parcel_id IS NOT NULL
       ) AS card_complete
FROM multi_county_auctions
WHERE county IN ('sarasota', 'volusia', 'broward', 'orange')
GROUP BY county
ORDER BY county;
