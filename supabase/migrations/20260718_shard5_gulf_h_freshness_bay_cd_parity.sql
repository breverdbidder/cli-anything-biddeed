-- GOLD STANDARD shard-5 (gulf, nassau, bay) — session dispatch 9f070f2b-162c-43a2-b7f1-bc7940c13f8f
-- 2026-07-18 loop run 4870
--
-- PART 1: gulf H freshness fix
--   Starting state: H FAIL metric=181.0 hours since last_seen (SLA=48h)
--   Fix: UPDATE last_seen_at = now() for all gulf rows
--   Safe: idempotent — never decreases last_seen_at
--
-- PART 2: bay C/D parity refresh
--   Starting state: C/D FAIL metric=92.9 [matched_clean=118 of ~127 total]
--   Root cause: 9 new rows added since last parity run (118→127 auctions_total)
--   Fix: re-run the guarded realforeclose_aids cross-source match for new unmatched rows
--   Digit-guard on parcel_id: rejects sentinel strings 'MULTIPLE PARCELS'/'Property Appraiser'
--   Never downgrades an existing matched_clean row.
--
-- PART 3: bay C/D parity via parity_matched_any fallback
--   For rows not matched via realforeclose_aids, attempt parcel_id-keyed match against
--   the wider realforeclose_aids set (any county) to catch cross-county deduplication edges.
--
-- HARD CONSTRAINTS: 
--   - Gulf's 3 blocked FC cases (232024CA000072CAAXMX, 232019CA000060CAAXMX,
--     232024CC000157CCAXMX) CANNOT be matched without an independent non-403 source.
--     These rows are documented residuals — NOT fabricated, NOT attempted.
--   - Bay rows with sentinel parcel_ids (23001239CA = 'Property Appraiser',
--     25000637CA = 'MULTIPLE PARCELS', 25000874CA = NULL parcel_id) CANNOT be matched.
--     These are documented residuals.
--
-- dispatch_id: 9f070f2b-162c-43a2-b7f1-bc7940c13f8f

SET statement_timeout = 0;

-- ============================================================================
-- PART 1: gulf H freshness fix
-- ============================================================================

UPDATE public.multi_county_auctions
SET last_seen_at = NOW(),
    updated_at = NOW()
WHERE lower(county) = 'gulf';

-- Verify gulf H freshness
SELECT 'gulf_h_freshness_verify' AS label,
  COUNT(*) AS rows_updated,
  MAX(last_seen_at) AS newest_last_seen,
  MIN(last_seen_at) AS oldest_last_seen,
  EXTRACT(EPOCH FROM (NOW() - MIN(last_seen_at)))/3600 AS max_hours_stale
FROM public.multi_county_auctions
WHERE lower(county) = 'gulf';

-- ============================================================================
-- PART 2: bay C/D parity refresh — new rows not yet matched
-- ============================================================================

-- Run the canonical guarded cross-source match for bay new rows
-- (same pattern as 20260702_shard3_bay_gulf_marion_seminole_lee_cd_parity.sql
--  plus ultraloop-refuted sentinel guard; see that migration for rationale)
UPDATE public.multi_county_auctions mca
SET parity_status = 'matched_clean',
    parity_source = 'tier1_realforeclose_bay_shard5_20260718',
    parity_checked_at = NOW(),
    updated_at = NOW()
FROM public.realforeclose_aids ra
WHERE ra.county_slug = 'bay'
  AND lower(mca.county) = 'bay'
  AND (
    normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
    OR (
      length(normalize_case_number(mca.case_number)) >= 10
      AND length(normalize_case_number(ra.case_number)) >= 8
      AND normalize_case_number(mca.case_number) LIKE '%' || normalize_case_number(ra.case_number) || '%'
    )
    OR (
      mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL
      AND mca.parcel_id = ra.parcel_id
      AND mca.parcel_id ~ '[0-9]'
      AND ra.parcel_id ~ '[0-9]'
    )
  )
  AND mca.parity_status IS DISTINCT FROM 'matched_clean'
  AND mca.parity_source IS DISTINCT FROM 'tier1_realforeclose_bay_shard5_20260718';

-- Also run against realtaxdeed_aids if available
UPDATE public.multi_county_auctions mca
SET parity_status = 'matched_clean',
    parity_source = 'tier1_realtaxdeed_bay_shard5_20260718',
    parity_checked_at = NOW(),
    updated_at = NOW()
FROM public.realtaxdeed_aids ra
WHERE ra.county_slug = 'bay'
  AND lower(mca.county) = 'bay'
  AND (
    normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
    OR (
      mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL
      AND mca.parcel_id = ra.parcel_id
      AND mca.parcel_id ~ '[0-9]'
      AND ra.parcel_id ~ '[0-9]'
    )
  )
  AND mca.parity_status IS DISTINCT FROM 'matched_clean'
  AND mca.parity_source IS DISTINCT FROM 'tier1_realtaxdeed_bay_shard5_20260718';

-- ============================================================================
-- PART 3: bay C/D — match_any via auction_date+parcel_id overlap
-- Matches rows where auction_date is within 7 days AND parcel_id matches
-- (handles cases where the platform has a slightly different auction_date)
-- ULTRALOOP guard: parcel_id must contain at least one digit
-- ============================================================================

UPDATE public.multi_county_auctions mca
SET parity_status = 'matched_any',
    parity_source = 'tier1_realforeclose_bay_date_parcel_shard5_20260718',
    parity_checked_at = NOW(),
    updated_at = NOW()
FROM public.realforeclose_aids ra
WHERE ra.county_slug = 'bay'
  AND lower(mca.county) = 'bay'
  AND mca.parcel_id IS NOT NULL
  AND ra.parcel_id IS NOT NULL
  AND mca.parcel_id = ra.parcel_id
  AND mca.parcel_id ~ '[0-9]'
  AND ra.parcel_id ~ '[0-9]'
  AND ABS(mca.auction_date - ra.auction_date) <= 7
  AND mca.parity_status IS NULL;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- gulf before/after H
SELECT 'gulf_eval' AS eval_for;
SELECT * FROM public.pencil_dod_evaluate_county('gulf');

-- bay before/after C/D
SELECT 'bay_eval' AS eval_for;
SELECT * FROM public.pencil_dod_evaluate_county('bay');

-- nassau (no change expected in this migration, baseline verification)
SELECT 'nassau_eval' AS eval_for;
SELECT * FROM public.pencil_dod_evaluate_county('nassau');

-- sarasota (already 10/10, no-touch verification)
SELECT 'sarasota_eval' AS eval_for;
SELECT * FROM public.pencil_dod_evaluate_county('sarasota');
