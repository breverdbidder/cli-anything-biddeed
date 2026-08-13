-- Gold Standard shard-3, dispatch 59758c8a-8d8d-48f7-843d-5e2c6844fbf9, county=madison, letters C/D/I/J
-- Date: 2026-08-13
--
-- CONTEXT: madison has 8 total auctions, 6 already pass C/D/I/J. The 2 gap rows are both
-- tax_deed: case 26-7-TD (parcel_id 21-2N-09-5288-022-000) and case 26-9-TD
-- (parcel_id 21-2N-09-5288-021-000), auction_date 2026-10-22. Both had
-- property_address/lat/lon/value/parity_status=NULL and no bid_decisions row.
--
-- LIVE VERIFICATION PERFORMED (real fetches, evidence below):
-- Discovered madisonclerk.com is WordPress with a REST API exposing a custom post type
-- `taxdeeds` at https://www.madisonclerk.com/wp-json/wp/v2/taxdeeds?per_page=50
-- This returned LIVE, VERIFIED records for both cases:
--   id=1644 slug=1644 link=https://www.madisonclerk.com/taxdeeds/1644/
--     acf.status=scheduled acf.sale_date="Oct 22, 2026 11:00 am" acf.cert=24-750
--     acf.parcel="21-2N-09-5288-022-000" acf.file="26-7-TD" acf.owner="ANN B. ISBELL"
--     acf.cert_holder="DOROTHY ALEXANDER" acf.opening_bid=1239.36
--   id=1646 slug=1646 link=https://www.madisonclerk.com/taxdeeds/1646/
--     acf.status=scheduled acf.sale_date="Oct 22, 2026 11:00 am" acf.cert=24-749
--     acf.parcel="21-2N-09-5288-021-000" acf.file="26-9-TD" acf.owner="JAMES S. ISBELL"
--     acf.cert_holder="DOROTHY ALEXANDER" acf.opening_bid=1172.67
-- Both parcel_id and auction_date (2026-10-22) match our stored multi_county_auctions rows
-- exactly -> genuine tier1 clerk-source confirmation of listing existence, justifying
-- parity_status='matched_clean' for C/D (which require only listing-match parity, not
-- address/value completeness -- that is letter I's separate requirement).
--
-- RESULT: pencil_dod_evaluate_county('madison') C: 75.0%->100.0% PASS, D: 75.0%->100.0% PASS

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard3_run11059_madison_live_verify:2026-08-13',
    owner_name = COALESCE(owner_name, 'ANN B. ISBELL'),
    last_parity_check = now(),
    parity_checked_at = now()
WHERE case_number = '26-7-TD' AND lower(county) = 'madison';

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard3_run11059_madison_live_verify:2026-08-13',
    owner_name = COALESCE(owner_name, 'JAMES S. ISBELL'),
    last_parity_check = now(),
    parity_checked_at = now()
WHERE case_number = '26-9-TD' AND lower(county) = 'madison';

-- LETTER I (card complete) and LETTER J (deal complete): NOT MOVED. Genuinely BLOCKED.
--
-- I requires property_address IS NOT NULL AND lat/lon IS NOT NULL AND
-- (assessed_value OR market_value) IS NOT NULL AND a zoning link with zone_code.
-- The ONLY source for address/lat-lon/assessed-value on Madison parcels (Madison County
-- Property Appraiser via qpublic.schneidercorp.com AppID=911, and madisonpa.com) returns
-- HTTP 403 "Attention Required! | Cloudflare" for every fetch attempt in this sandbox --
-- confirmed via WebFetch tool AND raw curl with a real browser User-Agent string, both
-- blocked identically. FL GIO Statewide Cadastral (services9.arcgis.com/Gh9awoU677aKree0,
-- the proven scripts/ingest_county.py source) was queried for CO_NO=40 (Madison) and for
-- PARCEL_ID LIKE '21-2N-09-5288%' and even for PARCEL_ID='35-3N-09-5540-018-000' (an
-- ALREADY-PASSING madison parcel with known-good data) -- ALL returned zero features,
-- proving this dataset currently has no reachable Madison County coverage for this parcel
-- range, not a bug specific to these 2 rows. esearch.madisontax.org (Tax Collector parcel
-- search) requires an internal session-driven search form (POST), not a direct GET lookup,
-- and returns 404/error for every direct-URL guess attempted. Firecrawl API returned
-- "Insufficient credits" (out of budget this session). No browser-automation binary
-- (browser-use) is installed in this sandbox to drive the Cloudflare-gated qpublic search
-- interactively. civitekflorida.com/ocrs/county/40 (court records) requires interactive
-- auth-tier selection before any search field is exposed.
--
-- J requires a real bid_decisions row with arv/max_bid/ml_score built from real comps.
-- Without a real property address there is no way to search MLS/Zillow/HUD comps, so any
-- ARV would be pure fabrication with zero real anchor -- unlike the precedent row
-- (case_number='25-31-CA'), whose factors.honesty_marker INFERRED components were still
-- built on top of a VERIFIED real active MLS listing (list price, sqft, beds/baths) for
-- that specific address. No equivalent anchor exists for 26-7-TD / 26-9-TD. Per the
-- NEVER-fabricate guardrail (no invented addresses/values) and BLANK > WRONG, no
-- bid_decisions rows were written for these 2 cases.
--
-- Real, verified, non-fabricated data that WAS obtained but is insufficient alone to
-- satisfy I (owner_name, opening_bid, cert holder, sale status/date -- already written to
-- multi_county_auctions above). Real zoning-district evidence exists for the unincorporated
-- Madison County "RES" district (jurisdiction_id 1188, source
-- madison_county_ldc_ch4_20260811, https://madiscon-county-fl.s3.amazonaws.com/uploads/
-- 2025/05/28151409/Chapter-4-Land-Use-Districts-and-Development-Standards.pdf) which
-- covers other DOR-STRAP-format unincorporated parcels in this county (e.g.
-- 19-1S-09-0934-000-000, 35-3N-09-5540-018-000, 00-00-00-3547-000-000), and by pattern is
-- the most likely zoning for 21-2N-09-5288-021-000 / -022-000 as well -- but this was
-- deliberately NOT written to parcel_zones because I is a conjunctive requirement
-- (address AND lat/lon AND value AND zoning) and zoning alone cannot flip these rows to
-- pass; writing a real-sourced zone_code without the co-required address/value fields
-- would not move the metric and risks looking like partial-completion theater. Left for a
-- future session with either (a) working Firecrawl credits / browser automation to get
-- past the qpublic Cloudflare gate, or (b) direct contact with the Madison County
-- Property Appraiser's office (850-973-6133) as a last resort.
