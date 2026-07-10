-- SHARD-2: pinellas + santa_rosa C/D — genuine tier1 parity via realforeclose_aids
-- dispatch_id: 2161cd0e-3eb7-4af7-be17-95e9891f56a3
-- Session: architect-20260702T160000 (gold standard shard-2: baker, glades, madison, santa_rosa, pinellas)
--
-- ROOT CAUSE (VERIFIED live 2026-07-02 via Management API, ULTRALOOP-style adversarial check):
-- biddeed.refresh_parity_chunk (cron job 45, every 5 min) sets multi_county_auctions.parity_status
-- for ALL counties fleet-wide by joining public.po_mca_matches / public.po_listings
-- (PropertyOnion) but never sets parity_source. pencil_dod_evaluate_county's C/D formula
-- (fixed this morning, commit 652678dc) correctly requires parity_source LIKE 'tier1%%',
-- so every PO-derived match is (correctly) excluded — this is by design, PO is litmus-only
-- per HARD GUARDRAILS #1, not a defect to route around.
--
-- pinellas: all 269 matched_clean/matched_divergent rows carry parity_source=NULL (PO-only,
-- correctly excluded) -> C/D genuinely 0.0%/0.0%.
--
-- santa_rosa: 29 matched_clean/matched_divergent rows carry parity_source=
-- 'tier1_clerk_supp_shard5_daily_r1524' -- but ALL 29 also carry parity_po_id (verified via
-- `count(*) filter (where parity_po_id is not null)` = 29/29). This source was never an
-- independent clerk cross-check; it is the same PO-derived match from
-- biddeed.refresh_parity_chunk, mislabeled with a 'tier1_' prefix by a prior shard-5 session.
-- This is the same false-positive class the shard-1 fix caught for escambia/hernando/lee/
-- palm_beach/pinellas/volusia this morning, just a different mislabeling vector (PO-linkage
-- dressed as tier1, vs E-criterion parcel-linkage dressed as tier1). santa_rosa's reported
-- 38.1%/46.0% C/D this loop run rests on this mislabeling and must not be built upon further.
--
-- GENUINE INDEPENDENT SOURCE FOUND: public.realforeclose_aids (fleet-wide, county_slug-
-- partitioned, scraped from RealForeclose AUCTION ITEM DETAIL pages -- a separate endpoint
-- from the anonymous JSON calendar-preview our own calendar_sweep_mca_v3 ingestion uses,
-- and already the sanctioned tier1 source for brevard (public.refresh_parity_chunk Path B)
-- and hillsborough (refresh_hillsborough_parity_v1) -- SEARCH-FIRST reuse, no new scraper
-- built). Already has REAL rows for our shard: pinellas=115, santa_rosa=18. Matching by
-- normalize_case_number() (exact or containment) or parcel_id, verbatim to the proven
-- brevard/hillsborough pattern.
--
-- PREVIEW (live query before shipping): distinct multi_county_auctions rows matched —
--   pinellas: 62 of 367 (would newly count toward C/D, all currently 0-credit)
--   santa_rosa: 14 of 63 (overlaps partially with the 29 mislabeled PO rows; only the
--     genuinely realforeclose_aids-confirmed subset earns tier1 credit going forward)
-- Both remain well under the 95%% PASS threshold -- this ships honest partial progress,
-- not a certification claim.
--
-- SCOPE: WHERE mca.county IN ('pinellas','santa_rosa') only -- PARALLEL-FLEET RULES forbid
-- touching other shards' counties even though realforeclose_aids and the mislabeling pattern
-- are almost certainly present fleet-wide (flagged in session report for the owning shards).
--
-- Idempotent: safe to re-run (WHERE parity_source IS DISTINCT FROM the target label guards
-- re-updates; the santa_rosa relabel only touches rows still carrying the disproven label).

CREATE OR REPLACE FUNCTION public.refresh_shard2_cd_tier1_v1()
 RETURNS TABLE(step text, rows_affected integer)
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_pinellas_rfa   INTEGER := 0;
  v_santarosa_rfa  INTEGER := 0;
  v_santarosa_fix  INTEGER := 0;
BEGIN
  -- 1) pinellas: genuine tier1 match via realforeclose_aids
  UPDATE public.multi_county_auctions mca
  SET parity_status = 'matched_clean',
      parity_source = 'tier1_realforeclose_pinellas',
      updated_at    = now()
  FROM public.realforeclose_aids ra
  WHERE ra.county_slug = 'pinellas'
    AND mca.county      = 'pinellas'
    AND (
      normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
      OR (
        length(normalize_case_number(mca.case_number)) >= 10
        AND length(normalize_case_number(ra.case_number)) >= 8
        AND normalize_case_number(mca.case_number) LIKE '%' || normalize_case_number(ra.case_number) || '%'
      )
      OR (mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL AND mca.parcel_id = ra.parcel_id)
    )
    AND mca.parity_source IS DISTINCT FROM 'tier1_realforeclose_pinellas';
  GET DIAGNOSTICS v_pinellas_rfa = ROW_COUNT;

  -- 2) santa_rosa: genuine tier1 match via realforeclose_aids (same pattern)
  UPDATE public.multi_county_auctions mca
  SET parity_status = 'matched_clean',
      parity_source = 'tier1_realforeclose_santa_rosa',
      updated_at    = now()
  FROM public.realforeclose_aids ra
  WHERE ra.county_slug = 'santa_rosa'
    AND mca.county      = 'santa_rosa'
    AND (
      normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
      OR (
        length(normalize_case_number(mca.case_number)) >= 10
        AND length(normalize_case_number(ra.case_number)) >= 8
        AND normalize_case_number(mca.case_number) LIKE '%' || normalize_case_number(ra.case_number) || '%'
      )
      OR (mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL AND mca.parcel_id = ra.parcel_id)
    )
    AND mca.parity_source IS DISTINCT FROM 'tier1_realforeclose_santa_rosa';
  GET DIAGNOSTICS v_santarosa_rfa = ROW_COUNT;

  -- 3) santa_rosa: correct the shard-5 mislabel (PO-derived match wearing a false 'tier1_'
  --    label). Only rows NOT already fixed by step 2 above, and only where parity_po_id
  --    proves the original match came from PropertyOnion, not an independent source.
  UPDATE public.multi_county_auctions mca
  SET parity_source = 'po_litmus_only:relabeled_shard2_run2450',
      updated_at    = now()
  WHERE mca.county = 'santa_rosa'
    AND mca.parity_source = 'tier1_clerk_supp_shard5_daily_r1524'
    AND mca.parity_po_id IS NOT NULL;
  GET DIAGNOSTICS v_santarosa_fix = ROW_COUNT;

  RETURN QUERY
    SELECT 'pinellas_realforeclose_aids_match'::text, v_pinellas_rfa
    UNION ALL SELECT 'santa_rosa_realforeclose_aids_match'::text, v_santarosa_rfa
    UNION ALL SELECT 'santa_rosa_po_mislabel_corrected'::text, v_santarosa_fix;
END;
$function$;
