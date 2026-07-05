-- Broward C/D parity fix (run3025 track: broward criteria C/D)
--
-- Diagnosis: of 179 unmatched tier1-eligible broward rows, only 12 had a
-- legitimate match against public.realforeclose_aids BEFORE this fix (matcher
-- did not exist yet). Root cause was overwhelmingly a scrape-coverage gap:
-- realforeclose_aids had zero rows for broward's Jan-Apr 2026 (+ 07/08/2026)
-- auction dates. Backfilled via scripts/realforeclose_aids_paginated_harvest.py
-- against broward.realforeclose.com for the 44 missing auction dates
-- (601 rows inserted/merged), which raised the legitimate-match count from
-- 12/179 to 175/179.
--
-- Landmine found + guarded against: both multi_county_auctions and
-- realforeclose_aids contain junk sentinel values in parcel_id
-- ('Property Appraiser', 'TIMESHARE', 'MULTIPLE PARCELS') that are NOT real
-- parcel numbers. A naive parcel_id equality match would false-positive
-- match unrelated cases sharing one of these sentinels (confirmed live:
-- CACE-24-004661 vs CACE-25-000988, both parcel_id='MULTIPLE PARCELS').
-- This function explicitly excludes those sentinels from the parcel-match arm.
--
-- Mirrors refresh_palm_beach_parity_v1 pattern (case-number match first,
-- unambiguous; parcel_id fallback only for non-sentinel real folio values).
--
-- Second correction: 46 rows carried parity_status='matched_divergent' from
-- the PRE-EXISTING generic refresh_parity_for_mca() function, which compares
-- multi_county_auctions against PropertyOnion (po_listings/po_mca_matches) --
-- litmus-only per ground rules, never authoritative for C/D. All 46 of those
-- rows DO have a clean case-number match against realforeclose_aids (verified
-- live query), so the "divergent" label is a PropertyOnion-vs-us artifact, not
-- a realforeclose-vs-us divergence. The function therefore gates re-matching
-- on parity_source (has THIS function already claimed the row?), not on
-- parity_status or on any other function's tier1-prefixed source tag.

CREATE OR REPLACE FUNCTION public.refresh_broward_parity_v1()
 RETURNS TABLE(path text, rows_updated integer)
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_case INTEGER := 0;
  v_parcel INTEGER := 0;
BEGIN
  -- Path A: case-number match (unambiguous, must win over parcel-only match).
  -- Gate on parity_status, not parity_source: rows previously classified by
  -- the generic PropertyOnion-based refresh_parity_for_mca as 'mca_only' or
  -- 'tier1_only' carry parity_source='tier1_parity_6county_beta_20260623'
  -- even though they are NOT matched against our tier1 realforeclose source
  -- (that source is PropertyOnion, litmus-only, never authoritative for C/D).
  -- Gating on parity_source would silently skip all of them.
  UPDATE public.multi_county_auctions mca
  SET parity_status = 'matched_clean',
      parity_source = 'tier1_realforeclose_broward',
      updated_at = now()
  FROM public.realforeclose_aids ra
  WHERE ra.county_slug = 'broward'
    AND lower(mca.county) = 'broward'
    AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR COALESCE(mca.tier1_authoritative,false) = true)
    AND normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
    AND normalize_case_number(mca.case_number) <> ''
    AND COALESCE(mca.parity_source, '') <> 'tier1_realforeclose_broward';
  GET DIAGNOSTICS v_case = ROW_COUNT;

  -- Path B: parcel_id fallback for rows the case-number pass couldn't resolve.
  -- Excludes known non-parcel sentinel values present in both tables.
  UPDATE public.multi_county_auctions mca
  SET parity_status = 'matched_clean',
      parity_source = 'tier1_realforeclose_broward',
      updated_at = now()
  FROM public.realforeclose_aids ra
  WHERE ra.county_slug = 'broward'
    AND lower(mca.county) = 'broward'
    AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR COALESCE(mca.tier1_authoritative,false) = true)
    AND mca.parcel_id IS NOT NULL
    AND ra.parcel_id IS NOT NULL
    AND mca.parcel_id = ra.parcel_id
    AND mca.parcel_id NOT IN ('Property Appraiser', 'TIMESHARE', 'MULTIPLE PARCELS')
    AND COALESCE(mca.parity_source, '') <> 'tier1_realforeclose_broward';
  GET DIAGNOSTICS v_parcel = ROW_COUNT;

  RETURN QUERY SELECT 'case_number'::TEXT, v_case
    UNION ALL SELECT 'parcel_id'::TEXT, v_parcel;
END;
$function$;
