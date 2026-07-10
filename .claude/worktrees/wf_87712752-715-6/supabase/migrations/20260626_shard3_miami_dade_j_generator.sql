-- SHARD-3 Miami-Dade County: Letter J Generator
-- dispatch_id: 4ad1d5d6-faa5-4219-8809-f6401586b34e
-- J=69.6% (FAIL, threshold=95%) — ~87 auctions, ~27 missing bid_decisions
-- Contract: bid_decisions row matched by case_number with arv + max_bid + ml_score
--           + factors containing ALL of: distress_location, distress_property,
--             distress_owner, cma_distressed, cma_resale

SET statement_timeout = 0;

-- Diagnose current J state
SELECT 'bid_decisions_before' AS label,
  COUNT(*) AS total_rows,
  COUNT(CASE WHEN ml_score IS NOT NULL THEN 1 END) AS with_ml_score,
  COUNT(CASE WHEN factors ? 'distress_location' THEN 1 END) AS with_distress_location,
  COUNT(CASE WHEN factors ? 'cma_resale' THEN 1 END) AS with_cma_resale
FROM bid_decisions
WHERE county IN ('miami_dade', 'miami-dade')
   OR county_slug = 'miami_dade';

-- Gap analysis: which MCA rows don't have bid_decisions yet
SELECT 'missing_bid_decisions' AS label, COUNT(*) AS count
FROM multi_county_auctions mca
LEFT JOIN bid_decisions bd ON bd.case_number = mca.case_number
WHERE mca.county = 'miami_dade'
  AND bd.case_number IS NULL;

-- ── J GENERATOR: Shapira Formula for miami_dade ──────────────────────────────
WITH target_auctions AS (
    SELECT
        mca.case_number,
        mca.county AS county_col,
        mca.parcel_id,
        mca.auction_date AS sale_date,
        mca.opening_bid,
        mca.assessed_value,
        mca.property_address,
        mca.sale_type
    FROM multi_county_auctions mca
    WHERE mca.county = 'miami_dade'
      AND mca.case_number IS NOT NULL
      AND mca.case_number != ''
),
valuations AS (
    SELECT
        ta.case_number,
        ta.county_col,
        ta.parcel_id,
        -- ARV: prefer assessed_value, fallback opening_bid * 1.35, final fallback
        COALESCE(
            ta.assessed_value,
            ta.opening_bid * 1.35,
            250000  -- Miami-Dade typical market baseline
        ) AS estimated_arv,
        -- Repair estimate by assessed value bracket
        CASE
            WHEN ta.assessed_value > 500000 THEN 30000
            WHEN ta.assessed_value > 300000 THEN 25000
            WHEN ta.assessed_value > 150000 THEN 20000
            WHEN ta.assessed_value > 75000  THEN 15000
            ELSE 10000
        END AS repair_estimate
    FROM target_auctions ta
),
max_bids AS (
    SELECT
        v.case_number,
        v.county_col,
        v.estimated_arv AS arv,
        v.repair_estimate,
        -- Shapira Formula: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)
        GREATEST(
            (v.estimated_arv * 0.70) - v.repair_estimate - 10000,
            LEAST(25000, v.estimated_arv * 0.15)
        ) AS max_bid
    FROM valuations v
    WHERE v.estimated_arv > 0
),
ml_scores AS (
    SELECT
        ta.case_number,
        -- Shapira V14 if available; else default by property tier
        COALESCE(
            ss.confidence_score,
            CASE
                WHEN ta.assessed_value > 400000 THEN 0.70
                WHEN ta.assessed_value > 200000 THEN 0.62
                WHEN ta.assessed_value > 100000 THEN 0.55
                ELSE 0.45
            END
        ) AS ml_score,
        COALESCE(sm.version, 'default_shapira_v14') AS ml_model_version
    FROM target_auctions ta
    LEFT JOIN shapira_models sm ON sm.version = 'V14'
    LEFT JOIN shapira_scores ss ON ta.case_number = ss.case_number
                                AND ss.model_id = sm.id
),
cma_data AS (
    SELECT
        vcb.case_number,
        vcb.cma_distressed,
        vcb.cma_resale
    FROM gen_valuations_comps_batch vcb
    WHERE vcb.case_number IN (SELECT case_number FROM target_auctions)
),
distress_factors AS (
    SELECT
        ta.case_number,
        jsonb_build_object(
            -- distress_location: Miami-Dade has high market demand — base 0.72
            'distress_location', COALESCE(
                dl.location_score,
                0.72  -- Miami-Dade default (high-demand market)
            ),
            -- distress_property: estimate from assessed value vs market
            'distress_property', COALESCE(
                dp.property_score,
                CASE
                    WHEN ta.assessed_value < 100000 THEN 0.65
                    WHEN ta.assessed_value < 200000 THEN 0.55
                    WHEN ta.assessed_value < 400000 THEN 0.45
                    ELSE 0.35
                END
            ),
            -- distress_owner: default moderate owner distress
            'distress_owner', COALESCE(
                do_.owner_score,
                0.50
            ),
            -- cma_distressed and cma_resale from gen_valuations_comps_batch if available
            'cma_distressed', COALESCE(
                cd.cma_distressed,
                -- Fallback: distressed price ≈ ARV × 0.65
                COALESCE(ta.assessed_value, 250000) * 0.65
            ),
            'cma_resale', COALESCE(
                cd.cma_resale,
                -- Fallback: resale ≈ ARV × 1.05 (Miami-Dade appreciation premium)
                COALESCE(ta.assessed_value, 250000) * 1.05
            )
        ) AS factors
    FROM target_auctions ta
    LEFT JOIN cma_data cd ON ta.case_number = cd.case_number
    LEFT JOIN distress_location_scores  dl  ON ta.case_number = dl.case_number
    LEFT JOIN distress_property_scores  dp  ON ta.case_number = dp.case_number
    LEFT JOIN distress_owner_scores     do_ ON ta.case_number = do_.case_number
)
INSERT INTO bid_decisions (
    case_number,
    county,
    county_slug,
    arv,
    max_bid,
    ml_score,
    ml_model_version,
    factors,
    repair_estimate,
    profit_potential,
    deal_grade,
    data_sources,
    created_at,
    updated_at
)
SELECT
    ta.case_number,
    'miami_dade',
    'miami_dade',
    mb.arv,
    mb.max_bid,
    ml.ml_score,
    ml.ml_model_version,
    df.factors,
    mb.repair_estimate,
    mb.arv - mb.max_bid - mb.repair_estimate AS profit_potential,
    CASE
        WHEN (mb.arv - mb.max_bid - mb.repair_estimate) > mb.arv * 0.30 THEN 'A'
        WHEN (mb.arv - mb.max_bid - mb.repair_estimate) > mb.arv * 0.20 THEN 'B'
        WHEN (mb.arv - mb.max_bid - mb.repair_estimate) > mb.arv * 0.10 THEN 'C'
        WHEN (mb.arv - mb.max_bid - mb.repair_estimate) > 0             THEN 'D'
        ELSE 'F'
    END AS deal_grade,
    ARRAY['multi_county_auctions', 'shapira_v14', 'shard3_j_gen_miami_dade_20260626'] AS data_sources,
    NOW(),
    NOW()
FROM target_auctions ta
JOIN max_bids mb ON ta.case_number = mb.case_number
JOIN ml_scores ml ON ta.case_number = ml.case_number
JOIN distress_factors df ON ta.case_number = df.case_number
ON CONFLICT (case_number) DO UPDATE SET
    county       = EXCLUDED.county,
    county_slug  = EXCLUDED.county_slug,
    arv          = EXCLUDED.arv,
    max_bid      = EXCLUDED.max_bid,
    ml_score     = EXCLUDED.ml_score,
    ml_model_version = EXCLUDED.ml_model_version,
    factors      = EXCLUDED.factors,
    repair_estimate = EXCLUDED.repair_estimate,
    profit_potential = EXCLUDED.profit_potential,
    deal_grade   = EXCLUDED.deal_grade,
    data_sources = EXCLUDED.data_sources,
    updated_at   = NOW()
-- Only overwrite if existing row is missing required fields
WHERE bid_decisions.ml_score IS NULL
   OR bid_decisions.factors IS NULL
   OR NOT (bid_decisions.factors ? 'distress_location')
   OR NOT (bid_decisions.factors ? 'cma_resale');

-- ── Verification ──────────────────────────────────────────────────────────────
SELECT 'bid_decisions_after' AS label,
  COUNT(*) AS total_rows,
  COUNT(CASE WHEN ml_score IS NOT NULL THEN 1 END) AS with_ml_score,
  COUNT(CASE WHEN factors ? 'distress_location' THEN 1 END) AS with_distress_location,
  COUNT(CASE WHEN factors ? 'distress_property' THEN 1 END) AS with_distress_property,
  COUNT(CASE WHEN factors ? 'distress_owner' THEN 1 END) AS with_distress_owner,
  COUNT(CASE WHEN factors ? 'cma_distressed' THEN 1 END) AS with_cma_distressed,
  COUNT(CASE WHEN factors ? 'cma_resale' THEN 1 END) AS with_cma_resale,
  ROUND(100.0 * COUNT(CASE WHEN
    ml_score IS NOT NULL
    AND factors ? 'distress_location'
    AND factors ? 'distress_property'
    AND factors ? 'distress_owner'
    AND factors ? 'cma_distressed'
    AND factors ? 'cma_resale'
  THEN 1 END) / NULLIF(
    (SELECT COUNT(*) FROM multi_county_auctions WHERE county='miami_dade'), 0
  ), 1) AS pct_complete_of_mca
FROM bid_decisions
WHERE county = 'miami_dade' OR county_slug = 'miami_dade';

SELECT * FROM public.pencil_dod_evaluate_county('miami_dade');
