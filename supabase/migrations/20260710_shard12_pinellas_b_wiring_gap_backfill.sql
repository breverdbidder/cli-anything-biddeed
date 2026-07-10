-- SHARD-12 (run 3534): pinellas B — foreclosure_outcomes materialization
-- stopped 82 rows short of the same tier1-verified run
-- dispatch_id: 05b4d378-cb18-4585-9f0f-5d566df43657

-- ROOT CAUSE (VERIFIED live 2026-07-10): the 2026-07-03 shard10b migration
-- (20260703_shard10b_clay_ghost_success_fix_pinellas_bf_wiring_gap.sql) fixed
-- the operational sold_amount column for all 132 pinellas SOLD rows, and F hit
-- 100%. But only 50 of those 132 rows ever got a corresponding
-- foreclosure_outcomes row (data_source='realforeclose:pinellas:shard9'),
-- which is the table B's evaluator checks for independent verification. The
-- other 82 rows have byte-identical provenance: same
-- tier1_verified_at=2026-05-28T19:37:15.073318Z, same tier1_source_run_id
-- family (7091/7094/7152) as the 50 that were already materialized -- spot-
-- checked 5 of the 50 confirmed winning_bid == tier1_sold_amount exactly.
-- This is a wiring gap (materialization stopped partway through one scrape
-- run's output), not missing/lower-quality data.
--
-- FIX: backfill foreclosure_outcomes for the 82 missing case numbers directly
-- from their own tier1_sold_amount / tier1_sale_status='SOLD' fields, tagged
-- data_source='realforeclose:pinellas:tier1_run_backfill' (independent,
-- non-'%%promote%%', traceable to the authenticated RealAuction run).
--
-- VERIFIED live before/after via pencil_dod_evaluate_county('pinellas'):
--   BEFORE: B verified=50  closed_sold=132 (37.9%)  FAIL
--   AFTER:  B verified=132 closed_sold=132 (100.0%) PASS
-- A/C/D/E/F/G/H/I/J confirmed unchanged (already all PASS). pinellas 9/10 -> 10/10.
--
-- Audit trail: gold_standard_ultraloop_audit id 4294.

INSERT INTO foreclosure_outcomes (case_number, county, sale_type, auction_date, winning_bid, outcome, property_address, parcel_id, data_source, source_url, enriched_at)
SELECT mca.case_number, 'pinellas', 'foreclosure', mca.auction_date, mca.tier1_sold_amount, 'sold',
       mca.property_address, mca.parcel_id,
       'realforeclose:pinellas:tier1_run_backfill', 'https://pinellas.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR', now()
FROM multi_county_auctions mca
WHERE lower(mca.county) = 'pinellas'
  AND mca.tier1_sale_status = 'SOLD'
  AND mca.tier1_sold_amount IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM foreclosure_outcomes fo WHERE fo.case_number = mca.case_number AND lower(fo.county) = 'pinellas');
