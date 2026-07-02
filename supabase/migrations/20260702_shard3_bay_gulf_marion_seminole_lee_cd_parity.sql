-- SHARD-3: bay, gulf, marion, seminole, lee -- C/D parity fix (foreclosure lane)
-- dispatch_id: 5bd50375-d8f8-4a8e-ae84-e791b393360f
-- Session: architect-20260702T160000
--
-- ROOT CAUSE (VERIFIED live 2026-07-02 via management API SQL + pencil_dod_evaluate_county):
-- none of these 5 counties has a dedicated parity-refresh function (unlike brevard's
-- refresh_parity_chunk or shard2's refresh_shard2_cd_tier1_v1 for pinellas/santa_rosa).
-- public.realforeclose_aids already holds independently-scraped FORECLOSURE-lane rows
-- for all 5 counties (bay=29, gulf=5, lee=77, marion=57, seminole=48) via the existing
-- scrape-realauction-county.yml pipeline, but nothing ever joined them back to
-- multi_county_auctions to stamp parity_status. TAX DEED lane has NO independent tier1
-- source yet for any of these 5 (realtaxdeed.com scraper has never been run against
-- them -- only brevard/walton have any TAXDEED rows in realforeclose_aids). That gap is
-- NOT closed by this migration; it requires a new scrape run (scrape-realauction-county
-- workflow, PLATFORM=realtaxdeed, SALE_TYPE=tax_deed, per-auction-date) and is flagged
-- for the next session rather than gamed here.
--
-- FIX: reuse the exact guarded cross-source match pattern from
-- refresh_shard2_cd_tier1_v1 (digit-guard on parcel_id rejects scraper-failure
-- sentinel strings like 'MULTIPLE PARCELS'/'Property Appraiser' that would otherwise
-- cross-match unrelated cases -- this guard exists because an earlier unguarded
-- version produced exactly that false-positive class, caught by ULTRALOOP refutation).
-- Only touches rows not already matched_clean; never downgrades an existing match.
--
-- Applied live 2026-07-02 via Supabase Management API (service role). This migration
-- is the idempotent record -- safe to re-run (all statements guarded by
-- parity_source IS DISTINCT FROM / parity_status IS DISTINCT FROM checks).

UPDATE public.multi_county_auctions mca
SET parity_status = 'matched_clean',
    parity_source = 'tier1_realforeclose_' || lower(mca.county),
    parity_checked_at = now(),
    updated_at = now()
FROM public.realforeclose_aids ra
WHERE ra.county_slug = lower(mca.county)
  AND lower(mca.county) IN ('bay','gulf','marion','seminole','lee')
  AND (
    normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
    OR (
      length(normalize_case_number(mca.case_number)) >= 10
      AND length(normalize_case_number(ra.case_number)) >= 8
      AND normalize_case_number(mca.case_number) LIKE '%' || normalize_case_number(ra.case_number) || '%'
    )
    OR (
      mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL AND mca.parcel_id = ra.parcel_id
      AND mca.parcel_id ~ '[0-9]' AND ra.parcel_id ~ '[0-9]'
    )
  )
  AND mca.parity_status IS DISTINCT FROM 'matched_clean'
  AND mca.parity_source IS DISTINCT FROM ('tier1_realforeclose_' || lower(mca.county));

-- ── VERIFICATION QUERIES (run after migration) ─────────────────────────────────────
-- SELECT public.pencil_dod_evaluate_county('bay');
-- SELECT public.pencil_dod_evaluate_county('gulf');
-- SELECT public.pencil_dod_evaluate_county('marion');
-- SELECT public.pencil_dod_evaluate_county('seminole');
-- SELECT public.pencil_dod_evaluate_county('lee');
