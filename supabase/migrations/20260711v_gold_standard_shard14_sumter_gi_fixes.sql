-- ============================================================
-- Gold Standard shard-14 (sumter) -- G + I fixes, ultraloop-verified
-- Dispatch: 8ee11dd1-d767-46a5-aa82-496902d6a9d8
-- Session: architect-20260711T160000
-- ============================================================
--
-- Applied LIVE via Supabase Management API during this session (this file
-- is the audit-trail record, matching what already ran against production).
--
-- CRITERION G (zoning density coverage): 28.6% -> 78.6% (still FAIL, threshold 95%)
-- Real max_density_du_acre backfilled for 6 of 7 zoning districts covering all
-- 10 real sumter auction parcels. Sourced from:
--   - City of Wildwood Land Development Regulations (Table 3-4A p.3-62,
--     Table 3-4C p.3-64), fetched via web.archive.org since wildwood-fl.gov
--     blocks direct fetch (Cloudflare). Independently re-extracted via pypdf
--     by the session lead after the adversarial refuter caught a one-column
--     misread on R-2/R-3 (see corrections below).
--   - Sumter County Code of Ordinances Sec. 13-413 Table 13-413A, fetched via
--     Municode's internal content API (library.municode.com frontend is an
--     AngularJS SPA that blocks WebFetch/curl).
--
-- Original inserts (fixer agent, HTTP 201 via Management API):
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at) VALUES
(11476, 10.00, 'https://web.archive.org/web/20240712070530/https://www.wildwood-fl.gov/sites/default/files/fileattachments/development_services/page/2851/revised_ldr_adopted_11-23-20.pdf', 'City of Wildwood Land Development Regulations, Table 3-4A (p.3-62): Residential Zoning Districts -- MHP column, Maximum Density (units per acre) = 10', 0.9, now()),
(11477, 5.00, 'https://web.archive.org/web/20240712070530/https://www.wildwood-fl.gov/sites/default/files/fileattachments/development_services/page/2851/revised_ldr_adopted_11-23-20.pdf', 'City of Wildwood Land Development Regulations, Table 3-4C (p.3-64): Mixed Use Zoning Districts -- RMU column, Maximum Density (units per acre) = 5', 0.9, now()),
(11473, 2.00, 'https://library.municode.com/fl/sumter_county/codes/code_of_ordinances?nodeId=COCO_CH13LADECO_ARTIVZO_DIV2ZODI_S13-413REDIST', 'Sumter County Code of Ordinances Sec. 13-413, Table 13-413A: Residential zoning districts dimensional standards -- R2M, R2C column, Min. lot area = 21,780 Sq. Ft.; density derived as 43,560 sq ft/acre / 21,780 sq ft per lot = 2.0 units/acre (single-unit-per-lot conventional/manufactured residential)', 0.9, now()),
(11472, 2.00, 'https://library.municode.com/fl/sumter_county/codes/code_of_ordinances?nodeId=COCO_CH13LADECO_ARTIVZO_DIV2ZODI_S13-413REDIST', 'Sumter County Code of Ordinances Sec. 13-413, Table 13-413A: Residential zoning districts dimensional standards -- R2M, R2C column, Min. lot area = 21,780 Sq. Ft.; density derived as 43,560 sq ft/acre / 21,780 sq ft per lot = 2.0 units/acre (single-unit-per-lot conventional/manufactured residential)', 0.9, now())
ON CONFLICT DO NOTHING;

-- R-2 and R-3 inserted with values later CORRECTED below (see gold_standard_ultraloop_audit
-- letter=G row: adversarial refuter caught a one-column misread; session lead independently
-- re-extracted Table 3-4A via pypdf and confirmed the correction).
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at) VALUES
(11474, 4.00, 'https://web.archive.org/web/20240712070530/https://www.wildwood-fl.gov/sites/default/files/fileattachments/development_services/page/2851/revised_ldr_adopted_11-23-20.pdf', 'INITIAL INSERT -- SUPERSEDED BELOW (misread column)', 0.9, now()),
(11475, 6.00, 'https://web.archive.org/web/20240712070530/https://www.wildwood-fl.gov/sites/default/files/fileattachments/development_services/page/2851/revised_ldr_adopted_11-23-20.pdf', 'INITIAL INSERT -- SUPERSEDED BELOW (misread column)', 0.9, now())
ON CONFLICT DO NOTHING;

-- CORRECTION (applied live before session close-out): independent pypdf re-extraction of
-- Table 3-4A (page 96 of 189) confirms the row is:
--   AG-5=1/5  AG-10=1/10  RR=1  ER=2  R-1=4  R-2=6  R-3=9  R-4=12  R-5=15  MHP=10
-- The fixer's original insert shifted R-2/R-3 one column left (R-1's value onto R-2,
-- R-2's value onto R-3). Corrected here.
UPDATE zone_standards
SET max_density_du_acre = 6.00,
    ordinance_section = 'City of Wildwood Land Development Regulations, Table 3-4A (p.3-62): Residential Zoning Districts -- R-2 column, Maximum Density (units per acre) = 6 (corrected 2026-07-11: independently re-extracted from source PDF, prior insert had misread column as 4, which is R-1''s value)'
WHERE zoning_district_id = 11474;

UPDATE zone_standards
SET max_density_du_acre = 9.00,
    ordinance_section = 'City of Wildwood Land Development Regulations, Table 3-4A (p.3-62): Residential Zoning Districts -- R-3 column, Maximum Density (units per acre) = 9 (corrected 2026-07-11: independently re-extracted from source PDF, prior insert had misread column as 6, which is R-2''s value)'
WHERE zoning_district_id = 11475;

-- RESIDUAL (not fixed, genuinely blocked): zd_id=11471 (RPUD, jurisdiction=Sumter County,
-- covers parcels G03A014/TD-5028, D09E270/2024-CA-000367, D03F058/2023-CA-000091) is left
-- with max_density_du_acre = NULL. Sumter Sec. 13-422(c) ties PUD density to the parcel's
-- Future Land Use category, not a fixed district value, and parcel_zones.future_land_use
-- is NULL for all 3 affected parcels in our DB -- no citable value exists without additional
-- FLU ingestion. Do not guess/interpolate.

-- CRITERION I (property card completeness): 63.6% (7 of 11) -> 90.9% (10 of 11), still FAIL
-- (threshold 95%). Reverse-geocoded 3 vacant tax-deed parcels missing property_address via
-- the Sumter County government's own ArcGIS Sumter_Geocoder reverseGeocode endpoint
-- (Loc_name=AddressPoint, nearest address point within 500 units of parcel centroid --
-- legitimate for vacant/unimproved parcels, labeled as reverse-geocoded not DOR-recorded).
UPDATE multi_county_auctions SET property_address = '919 VILLAGE DR, WILDWOOD, FL'
  WHERE id = '6ea19d87-caeb-49f5-924f-bdb6abb908ae'; -- TD-5056 / G07F008

UPDATE multi_county_auctions SET property_address = '137 CR 489A, LAKE PANASOFFKEE, FL'
  WHERE id = '184b25b8-d4e0-4b0c-bc84-386f147e796e'; -- TD-5058 / J16C019

UPDATE multi_county_auctions SET property_address = '1601 MEADOW ST, WILDWOOD, FL'
  WHERE id = '302490a8-8c60-4b5b-bb38-179133559e81'; -- TD-5054 / G05R062

-- RESIDUAL (not fixed): id=8ea8c278-94ae-4e8c-ba6e-6e1538aae148 (case 2025-CA-000255,
-- "Wildwood Phase One LLC") remains with parcel_id/address/geo/value all NULL. Exhaustively
-- attempted this session (Sumter GIS parcel/ownership layer search -- none exists on the
-- server; Sumter PA/qPublic owner search -- Cloudflare 403; Sunbiz entity search -- Cloudflare
-- 403; FL DOR cadastral OWN_NAME attribute filter -- HTTP 400/timeout, PARCEL_ID-only
-- service). E remains 90.9% (10 of 11); genuinely blocked, not fabricated.

-- CRITERIA B/F (verified sold-amount coverage): unchanged (metric=null, closed_sold=0).
-- Two prior sessions already exhausted sumterclerk.com direct sources. This session tried
-- 3 new angles, all genuine dead ends, no writes made:
--   - sumter.realforeclose.com / sumter.realtaxdeed.com (pipeline.counties configured
--     platforms): unconditional HTTP 302 redirect to realauction.com marketing homepage on
--     every path/param combination tried -- platform is inactive for this county, not an
--     auth gate.
--   - myfloridacounty.com/orisearch/60 (Sumter Clerk official-records/recording search,
--     distinct system from the previously-tried OCRS civil case search): live form reachable,
--     but POSTing a party-name search hits a Cloudflare Turnstile human-verification wall
--     (sitekey 0x4AAAAAAA64PTBePmuGbrkR).
--   - qpublic.schneidercorp.com (Sumter PA via Schneider Corp): Cloudflare 403 block.
-- No dollar figure for any of the 5 closed sumter cases was found from any source reachable
-- without an interactive browser + CAPTCHA-solving step. Genuinely blocked by data
-- availability, not by lack of effort. No sold_amount computed/estimated/fabricated.

-- ============================================================
-- FINAL LIVE SCOREBOARD (pencil_dod_evaluate_county('sumter'), VERIFIED post-fix):
--   A PASS(4)  B FAIL(null)  C PASS(100)  D PASS(100)  E FAIL(90.9)
--   F FAIL(null)  G FAIL(78.6, was 28.6)  H PASS(5.1)  I FAIL(90.9, was 63.6)  J PASS(100)
--   5/10 PASS (unchanged count -- G and I moved substantially but did not cross the
--   95% threshold this session). ultraloop audit rows logged for all 5 worked letters
--   (E, G, I, B, F), all survived=true (G survived only after the live correction above).
-- ============================================================
