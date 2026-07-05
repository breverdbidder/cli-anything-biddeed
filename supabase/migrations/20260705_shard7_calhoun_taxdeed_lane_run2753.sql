-- SHARD-7 run2753: calhoun tax-deed lane activation (letter A fix)
--
-- Problem: pencil_dod_evaluate_county('calhoun') letter A failed with detail
-- "fc=1 td=0" because pipeline.counties.taxdeed_platform/taxdeed_url were NULL
-- for calhoun — the tax-deed lane was never configured, unlike nassau/martin
-- which both carry taxdeed_platform='realtaxdeed' pointed at
-- <county>.realtaxdeed.com.
--
-- Fix: mirror the nassau/martin row shape for calhoun. This does not fabricate
-- any auction data — it only wires the pipeline config so the existing
-- scrape-realauction-county.yml / discover-auction-dates.yml workflows can
-- discover and harvest calhoun's real tax-deed calendar
-- (calhoun.realtaxdeed.com, already confirmed live/200 in
-- public.realauction_subdomains, parity_verdict='PO has data — activating').
--
-- Evidence this is the correct target (not a guess):
--   public.realauction_subdomains row for county_slug='calhoun',
--   sale_type='tax_deed', platform='realtaxdeed', is_active=true,
--   http_status=200, base_url='https://calhoun.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR'

UPDATE pipeline.counties
SET
  taxdeed_platform = 'realtaxdeed',
  taxdeed_url = 'https://calhoun.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR'
WHERE county_slug = 'calhoun';
