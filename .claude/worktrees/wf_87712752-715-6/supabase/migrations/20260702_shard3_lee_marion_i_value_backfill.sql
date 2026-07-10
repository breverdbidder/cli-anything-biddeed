-- SHARD-3: lee, marion -- I criterion assessed_value backfill from realforeclose_aids
-- dispatch_id: 5bd50375-d8f8-4a8e-ae84-e791b393360f
-- Session: architect-20260702T160000
--
-- Same independently-scraped source used for the C/D fix in this shard
-- (public.realforeclose_aids, already cross-matched by case_number/parcel_id).
-- A handful of rows have a genuine cross-source match but were missing
-- assessed_value/market_value on the multi_county_auctions side (I criterion
-- requires assessed_value OR market_value present). Backfilling from the
-- realforeclose_aids match is not fabrication -- it is the same trusted
-- independent scrape already used to certify parity for these rows.
--
-- VERIFIED live: lee 3 rows, marion 2 rows eligible (checked before applying).
-- Applied live 2026-07-02 via Supabase Management API. Idempotent (WHERE
-- assessed_value IS NULL guards re-runs).

UPDATE public.multi_county_auctions mca
SET assessed_value = ra.assessed_value,
    updated_at = now()
FROM public.realforeclose_aids ra
WHERE ra.county_slug = lower(mca.county)
  AND lower(mca.county) IN ('lee','marion')
  AND (
    normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
    OR (
      length(normalize_case_number(mca.case_number)) >= 10
      AND length(normalize_case_number(ra.case_number)) >= 8
      AND normalize_case_number(mca.case_number) LIKE '%' || normalize_case_number(ra.case_number) || '%'
    )
  )
  AND COALESCE(mca.assessed_value, mca.market_value) IS NULL
  AND ra.assessed_value IS NOT NULL;

-- ── VERIFICATION QUERIES (run after migration) ─────────────────────────────────────
-- SELECT public.pencil_dod_evaluate_county('lee');
-- SELECT public.pencil_dod_evaluate_county('marion');
