-- GOLD STANDARD shard-4 brevard, dispatch 09f985fc-69a6-48a7-9803-80e813b38d39
--
-- Letter I (card_complete) enrichment. Live re-scrape of FL DOR Statewide
-- Cadastral (CO_NO=15, full 345,999-parcel dump, ALT_KEY not server-side
-- filterable on this layer) cross-checked against Brevard County's own GIS
-- parcel layer (gis.brevardfl.gov, TaxAcct batch IN queries). Both sources
-- independently confirm ~1,350 of the ~1,588-row I gap are vacant-land
-- parcels with literal "UNKNOWN" street data at the source -- a genuine,
-- verified data-availability wall, not a scraping gap. See
-- GOLD_STANDARD_SHARD4_BREVARD_DISPATCH_09F985FC_SESSION_REPORT.md for the
-- full investigation, including a false-positive reverse-geocode result
-- caught and debunked by the ULTRALOOP adversarial verify pass.
--
-- Only 2 rows were legitimately mechanically enrichable this session: real
-- (non-UNKNOWN) property_address already present, missing lat/lon/value
-- only. Applied live via PostgREST scoped PATCH (per-row -- bulk
-- upsert-by-id via `Prefer: resolution=merge-duplicates` was attempted
-- first and rejected: Postgres validates the full implicit INSERT row
-- against NOT NULL columns before resolving ON CONFLICT, even for rows
-- that only ever take the UPDATE branch). Recorded here as the equivalent
-- SQL for audit trail; already applied at the time this file lands.

UPDATE public.multi_county_auctions
SET latitude = 28.585894616796587, longitude = -80.80002542259467, assessed_value = 182840.0
WHERE id = '05a90e38-62d9-4e50-b9a5-5bf94d7cab03'
  AND lower(county) = 'brevard';

UPDATE public.multi_county_auctions
SET latitude = 28.560698922834273, longitude = -80.81419787838264, assessed_value = 144050.0
WHERE id = '464c8c70-57c2-4285-b679-71f1a3eebe6c'
  AND lower(county) = 'brevard';
