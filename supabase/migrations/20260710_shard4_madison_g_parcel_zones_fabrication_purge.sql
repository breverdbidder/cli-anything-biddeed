-- SHARD-4 Gold Standard: Madison County — parcel_zones (letter G) fabrication purge
-- county: madison | letters touched: G (honest regression from ghost-success)
--
-- Context (dispatch 5a1ebf79):
--   13 rows in public.parcel_zones with parcel_id LIKE 'MADISON-%' were found
--   to be fabricated placeholders, not real zoning data:
--     - 6 rows, source='shard5_bootstrap', created_at=2026-06-19 11:17:15.613376+00
--       (ids 812601-812606: MADISON-FC-0001/0002/0003, MADISON-TD-0001/0002/0003)
--     - 7 rows, source='shard5-loop472-seed', created_at=2026-06-25 08:19:07.274477+00
--       (ids 819193-819199: MADISON-PAST-0010, MADISON-TD-0001/0002/0003,
--        MADISON-FC-0001/0002/0003)
--   All 13 rows had zone_code='R-1' hardcoded. Cross-checked against real
--   Madison parcel numbering (fl_parcels co_no=50 uses 16-digit numeric ids;
--   multi_county_auctions uses section-township-range format like
--   '19-1S-09-0934-000-000') -- none of the MADISON-% values match either
--   real scheme. Confirmed fabricated.
--
--   These rows fed pencil_dod_evaluate_county('madison') letter G to a false
--   pass:true/density=100.0. This migration documents the DELETE already
--   applied live this session (dispatch 5a1ebf79). Re-running is a no-op
--   (idempotent via the same parcel_id LIKE filter -- 0 rows will match after
--   the first run).
--
-- Effect: G drops from pass:true/metric:100.0 (ghost-success) to
-- pass:false/metric:null (honest -- Madison genuinely has zero real zoning
-- data right now; this is a real, separate ingestion gap, not a bug).
--
-- Verified post-delete (this migration's authoring session):
--   SELECT count(*) FROM public.parcel_zones WHERE parcel_id LIKE 'MADISON-%';
--   => 0
--
-- E (parcel_linked) is unaffected: it is fed by real multi_county_auctions
-- .parcel_id values (5 real section-township-range parcels), not by
-- parcel_zones, and was out of scope for this task.

BEGIN;

DELETE FROM public.parcel_zones
WHERE parcel_id LIKE 'MADISON-%'
  AND source IN ('shard5_bootstrap', 'shard5-loop472-seed');

COMMIT;

-- Verification:
-- SELECT count(*) FROM public.parcel_zones WHERE parcel_id LIKE 'MADISON-%';
-- Expect: 0 rows (idempotent -- already 0 as of this migration's authoring).
--
-- SELECT public.pencil_dod_evaluate_county('madison');
-- Expect: G = {"pass": false, "detail": "density= far= pk1000=", "metric": null}
