-- Lake county, letter E (parcel_linked) — session audit + 1 real match applied.
--
-- Source of the write below: Lake County Property Appraiser ArcGIS FieldMap
-- MapServer (live, county-owned GIS service):
--   https://gis.lakecountyfl.gov/lakegis/rest/services/PropertyAppraiser/FieldMap/MapServer/0
-- Matched via the existing, proven owner-name matcher
-- scripts/shard14_lake_e_ownername_match.py (conservative surname-position +
-- full-token-containment rule, BLANK > WRONG). Re-ran fresh live against the
-- current 30-row gap (2026-07-24) and it found exactly 1 new unique match:
--
--   case_number 2025CA001896  owner_name "CHARLES J ELLISON ET AL"
--     -> ArcGIS OwnerName "ELLISON CHARLES J & DOREATHA"
--     -> parcel_id 291927005014000001
--     -> property_address "1311 N CLAYTON ST"
--     -> assessed_value 178634 (TotalJustValue, live)
--     -> latitude/longitude 28.808222 / -81.63883 (ring centroid of the live
--        ArcGIS polygon, outSR=4326)
--
-- The actual UPDATE was already applied live via that script's own Supabase
-- REST PATCH call (HTTP 200) at the time this file was written — this
-- migration file exists to document provenance per repo convention; running
-- it again is a no-op idempotency check (WHERE parcel_id IS NULL guards it).
UPDATE public.multi_county_auctions
SET parcel_id = '291927005014000001',
    property_address = COALESCE(property_address, '1311 N CLAYTON ST'),
    assessed_value = COALESCE(assessed_value, 178634),
    assessed_value_source = COALESCE(assessed_value_source, 'lake_county_arcgis_fieldmap_live'),
    latitude = COALESCE(latitude, 28.808222),
    longitude = COALESCE(longitude, -81.63883),
    parity_source = COALESCE(parity_source, 'e_match:lake_pa_ownername_v1:ownername_surname_position_unique')
WHERE lower(county) = 'lake'
  AND case_number = '2025CA001896'
  AND parcel_id IS NULL;

-- ─────────────────────────────────────────────────────────────────────────
-- CEILING AUDIT (read-only conclusion, no further writes) — 2026-07-24
--
-- Live gap requery immediately before this fix: 30 of 109 gold-standard-scope
-- lake auctions (WHERE data_source <> 'propertyonion' OR tier1_authoritative)
-- had parcel_id IS NULL. ALL 30 are data_source='lake_clerk_foreclosure_calendar_v1'
-- with owner_name populated but property_address NULL (Lake has no
-- RealForeclose/RealAuction FC platform; the Clerk's public calendar
-- (foreclosurecalendar.lakecountyclerkfl.gov) publishes only case_number +
-- plaintiff + defendant per sale — confirmed live via /sale_details.aspx?id=
-- for case 2025CA001886: no property address, parcel, or legal description
-- field exists on that page).
--
-- Attempted this session, each confirmed live, in order of leverage:
--   1. Re-run scripts/shard14_lake_e_ownername_match.py fresh (proven,
--      conservative ArcGIS OwnerName surname-position matcher) -> exactly 1
--      new unique match (applied above). 29 remain: no-hit, no
--      surname-position survivor among seed hits, or ambiguous (2+ same-
--      surname candidates) -- BLANK > WRONG, correctly left unlinked.
--   2. New multi-seed variant (try every signal token as ArcGIS seed, not
--      just the longest, to fix a same-length tie-break edge case) ->
--      reproduced the SAME 1 match, zero incremental gain. Verified example:
--      "TERENCE BLACKIE, ET AL" resolves to ArcGIS "BLACKIE TERRY & KARIN"
--      on the BLACKIE seed -- correctly rejected because required token
--      TERENCE is absent from the candidate's tokens (TERRY != TERENCE);
--      this is either a stale/changed-hands owner record or a different
--      individual, not a safe match.
--   3. Lake Clerk official records portal
--      (https://officialrecords.lakecountyclerk.org/) -- reachable (HTTP 200
--      landing page, unlike prior session's DNS failure), but
--      /search/SearchTypeCaseNumber redirects through /search/Disclaimer back
--      to the login-gated home page. This ACCLAIM-based portal requires an
--      account for search functionality; not accessible from this
--      environment.
--   4. Lake Clerk court-records agreement portal
--      (lakecountyclerk.org/record_searches/court_records_agreement.aspx,
--      linked from the sale_details.aspx "Online Court Records" link) --
--      301-redirects behind Cloudflare; not reachable.
--   5. Lake County GIS ArcGIS Server root
--      (gis.lakecountyfl.gov/lakegis/rest/services/PropertyAppraiser?f=json)
--      -- probed live; only 6 services exist (FieldMap, All_Aerials,
--      BuildingFootprints_Dashboard, FutureDevelopment, FutureSubdivisions,
--      PermitMap_Working). No sales/deed/owner-history layer distinct from
--      FieldMap exists to cross-reference against.
--   6. Lake PA's own HTML search UI (lakecopropappr.com/property-search.aspx)
--      -- 302-redirects (legacy ASP.NET postback UI); same underlying FieldMap
--      dataset as (1)/(2) regardless, so would not surface new matches even
--      if scraped.
--
-- CONCLUSION: E=73.4% (80/109) is the real, verified ceiling for Lake's
-- FC-Clerk-calendar lane this session. Closing the remaining 29-case gap to
-- reach the >=95% (104/109) target requires one of:
--   (a) An authenticated Lake Clerk official-records or court-e-filing
--       session (officialrecords.lakecountyclerk.org account, or
--       lakecountyclerk.org court-records login) to pull the filed complaint
--       / lis pendens for each case and read its legal description --
--       not available in this environment.
--   (b) A fuzzy address/owner matcher against the 668 archived
--       county='lake' data_source='propertyonion' rows (previously attempted
--       exact case_number join in shard7_run3679_lake_cd_e_ceiling_diagnosis.py,
--       0 matches because PO case numbers are synthetic 'PO-nnnnnnn' IDs) --
--       real scope, a new matcher build, out of this session's mandate.
-- This file documents (a)/(b) as the deferred next-session priority rather
-- than re-attempting the same exhausted script again next session.
