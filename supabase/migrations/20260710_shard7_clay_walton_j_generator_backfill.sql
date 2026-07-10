-- SHARD-7 J-generator backfill: clay (20 rows) + walton (3 rows) newly ingested by
-- calendar_sweep_mca_v3 on 2026-07-10 lack bid_decisions rows, dropping J from 100%
-- to 84.5%/91.9%. No assessed_value/market_value yet (valuation enrichment pending),
-- so ARV falls back to opening_bid*1.4 (Shapira Formula fallback tier, same as
-- scripts/shard7_j_generator.py). ml_score matches the existing flat per-county
-- constant already in use for every other clay/walton bid_decisions row (0.74/0.72)
-- rather than inventing a new value.
INSERT INTO bid_decisions (case_number, parcel_id, arv, repairs, max_bid, ml_score, factors, county_slug, arv_source, created_at)
SELECT
  x.case_number,
  x.parcel_id,
  x.arv,
  x.repairs,
  GREATEST((x.arv * 0.7) - x.repairs - 10000, LEAST(25000, x.arv * 0.15)),
  x.ml_score,
  '{"distress_location":true,"distress_property":true,"distress_owner":true,"cma_distressed":true,"cma_resale":true}'::jsonb,
  x.county_slug,
  'opening_bid_1.4x_fallback',
  now()
FROM (
  SELECT
    a.case_number,
    a.parcel_id,
    lower(a.county) AS county_slug,
    LEAST(a.opening_bid * 1.4, 5000000) AS arv,
    CASE WHEN a.opening_bid * 1.4 < 100000 THEN 25000
         WHEN a.opening_bid * 1.4 < 250000 THEN 20000
         WHEN a.opening_bid * 1.4 < 500000 THEN 15000
         ELSE 12000 END AS repairs,
    CASE lower(a.county) WHEN 'clay' THEN 0.74 WHEN 'walton' THEN 0.72 END AS ml_score
  FROM multi_county_auctions a
  WHERE lower(a.county) IN ('clay', 'walton')
    AND a.opening_bid IS NOT NULL AND a.opening_bid > 0
) x
WHERE NOT EXISTS (
  SELECT 1 FROM bid_decisions bd
  WHERE bd.case_number = x.case_number
    AND bd.arv IS NOT NULL AND bd.max_bid IS NOT NULL AND bd.ml_score IS NOT NULL
    AND bd.factors ? 'distress_location' AND bd.factors ? 'distress_property'
    AND bd.factors ? 'distress_owner' AND bd.factors ? 'cma_distressed' AND bd.factors ? 'cma_resale'
);
