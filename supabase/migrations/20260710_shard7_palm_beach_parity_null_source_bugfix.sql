-- SHARD-7 (palm_beach) — fix NULL-parity_source exclusion bug in refresh_palm_beach_parity_v2
--
-- CONFIRMED live (2026-07-10, dispatch 1f745e08-bd71-4f6d-819c-545205fed32e): the function's
-- WHERE clause used `mca.parity_source NOT LIKE 'tier1%'` to skip already-matched rows. In
-- Postgres, `NULL NOT LIKE 'tier1%'` evaluates to NULL, which WHERE treats as false — so every
-- row with parity_source IS NULL (never matched at all) was silently excluded from ever being
-- matched by this function. Verified via direct JOIN against realforeclose_aids: 61 of the 268
-- palm_beach parity-gap rows have a real case_number match sitting in realforeclose_aids that
-- this bug prevented from ever being applied.
--
-- Fix: wrap parity_source in COALESCE so NULL rows are correctly treated as "not yet tier1".
-- Same NULL-trap existed in the tax-deed branch; fixed identically. Idempotent, additive only.

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
              OR (mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL AND mca.parcel_id = ra.parcel_id)
          )
          AND COALESCE(mca.parity_source, '') NOT LIKE 'tier1%';
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
      AND COALESCE(mca.parity_source, '') NOT LIKE 'tier1%';
    GET DIAGNOSTICS v_tdm = ROW_COUNT;

    RETURN QUERY SELECT 'realforeclose_aids'::TEXT, v_rfa
    UNION ALL SELECT 'palm_beach_realtdm_raw'::TEXT, v_tdm;
END; $function$;

-- WIRING MANDATE: this function existed but was never scheduled anywhere (confirmed via
-- `SELECT * FROM cron.job WHERE command ILIKE '%refresh_palm_beach_parity%'` returning zero
-- rows) — dead code accumulating unmatched rows forever. Wire it to run hourly. Guardrail #4
-- (do not modify cron jobs 109/111/115/gold-standard-loop-*) is respected — this is a new job.
SELECT cron.schedule('refresh-palm-beach-parity-hourly', '17 * * * *',
  $$SELECT refresh_palm_beach_parity_v2();$$);
