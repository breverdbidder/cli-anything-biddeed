-- SHARD-4 Gold Standard: Madison County — letter I card-completeness backfill
-- county: madison | letters touched: I (honest attempt, metric unchanged, still FAIL)
--
-- Context (dispatch 5a1ebf79):
--   pencil_dod_evaluate_county('madison') letter I was card_complete=0 of 5
--   (0.0%). All 5 madison multi_county_auctions rows match fl_parcels
--   (co_no=50) on replace(parcel_id,'-','') with real centroid_lat/
--   centroid_lng/av_sd/jv present on the fl_parcels side, but NULL
--   latitude/longitude/assessed_value/market_value on the auction side.
--
--   This migration documents the COALESCE-only UPDATE already applied live
--   this session (exactly 5 rows updated, verified via RETURNING). Re-running
--   is idempotent: COALESCE only writes where the auction-side field is
--   currently NULL, so a second run changes 0 rows.
--
-- Effect: I metric did NOT move (0.0% -> 0.0%, still FAIL). Confirmed by
-- reading pg_get_functiondef(pencil_dod_evaluate_county): card_complete
-- requires address AND lat/lng AND assessed/market value AND a zone match
-- against v_zoning_gold_standard_card (zone_code IS NOT NULL). Madison has
-- zero zone_code-populated zoning rows for co_no=50 (the DOR_UC crosswalk
-- was never run for Madison, and this campaign correctly purged fabricated
-- placeholder parcel_zones rows earlier this session rather than leave fake
-- zone_code values in place -- see
-- 20260710_shard4_madison_g_parcel_zones_fabrication_purge.sql).
--
-- This backfill was still worth applying and documenting: it satisfies 3 of
-- the 4 required card_complete conditions for all 5 rows and removes any
-- future ambiguity about whether lat/lng/value data exists for Madison.
-- The remaining gap (real zoning/parcel_zones ingestion for co_no=50) is
-- named, not fixed, and is out of scope for this task.

BEGIN;

UPDATE public.multi_county_auctions a
SET latitude       = COALESCE(a.latitude, fp.centroid_lat),
    longitude      = COALESCE(a.longitude, fp.centroid_lng),
    assessed_value = COALESCE(a.assessed_value, fp.av_sd::numeric),
    market_value   = COALESCE(a.market_value, fp.jv::numeric)
FROM public.fl_parcels fp
WHERE lower(a.county) = 'madison'
  AND fp.co_no = 50
  AND fp.parcel_id = replace(a.parcel_id, '-', '')
  AND a.parcel_id IS NOT NULL
  AND (
    a.latitude IS NULL
    OR a.longitude IS NULL
    OR a.assessed_value IS NULL
    OR a.market_value IS NULL
  );

COMMIT;

-- Verification:
-- SELECT public.pencil_dod_evaluate_county('madison');
-- Expect: I = {"pass": false, "detail": "card_complete=0 of 5", "metric": 0.0}
--   (unchanged -- root cause is zero zone_code rows for madison co_no=50 in
--    v_zoning_gold_standard_card, a separate ingestion gap, not this backfill)
--
-- Idempotency check (second run should update 0 rows):
-- SELECT count(*) FROM public.multi_county_auctions a
-- JOIN public.fl_parcels fp ON fp.co_no=50 AND fp.parcel_id = replace(a.parcel_id,'-','')
-- WHERE lower(a.county)='madison' AND a.parcel_id IS NOT NULL
--   AND (a.latitude IS NULL OR a.longitude IS NULL OR a.assessed_value IS NULL OR a.market_value IS NULL);
