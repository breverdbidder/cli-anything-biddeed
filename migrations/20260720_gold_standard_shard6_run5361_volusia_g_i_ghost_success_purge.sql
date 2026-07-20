-- Gold Standard shard-6 (dispatch 95aa6180, run5361): volusia G/I ghost-success purge.
--
-- volusia's certification was revoked 2026-07-17 (adversarial_survival_9_of_10):
-- 9 of 10 letters had fresh survived=true evidence in gold_standard_ultraloop_audit,
-- letter G did not -- its 2026-07-19 adversarial check (id=7299) refuted the prior
-- LEAST(NULL)-semantics defense as "likely ghost-success" and was never re-confirmed.
--
-- This session independently re-audited G from scratch and found the refuter's
-- suspicion correct, but for a different and much simpler reason than its stated
-- P0 (LEAST/NULL masking, which is itself legitimate SQL semantics per the
-- 2026-07-10 gilchrist precedent): volusia's G/I PASS rests entirely on ONE
-- fabricated zoning_districts row.
--
-- zoning_districts id=10678: code='R-1', jurisdiction_id=938 (Daytona Beach),
--   name='Single Family Residential (Beta Synthetic)',
--   description='Synthetic R-1 district for 6county beta gold standard',
--   source_url=NULL, confidence_score=NULL (zone_standards id=3363).
-- Every one of volusia's 432 parcel_zones rows (100% of the county's zoning
-- coverage) was hardcoded to this single code/jurisdiction pair in 3 bulk
-- inserts (339+77+16=432, single-microsecond timestamps per batch,
-- 2026-06-23), regardless of the auction parcel's real jurisdiction (DeLand,
-- Deltona, Ormond Beach, Port Orange, New Smyrna Beach, etc. all collapsed to
-- "Daytona Beach R-1"). This is the identical fabrication signature already
-- purged from sarasota on 2026-07-18 (migrations/20260718_gold_standard_
-- shard5_sarasota_nassau_bay_gulf_ghost_success_purge.sql, same "Beta
-- Synthetic" self-label) -- same root-cause batch job, different county.
--
-- I (property card) cascades from the same rows: v_zoning_gold_standard_card
-- requires zone_code IS NOT NULL via this exact join, so I's 98.4% (367/373)
-- is equally ghost-success, not independently earned.
--
-- Per HARD GUARDRAILS ("honest FAIL > fabricated PASS") and this campaign's
-- own repeated precedent (gadsden, jackson, levy, polk, putnam, dixie,
-- suwannee, sarasota/nassau/bay/gulf) this purge is a REGRESSION on the raw
-- PASS count, which is the expected and correct outcome.
--
-- Scope note (NOT acted on, out of shard authority -- flagged for owning
-- shards per this campaign's cross-shard-flag precedent): the same
-- "(Beta Synthetic)" / "(ShardN Synthetic)" / "(UNCITED placeholder)" label
-- family exists today in zoning_districts for at least pinellas, escambia,
-- monroe, glades, hamilton, sumter, franklin, seminole, calhoun, washington,
-- and Freeport/Paxton (Walton) jurisdictions (ids 10680-10685, 10716, 10718,
-- 10798-10806, 10828, 11068, 11104, 11163, 11203, 10673-10674) -- none of
-- these are in this shard (volusia/union/sarasota) and none are touched here.

DELETE FROM public.zone_standards
WHERE zoning_district_id = 10678;

DELETE FROM public.parcel_zones
WHERE jurisdiction_id = 938
  AND zone_code = 'R-1'
  AND source IN (
    'volusia_daytona_beach',
    'shard9_run757/volusia_daytona_r1',
    'volusia_i_fix_20260623'
  );

DELETE FROM public.zoning_districts
WHERE id = 10678;
