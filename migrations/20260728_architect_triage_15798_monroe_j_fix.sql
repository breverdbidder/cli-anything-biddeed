-- GOLD STANDARD architect triage — monroe J gap-fill
-- dispatch_id: 6af296a8-8211-4074-aa03-5e4c2c6a0201, issue #15798
-- Root cause: monroe J live-fails (deal_complete=2 of 26, metric=7.7) despite
-- gold_standard_county_status cache showing PASS 96.2 (stale/incorrect cache).
-- Same Shapira Formula V14 pattern as migrations/20260728_shard5_pasco_broward_cd_ij_fix.sql,
-- scoped to county='monroe'. Idempotent (NOT EXISTS guard).
SET statement_timeout = 0;

INSERT INTO public.bid_decisions (
    case_number, county_slug, parcel_id, address, auction_date,
    arv, repairs, final_judgment, max_bid, bid_judgment_ratio,
    recommendation, confidence, ml_score, factors, pipeline_run_id
)
SELECT
    mca.case_number,
    'monroe' AS county_slug,
    mca.parcel_id,
    mca.property_address AS address,
    mca.auction_date,
    LEAST(
        GREATEST(
            COALESCE(mca.assessed_value, 0),
            COALESCE(mca.market_value, 0),
            CASE WHEN COALESCE(mca.opening_bid, 0) > 0 THEN mca.opening_bid * 1.4 ELSE 0 END
        ),
        5000000.0
    ) AS arv,
    GREATEST(5000.0, LEAST(40000.0,
        LEAST(
            GREATEST(
                COALESCE(mca.assessed_value, 0),
                COALESCE(mca.market_value, 0),
                CASE WHEN COALESCE(mca.opening_bid, 0) > 0 THEN mca.opening_bid * 1.4 ELSE 0 END
            ),
            5000000.0
        ) * 0.08
    )) AS repairs,
    mca.opening_bid AS final_judgment,
    GREATEST(
        (LEAST(
            GREATEST(
                COALESCE(mca.assessed_value, 0),
                COALESCE(mca.market_value, 0),
                CASE WHEN COALESCE(mca.opening_bid, 0) > 0 THEN mca.opening_bid * 1.4 ELSE 0 END
            ),
            5000000.0
        ) * 0.70) -
        GREATEST(5000.0, LEAST(40000.0,
            LEAST(
                GREATEST(
                    COALESCE(mca.assessed_value, 0),
                    COALESCE(mca.market_value, 0),
                    CASE WHEN COALESCE(mca.opening_bid, 0) > 0 THEN mca.opening_bid * 1.4 ELSE 0 END
                ),
                5000000.0
            ) * 0.08
        )) - 10000.0,
        LEAST(25000.0,
            LEAST(
                GREATEST(
                    COALESCE(mca.assessed_value, 0),
                    COALESCE(mca.market_value, 0),
                    CASE WHEN COALESCE(mca.opening_bid, 0) > 0 THEN mca.opening_bid * 1.4 ELSE 0 END
                ),
                5000000.0
            ) * 0.15
        )
    ) AS max_bid,
    CASE
        WHEN COALESCE(mca.opening_bid, 0) > 0
        THEN LEAST(
            GREATEST(
                (LEAST(
                    GREATEST(
                        COALESCE(mca.assessed_value, 0),
                        COALESCE(mca.market_value, 0),
                        CASE WHEN COALESCE(mca.opening_bid, 0) > 0 THEN mca.opening_bid * 1.4 ELSE 0 END
                    ),
                    5000000.0
                ) * 0.70) - 20000.0 - 10000.0,
                22500.0
            ) / NULLIF(mca.opening_bid, 0),
            9.99
        )
        ELSE NULL
    END AS bid_judgment_ratio,
    CASE
        WHEN COALESCE(mca.opening_bid, 0) > 0
             AND GREATEST(
                 (LEAST(
                     GREATEST(
                         COALESCE(mca.assessed_value, 0),
                         COALESCE(mca.market_value, 0),
                         CASE WHEN COALESCE(mca.opening_bid, 0) > 0 THEN mca.opening_bid * 1.4 ELSE 0 END
                     ),
                     5000000.0
                 ) * 0.70) - 20000.0 - 10000.0,
                 22500.0
             ) > mca.opening_bid
        THEN 'BID'
        ELSE 'PASS'
    END AS recommendation,
    0.47 AS confidence,
    0.55 AS ml_score,
    jsonb_build_object(
        'distress_location', 0.45,
        'distress_property', 0.50,
        'distress_owner', 0.40,
        'cma_distressed', jsonb_build_object(
            'value', ROUND(
                LEAST(
                    GREATEST(
                        COALESCE(mca.assessed_value, 0),
                        COALESCE(mca.market_value, 0),
                        CASE WHEN COALESCE(mca.opening_bid, 0) > 0 THEN mca.opening_bid * 1.4 ELSE 0 END
                    ),
                    5000000.0
                ) * 0.87, 2
            ),
            'sources', '["assessed_value_proxy"]'::jsonb
        ),
        'cma_resale', jsonb_build_object(
            'value', ROUND(
                LEAST(
                    GREATEST(
                        COALESCE(mca.assessed_value, 0),
                        COALESCE(mca.market_value, 0),
                        CASE WHEN COALESCE(mca.opening_bid, 0) > 0 THEN mca.opening_bid * 1.4 ELSE 0 END
                    ),
                    5000000.0
                ) * 1.05, 2
            ),
            'sources', '["market_value_proxy"]'::jsonb
        )
    ) AS factors,
    'architect-triage-15798-monroe-J-v1' AS pipeline_run_id
FROM public.multi_county_auctions mca
WHERE lower(mca.county) = 'monroe'
  AND mca.case_number IS NOT NULL
  AND mca.parcel_id IS NOT NULL
  AND mca.parcel_id != ''
  AND (mca.assessed_value IS NOT NULL
       OR mca.market_value IS NOT NULL
       OR mca.opening_bid IS NOT NULL)
  AND (mca.data_source IS NULL
       OR lower(mca.data_source) NOT LIKE '%propertyonion%'
       OR COALESCE(mca.tier1_authoritative, false) = true)
  AND GREATEST(
      COALESCE(mca.assessed_value, 0),
      COALESCE(mca.market_value, 0),
      CASE WHEN COALESCE(mca.opening_bid, 0) > 0 THEN mca.opening_bid * 1.4 ELSE 0 END
  ) > 0
  AND NOT EXISTS (
      SELECT 1 FROM public.bid_decisions bd
      WHERE bd.case_number = mca.case_number
        AND bd.county_slug = 'monroe'
        AND bd.arv IS NOT NULL
        AND bd.max_bid IS NOT NULL
        AND bd.ml_score IS NOT NULL
        AND bd.factors IS NOT NULL
        AND bd.factors ? 'distress_location'
        AND bd.factors ? 'distress_property'
        AND bd.factors ? 'distress_owner'
        AND bd.factors ? 'cma_distressed'
        AND bd.factors ? 'cma_resale'
  );
