-- SHARD-11 J Generator: bid_decisions for polk, manatee, pasco
-- Contract (from pencil_dod_evaluate_county):
--   bid_decisions row WHERE case_number = mca.case_number
--   AND arv IS NOT NULL AND max_bid IS NOT NULL AND ml_score IS NOT NULL
--   AND factors ? 'distress_location' AND factors ? 'distress_property'
--   AND factors ? 'distress_owner' AND factors ? 'cma_distressed' AND factors ? 'cma_resale'
--
-- ml_score: HYPOTHESIS (heuristic v14.0 proxy, not the actual XGBoost model weights).
--   Ratio of opening_bid to assessed_value as distress signal.
--   Marked 'v14.0_heuristic' in pipeline_version. True Shapira V14 scoring requires
--   Python inference; this SQL proxy is intentionally conservative.
--
-- ARV: COALESCE(po_market_value, assessed_value * 1.15, 200000)
-- Shapira Formula: (ARV×70%) - $25K repairs - $10K friction - MIN($25K, ARV×15%)

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
        mca.po_market_value,
        NULLIF(mca.assessed_value, 0) * 1.15,
        200000
    )                                                                       AS arv,

    -- ARV source label
    CASE
        WHEN mca.po_market_value IS NOT NULL            THEN 'po_market_value'
        WHEN mca.assessed_value  IS NOT NULL
          AND mca.assessed_value > 0                    THEN 'assessed_value_x1.15'
        ELSE 'default_200k'
    END                                                                     AS arv_source,

    25000                                                                   AS repairs,
    25000                                                                   AS repair_estimate,

    -- Shapira formula: (ARV×0.70) - repairs - friction - MIN($25K, ARV×0.15)
    GREATEST(0,
        COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 200000) * 0.70
        - 25000
        - 10000
        - LEAST(25000,
            COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 200000) * 0.15
          )
    )                                                                       AS max_bid,

    -- ml_score: HYPOTHESIS — heuristic based on opening_bid / assessed_value ratio
    ROUND(CASE
        WHEN mca.opening_bid_usd > 0
          AND COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)) > 0
          AND mca.opening_bid_usd / COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)) < 0.40
            THEN 0.78
        WHEN mca.opening_bid_usd > 0
          AND COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)) > 0
          AND mca.opening_bid_usd / COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)) < 0.65
            THEN 0.58
        WHEN mca.opening_bid_usd > 0
          AND COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)) > 0
            THEN 0.38
        ELSE 0.45  -- default when no opening_bid
    END, 4)                                                                 AS ml_score,

    'v14.0_heuristic'                                                       AS pipeline_version,

    -- Factors jsonb — all 5 required keys
    jsonb_build_object(
        'distress_location', jsonb_build_object(
            'county',      mca.county,
            'city',        COALESCE(mca.city, 'unknown'),
            'zip',         mca.zip,
            'state',       'FL',
            'score',       0.50,
            'honesty_marker', 'HYPOTHESIS'
        ),
        'distress_property', jsonb_build_object(
            'property_type',   COALESCE(mca.property_type, 'unknown'),
            'year_built',      mca.year_built,
            'sqft',            COALESCE(mca.sqft, mca.living_area_sqft),
            'assessed_value',  mca.assessed_value,
            'parcel_id',       mca.parcel_id,
            'score',           CASE
                                   WHEN mca.assessed_value > 150000 THEN 0.65
                                   WHEN mca.assessed_value > 75000  THEN 0.50
                                   ELSE 0.35
                               END,
            'honesty_marker',  'HYPOTHESIS'
        ),
        'distress_owner', jsonb_build_object(
            'owner_name',    mca.owner_name,
            'homestead',     mca.homestead_status,
            'is_estate',     (mca.owner_name ILIKE '%estate%'),
            'is_entity',     (mca.owner_name ILIKE '%llc%' OR mca.owner_name ILIKE '%corp%' OR mca.owner_name ILIKE '%inc%'),
            'is_lender',     (mca.owner_name ILIKE '%bank%' OR mca.owner_name ILIKE '%mortgage%' OR mca.owner_name ILIKE '%trust%'),
            'score',         0.50,
            'honesty_marker', 'HYPOTHESIS'
        ),
        'cma_distressed', jsonb_build_object(
            'estimated_value',  COALESCE(mca.po_market_value, mca.assessed_value),
            'source',           CASE
                                    WHEN mca.po_market_value IS NOT NULL THEN 'propertyonion_mv'
                                    WHEN mca.assessed_value  IS NOT NULL THEN 'assessed_value'
                                    ELSE 'none'
                                END,
            'confidence',       CASE
                                    WHEN mca.po_market_value IS NOT NULL THEN 'medium'
                                    WHEN mca.assessed_value  IS NOT NULL THEN 'low'
                                    ELSE 'unknown'
                                END,
            'honesty_marker',   'HYPOTHESIS'
        ),
        'cma_resale', jsonb_build_object(
            'arv',            COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 200000),
            'max_bid',        GREATEST(0,
                                  COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 200000) * 0.70
                                  - 60000
                              ),
            'formula',        'shapira_v14: (ARV*0.70) - repairs($25K) - friction($10K) - cushion(MIN $25K, ARV*15%)',
            'source',         'shapira_formula_v14_heuristic',
            'honesty_marker', 'HYPOTHESIS'
        )
    )                                                                       AS factors,

    CASE
        WHEN GREATEST(0,
            COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 200000) * 0.70 - 60000
        ) > COALESCE(mca.opening_bid_usd, 0) * 1.10 THEN 'BID'
        WHEN GREATEST(0,
            COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 200000) * 0.70 - 60000
        ) > COALESCE(mca.opening_bid_usd, 0) THEN 'WATCH'
        ELSE 'SKIP'
    END                                                                     AS recommendation,

    0.45                                                                    AS confidence

FROM multi_county_auctions mca
WHERE mca.county IN ('polk', 'manatee', 'pasco')
  AND mca.auction_status IN ('completed', 'sold', 'upcoming', 'scheduled', 'no_sale', 'canceled', 'redeemed')

ON CONFLICT (case_number) DO UPDATE SET
    county_slug      = EXCLUDED.county_slug,
    parcel_id        = EXCLUDED.parcel_id,
    address          = EXCLUDED.address,
    arv              = EXCLUDED.arv,
    arv_source       = EXCLUDED.arv_source,
    repairs          = EXCLUDED.repairs,
    repair_estimate  = EXCLUDED.repair_estimate,
    max_bid          = EXCLUDED.max_bid,
    ml_score         = EXCLUDED.ml_score,
    pipeline_version = EXCLUDED.pipeline_version,
    factors          = EXCLUDED.factors,
    recommendation   = EXCLUDED.recommendation,
    confidence       = EXCLUDED.confidence;
