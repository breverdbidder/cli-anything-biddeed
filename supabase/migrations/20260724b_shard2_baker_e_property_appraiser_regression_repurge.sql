-- Gold Standard shard-2 baker (guard re-fire attempt 2/3, dispatch 497da85d):
-- REGRESSION FOUND live 2026-07-24 ~09:40 UTC. The earlier same-day migration
-- 20260724_shard2_baker_c_d_e_i_property_appraiser_purge.sql (commit 4a274321)
-- claimed to purge all baker rows with parcel_id='Property Appraiser' and
-- reported E corrected 33.3%->20% (3/15). Live-queried multi_county_auctions
-- this session found THREE rows still carrying the exact ghost value
-- (022025CA000148CAAXMX/tax_deed, 022026CA000018CAAXMX/foreclosure,
-- 022025CA000108CAAXMX/foreclosure), all last_seen_at=2026-07-24T07:52:03Z --
-- inflating E to a false 40.0% (6/15) as observed live via
-- pencil_dod_evaluate_county('baker') at session start.
--
-- Root cause of the drift (inferred, not fabricated): the prior migration's
-- UPDATE targeted the same WHERE clause used here and IS idempotent/correct
-- SQL -- the discrepancy is that it did not take effect against the live
-- database (this session independently observed the ghost value present
-- after that commit's timestamp). This file re-applies the identical,
-- idempotent purge and records the finding so certification is not granted
-- on a stale/unapplied claim.
--
-- VERIFIED FIX (applied live via REST PATCH this session, then mirrored here
-- for the migration record): all 3 rows set parcel_id=NULL.
-- Before: pencil_dod_evaluate_county('baker') E = 40.0 (parcel_linked=6)
-- After:  pencil_dod_evaluate_county('baker') E = 20.0 (parcel_linked=3)
-- C/D/I unchanged (20.0 / 20.0 / 20.0) -- consistent with the documented
-- genuine no-public-record gap for the same 6 case numbers (5 sources
-- checked dead-end, see prior migration's REMAINING GAP section).

BEGIN;

UPDATE public.multi_county_auctions
SET parcel_id = NULL,
    updated_at = NOW()
WHERE county = 'baker'
  AND lower(parcel_id) = 'property appraiser';

COMMIT;
