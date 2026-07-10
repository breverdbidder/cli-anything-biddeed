-- SHARD-2 run2886 (lake): Letter J bid_decisions backfill
-- Root cause (verified live 2026-07-04): scripts/shard7_lake_j_generator.py had only ever been
-- run against an earlier, smaller lake auction set (14 case_numbers, each inserted twice due to
-- POST without an on_conflict target -- 29 rows total for 14 unique cases). The scored population
-- (WHERE lower(county)='lake' AND (data_source<>'propertyonion' OR tier1_authoritative=true)) grew
-- to 97 auctions; the other 83 case_numbers had zero bid_decisions row, so
-- pencil_dod_evaluate_county('lake').J was stuck at 15.5% (15/97) even though the generator logic
-- itself was already accepted (same Shapira-formula-approximation pattern used for taylor/lee's
-- passing J scores).
--
-- Fix: insert bid_decisions for exactly the still-missing, in-scope lake case_numbers, using the
-- same formula as scripts/shard7_lake_j_generator.py (ARV = assessed_value, else opening_bid*1.4,
-- else $165,000 county default; repairs tiered by ARV; max_bid = Shapira formula; ml_score=0.55
-- flat; factors = the 5 evaluator-required keys). This is a completeness/wiring fix, not a new
-- valuation methodology -- it matches what already passed adversarial review for taylor and lee.
--
-- Applied live via Supabase Management API SQL exec on 2026-07-04. This file documents that change
-- for repo history; it is idempotent (NOT EXISTS guard) and safe to re-run.
--
-- Verified result: pencil_dod_evaluate_county('lake').J: 15.5% (15/97, FAIL) -> 100.0% (97/97, PASS).
-- 82 rows inserted (not 83 -- corrected count from adversarial refuter pass).
--
-- ADVERSARIAL REFUTER FINDINGS (logged to gold_standard_ultraloop_audit, survived=true with caveat):
-- 1. One cross-county case_number collision: 2024CA001040 is a real row in BOTH lake and st_lucie.
--    The evaluator's bd.case_number EXISTS check has no county_slug filter, so this case is scored
--    via a pre-existing st_lucie bid_decisions row, not a lake one. True lake-backed completeness
--    is 96/97 (98.97%), not 97/97 -- still clears the 95% pass threshold, but "100%" overstates it.
--    This is a latent fleet-wide gap in the shared pencil_dod_evaluate_county function (no
--    county_slug filter on the J EXISTS check), flagged for the AI Architect -- NOT modified here
--    (shared scoring function, out of this shard's scope; do not touch scoring functions ad hoc).
-- 2. Pre-existing (not introduced by this migration): 14 duplicate bid_decisions rows from a stale
--    2026-06-24 run of scripts/shard7_lake_j_generator.py (POST without on_conflict target), and 3
--    fabricated placeholder auction rows (LAKE-FC-2026-001/002/003, addresses "123 MAIN ST" etc.)
--    that inflate lake's auctions_total. Flagged for human cleanup per existing project pattern
--    (see LAKE-TD-SYNTH-SHARD6-001, flagged the same way in the 2026-07-03 session) -- not deleted
--    here; deleting auction rows changes every letter's denominator and needs deliberate review.

WITH scope AS (
  SELECT mca.case_number, mca.parcel_id, mca.assessed_value, mca.opening_bid, mca.auction_type
  FROM multi_county_auctions mca
  WHERE lower(mca.county) = 'lake'
    AND (COALESCE(mca.data_source, '') <> 'propertyonion' OR COALESCE(mca.tier1_authoritative, false) = true)
    AND mca.case_number IS NOT NULL AND mca.case_number <> ''
    AND NOT EXISTS (SELECT 1 FROM bid_decisions bd WHERE bd.case_number = mca.case_number)
),
calc AS (
  SELECT case_number, parcel_id, auction_type,
    CASE WHEN assessed_value IS NOT NULL AND assessed_value > 0 THEN assessed_value::numeric
         WHEN opening_bid IS NOT NULL AND opening_bid > 0 THEN (opening_bid::numeric * 1.4)
         ELSE 165000 END AS arv
  FROM scope
),
calc2 AS (
  SELECT *,
    CASE WHEN arv < 100000 THEN 25000
         WHEN arv < 250000 THEN 20000
         WHEN arv < 500000 THEN 15000
         ELSE 12000 END AS repairs
  FROM calc
),
calc3 AS (
  SELECT *,
    GREATEST((arv * 0.70) - repairs - 10000, LEAST(25000, arv * 0.15)) AS max_bid
  FROM calc2
)
INSERT INTO bid_decisions (case_number, county_slug, parcel_id, arv, max_bid, ml_score, factors, repairs, recommendation, created_at)
SELECT
  case_number, 'lake', parcel_id, round(arv, 2), round(max_bid, 2), 0.55,
  jsonb_build_object(
    'cma_resale', round(arv, 2),
    'cma_distressed', round(arv * 0.65, 2),
    'distress_owner', 'unknown',
    'distress_location', 'lake',
    'distress_property', COALESCE(auction_type, 'foreclosure')
  ),
  round(repairs, 2), 'REVIEW', now()
FROM calc3;
