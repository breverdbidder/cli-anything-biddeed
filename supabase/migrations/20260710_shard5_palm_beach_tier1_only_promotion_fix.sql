-- SHARD5 run3645: palm_beach tier1_only promotion fix
-- Root cause (VERIFIED via pg_get_functiondef): both UPDATE blocks in
-- public.refresh_palm_beach_parity_v2() gate on
--   COALESCE(mca.parity_source, '') NOT LIKE 'tier1%'
-- Once a row's parity_source is set to a 'tier1_...' value, EVERY future run
-- of this function (hourly cron job 4103) permanently skips it, even if
-- parity_status is still stuck at 'tier1_only' with real linkage already
-- proven to exist in realforeclose_aids / foreclosure_outcomes /
-- tax_deed_outcomes. The function never re-evaluates rows it already
-- touched, so a row that was ever left at tier1_only can never be promoted.
--
-- REGRESSION CAUGHT + FIXED IN THE SAME SESSION (ULTRALOOP adversarial verify):
-- the first deployed version of this fix loosened the stale-row guard from
-- "parity_source NOT LIKE 'tier1%'" to "parity_status NOT IN
-- ('matched_clean','matched_divergent')" but left the parcel_id-equality
-- match branch unrestricted. Palm Beach's own data has ~15 rows across
-- multi_county_auctions/realforeclose_aids sharing literal placeholder
-- strings in the parcel_id column ('Property Appraiser', 'MULTIPLE
-- PARCELS' -- upstream scrape artifacts, not real parcel IDs). The loosened
-- guard let the parcel_id-equality branch promote 8 rows to matched_clean
-- purely because both sides carried the SAME placeholder string, with zero
-- real case_number or parcel corroboration for at least one of them
-- (502025CC012960XXXASB, independently confirmed to have no real linkage by
-- any method). This migration adds `AND mca.parcel_id ~ '^[0-9]{8,}$'` to
-- the parcel_id-equality branch so only real numeric parcel folios can
-- satisfy that match path; case_number-based matching (the two other OR
-- branches) is untouched and unaffected. The 8 falsely-promoted rows were
-- reverted to tier1_only live during this session; on re-run, 7 of the 8
-- were correctly re-promoted via genuine case_number matches (verified) and
-- 1 (502025CC012960XXXASB, the one with no real linkage by any method)
-- correctly remained at tier1_only.
--
-- Confirmed originally-stuck rows (VERIFIED via SELECT before this
-- migration): 502025CA005317XXXAMB, 502025CA000880XXXAMB,
-- 502025CA008769XXXAMB -- all 3 have identical linkage in realforeclose_aids
-- (case_number AND real numeric parcel_id match) plus agreeing
-- foreclosure_outcomes AND tax_deed_outcomes rows (outcome='sold' in both,
-- matching auction_date). No conflicting data found for these 3 rows.
--
-- Fix strategy: ALTER the function so it self-heals on next hourly cron run
-- (job 4103), instead of a one-off UPDATE that would just regress again.
-- Final live metric (VERIFIED, post-correction): palm_beach C (matched_clean)
-- 465->475 of 688 (67.6%->69.0%), D (matched_any) 468->478 (68.0%->69.5%).
-- Both remain FAIL (<95% threshold) -- the residual gap is a genuine data
-- ceiling (upcoming auctions with no real counterpart yet), not a matcher bug.

CREATE OR REPLACE FUNCTION public.refresh_palm_beach_parity_v2()
 RETURNS TABLE(path text, rows_updated integer)
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_rfa INTEGER := 0;
    v_tdm INTEGER := 0;
    v_rfa_exists BOOLEAN;
BEGIN
    SELECT EXISTS(
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'realforeclose_aids' AND n.nspname = 'public'
    ) INTO v_rfa_exists;

    IF v_rfa_exists THEN
        UPDATE public.multi_county_auctions mca
        SET parity_status = 'matched_clean',
            parity_source = 'tier1_realforeclose_palm_beach',
            updated_at = now()
        FROM public.realforeclose_aids ra
        WHERE ra.county_slug IN ('palm_beach','palm-beach','palmbeach')
          AND lower(mca.county) = 'palm_beach'
          AND (
              public.normalize_case_number(mca.case_number) = public.normalize_case_number(ra.case_number)
              OR (LENGTH(public.normalize_case_number(mca.case_number)) >= 10
                  AND LENGTH(public.normalize_case_number(ra.case_number)) >= 8
                  AND public.normalize_case_number(mca.case_number)
                      LIKE '%' || public.normalize_case_number(ra.case_number) || '%')
              OR (mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL AND mca.parcel_id = ra.parcel_id
                  AND mca.parcel_id ~ '^[0-9]{8,}$')
          )
          AND COALESCE(mca.parity_status, '') NOT IN ('matched_clean', 'matched_divergent');
        GET DIAGNOSTICS v_rfa = ROW_COUNT;
    END IF;

    UPDATE public.multi_county_auctions mca
    SET parity_status = 'matched_clean',
        parity_source = 'tier1_realtdm_palm_beach',
        tier1_sold_amount = CASE
            WHEN pr.surplus_balance ~ '^[0-9]+(\.[0-9]+)?$' THEN pr.surplus_balance::NUMERIC
            ELSE mca.tier1_sold_amount END,
        updated_at = now()
    FROM public.palm_beach_realtdm_raw pr
    WHERE public.normalize_case_number(mca.case_number) = public.normalize_case_number(pr.case_number)
      AND lower(mca.county) = 'palm_beach'
      AND COALESCE(mca.parity_status, '') NOT IN ('matched_clean', 'matched_divergent');
    GET DIAGNOSTICS v_tdm = ROW_COUNT;

    RETURN QUERY SELECT 'realforeclose_aids'::TEXT, v_rfa
    UNION ALL SELECT 'palm_beach_realtdm_raw'::TEXT, v_tdm;
END; $function$
;

-- Immediately re-run to self-heal confirmed stuck rows with real linkage.
SELECT public.refresh_palm_beach_parity_v2();
