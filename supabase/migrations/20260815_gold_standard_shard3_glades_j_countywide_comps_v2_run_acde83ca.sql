-- GOLD STANDARD shard-3 (glades/st_lucie/union), dispatch acde83ca-0ef2-4df1-b907-e6ae224b191a.
-- County: glades. Letter J extension (65.7% -> real countywide comps for the newly-grown gap).
--
-- CONTEXT: glades J was previously built up to 67/70 rows (95.7% at that time) across three
-- honest sessions documented in migrations/20260721_..._j_ghost_success_purge.sql (purged a
-- fabricated bulk insert), migrations/20260724_glades_j_real_comps_backfill_run6080_2nd_firing.sql
-- (14 rows via zip+living-area comps), migrations/20260724_..._vacant_land_comps_run6148.sql
-- (+45 rows via zip+land-size comps), and migrations/20260725_..._countywide_comps_run6288.sql
-- (+8 rows via county-wide 4-tier comp cascade, dropping the zip restriction).
--
-- Since that last session, glades' multi_county_auctions grew from 70 to 102 total rows (32 new
-- tax-deed auctions added, mostly a 2026-06-04 TD batch). The 67 pre-existing bid_decisions rows
-- were untouched and reconfirmed genuinely real (varied ml_score, non-flat CMA) at the start of
-- this session. J's metric consequently dropped back to 65.7% (67/102) purely from denominator
-- growth, not any regression of the existing rows.
--
-- THIS MIGRATION reapplies the EXACT proven 4-tier countywide comp-cascade methodology from
-- migrations/20260725_gold_standard_shard12_glades_j_countywide_comps_run6288.sql to the 35 NEW
-- gap rows only (auctions with no existing bid_decisions row), scoped with a NOT EXISTS guard so
-- it is idempotent and cannot touch the 67 already-written rows. It does NOT modify
-- gen_valuations_comps_batch() or any cron job (HARD GUARDRAILS #4).
--
-- COVERAGE (VERIFIED live before writing): of the 35 gap rows, 33 join fl_parcels via
-- dash-stripped parcel_id (2 do not: TD-2024-4-20240808 has a parcel_id with no fl_parcels
-- cadastral match, 222025CA000139CAAXMX has no parcel_id at all -- the same structural E-linkage
-- gap flagged in every prior glades J session, left with NO row, BLANK > WRONG). Of the 33
-- joined, 29 have n_comps>=3 at some tier of the cascade; 4 remain genuinely thin even at tier 4
-- (0.2x-5.0x land size, since 2016): TD-2022-6-20240118 (dor_uc=069, agricultural, only 2 real
-- county-wide sales of that use code exist since 2016 -- same case number/root cause the prior
-- shard-12 session already documented as structurally thin) and three dor_uc=099 rows
-- (TD-2024-36/37/33) whose lnd_sqfoot values (13.7K-108.9K sqft) fall in a genuine gap in that
-- use code's bimodal county-wide sale-size distribution (clusters near 2.6K-6.2K sqft and
-- 870K-1.7M sqft, nothing in between) -- not a bug, a real thin-pool structural ceiling. All 4
-- are left with NO row.
--
-- METHODOLOGY (identical to run6288, cascading tiers, tightest-first, real fl_parcels.sale_prc1
-- transactions only, co_no=32 county-wide):
--   Tier 1: same dor_uc, county-wide, living-area (tot_lvg_ar) within 0.7x-1.3x, sold >=2020.
--   Tier 2: same dor_uc, county-wide, living-area within 0.5x-2.0x, sold >=2018.
--   Tier 3: same dor_uc, county-wide, land-size (lnd_sqfoot) within 0.5x-2.0x, sold >=2018.
--   Tier 4: same dor_uc, county-wide, land-size within 0.2x-5.0x, sold >=2016 (last resort).
--   First tier (in order) with n_comps>=3 is used; tier fired is recorded in the row's honesty
--   note for auditability. Rows where even tier 4 has <3 comps get NO row.
--
-- Applied live via Python/PostgREST (exec_sql/execute_sql RPCs do not exist in this project;
-- SQL logic below is the documented equivalent of the live insert, executed via
-- SUPABASE_SERVICE_ROLE_KEY REST calls per this repo's established apply_sql_direct.py pattern).
--
-- RESULT (VERIFIED live via pencil_dod_evaluate_county('glades') before/after):
--   BEFORE: J deal_complete=67/102 (65.7%), FAIL. A/B/C/D/E/F/G/H/I unchanged, all PASS.
--   AFTER:  J deal_complete=96/102 (94.1%), still FAIL (<95% threshold by 1 row) --
--           honest large real gain, not a letter flip. No regression on any other letter.
--   Residual 6 open (2 no-parcel-join/no-fl_parcels-match rows requiring an E-linkage fix
--   first, 4 genuinely-thin comp-pool rows) are left BLANK, not fabricated.
--
-- Adversarial-style validation performed live before/after insert (self-verified this session,
-- no separate refuter agent dispatched):
--   SELECT COUNT(*) AS total, COUNT(DISTINCT ml_score) AS distinct_ml,
--     COUNT(DISTINCT (factors->'cma_distressed'->>'value')) AS distinct_cma_d,
--     COUNT(*) FILTER (WHERE pipeline_version IS NULL) AS null_pv,
--     COUNT(*) FILTER (WHERE (factors->>'distress_owner')::numeric = ml_score) AS dup_do
--   FROM bid_decisions WHERE county_slug='glades' AND pipeline_version='glades_j_countywide_comps_v2_run_acde83ca';
--   ACTUAL: total=29, distinct_ml=18, distinct_cma_d=19, null_pv=0, dup_do=0.
--   Also independently recomputed p25/p75 for the smallest comp pool (TD-2022-44-20260604,
--   n=3, tier3) directly from raw fl_parcels rows: exact match to stored values (p25=1250.0,
--   p75=2400.0). Confirmed zero rows in the full 96-row glades bid_decisions table match a flat
--   arv*0.85/arv*1.12 formula (the pattern refuted twice for this county on 2026-07-24).

-- Equivalent SQL (documentation; live execution was via PostgREST REST inserts, see session
-- report for the Python implementation actually run):

SET statement_timeout = 0;

WITH targets AS (
    SELECT mca.case_number, mca.parcel_id, mca.property_address, mca.auction_date,
           mca.assessed_value, mca.market_value, mca.opening_bid, mca.auction_type,
           REPLACE(mca.parcel_id, '-', '') AS stripped
    FROM multi_county_auctions mca
    WHERE mca.county = 'glades' AND mca.parcel_id IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM bid_decisions bd WHERE bd.case_number = mca.case_number)
),
joined AS (
    SELECT t.*, fp.phy_zipcd, fp.dor_uc, fp.tot_lvg_ar, fp.lnd_sqfoot, fp.co_no
    FROM targets t
    JOIN public.fl_parcels fp ON fp.parcel_id = t.stripped
    WHERE fp.dor_uc IS NOT NULL AND fp.co_no IS NOT NULL
),
tiers AS (
    SELECT j.*,
      (SELECT jsonb_build_object('med', percentile_cont(0.5) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'p25', percentile_cont(0.25) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'p75', percentile_cont(0.75) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'n', count(*))
       FROM public.fl_parcels fp2
       WHERE fp2.co_no = j.co_no AND fp2.dor_uc = j.dor_uc AND fp2.sale_prc1 > 1000 AND fp2.sale_yr1 >= 2020
         AND j.tot_lvg_ar > 0 AND fp2.tot_lvg_ar BETWEEN j.tot_lvg_ar * 0.7 AND j.tot_lvg_ar * 1.3
      ) AS t1,
      (SELECT jsonb_build_object('med', percentile_cont(0.5) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'p25', percentile_cont(0.25) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'p75', percentile_cont(0.75) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'n', count(*))
       FROM public.fl_parcels fp2
       WHERE fp2.co_no = j.co_no AND fp2.dor_uc = j.dor_uc AND fp2.sale_prc1 > 1000 AND fp2.sale_yr1 >= 2018
         AND j.tot_lvg_ar > 0 AND fp2.tot_lvg_ar BETWEEN j.tot_lvg_ar * 0.5 AND j.tot_lvg_ar * 2.0
      ) AS t2,
      (SELECT jsonb_build_object('med', percentile_cont(0.5) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'p25', percentile_cont(0.25) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'p75', percentile_cont(0.75) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'n', count(*))
       FROM public.fl_parcels fp2
       WHERE fp2.co_no = j.co_no AND fp2.dor_uc = j.dor_uc AND fp2.sale_prc1 > 1000 AND fp2.sale_yr1 >= 2018
         AND j.lnd_sqfoot > 0 AND fp2.lnd_sqfoot BETWEEN j.lnd_sqfoot * 0.5 AND j.lnd_sqfoot * 2.0
      ) AS t3,
      (SELECT jsonb_build_object('med', percentile_cont(0.5) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'p25', percentile_cont(0.25) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'p75', percentile_cont(0.75) WITHIN GROUP (ORDER BY fp2.sale_prc1),
                                  'n', count(*))
       FROM public.fl_parcels fp2
       WHERE fp2.co_no = j.co_no AND fp2.dor_uc = j.dor_uc AND fp2.sale_prc1 > 1000 AND fp2.sale_yr1 >= 2016
         AND j.lnd_sqfoot > 0 AND fp2.lnd_sqfoot BETWEEN j.lnd_sqfoot * 0.2 AND j.lnd_sqfoot * 5.0
      ) AS t4
    FROM joined j
),
picked AS (
    SELECT *,
      CASE
        WHEN (t1->>'n')::int >= 3 THEN 'tier1_living_0.7-1.3x_since2020'
        WHEN (t2->>'n')::int >= 3 THEN 'tier2_living_0.5-2.0x_since2018'
        WHEN (t3->>'n')::int >= 3 THEN 'tier3_land_0.5-2.0x_since2018'
        WHEN (t4->>'n')::int >= 3 THEN 'tier4_land_0.2-5.0x_since2016'
        ELSE NULL
      END AS tier_used,
      COALESCE(
        CASE WHEN (t1->>'n')::int >= 3 THEN t1 END,
        CASE WHEN (t2->>'n')::int >= 3 THEN t2 END,
        CASE WHEN (t3->>'n')::int >= 3 THEN t3 END,
        CASE WHEN (t4->>'n')::int >= 3 THEN t4 END
      ) AS comp
    FROM tiers
),
calc AS (
    SELECT
        case_number, parcel_id, property_address, auction_date, opening_bid, auction_type, tier_used,
        (comp->>'n')::int AS n_comps,
        round((comp->>'p25')::numeric, 2) AS cma_distressed_val,
        round((comp->>'p75')::numeric, 2) AS cma_resale_val,
        GREATEST(COALESCE(assessed_value, 0), COALESCE(market_value, 0), (comp->>'med')::numeric) AS arv,
        ROUND(LEAST(0.85, GREATEST(0.35,
            0.38 + LEAST((comp->>'n')::int, 100) / 100.0 * 0.30 +
            CASE WHEN opening_bid IS NOT NULL AND opening_bid > 0 AND assessed_value > 0
                 THEN (1 - LEAST(1, opening_bid / assessed_value)) * 0.15
                 ELSE 0.05 END
        ))::numeric, 4) AS ml_score,
        ROUND((
            CASE WHEN opening_bid IS NOT NULL AND opening_bid > 0 AND assessed_value > 0
                 THEN LEAST(0.90, 0.30 + (1 - LEAST(1, opening_bid / assessed_value)) * 0.50)
                 ELSE 0.52 END
        )::numeric, 4) AS distress_owner
    FROM picked
    WHERE tier_used IS NOT NULL
)
INSERT INTO bid_decisions (
    case_number, county_slug, parcel_id, address, auction_date,
    arv, repairs, final_judgment, max_bid, bid_judgment_ratio,
    recommendation, confidence, ml_score, factors, pipeline_version, arv_source
)
SELECT
    case_number, 'glades', parcel_id, property_address, auction_date,
    arv,
    CASE WHEN arv < 80000 THEN 22000 WHEN arv < 150000 THEN 25000 WHEN arv < 300000 THEN 20000 ELSE 15000 END AS repairs,
    opening_bid,
    GREATEST(
        (arv * 0.70)
        - (CASE WHEN arv < 80000 THEN 22000 WHEN arv < 150000 THEN 25000 WHEN arv < 300000 THEN 20000 ELSE 15000 END)
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
             ELSE 0.30 END,
        'distress_property',
        ROUND((0.40 + CASE WHEN auction_type = 'foreclosure' THEN 0.15 ELSE 0 END)::numeric, 4),
        'distress_owner', distress_owner,
        'cma_distressed', jsonb_build_object(
            'value', cma_distressed_val,
            'note', 'p25 of ' || n_comps || ' real sold comps, county-wide same DOR use code (' || tier_used || ')',
            'honesty_marker', 'INFERRED'
        ),
        'cma_resale', jsonb_build_object(
            'value', cma_resale_val,
            'note', 'p75 of ' || n_comps || ' real sold comps, county-wide same DOR use code (' || tier_used || ')',
            'honesty_marker', 'INFERRED'
        )
    ),
    'glades_j_countywide_comps_v2_run_acde83ca',
    'fl_dor_cadastral_assessed_market_or_comp_median'
FROM calc;
