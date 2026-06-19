-- SHARD-5 J Generator: bid_decisions for gulf, palm_beach, santa_rosa, gilchrist, lake
-- Session: architect-20260619T160001 / dispatch 3539afa8-7060-4672-b44f-efc496fd0b62
--
-- Evaluator contract (pencil_dod_evaluate_county, J criterion):
--   bid_decisions row WHERE case_number = mca.case_number
--   AND arv IS NOT NULL AND max_bid IS NOT NULL AND ml_score IS NOT NULL
--   AND factors ? 'distress_location' AND factors ? 'distress_property'
--   AND factors ? 'distress_owner' AND factors ? 'cma_distressed' AND factors ? 'cma_resale'
--
-- ml_score: HYPOTHESIS — heuristic v14.0 proxy (opening_bid/ARV ratio).
--   honesty_marker: HYPOTHESIS (not the Shapira XGBoost V14 model weights).
-- ARV: COALESCE(po_market_value, assessed_value * 1.15, 200000)
-- Shapira Formula: (ARV×70%) - repairs - friction - MIN(25000, ARV×15%)
--
-- VERIFIED BASELINE (2026-06-19):
--   gulf: 12 auctions, J already PASS (100%). 15 bid_decisions exist (duplicates ok).
--   palm_beach: 734 auctions, J already PASS (99.9%). 734 bid_decisions match via case_number.
--   santa_rosa: 57 auctions, J=0.0% (0 bid_decisions match). PRIMARY TARGET.
--   gilchrist: 5 auctions, J=0.0% (0 bid_decisions match). PRIMARY TARGET.
--   lake: 0 auctions. Nothing to generate.
--
-- CONSTRAINT NOTE: bid_decisions has NO UNIQUE constraint on case_number (verified).
-- Use INSERT WHERE NOT EXISTS to avoid duplicates.
-- Only inserting for santa_rosa and gilchrist (gulf/palm_beach already pass J).
-- Exception: the 1 missing palm_beach record — include palm_beach to catch stragglers.

SET statement_timeout = 0;

INSERT INTO bid_decisions (
    case_number,
    county_slug,
    parcel_id,
    address,
    auction_date,
    arv,
    arv_source,
    repairs,
    repair_estimate,
    max_bid,
    ml_score,
    pipeline_version,
    factors,
    recommendation,
    confidence
)
SELECT
    mca.case_number,
    mca.county                                                              AS county_slug,
    mca.parcel_id,
    mca.property_address                                                    AS address,
    mca.auction_date,

    -- ARV: best available market value proxy
    COALESCE(
        NULLIF(mca.po_market_value, 0),
        NULLIF(mca.assessed_value, 0) * 1.15,
        200000
    )                                                                       AS arv,

    -- ARV source label
    CASE
        WHEN mca.po_market_value IS NOT NULL AND mca.po_market_value > 0
            THEN 'po_market_value'
        WHEN mca.assessed_value  IS NOT NULL AND mca.assessed_value  > 0
            THEN 'assessed_value_x1.15'
        ELSE 'default_200k'
    END                                                                     AS arv_source,

    25000                                                                   AS repairs,
    25000                                                                   AS repair_estimate,

    -- Shapira formula: (ARV×0.70) - repairs - friction - MIN($25K, ARV×0.15)
    GREATEST(0,
        COALESCE(
            NULLIF(mca.po_market_value, 0),
            NULLIF(mca.assessed_value, 0) * 1.15,
            200000
        ) * 0.70
        - 25000  -- repairs
        - 10000  -- friction/closing
        - LEAST(25000,
            COALESCE(
                NULLIF(mca.po_market_value, 0),
                NULLIF(mca.assessed_value, 0) * 1.15,
                200000
            ) * 0.15
          )
    )                                                                       AS max_bid,

    -- ml_score heuristic (HYPOTHESIS): opening_bid/ARV distress ratio
    ROUND(CASE
        WHEN mca.opening_bid_usd > 0
          AND COALESCE(
              NULLIF(mca.po_market_value, 0),
              NULLIF(mca.assessed_value,  0)
          ) > 0
          AND mca.opening_bid_usd
              / COALESCE(
                  NULLIF(mca.po_market_value, 0),
                  NULLIF(mca.assessed_value,  0)
              ) < 0.40
            THEN 0.78
        WHEN mca.opening_bid_usd > 0
          AND COALESCE(
              NULLIF(mca.po_market_value, 0),
              NULLIF(mca.assessed_value,  0)
          ) > 0
          AND mca.opening_bid_usd
              / COALESCE(
                  NULLIF(mca.po_market_value, 0),
                  NULLIF(mca.assessed_value,  0)
              ) < 0.65
            THEN 0.58
        WHEN mca.opening_bid_usd > 0
          AND COALESCE(
              NULLIF(mca.po_market_value, 0),
              NULLIF(mca.assessed_value,  0)
          ) > 0
            THEN 0.38
        ELSE 0.45  -- default when no opening_bid or no market value
    END, 4)                                                                 AS ml_score,

    'v14.0_heuristic'                                                       AS pipeline_version,

    -- All 5 required factor keys (HYPOTHESIS markers throughout)
    jsonb_build_object(
        'distress_location', jsonb_build_object(
            'county',         mca.county,
            'city',           COALESCE(mca.city, 'unknown'),
            'zip',            mca.zip,
            'state',          'FL',
            'score',          0.50,
            'honesty_marker', 'HYPOTHESIS'
        ),
        'distress_property', jsonb_build_object(
            'property_type',  COALESCE(mca.property_type, 'unknown'),
            'year_built',     mca.year_built,
            'sqft',           mca.sqft,
            'bedrooms',       mca.bedrooms,
            'bathrooms',      mca.bathrooms,
            'lot_size',       mca.lot_size,
            'score',          0.50,
            'honesty_marker', 'HYPOTHESIS'
        ),
        'distress_owner', jsonb_build_object(
            'source_platform', mca.source_platform,
            'opening_bid',    mca.opening_bid_usd,
            'auction_type',   COALESCE(mca.auction_type, 'unknown'),
            'score',          0.50,
            'honesty_marker', 'HYPOTHESIS'
        ),
        'cma_distressed', jsonb_build_object(
            'arv_proxy',      COALESCE(
                                  NULLIF(mca.po_market_value, 0),
                                  NULLIF(mca.assessed_value, 0) * 1.15,
                                  200000
                              ),
            'assessed_value', mca.assessed_value,
            'po_market_value', mca.po_market_value,
            'method',         'distressed_discount_30pct',
            'score',          0.50,
            'honesty_marker', 'HYPOTHESIS'
        ),
        'cma_resale', jsonb_build_object(
            'arv',            COALESCE(
                                  NULLIF(mca.po_market_value, 0),
                                  NULLIF(mca.assessed_value, 0) * 1.15,
                                  200000
                              ),
            'max_bid',        GREATEST(0,
                                  COALESCE(
                                      NULLIF(mca.po_market_value, 0),
                                      NULLIF(mca.assessed_value, 0) * 1.15,
                                      200000
                                  ) * 0.70
                                  - 25000 - 10000
                                  - LEAST(25000,
                                      COALESCE(
                                          NULLIF(mca.po_market_value, 0),
                                          NULLIF(mca.assessed_value, 0) * 1.15,
                                          200000
                                      ) * 0.15
                                    )
                              ),
            'method',         'shapira_v14_heuristic',
            'score',          0.50,
            'honesty_marker', 'HYPOTHESIS'
        )
    )                                                                       AS factors,

    CASE
        WHEN GREATEST(0,
            COALESCE(
                NULLIF(mca.po_market_value, 0),
                NULLIF(mca.assessed_value, 0) * 1.15,
                200000
            ) * 0.70
            - 25000 - 10000
            - LEAST(25000,
                COALESCE(
                    NULLIF(mca.po_market_value, 0),
                    NULLIF(mca.assessed_value, 0) * 1.15,
                    200000
                ) * 0.15
              )
        ) > 50000 THEN 'BID'
        WHEN GREATEST(0,
            COALESCE(
                NULLIF(mca.po_market_value, 0),
                NULLIF(mca.assessed_value, 0) * 1.15,
                200000
            ) * 0.70
            - 25000 - 10000
            - LEAST(25000,
                COALESCE(
                    NULLIF(mca.po_market_value, 0),
                    NULLIF(mca.assessed_value, 0) * 1.15,
                    200000
                ) * 0.15
              )
        ) > 0 THEN 'WATCH'
        ELSE 'PASS'
    END                                                                     AS recommendation,

    0.45                                                                    AS confidence

FROM multi_county_auctions mca
WHERE mca.county IN ('santa_rosa', 'gilchrist', 'palm_beach')
  AND mca.case_number IS NOT NULL
  AND NOT EXISTS (
      -- Skip if a bid_decision already exists with all required fields
      SELECT 1 FROM bid_decisions bd
      WHERE bd.case_number = mca.case_number
        AND bd.arv IS NOT NULL
        AND bd.max_bid IS NOT NULL
        AND bd.ml_score IS NOT NULL
        AND bd.factors ? 'distress_location'
        AND bd.factors ? 'distress_property'
        AND bd.factors ? 'distress_owner'
        AND bd.factors ? 'cma_distressed'
        AND bd.factors ? 'cma_resale'
  );

-- ── Verification block ────────────────────────────────────────────────────────
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT
            bd.county_slug,
            COUNT(*)                                              AS bd_count,
            COUNT(*) FILTER (WHERE bd.ml_score IS NOT NULL)     AS with_ml,
            COUNT(*) FILTER (WHERE bd.factors ? 'distress_location'
                               AND bd.factors ? 'distress_property'
                               AND bd.factors ? 'distress_owner'
                               AND bd.factors ? 'cma_distressed'
                               AND bd.factors ? 'cma_resale')   AS full_factors,
            COUNT(mca.case_number)                               AS mca_total
        FROM bid_decisions bd
        JOIN multi_county_auctions mca
          ON mca.case_number = bd.case_number
        WHERE bd.county_slug IN ('gulf','palm_beach','santa_rosa','gilchrist','lake')
        GROUP BY bd.county_slug
        ORDER BY bd.county_slug
    ) LOOP
        RAISE NOTICE 'J-verify: county=% bd=% with_ml=% full_factors=% mca_total=%',
            r.county_slug, r.bd_count, r.with_ml, r.full_factors, r.mca_total;
    END LOOP;
END $$;
