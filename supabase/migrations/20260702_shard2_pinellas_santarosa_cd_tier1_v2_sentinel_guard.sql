-- SHARD-2 FOLLOW-UP: fix sentinel-parcel_id false-positive in refresh_shard2_cd_tier1_v1()
-- dispatch_id: 2161cd0e-3eb7-4af7-be17-95e9891f56a3
-- Session: architect-20260702T160000
-- Supersedes: 20260702_shard2_pinellas_santarosa_cd_tier1_realforeclose.sql (applied live
-- moments earlier this same session, then adversarially refuted before being reported PASS).
--
-- ULTRALOOP ADVERSARIAL VERIFICATION (independent refuter subagent, live queries):
-- the v1 parcel_id join arm (`mca.parcel_id = ra.parcel_id`, guarded only by IS NOT NULL)
-- cross-matched rows purely because BOTH sides carry the same scraper-failure sentinel
-- string ("Property Appraiser", "MULTIPLE PARCELS", "MOBILE HOME", ...) instead of a real
-- parcel ID -- these are not the same auction. REFUTED: 12/62 pinellas and 4/14 santa_rosa
-- newly-"matched_clean" rows were false positives from this collision, cross-linking
-- completely unrelated case numbers.
--
-- FIX: require both sides of the parcel_id arm to contain at least one digit (`~ '[0-9]'`)
-- -- none of the known sentinel strings contain a digit, real FL parcel/PIN formats always
-- do (including space-delimited PINs, e.g. "15 30 22 92817 010 0490"). Also revert any row
-- whose tier1_realforeclose_* label rests SOLELY on a sentinel-parcel collision (no
-- independent case_number match backing it) back to its pre-fix state.
--
-- RESULT (live, re-verified against pencil_dod_evaluate_county after applying the guard):
--   pinellas:   C/D 16.9% (62/367, UNVERIFIED/refuted) -> 13.9% (51/367, verified)
--   santa_rosa: C/D 22.2% (14/63,  UNVERIFIED/refuted) -> 19.0% (12/63,  verified)
-- Remaining sentinel-parcel_id rows on the mca side (7 total) independently carry a genuine
-- normalize_case_number() match to realforeclose_aids -- confirmed NOT sentinel-only, kept.
-- Both counties remain honest FAIL (<95%). gold_standard_ultraloop_audit ids 2782-2787 record
-- the refute/survive pair for this claim.

CREATE OR REPLACE FUNCTION public.refresh_shard2_cd_tier1_v1()
 RETURNS TABLE(step text, rows_affected integer)
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_pinellas_rfa   INTEGER := 0;
  v_santarosa_rfa  INTEGER := 0;
  v_santarosa_fix  INTEGER := 0;
BEGIN
  -- 1) pinellas: genuine tier1 match via realforeclose_aids.
  --    parcel_id arm requires a digit on BOTH sides to reject scraper-failure sentinel
  --    strings ('Property Appraiser','MULTIPLE PARCELS','MOBILE HOME', etc.) that would
  --    otherwise cross-match unrelated cases (caught live by adversarial refutation).
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
      OR (mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL AND mca.parcel_id = ra.parcel_id
          AND mca.parcel_id ~ '[0-9]' AND ra.parcel_id ~ '[0-9]')
    )
    AND mca.parity_source IS DISTINCT FROM 'tier1_realforeclose_pinellas';
  GET DIAGNOSTICS v_pinellas_rfa = ROW_COUNT;

  -- 2) santa_rosa: genuine tier1 match via realforeclose_aids (same guarded pattern)
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
      OR (mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL AND mca.parcel_id = ra.parcel_id
          AND mca.parcel_id ~ '[0-9]' AND ra.parcel_id ~ '[0-9]')
    )
    AND mca.parity_source IS DISTINCT FROM 'tier1_realforeclose_santa_rosa';
  GET DIAGNOSTICS v_santarosa_rfa = ROW_COUNT;

  -- 2b) revert any prior false-positive sentinel-parcel matches from the unguarded v1 run
  --     that are NOT independently backed by a genuine case_number match.
  UPDATE public.multi_county_auctions mca
  SET parity_status = 'mca_only',
      parity_source = NULL,
      updated_at    = now()
  WHERE mca.county IN ('pinellas','santa_rosa')
    AND mca.parity_source IN ('tier1_realforeclose_pinellas','tier1_realforeclose_santa_rosa')
    AND mca.parcel_id IN ('Property Appraiser','MULTIPLE PARCELS','MOBILE HOME',
                           'ALCOHOLIC BERVERAGE LICENSE','SINGLE MEMBER INTEREST','LEIN SALE')
    AND NOT EXISTS (
      SELECT 1 FROM public.realforeclose_aids ra2
      WHERE ra2.county_slug = mca.county
        AND normalize_case_number(mca.case_number) = normalize_case_number(ra2.case_number)
    );

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
