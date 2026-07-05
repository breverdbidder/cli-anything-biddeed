-- Escambia C/D parity fix (run3025 track: escambia criteria C/D)
--
-- Diagnosis: of the 266 tier1-eligible escambia rows, 76 had parity_status
-- IS NULL going in (12 foreclosure, 64 tax_deed). ZERO of those 76 existed in
-- public.realforeclose_aids for county_slug='escambia' beforehand — a genuine
-- scrape-coverage gap in realforeclose_aids, not a join/normalization bug
-- (confirmed same-session by exhaustively checking every escambia auction
-- date the site currently exposes).
--
-- RESOLVED (12 of 76, all foreclosure): live-scraped
-- escambia.realforeclose.com via scripts/realforeclose_aids_paginated_harvest.py
-- for each of the 12 foreclosure cases' exact auction_date. All 12 matched
-- cleanly by case_number, with parcel_id from the live scrape confirmed
-- byte-identical to the parcel_id already stored in multi_county_auctions
-- (independent corroboration, not a coincidental id collision). Inserted into
-- realforeclose_aids with county_slug='escambia'.
--
-- NOT RESOLVED (64 of 76, all tax_deed) — genuinely unretrievable right now:
-- escambia.realtaxdeed.com only exposes ONE forward chain of auction dates via
-- its own Previous/Next Auction navigation: 07/01/2026 -> 08/05/2026 (current)
-- -> 09/02/2026 -> 10/07/2026 -> 11/04/2026 -> 12/02/2026. All 64 target case
-- numbers were checked against the FULL, exhaustively-paginated (AREA=W and
-- AREA=C, stagnant-cutoff verified stable well past normal termination)
-- listing for every one of those 6 dates. Zero matches on any date, in either
-- area. These 64 rows were written by data_source='calendar_sweep_mca_v3' with
-- auction_date=one of (08/05, 09/02, 10/07, 11/04)/2026 and last_seen_at =
-- 2026-07-04T15:27:25Z (all 64 share the exact same timestamp, i.e. one prior
-- run) — but by 2026-07-05 (today, this session) none of them appear anywhere
-- on the live calendar for any date the site currently serves. Most likely
-- explanation: tax deed sales in FL commonly get redeemed/withdrawn/continued
-- between initial scheduling and the sale date, and calendar_sweep_mca.py's
-- own AREA=W-only pagination (see .github/scripts/calendar_sweep_mca.py:322,
-- 337, 350 — page_dir hardcoded to 1 on continuation pages, AREA never set to
-- 'C') means it may also have only ever seen a partial slice to begin with.
-- Whatever the original cause, these 64 case numbers are NOT present on the
-- live, unauthenticated RealAuction calendar today, and there is no
-- unauthenticated case-search endpoint on this platform (case-detail pages
-- and the Clerk's own document/case-search sites all redirect to a
-- login-gated splash page or a Cloudflare bot challenge — confirmed via
-- direct HTTP + WebFetch, both blocked). Deferred, not fabricated. Do not
-- force a match for these 64.
--
-- Mirrors refresh_broward_parity_v1 / refresh_palm_beach_parity_v1 pattern
-- (case-number match first; parcel_id fallback excluding known junk sentinel
-- values 'Property Appraiser' / 'MULTIPLE PARCELS' confirmed present in this
-- county's multi_county_auctions.parcel_id column).

CREATE OR REPLACE FUNCTION public.refresh_escambia_parity_v1()
 RETURNS TABLE(path text, rows_updated integer)
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_case INTEGER := 0;
  v_parcel INTEGER := 0;
BEGIN
  -- Path A: case-number match (unambiguous, must win over parcel-only match).
  UPDATE public.multi_county_auctions mca
  SET parity_status = 'matched_clean',
      parity_source = 'tier1_realforeclose_escambia',
      updated_at = now()
  FROM public.realforeclose_aids ra
  WHERE ra.county_slug = 'escambia'
    AND lower(mca.county) = 'escambia'
    AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR COALESCE(mca.tier1_authoritative,false) = true)
    AND normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
    AND normalize_case_number(mca.case_number) <> ''
    AND (mca.parity_status IS NULL OR mca.parity_status NOT IN ('matched_clean', 'matched_divergent'));
  GET DIAGNOSTICS v_case = ROW_COUNT;

  -- Path B: parcel_id fallback for rows the case-number pass couldn't resolve.
  -- Excludes known non-parcel sentinel values present in this county's data.
  UPDATE public.multi_county_auctions mca
  SET parity_status = 'matched_clean',
      parity_source = 'tier1_realforeclose_escambia',
      updated_at = now()
  FROM public.realforeclose_aids ra
  WHERE ra.county_slug = 'escambia'
    AND lower(mca.county) = 'escambia'
    AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR COALESCE(mca.tier1_authoritative,false) = true)
    AND mca.parcel_id IS NOT NULL
    AND ra.parcel_id IS NOT NULL
    AND mca.parcel_id = ra.parcel_id
    AND mca.parcel_id NOT IN ('Property Appraiser', 'TIMESHARE', 'MULTIPLE PARCELS')
    AND (mca.parity_status IS NULL OR mca.parity_status NOT IN ('matched_clean', 'matched_divergent'));
  GET DIAGNOSTICS v_parcel = ROW_COUNT;

  RETURN QUERY SELECT 'case_number'::TEXT, v_case
    UNION ALL SELECT 'parcel_id'::TEXT, v_parcel;
END;
$function$;
