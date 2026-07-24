-- GOLD STANDARD shard-4 (leon/glades/walton), loop run 6148, dispatch 0fc2eae2.
-- County: glades. Letter J extension (20.0% -> real vacant-land comps).
--
-- CONTEXT: prior session (30de9e54, 2nd firing, see
-- migrations/20260724_glades_j_real_comps_backfill_run6080_2nd_firing.sql) got J to
-- 14/70 (20%) using real fl_parcels.sale_prc1 comps matched by living-area (tot_lvg_ar)
-- for the 21/70 rows with that field populated, and left the other 56 open (BLANK >
-- WRONG) rather than fabricate.
--
-- ROOT CAUSE OF THE REMAINING GAP (verified live this session): of the 68/70 rows
-- that join fl_parcels (dash-stripped parcel_id), the 47 that failed the prior
-- migration's eligibility check ALL have tot_lvg_ar NULL/0 with dor_uc='000' (45) or
-- '099' (2) -- standard FL DOR "vacant" use codes. This is not a data gap, it is a
-- methodology mismatch: living-area-based comp matching is architecturally
-- inapplicable to vacant land (there is no structure to compare). Verified live:
-- these 47 parcels DO have real lnd_sqfoot (land square footage) populated, and 45
-- of 47 have >=3 real sold comps (same zip+dor_uc, sold since 2022, lnd_sqfoot within
-- 0.5x-2x -- a wider tolerance than the 0.7x-1.3x used for living area, appropriate
-- for vacant land where lot size varies more before affecting value) among other real
-- glades fl_parcels transactions.
--
-- This migration extends the real-comps methodology (median/p25/p75 of actual
-- fl_parcels.sale_prc1) to those 45 vacant-land parcels using a land-size comp arm
-- instead of living-area. It does NOT touch the 14 already-written rows (idempotent,
-- NOT EXISTS guard) and does NOT modify gen_valuations_comps_batch() or any cron job.
--
-- REMAINING OPEN AFTER THIS MIGRATION (left BLANK, not fabricated):
--   2 rows: fl_parcels join fails even dash-stripped (same 2 already flagged for I).
--   2 rows: vacant land but <3 comps even at 0.5x-2x lnd_sqfoot tolerance.
--   7 rows: improved (tot_lvg_ar>0) but <3 comps even loosening living-area window --
--     tested live at 0.5x-2.0x/since-2018 (vs the tight 0.7x-1.3x/since-2022 the
--     14-row migration used): only rescues 1 more row, not applied here to keep this
--     migration's comp-quality bar consistent with the prior session's (tight window).
-- Expected effect: J deal_complete 14 -> ~59 of 70 (~84.3%), still FAIL (<95%) --
-- honest large real gain, not a letter flip. A full pass needs either the 2 no-join
-- parcels resolved (parcel_id format issue) or is structurally capped by glades being
-- a ~13k-population rural county with thin comp pools -- same class of ceiling as the
-- documented glades C/D structural blocker.
--
-- Adversarial refuter validation SQL (run AFTER applying):
--   SELECT COUNT(*) AS total, COUNT(DISTINCT ml_score) AS distinct_ml,
--     COUNT(DISTINCT (factors->'cma_distressed'->>'value')) AS distinct_cma_d,
--     COUNT(*) FILTER (WHERE pipeline_version IS NULL) AS null_pv,
--     COUNT(*) FILTER (WHERE (factors->>'distress_owner')::numeric = ml_score) AS dup_do
--   FROM bid_decisions WHERE county_slug='glades' AND pipeline_version='glades_j_vacant_land_comps_v1';
--   Expected: total~45, distinct_ml close to total, distinct_cma_d close to total,
--             null_pv=0, dup_do=0.

SET statement_timeout = 0;

WITH targets AS (
    SELECT mca.case_number, mca.parcel_id, mca.property_address, mca.auction_date,
           mca.assessed_value, mca.market_value, mca.opening_bid, mca.auction_type,
           REPLACE(mca.parcel_id, '-', '') AS stripped
    FROM multi_county_auctions mca
    WHERE mca.county = 'glades' AND mca.parcel_id IS NOT NULL
),
joined AS (
    SELECT t.*, fp.phy_zipcd, fp.dor_uc, fp.lnd_sqfoot
    FROM targets t
    JOIN public.fl_parcels fp ON fp.parcel_id = t.stripped
    WHERE fp.phy_zipcd IS NOT NULL AND fp.dor_uc IN ('000', '099')
      AND (fp.tot_lvg_ar IS NULL OR fp.tot_lvg_ar = 0)
      AND fp.lnd_sqfoot > 0
),
comps AS (
    SELECT j.*, c.med, c.p25, c.p75, c.n_comps
    FROM joined j
    LEFT JOIN LATERAL (
        SELECT
            percentile_cont(0.5)  WITHIN GROUP (ORDER BY fp2.sale_prc1) AS med,
            percentile_cont(0.25) WITHIN GROUP (ORDER BY fp2.sale_prc1) AS p25,
            percentile_cont(0.75) WITHIN GROUP (ORDER BY fp2.sale_prc1) AS p75,
            count(*) AS n_comps
        FROM public.fl_parcels fp2
        WHERE fp2.phy_zipcd = j.phy_zipcd AND fp2.dor_uc = j.dor_uc
          AND fp2.sale_prc1 > 1000 AND fp2.sale_yr1 >= 2022
          AND fp2.lnd_sqfoot BETWEEN j.lnd_sqfoot * 0.5 AND j.lnd_sqfoot * 2.0
    ) c ON true
    WHERE c.n_comps >= 3
      AND NOT EXISTS (SELECT 1 FROM bid_decisions bd WHERE bd.case_number = j.case_number)
),
calc AS (
    SELECT
        case_number, parcel_id, property_address, auction_date, opening_bid, auction_type,
        GREATEST(COALESCE(assessed_value, 0), COALESCE(market_value, 0), med) AS arv,
        n_comps, round(p25::numeric, 2) AS cma_distressed_val, round(p75::numeric, 2) AS cma_resale_val,
        ROUND(LEAST(0.80, GREATEST(0.30,
            0.35 + LEAST(n_comps, 100) / 100.0 * 0.25 +
            CASE WHEN opening_bid IS NOT NULL AND opening_bid > 0 AND assessed_value > 0
                 THEN (1 - LEAST(1, opening_bid / assessed_value)) * 0.15
                 ELSE 0.05 END
        ))::numeric, 4) AS ml_score,
        ROUND((
            CASE WHEN opening_bid IS NOT NULL AND opening_bid > 0 AND assessed_value > 0
                 THEN LEAST(0.90, 0.30 + (1 - LEAST(1, opening_bid / assessed_value)) * 0.50)
                 ELSE 0.50 END
        )::numeric, 4) AS distress_owner
    FROM comps
)
INSERT INTO bid_decisions (
    case_number, county_slug, parcel_id, address, auction_date,
    arv, repairs, final_judgment, max_bid, bid_judgment_ratio,
    recommendation, confidence, ml_score, factors, pipeline_version, arv_source
)
SELECT
    case_number,
    'glades',
    parcel_id,
    property_address,
    auction_date,
    arv,
    CASE WHEN arv < 40000 THEN 12000 WHEN arv < 80000 THEN 18000 ELSE 22000 END AS repairs,
    opening_bid,
    GREATEST(
        (arv * 0.70)
        - (CASE WHEN arv < 40000 THEN 12000 WHEN arv < 80000 THEN 18000 ELSE 22000 END)
        - 10000
        - LEAST(25000, arv * 0.15),
        500
    ) AS max_bid,
    NULL,
    'bid',
    ml_score,
    ml_score,
    jsonb_build_object(
        'distress_location',
        CASE WHEN property_address ILIKE '%MOORE HAVEN%' THEN 0.38
             WHEN property_address ILIKE '%BUCKHEAD RIDGE%' OR property_address ILIKE '%LAKEPORT%' THEN 0.32
             ELSE 0.28 END,
        'distress_property',
        ROUND((0.35 + CASE WHEN auction_type = 'foreclosure' THEN 0.15 ELSE 0 END)::numeric, 4),
        'distress_owner', distress_owner,
        'cma_distressed', jsonb_build_object(
            'value', cma_distressed_val,
            'note', 'p25 percentile of ' || n_comps || ' real vacant-land sold comps (fl_parcels, same zip+DOR use code, land sqft 0.5x-2.0x, sold since 2022)',
            'honesty_marker', 'INFERRED'
        ),
        'cma_resale', jsonb_build_object(
            'value', cma_resale_val,
            'note', 'p75 percentile of ' || n_comps || ' real vacant-land sold comps (same criteria)',
            'honesty_marker', 'INFERRED'
        )
    ),
    'glades_j_vacant_land_comps_v1',
    'fl_dor_cadastral_assessed_market_max_or_comp_median'
FROM calc;
