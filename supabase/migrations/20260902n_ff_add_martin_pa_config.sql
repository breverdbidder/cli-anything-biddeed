-- Issue #19747: FF 7dd22ccb (case 25001204CAAXMX, Martin County, co_no 53)
-- rendered "NOT VERIFIED -- No property appraiser URL on file for this
-- county" because public.fl_property_appraiser_configs (the table
-- ff_get_lead's `verification.appraiser_url` actually reads, see
-- 20260901f_ff_appraiser_deep_link_broward_p0.sql) has no martin row, and
-- public.fl_counties.appraiser_url (the fallback) is also null for martin
-- (co_no=53) -- both confirmed live before writing this migration.
--
-- Deviation from the issue body, logged per CC_META_PROMPT 2.3 (the DoD
-- query/URL itself may be wrong -- verify, don't silently trust):
-- the brief's suggested parcel_url_template path was
-- `/search/real-property?search={{FOLIO}}&searchField=pin&exact=true`
-- (no `/app` prefix). Live-curled 2026-09-02: that path 404s. The real
-- search app lives at `/app/search/real-property` (confirmed via the
-- pamartinfl.gov homepage nav, which links to `/app/search/real-property`).
-- With the `/app` prefix and the brief's own query params, a plain GET (no
-- JS, no Playwright) returns the exact record embedded server-side in a
-- `window.initialState` JSON blob -- verified for this exact case's PCN:
--   PIN 27-38-40-002-000-00420-9 -> PrimaryOwner "APOSTOL NICHOLAS",
--   SitusAddress "5755 SW RANCHITO ST PALM CITY FL", TotalMarketValue
--   1528180 -- matches public.fl_parcels for this parcel (own_name
--   'APOSTOL NICHOLAS', phy_addr1 '5755 SW RANCHITO ST'). HTTP 200, plain
--   curl, no cert bypass, no cookies required.
-- platform is recorded as 'php_ajax_search_get' rather than the brief's
-- suggested 'joomla_search_get' -- the outer pamartinfl.gov site is
-- Joomla-templated (nav links through /component/search/), but the actual
-- property-search app at /app/search/ is a bespoke PHP/jQuery AJAX app
-- (window.ROOT_URL = "/app/search"), not Joomla itself. This field isn't
-- read anywhere else in the codebase (informational only) -- corrected here
-- rather than writing a label known to be inaccurate.
--
-- GIS fallback (not wired as parcel_url_template -- stored as a documented
-- alternate in known_issues per the brief): https://geoweb.martin.fl.us/general/?pcn={{FOLIO}}
-- Live-curled 2026-09-02: HTTP 200 (a map-viewer shell; not verified beyond
-- reachability since the primary deep link already returns full data).

INSERT INTO public.fl_property_appraiser_configs
    (county_slug, appraiser_url, search_method, platform, needs_js, blocked_by_waf, parcel_url_template, known_issues)
VALUES (
    'martin',
    'https://www.pamartinfl.gov/',
    'pin_get',
    'php_ajax_search_get',
    false,
    false,
    'https://www.pamartinfl.gov/app/search/real-property?search={{FOLIO}}&searchField=pin&exact=true',
    'Live-verified 2026-09-02 (issue #19747) for PIN 27-38-40-002-000-00420-9: plain GET, no JS/Playwright needed -- the record is embedded server-side in a window.initialState JSON blob even though display rendering is client-side jQuery. The brief''s originally-suggested path (/search/real-property, no /app prefix) 404s -- corrected to /app/search/real-property, confirmed via the site''s own nav links. GIS fallback (not wired as the primary template, PCN deep-links by parcel): https://geoweb.martin.fl.us/general/?pcn={{FOLIO}} -- HTTP 200, map-viewer shell, reachability-only check.'
)
ON CONFLICT (county_slug) DO UPDATE SET
    appraiser_url = EXCLUDED.appraiser_url,
    search_method = EXCLUDED.search_method,
    platform = EXCLUDED.platform,
    needs_js = EXCLUDED.needs_js,
    blocked_by_waf = EXCLUDED.blocked_by_waf,
    parcel_url_template = EXCLUDED.parcel_url_template,
    known_issues = EXCLUDED.known_issues,
    updated_at = now();

-- public.county_appraiser_urls is a separate table (read by src/worker.js,
-- NOT by ff_get_lead) that already had a martin row pointing at the county
-- government homepage (no parcel deep link) -- fixed here for data-hygiene
-- consistency per the issue body, even though it is not the table this
-- FF's "no URL on file" defect was actually caused by.
UPDATE public.county_appraiser_urls
SET appraiser_url = 'https://www.pamartinfl.gov/',
    parcel_search_pattern = '/app/search/real-property?search={pin}&searchField=pin&exact=true'
WHERE county_slug = 'martin';
