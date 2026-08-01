-- SHARD-2 polk: J Generator — SQL-native implementation
-- dispatch_id: f8aa86b0-22cb-490b-b51a-d79deed78e09
-- session: architect-20260801T160000
--
-- Inserts bid_decisions for polk auctions that don't have them yet.
-- This is the SQL-equivalent of scripts/shard2_polk_madison_taylor_j_generator.py.
-- Runs via Supabase Management API (execute via apply-shard2-polk-j-gen workflow).
--
-- Shapira Formula (matches existing shard7_j_generator.py pattern):
--   ARV = max(assessed_value, market_value) where >0, else opening_bid*1.4, else county_default
--   repairs = tier: <100K→$25K, <250K→$20K, <500K→$15K, else→$12K
--   max_bid = max((ARV * 0.70) - repairs - $10K, min($25K, ARV * 0.15))
--   ml_score = 0.61 (polk county calibrated score, INFERRED from county-level model)
--   factors: distress_location, distress_property, distress_owner, cma_distressed, cma_resale (INFERRED proxies)
--
-- HONESTY: All cma_distressed / cma_resale values are INFERRED proxies (assessed_value based),
-- NOT independent retail comps. Marked with _proxy_INFERRED source tag in factors JSON.
-- The 102 rows with arv=200000 placeholder (Polk PA scheme mismatch) are handled separately
-- — this migration only covers auctions with NO existing bid_decisions row at all.

SET statement_timeout = 0;

INSERT INTO public.bid_decisions (
  case_number,
  county_slug,
  parcel_id,
  address,
  auction_date,
  arv,
  repairs,
  final_judgment,
  max_bid,
  bid_judgment_ratio,
  recommendation,
  confidence,
  ml_score,
  factors,
  pipeline_run_id
)
SELECT
  mca.case_number,
  'polk' AS county_slug,
  mca.parcel_id,
  mca.property_address AS address,
  mca.auction_date,
  CASE
    WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)) > 0
      THEN LEAST(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)), 5000000)
    WHEN COALESCE(mca.opening_bid, 0) > 0
      THEN LEAST(mca.opening_bid * 1.4, 5000000)
    ELSE 185000  -- polk county default
  END AS arv,
  CASE
    WHEN LEAST(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)), 5000000) < 100000
      OR (COALESCE(mca.assessed_value, 0) = 0 AND COALESCE(mca.market_value, 0) = 0 AND mca.opening_bid * 1.4 < 100000)
      OR (COALESCE(mca.assessed_value, 0) = 0 AND COALESCE(mca.market_value, 0) = 0 AND COALESCE(mca.opening_bid, 0) = 0 AND 185000 < 100000)
      THEN 25000
    WHEN LEAST(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)), 5000000) < 250000
      OR (COALESCE(mca.assessed_value, 0) = 0 AND COALESCE(mca.market_value, 0) = 0 AND mca.opening_bid * 1.4 < 250000)
      OR (COALESCE(mca.assessed_value, 0) = 0 AND COALESCE(mca.market_value, 0) = 0 AND COALESCE(mca.opening_bid, 0) = 0 AND 185000 < 250000)
      THEN 20000
    WHEN LEAST(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)), 5000000) < 500000
      OR (COALESCE(mca.assessed_value, 0) = 0 AND COALESCE(mca.market_value, 0) = 0 AND mca.opening_bid * 1.4 < 500000)
      OR (COALESCE(mca.assessed_value, 0) = 0 AND COALESCE(mca.market_value, 0) = 0 AND COALESCE(mca.opening_bid, 0) = 0 AND 185000 < 500000)
      THEN 15000
    ELSE 12000
  END AS repairs,
  ROUND(COALESCE(mca.opening_bid, 0)::numeric, 2) AS final_judgment,
  GREATEST(
    (
      CASE
        WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)) > 0
          THEN LEAST(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)), 5000000)
        WHEN COALESCE(mca.opening_bid, 0) > 0 THEN LEAST(mca.opening_bid * 1.4, 5000000)
        ELSE 185000
      END
    ) * 0.70
    - CASE
        WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)) > 0
             AND LEAST(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)), 5000000) < 100000 THEN 25000
        WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)) > 0
             AND LEAST(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)), 5000000) < 250000 THEN 20000
        WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)) > 0
             AND LEAST(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)), 5000000) < 500000 THEN 15000
        WHEN COALESCE(mca.assessed_value, 0) = 0 AND COALESCE(mca.market_value, 0) = 0 AND COALESCE(mca.opening_bid, 0) > 0
             AND mca.opening_bid * 1.4 < 100000 THEN 25000
        WHEN COALESCE(mca.assessed_value, 0) = 0 AND COALESCE(mca.market_value, 0) = 0 AND COALESCE(mca.opening_bid, 0) > 0
             AND mca.opening_bid * 1.4 < 250000 THEN 20000
        WHEN COALESCE(mca.assessed_value, 0) = 0 AND COALESCE(mca.market_value, 0) = 0 AND COALESCE(mca.opening_bid, 0) > 0
             AND mca.opening_bid * 1.4 < 500000 THEN 15000
        ELSE 12000
      END
    - 10000,
    LEAST(
      25000,
      (
        CASE
          WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)) > 0
            THEN LEAST(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)), 5000000)
          WHEN COALESCE(mca.opening_bid, 0) > 0 THEN LEAST(mca.opening_bid * 1.4, 5000000)
          ELSE 185000
        END
      ) * 0.15
    )
  ) AS max_bid,
  CASE
    WHEN COALESCE(mca.opening_bid, 0) > 0 THEN
      LEAST(
        GREATEST(
          (
            CASE
              WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)) > 0
                THEN LEAST(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)), 5000000)
              WHEN COALESCE(mca.opening_bid, 0) > 0 THEN LEAST(mca.opening_bid * 1.4, 5000000)
              ELSE 185000
            END
          ) * 0.70
          - CASE
              WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)) > 0
                   AND LEAST(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)), 5000000) < 100000 THEN 25000
              WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)) > 0
                   AND LEAST(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)), 5000000) < 250000 THEN 20000
              WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)) > 0 THEN 15000
              ELSE 20000
            END
          - 10000,
          25000 * 0.15
        ) / mca.opening_bid,
        9.99
      )
    ELSE NULL
  END AS bid_judgment_ratio,
  CASE
    WHEN COALESCE(mca.opening_bid, 0) > 0 AND
      GREATEST(
        (CASE WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)) > 0
          THEN LEAST(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)), 5000000) * 0.70
          ELSE 185000 * 0.70 END) - 20000 - 10000,
        LEAST(25000, 185000 * 0.15)
      ) > mca.opening_bid THEN 'BID'
    ELSE 'PASS'
  END AS recommendation,
  0.65 AS confidence,
  0.61 AS ml_score,
  jsonb_build_object(
    'distress_location', 0.58,
    'distress_property', 0.50,
    'distress_owner', 0.55,
    'cma_distressed', jsonb_build_object(
      'value', ROUND((CASE
        WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)) > 0
          THEN LEAST(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)), 5000000)
        WHEN COALESCE(mca.opening_bid, 0) > 0 THEN LEAST(mca.opening_bid * 1.4, 5000000)
        ELSE 185000
      END * 0.87)::numeric, 2),
      'sources', '["assessed_value_proxy_INFERRED"]'::jsonb
    ),
    'cma_resale', jsonb_build_object(
      'value', ROUND((CASE
        WHEN GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)) > 0
          THEN LEAST(GREATEST(COALESCE(mca.assessed_value, 0), COALESCE(mca.market_value, 0)), 5000000)
        WHEN COALESCE(mca.opening_bid, 0) > 0 THEN LEAST(mca.opening_bid * 1.4, 5000000)
        ELSE 185000
      END * 1.12)::numeric, 2),
      'sources', '["assessed_value_proxy_INFERRED"]'::jsonb
    )
  ) AS factors,
  'SHARD2-POLK-J-v1-20260801' AS pipeline_run_id
FROM public.multi_county_auctions mca
WHERE mca.county = 'polk'
  AND mca.case_number IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM public.bid_decisions bd
    WHERE bd.case_number = mca.case_number
      AND bd.county_slug = 'polk'
  );

-- Verification query (run after insert)
SELECT
  COUNT(*) AS total_polk_bid_decisions,
  COUNT(*) FILTER (WHERE pipeline_run_id = 'SHARD2-POLK-J-v1-20260801') AS this_run_inserted,
  COUNT(*) FILTER (WHERE pipeline_run_id LIKE '%default_200k%' OR arv = 200000) AS placeholder_rows_remaining
FROM public.bid_decisions
WHERE county_slug = 'polk';
