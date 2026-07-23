-- SHARD-9 dispatch 503717c8: martin + bay diagnostic
-- Run before any fixes to establish baseline
SET statement_timeout = 0;

-- ============================================================
-- MARTIN: current state
-- ============================================================
SELECT public.pencil_dod_evaluate_county('martin') AS martin_eval;

-- Martin: which rows are NOT parcel-linked (E gaps)
SELECT case_number, property_address, parcel_id, auction_status, source_platform
FROM public.multi_county_auctions
WHERE lower(county) = 'martin'
  AND parcel_id IS NULL
ORDER BY case_number;

-- Martin: which rows are NOT card_complete (I gaps)
SELECT
  a.case_number,
  a.property_address,
  a.parcel_id,
  COALESCE(a.assessed_value, a.market_value) AS av,
  a.latitude,
  a.longitude,
  pz.zone_code
FROM public.multi_county_auctions a
LEFT JOIN public.parcel_zones pz ON pz.parcel_id = a.parcel_id
WHERE lower(a.county) = 'martin'
  AND NOT (
    a.property_address IS NOT NULL
    AND a.latitude IS NOT NULL
    AND a.longitude IS NOT NULL
    AND COALESCE(a.assessed_value, a.market_value) IS NOT NULL
    AND a.parcel_id IS NOT NULL
    AND pz.zone_code IS NOT NULL
  )
ORDER BY a.case_number;

-- ============================================================
-- BAY: current state
-- ============================================================
SELECT public.pencil_dod_evaluate_county('bay') AS bay_eval;

-- Bay: total row count and key field completeness
SELECT
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE latitude IS NOT NULL) AS has_lat,
  COUNT(*) FILTER (WHERE longitude IS NOT NULL) AS has_lon,
  COUNT(*) FILTER (WHERE assessed_value IS NOT NULL) AS has_av,
  COUNT(*) FILTER (WHERE property_address IS NOT NULL) AS has_addr,
  COUNT(*) FILTER (WHERE parcel_id IS NOT NULL AND parcel_id NOT IN ('TIMESHARE','Property Appraiser','MULTIPLE PARCELS')) AS valid_parcel
FROM public.multi_county_auctions
WHERE lower(county) = 'bay';

-- Bay: parity status breakdown
SELECT
  COALESCE(parity_status, 'NULL') AS status,
  COUNT(*) AS n
FROM public.multi_county_auctions
WHERE lower(county) = 'bay'
GROUP BY parity_status
ORDER BY n DESC;

-- Bay: rows missing parity (C/D gaps)
SELECT case_number, property_address, parcel_id, parity_status, parity_source, auction_status
FROM public.multi_county_auctions
WHERE lower(county) = 'bay'
  AND (parity_status IS NULL OR parity_status NOT IN ('matched_clean', 'matched_divergent'))
ORDER BY case_number;

-- Bay: verified outcomes count (B metric)
SELECT
  'foreclosure_outcomes' AS tbl,
  COUNT(*) AS n,
  COUNT(*) FILTER (WHERE data_source NOT ILIKE '%propertyonion%') AS independent_count
FROM public.foreclosure_outcomes
WHERE lower(county) = 'bay'
UNION ALL
SELECT
  'tax_deed_outcomes' AS tbl,
  COUNT(*) AS n,
  COUNT(*) FILTER (WHERE data_source NOT ILIKE '%propertyonion%') AS independent_count
FROM public.tax_deed_outcomes
WHERE lower(county) = 'bay';

-- Bay: concluded/completed auctions (B/F potential)
SELECT case_number, auction_status, sold_amount, winning_bidder, auction_date, source_platform
FROM public.multi_county_auctions
WHERE lower(county) = 'bay'
  AND auction_status IN ('concluded', 'completed', 'sold', 'results_posted')
ORDER BY auction_date DESC
LIMIT 30;

-- Bay: card-incomplete rows (I gaps)
SELECT
  a.case_number,
  a.property_address,
  a.parcel_id,
  COALESCE(a.assessed_value, a.market_value) AS av,
  a.latitude,
  a.longitude,
  pz.zone_code,
  a.auction_status
FROM public.multi_county_auctions a
LEFT JOIN public.parcel_zones pz ON pz.parcel_id = a.parcel_id
WHERE lower(a.county) = 'bay'
  AND NOT (
    a.property_address IS NOT NULL
    AND a.latitude IS NOT NULL
    AND a.longitude IS NOT NULL
    AND COALESCE(a.assessed_value, a.market_value) IS NOT NULL
    AND a.parcel_id IS NOT NULL
    AND a.parcel_id NOT IN ('TIMESHARE','Property Appraiser','MULTIPLE PARCELS')
    AND pz.zone_code IS NOT NULL
  )
ORDER BY a.case_number;

-- Bay: parcel_zones coverage
SELECT COUNT(*) AS bay_parcel_zones
FROM public.parcel_zones pz
WHERE EXISTS (
  SELECT 1 FROM public.multi_county_auctions a
  WHERE a.parcel_id = pz.parcel_id AND lower(a.county) = 'bay'
);
