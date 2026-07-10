-- SHARD-11 (dispatch dd396ee4-e383-45ea-8953-5ad92fb1c1af), county=hardee
--
-- J (deal_complete) bid_decisions row for the single hardee auction, case
-- 25000327CAAXMX. Reuses the EXACT proven formula/factor-JSON structure from
-- supabase/migrations/20260619_shard11_j_generator.sql (shipped, live for
-- polk/manatee/pasco -- same shard, same session-family). Not a new design:
-- same Shapira v14.0 heuristic formula, same 5-key factors object, same
-- 'HYPOTHESIS' honesty_marker convention on every derived/inferred sub-field.
--
-- INPUTS NOW AVAILABLE (previously NULL, backfilled earlier in this session via
-- 20260710_gold_standard_shard11_hardee_e_parcel_geo_backfill.sql):
--   assessed_value = 361086 (FL GIO cadastral JV, CONFIRMED, cross-verified against
--     owner name match with the clerk foreclosure docket -- see that migration's
--     comment block for full sourcing)
--   parcel_id = 2534250000012900000
--   owner_name = 'SOTO JUSTIN'
--
-- HONEST LIMITATION: hardee has no gen_valuations_comps_batch / property_valuations
-- / valuations_comps table rows (checked live this session, tables do not exist /
-- are empty for this case). Per the accepted precedent in
-- 20260619_shard11_j_generator.sql, cma_distressed/cma_resale are therefore derived
-- from assessed_value (COALESCE(po_market_value, assessed_value*1.15, 200000)) and
-- explicitly tagged 'honesty_marker':'HYPOTHESIS' throughout factors -- NOT
-- presented as a verified independent CMA. This is the same standard already
-- shipped and accepted for polk/manatee/pasco/bay, not a lowered bar invented for
-- hardee.
--
-- Uses a plain INSERT (not ON CONFLICT (case_number) DO UPDATE like the source
-- migration) because bid_decisions has NO unique constraint on case_number
-- (confirmed live: only bid_decisions_pkey on id, and a non-unique btree index
-- idx_bid_decisions_case) -- an ON CONFLICT (case_number) clause would fail with
-- "there is no unique or exclusion constraint matching the ON CONFLICT
-- specification". Verified zero existing bid_decisions rows for case
-- 25000327CAAXMX before this insert, so no upsert semantics are needed.

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

    COALESCE(
        mca.po_market_value,
        NULLIF(mca.assessed_value, 0) * 1.15,
        200000
    )                                                                       AS arv,

    CASE
        WHEN mca.po_market_value IS NOT NULL            THEN 'po_market_value'
        WHEN mca.assessed_value  IS NOT NULL
          AND mca.assessed_value > 0                    THEN 'assessed_value_x1.15'
        ELSE 'default_200k'
    END                                                                     AS arv_source,

    25000                                                                   AS repairs,
    25000                                                                   AS repair_estimate,

    GREATEST(0,
        COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 200000) * 0.70
        - 25000
        - 10000
        - LEAST(25000,
            COALESCE(mca.po_market_value, NULLIF(mca.assessed_value,0)*1.15, 200000) * 0.15
          )
    )                                                                       AS max_bid,

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
        ELSE 0.45  -- default when no opening_bid (hardee: opening_bid_usd is NULL)
    END, 4)                                                                 AS ml_score,

    'v14.0_heuristic'                                                       AS pipeline_version,

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
WHERE mca.county = 'hardee'
  AND mca.case_number = '25000327CAAXMX'
  AND NOT EXISTS (
    SELECT 1 FROM bid_decisions bd WHERE bd.case_number = mca.case_number
  );
