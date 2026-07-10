-- SHARD-3 run2886 (charlotte/highlands/volusia/manatee/liberty), 2026-07-04
--
-- Highlands pipeline.counties row was auto-seeded 2026-05-20 as a placeholder
-- (foreclosure_platform/taxdeed_platform NULL, pipeline_status='pending',
-- pipeline_health='inactive') even though public.realauction_subdomains already
-- has both FQDNs verified live (is_active=true, http_status=200,
-- last_verified='2026-05-24'):
--   highlands.realforeclose.com  (sale_type=foreclosure)
--   highlands.realtaxdeed.com    (sale_type=tax_deed)
-- This left the county unwired for the county-outcome-harvest.yml workflow
-- despite discovery data already proving the endpoints exist. Wiring config
-- only — no fabricated counts, no auction data touched here.

UPDATE pipeline.counties
SET
  foreclosure_platform = 'realforeclose',
  foreclosure_url       = 'https://highlands.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR',
  taxdeed_platform      = 'realtaxdeed',
  taxdeed_url           = 'https://highlands.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR',
  pipeline_status       = 'active',
  pipeline_health       = 'healthy',
  notes                 = notes || ' | SHARD-3 run2886 2026-07-04: wired from verified realauction_subdomains (highlands.realforeclose.com + highlands.realtaxdeed.com, last_verified 2026-05-24)'
WHERE county_slug = 'highlands';
