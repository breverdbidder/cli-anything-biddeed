-- Gold Standard shard-2: LEE + LAKE letter E (parcel_id linkage >=95%)
-- Session: 2026-08-03. Applied LIVE via Supabase Management API SQL endpoint
-- (curl -X POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query)
-- because psql/pooler password auth is broken in this runner (SUPABASE_DB_PASSWORD
-- auth fails) -- `supabase db push` / CLI was unavailable this session.
--
-- SCOPE (per row-level filter used by pencil_dod_evaluate_county for E):
--   lower(county)='lee'|'lake' AND (data_source <> 'propertyonion' OR tier1_authoritative=true)
--
-- LEE: 18 unlinked rows (of 322 total). 3 had a non-null property_address:
--   - 18-CC-004510  "98 SABLE DR LOT 98, NORTH FORT MYERS, FL- 33917"
--   - 24-CC-004249  "16300 PINE RIDGE RD LOT X18, FORT MYERS , FL- 33908"
--   - 25-CA-004959  "2825 PALM BEACH BLVD, FORT MYERS, FL 33916"
--
-- RESULT (VERIFIED via live Lee County ArcGIS FeatureServer queries):
--   18-CC-004510  MATCHED. The standard Lee_County_Parcels FeatureServer has no
--     "SABLE DR" street at all (only CAPE SABLE LN / SABLE KEY CIR / SABLE CT).
--     Found instead via the Lee County MobileHomeLots FeatureServer
--     (services2.arcgis.com/LvWGAAhHwbCJ2GMP/.../MobileHomeLots/FeatureServer/0):
--     ParkName='ISLAND VISTA ESTATES', LotNumber='98', SiteAddr='98 SABLE DR',
--     SITECITY='NORTH FORT MYERS', STRAP='22432400000020000'. That STRAP was
--     cross-verified against the main Lee_County_Parcels layer: it is the real
--     master parcel (owner 'ISLAND VISTA ESTATES LLC +', SITEADDR '3000 N
--     TAMIAMI TRL') for the whole landlord-owned mobile home community -- the
--     individual lots do not have separate real-property STRAPs, so the park's
--     master parcel is the correct and only valid parcel_id for this address.
--   24-CC-004249  NOT MATCHED (structural block). "16300 Pine Ridge Rd" is
--     confirmed via public listing sites (Zillow/Apartments.com/Trulia/Redfin,
--     all showing unit labels like X33/Y32/V12 matching the "LOT X18" pattern)
--     to be "Pine Ridge Palms", a 55+ leasehold mobile home rental community.
--     It does NOT appear in Lee_County_Parcels (SITEADDR/SITESTREET) nor in
--     MobileHomeLots (ParkName LIKE '%PINE%RIDGE%' -> 0 rows; SiteAddr LIKE
--     '16300%' -> 0 rows). No real-property STRAP exists for this address in
--     Lee County's own GIS data -- cannot fabricate a match.
--   25-CA-004959  NOT MATCHED (ambiguous, refused to guess). Address matches
--     "ALTA MAR" condominium at 2825 Palm Beach Blvd (141 units per public
--     listing sites). ArcGIS query for SITENUMBER=2825/SITESTREET=PALM BEACH
--     BLVD returns 10 distinct unit STRAPs (RFU1-RFU8, CU01) plus one Common
--     Elements STRAP -- but the case's stored property_address carries no unit
--     number, so there is no way to determine which of the 10 units is the
--     actual foreclosure subject without the case docket. Docket lookup was
--     attempted (see LAKE section below for the identical tooling blocker) and
--     failed -- leeclerk.org / matrix.leeclerk.org returned HTTP 403 / no
--     response from this sandbox for every hostname tried. Left unmatched
--     rather than guess a unit and risk a false parcel_id.
--
--   The remaining 15 Lee rows with NULL property_address (17-CA-003958,
--   25-CA-000630, 25-CA-001853, 25-CA-003243, 25-CA-003281, 25-CA-003295,
--   25-CA-003836, 25-CA-004751, 25-CA-004836, 25-CA-005293, 25-CA-006176,
--   25-CA-006956, 25-CA-007015, 25-CA-007139, 25-CC-010740 -- re-queried live
--   this session, confirming 15 rows, 2 more than the 13 originally listed in
--   the task, i.e. 25-CA-003281 and 25-CA-003295 newly appeared) require a
--   Lee Clerk docket lookup to recover an address before any parcel match is
--   possible. leeclerk.org, matrix.leeclerk.org, or.leeclerk.org, and
--   civil.leeclerk.org were all tried directly via curl and via the WebFetch
--   tool from this session: leeclerk.org returns HTTP 403, the others return
--   no response (DNS/connection failure) from this sandbox's network egress.
--   No browser-automation tool was available in this session (browser-use
--   skill has no backing tool registered) to drive the JS-rendered case
--   search. RESULT: 0 of 15 recovered. This is a genuine tooling/network
--   blocker for this session, not a refusal.
--
-- LAKE: 30 unlinked rows (of 110 total), ALL NULL property_address, all
--   data_source='lake_clerk_foreclosure_calendar_v1'. Re-queried live this
--   session -- confirmed all 30 case numbers from the task match exactly.
--   Same recovery attempt: Lake Clerk's case-record portal
--   (courtrecords.lakecountyclerk.org/showcaseweb/, Equivant ShowCase Web) IS
--   reachable at the HTTP level (200) from this sandbox, unlike leeclerk.org,
--   but it is an Angular SPA with no accessible non-JS search API -- probed
--   api/CaseSearch, api/case/search, ShowCaseSearchAPI/api/CaseSearch,
--   api/v1/case, odata/Cases, api/Search/CaseSearch, CoreOData/Case; all
--   either SPA-fallback 200s with no case data or empty bodies. The public
--   "Foreclosure Sales Calendar" page (lakecountyclerkfl.gov) does not expose
--   case numbers/addresses in fetchable page content (calendar is itself
--   dynamic/PDF-linked). realauction.com and lake.realforeclose.com (the
--   other common source for FL foreclosure-calendar case detail pages) return
--   HTTP 403 from this sandbox. WebSearch for individual case numbers
--   (e.g. "2025CA002823", "2024CA002312") returned zero indexed hits.
--   RESULT: 0 of 30 recovered. Same root cause as the Lee bare-docket rows:
--   no browser-automation tool available to drive the JS-rendered clerk
--   portal, and every non-JS fallback path is either blocked or has no data.
--
-- NET CHANGE THIS SESSION: 1 Lee row (18-CC-004510) parcel-linked.
--   Lee E: 304/322 (94.4%) -> 305/322 (94.7%) -- still FAIL (<95% threshold,
--   needs 306/322 = 95.03% to pass). Lake E: unchanged, 80/110 (72.7%).

BEGIN;

UPDATE public.multi_county_auctions
SET parcel_id = '22432400000020000',
    updated_at = now()
WHERE county = 'lee'
  AND case_number = '18-CC-004510'
  AND parcel_id IS NULL;

COMMIT;
