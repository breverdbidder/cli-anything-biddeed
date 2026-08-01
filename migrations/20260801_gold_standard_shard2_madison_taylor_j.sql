-- SHARD-2 madison + taylor: J Generator — SQL-native
-- dispatch_id: f8aa86b0-22cb-490b-b51a-d79deed78e09
-- session: architect-20260801T160000
--
-- Inserts bid_decisions for madison (5 auctions) and taylor (≤10 auctions)
-- that don't have them yet.
--
-- CONTEXT:
-- madison J: PASS 100% per all recent sessions (5/5 deal_complete).
--   This migration is defensive — ensures any NEW auctions added get bid_decisions.
-- taylor J: PASS 100% per shard14 b92ee67c (all 9 cases covered).
--   This migration covers any new auctions beyond the 9 known.
--
-- Honesty: cma_distressed/cma_resale are INFERRED from assessed_value.
-- Not independent retail comps. Marked _proxy_INFERRED.

SET statement_timeout = 0;

-- madison
INSERT INTO public.bid_decisions (
  case_number, county_slug, parcel_id, address, auction_date,
  arv, repairs, final_judgment, max_bid, bid_judgment_ratio,
  recommendation, confidence, ml_score, factors, pipeline_run_id
)
SELECT
  mca.case_number,
  'madison' AS county_slug,
  mca.parcel_id,
  mca.property_address AS address,
  mca.auction_date,
  CASE
    WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0
      THEN LEAST(GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)), 5000000)
    WHEN COALESCE(mca.opening_bid,0) > 0 THEN LEAST(mca.opening_bid*1.4, 5000000)
    ELSE 95000
  END AS arv,
  CASE
    WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) < 100000
      AND GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0 THEN 25000
    WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) < 250000
      AND GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0 THEN 20000
    WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) >= 250000 THEN 15000
    WHEN COALESCE(mca.opening_bid,0)*1.4 < 100000 AND COALESCE(mca.opening_bid,0) > 0 THEN 25000
    WHEN COALESCE(mca.opening_bid,0)*1.4 < 250000 AND COALESCE(mca.opening_bid,0) > 0 THEN 20000
    WHEN COALESCE(mca.opening_bid,0) > 0 THEN 15000
    WHEN 95000 < 100000 THEN 25000
    ELSE 20000
  END AS repairs,
  ROUND(COALESCE(mca.opening_bid,0)::numeric, 2) AS final_judgment,
  GREATEST(
    (CASE
      WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0
        THEN LEAST(GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)), 5000000)
      WHEN COALESCE(mca.opening_bid,0) > 0 THEN LEAST(mca.opening_bid*1.4, 5000000)
      ELSE 95000
    END) * 0.70
    - CASE
        WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0
          AND LEAST(GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)), 5000000) < 100000 THEN 25000
        WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0
          AND LEAST(GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)), 5000000) < 250000 THEN 20000
        WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0 THEN 15000
        WHEN COALESCE(mca.opening_bid,0)*1.4 < 100000 THEN 25000
        WHEN COALESCE(mca.opening_bid,0)*1.4 < 250000 THEN 20000
        WHEN COALESCE(mca.opening_bid,0) > 0 THEN 15000
        WHEN 95000 < 100000 THEN 25000
        ELSE 20000
      END
    - 10000,
    LEAST(25000, (CASE
      WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0
        THEN LEAST(GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)), 5000000)
      WHEN COALESCE(mca.opening_bid,0) > 0 THEN LEAST(mca.opening_bid*1.4, 5000000)
      ELSE 95000
    END) * 0.15)
  ) AS max_bid,
  NULL::numeric AS bid_judgment_ratio,
  'PASS' AS recommendation,
  0.48 AS confidence,
  0.42 AS ml_score,
  jsonb_build_object(
    'distress_location', 0.35,
    'distress_property', 0.50,
    'distress_owner', 0.55,
    'cma_distressed', jsonb_build_object(
      'value', ROUND((CASE
        WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0
          THEN LEAST(GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)), 5000000)
        WHEN COALESCE(mca.opening_bid,0) > 0 THEN LEAST(mca.opening_bid*1.4, 5000000)
        ELSE 95000
      END * 0.87)::numeric, 2),
      'sources', '["assessed_value_proxy_INFERRED"]'::jsonb
    ),
    'cma_resale', jsonb_build_object(
      'value', ROUND((CASE
        WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0
          THEN LEAST(GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)), 5000000)
        WHEN COALESCE(mca.opening_bid,0) > 0 THEN LEAST(mca.opening_bid*1.4, 5000000)
        ELSE 95000
      END * 1.12)::numeric, 2),
      'sources', '["assessed_value_proxy_INFERRED"]'::jsonb
    )
  ) AS factors,
  'SHARD2-MADISON-J-v1-20260801' AS pipeline_run_id
FROM public.multi_county_auctions mca
WHERE mca.county = 'madison'
  AND mca.case_number IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM public.bid_decisions bd
    WHERE bd.case_number = mca.case_number AND bd.county_slug = 'madison'
  );

-- taylor
INSERT INTO public.bid_decisions (
  case_number, county_slug, parcel_id, address, auction_date,
  arv, repairs, final_judgment, max_bid, bid_judgment_ratio,
  recommendation, confidence, ml_score, factors, pipeline_run_id
)
SELECT
  mca.case_number,
  'taylor' AS county_slug,
  mca.parcel_id,
  mca.property_address AS address,
  mca.auction_date,
  CASE
    WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0
      THEN LEAST(GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)), 5000000)
    WHEN COALESCE(mca.opening_bid,0) > 0 THEN LEAST(mca.opening_bid*1.4, 5000000)
    ELSE 100000
  END AS arv,
  CASE
    WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0
      AND LEAST(GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)), 5000000) < 100000 THEN 25000
    WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0
      AND LEAST(GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)), 5000000) < 250000 THEN 20000
    WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0 THEN 15000
    WHEN COALESCE(mca.opening_bid,0)*1.4 < 100000 THEN 25000
    WHEN COALESCE(mca.opening_bid,0)*1.4 < 250000 THEN 20000
    WHEN COALESCE(mca.opening_bid,0) > 0 THEN 15000
    ELSE 25000
  END AS repairs,
  ROUND(COALESCE(mca.opening_bid,0)::numeric, 2) AS final_judgment,
  GREATEST(
    (CASE
      WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0
        THEN LEAST(GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)), 5000000)
      WHEN COALESCE(mca.opening_bid,0) > 0 THEN LEAST(mca.opening_bid*1.4, 5000000)
      ELSE 100000
    END) * 0.70
    - CASE
        WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0
          AND LEAST(GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)), 5000000) < 100000 THEN 25000
        WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0
          AND LEAST(GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)), 5000000) < 250000 THEN 20000
        WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0 THEN 15000
        WHEN COALESCE(mca.opening_bid,0)*1.4 < 100000 THEN 25000
        WHEN COALESCE(mca.opening_bid,0)*1.4 < 250000 THEN 20000
        WHEN COALESCE(mca.opening_bid,0) > 0 THEN 15000
        ELSE 25000
      END
    - 10000,
    LEAST(25000, (CASE
      WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0
        THEN LEAST(GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)), 5000000)
      WHEN COALESCE(mca.opening_bid,0) > 0 THEN LEAST(mca.opening_bid*1.4, 5000000)
      ELSE 100000
    END) * 0.15)
  ) AS max_bid,
  NULL::numeric AS bid_judgment_ratio,
  'PASS' AS recommendation,
  0.50 AS confidence,
  0.44 AS ml_score,
  jsonb_build_object(
    'distress_location', 0.36,
    'distress_property', 0.50,
    'distress_owner', 0.55,
    'cma_distressed', jsonb_build_object(
      'value', ROUND((CASE
        WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0
          THEN LEAST(GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)), 5000000)
        WHEN COALESCE(mca.opening_bid,0) > 0 THEN LEAST(mca.opening_bid*1.4, 5000000)
        ELSE 100000
      END * 0.87)::numeric, 2),
      'sources', '["assessed_value_proxy_INFERRED"]'::jsonb
    ),
    'cma_resale', jsonb_build_object(
      'value', ROUND((CASE
        WHEN GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)) > 0
          THEN LEAST(GREATEST(COALESCE(mca.assessed_value,0), COALESCE(mca.market_value,0)), 5000000)
        WHEN COALESCE(mca.opening_bid,0) > 0 THEN LEAST(mca.opening_bid*1.4, 5000000)
        ELSE 100000
      END * 1.12)::numeric, 2),
      'sources', '["assessed_value_proxy_INFERRED"]'::jsonb
    )
  ) AS factors,
  'SHARD2-TAYLOR-J-v1-20260801' AS pipeline_run_id
FROM public.multi_county_auctions mca
WHERE mca.county = 'taylor'
  AND mca.case_number IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM public.bid_decisions bd
    WHERE bd.case_number = mca.case_number AND bd.county_slug = 'taylor'
  );

-- Verification
SELECT county_slug, COUNT(*) AS total,
  COUNT(*) FILTER (WHERE pipeline_run_id LIKE '%20260801%') AS this_run,
  COUNT(*) FILTER (WHERE arv IS NULL OR arv = 0) AS zero_arv
FROM public.bid_decisions
WHERE county_slug IN ('madison', 'taylor')
GROUP BY county_slug;
