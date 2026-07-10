-- applied live already via Management API during session; migration file for audit trail
UPDATE multi_county_auctions
SET parcel_id = '3523039',
    property_address = '10806 E IRENE ST',
    city = 'INVERNESS', zip = '34450',
    assessed_value_source = 'realforeclose_aids:shard10_run3534'
WHERE lower(county)='citrus' AND case_number = '2025 CA 000569 A';

UPDATE multi_county_auctions
SET parcel_id = '1151457',
    property_address = '5360 S ELM AVE',
    city = 'HOMOSASSA', zip = '34448',
    assessed_value = 133292.0, market_value = 133292.0,
    latitude = 28.78376835879, longitude = -82.603865063298,
    assessed_value_source = 'realforeclose_aids:shard10_run3534 (assessed_value corrected from placeholder 180000); lat/lon from census.gov geocoder'
WHERE lower(county)='citrus' AND case_number = '2025 CA 000830 A';
INSERT INTO zoning_districts (jurisdiction_id, code, name, category)
VALUES (1327, 'CLR MH', 'Coastal/Lakes Residential - Mobile Home Allowed', 'residential')
ON CONFLICT DO NOTHING;

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES ('1151457', NULL, 1327, 'CLR MH', 'Coastal/Lakes Residential - Mobile Home Allowed',
  'citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (50m-buffer point-in-polygon, all 10 nearby parcels uniformly CLR MH, case 2025 CA 000830 A / shard10_run3534)')
ON CONFLICT DO NOTHING;
UPDATE pipeline.counties
SET notes = notes || E'\n| 2026-07-10 shard10 run3534 (dispatch 3a90abbe): re-probed both dead RealAuction tenants live -- okaloosa.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW... still 302-redirects to www.realauction.com marketing splash (HTTP 302, Location: http://www.realauction.com); tenant remains deprovisioned, NOT back. Confirmed Bid4Assets is the real live replacement: bid4assets.com/OkaloosaFL/listings server-renders ONE embedded Kendo grid row per page load (today''s nearest closing auction only, e.g. AuctionID 1286660 / CourtCase 2025-CA-001813-F / 4207 Indian Bayou Trl Destin -- confirms real live 2026 Okaloosa foreclosure data with full CourtCase+Address+DebtAmount+Plaintiff+Defendant fields). Grid transport read url is empty (no AJAX endpoint) -- data is embedded server-side per page render, NOT a queryable REST API. The header keyword search form posts GET to /search/redirect/get but resolves to a client-side SPA route (#t=ps|q=...) with Total:0 in the static HTML shell -- the actual result set loads via an XHR this runner cannot observe without a real browser (Firecrawl/Playwright). Our 2 existing okaloosa multi_county_auctions rows (case 2024-CA-000470 FC, 2024-TDD-000089 TD, both dated 2026-08-19) do NOT appear in Bid4Assets today-view and cannot be confirmed live via this method -- left untouched, not fabricated. NEXT SESSION: a Firecrawl/browser-capable runner should (a) load bid4assets.com/OkaloosaFL/listings and /OkaloosaFLTax/listings with JS execution to capture the full upcoming-auction grid (not just today''s row), (b) cross-check our 2 seed case numbers against that set, (c) only then attempt case-number-keyed detail scraping. Do not re-spend a non-Firecrawl session probing the search SPA further -- confirmed dead end this session.'
WHERE county_slug = 'okaloosa';
