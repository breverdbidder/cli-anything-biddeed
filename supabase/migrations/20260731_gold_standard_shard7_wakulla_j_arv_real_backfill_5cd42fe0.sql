-- Gold Standard shard-7 (wakulla/suwannee), dispatch 5cd42fe0-1db0-4108-aef0-9119d1633305.
--
-- Wakulla letter J certification-freshness audit (this session) found the 24 tax-deed
-- bid_decisions rows share an identical arv=$120,000/max_bid=$54,000 template -- a ghost-
-- fill signature. Root cause (VERIFIED live): migration
-- 20260710_shard13_wakulla_j_generator_and_fake_row_purge.sql used an honest documented
-- fallback (flat county_default=$120,000) because AT THAT TIME wakulla's multi_county_
-- auctions had zero opening_bid/assessed_value/market_value on any row. A later enrichment
-- session (20260724z_gold_standard_shard3_wakulla_bf_landmarkweb_outcomes.sql and others)
-- has since populated real, distinct per-parcel assessed_value/market_value ($7,500 to
-- $192,255 across the 24 tax-deed parcels), but bid_decisions was never regenerated to use
-- them.
--
-- This migration applies the same Shapira Formula already established and audit-survived
-- for franklin/sumter/marion/orange/flagler (scripts/shard7_j_generator.py) --
-- ARV = max(assessed_value, market_value); repairs tiered by ARV
-- (<100K->$25K, <250K->$20K, <500K->$15K, else->$12K);
-- max_bid = GREATEST(ARV*0.70 - repairs - 10000, LEAST(25000, ARV*0.15))
-- -- to the 24 wakulla tax-deed rows, using the now-real per-parcel inputs. Idempotent:
-- safe to re-run, only touches rows with non-null assessed_value/market_value (excludes
-- 2026-TXD-097, which still has neither).
--
-- Does NOT resolve J fully: ml_score remains a flat 0.52 constant (documented limitation,
-- matching franklin's established county-level placeholder) and factors JSON remains an
-- identical all-true blob across all 30 rows -- no real per-property ML/distress-signal
-- computation exists in this pipeline yet. Logged as an open gap in
-- gold_standard_ultraloop_audit (id 11361, county_slug=wakulla, letter=J, survived=false)
-- for a future session to build real per-property scoring.

UPDATE bid_decisions bd
SET arv = x.arv,
    repairs = x.repairs,
    max_bid = GREATEST((x.arv * 0.7) - x.repairs - 10000, LEAST(25000, x.arv * 0.15)),
    arv_source = 'assessed_market_value_live_20260731'
FROM (
  SELECT
    a.case_number,
    GREATEST(COALESCE(a.assessed_value, 0), COALESCE(a.market_value, 0)) AS arv,
    CASE
      WHEN GREATEST(COALESCE(a.assessed_value, 0), COALESCE(a.market_value, 0)) < 100000 THEN 25000
      WHEN GREATEST(COALESCE(a.assessed_value, 0), COALESCE(a.market_value, 0)) < 250000 THEN 20000
      WHEN GREATEST(COALESCE(a.assessed_value, 0), COALESCE(a.market_value, 0)) < 500000 THEN 15000
      ELSE 12000
    END AS repairs
  FROM multi_county_auctions a
  WHERE lower(a.county) = 'wakulla'
    AND a.sale_type = 'tax_deed'
    AND (a.assessed_value IS NOT NULL OR a.market_value IS NOT NULL)
) x
WHERE bd.case_number = x.case_number
  AND bd.county_slug = 'wakulla';
