-- GOLD STANDARD shard-1 (brevard/sumter/citrus/madison), dispatch 2f4312f9-1601-4103-8c7e-0eeb036ac834
-- Continuation: real address backfill for brevard letter I (residual priority #2 from the
-- session report already shipped this session, GOLD_STANDARD_SHARD1_BREVARD_SUMTER_CITRUS_MADISON_DISPATCH_2f4312f9_SESSION_REPORT.md).
--
-- CONTEXT: earlier this session, 2,122 UNKNOWN-placeholder property_address values were
-- purged from multi_county_auctions (brevard), correctly flipping I from a false 96.1%
-- PASS to an honest 67.4% FAIL (4865/7215). This migration recovers real addresses for
-- the subset of those rows where a genuine (non-placeholder) BCPAO street address is
-- available, joining via the tax account number.
--
-- SOURCE: public.parcel_cache, joined multi_county_auctions.parcel_id = parcel_cache.tax_acct
-- (parcel_cache.tax_acct is the BCPAO account-number identifier, matching the format of
-- multi_county_auctions.parcel_id for brevard -- confirmed live: parcel_cache.parcel_id
-- itself is the STRAP identifier, a different format, NOT the join key here).
--
-- HONESTY GUARD (VERIFIED live before writing): parcel_cache carries the SAME
-- UNKNOWN-placeholder poison found in multi_county_auctions -- 1,377 of 2,063 matched
-- rows have street_name/street_number literally 'UNKNOWN'. Naively concatenating would
-- have reintroduced the exact ghost-success pattern purged earlier this session. Filtered
-- those out explicitly. Of 2,278 total brevard rows missing property_address, 2,121 have
-- a real (non-SYN) parcel_id, 2,063 of those match parcel_cache by tax_acct, and only
-- 680 have genuinely real (non-UNKNOWN, non-blank) street_number + street_name -- those
-- 680 are backfilled here. The remaining ~1,598 gap rows have no real address available
-- in any table currently loaded (parcel_cache is UNKNOWN-poisoned for them; fl_parcels_addr_lookup
-- has zero co_no=5/Brevard coverage; public.parcels ATTOM-style table matched only 4 rows;
-- bcpao_results is empty) -- they remain a genuine, honestly-reported FAIL requiring a live
-- BCPAO ArcGIS re-scrape, out of this migration's scope.

UPDATE public.multi_county_auctions m
SET property_address = addr.built
FROM (
  SELECT m2.id,
    btrim(regexp_replace(
      coalesce(p.street_number,'') || ' ' || coalesce(nullif(btrim(p.street_dir),''),'') || ' ' ||
      coalesce(p.street_name,'') || ' ' || coalesce(p.street_type,'') || ', ' ||
      btrim(coalesce(p.city,'')) || ', FL ' || coalesce(p.zip_code,'')
    , '\s+', ' ', 'g')) AS built
  FROM public.multi_county_auctions m2
  JOIN public.parcel_cache p ON p.tax_acct::text = m2.parcel_id
  WHERE lower(m2.county) = 'brevard'
    AND m2.property_address IS NULL
    AND m2.parcel_id IS NOT NULL
    AND p.street_name IS NOT NULL AND btrim(p.street_name) <> '' AND upper(p.street_name) NOT LIKE '%UNKNOWN%'
    AND p.street_number IS NOT NULL AND btrim(p.street_number) <> '' AND upper(p.street_number) NOT LIKE '%UNKNOWN%'
) addr
WHERE m.id = addr.id;
