#!/usr/bin/env python3
"""GOLD STANDARD shard7, dispatch f4e7f681-ebf0-4732-af8c-ae2ace00840b, county=st_johns.

RESULT (executed live 2026-07-11): NO WRITES MADE. This is a diagnostic/investigation
record, not a fix script -- documenting a genuinely blocked residual gap per the
campaign's fail-loud invariant ("if a fix attempt finds zero real data, report it as
blocked, never fabricate").

Baseline (pencil_dod_evaluate_county, live, before AND after this session -- unchanged
since zero writes were made):
  E: pass=false, parcel_linked=32 of 37 (86.5%), gate >=95% (36+/37)
  I: pass=false, card_complete=32 of 37 (86.5%), gate >=95% (36+/37)

DIAGNOSIS: The exact same 5 case_numbers fail both E and I (confirmed via direct SQL
join against v_zoning_gold_standard_card using norm_county_key('st_johns') = 'st johns'
-- the view stores county with a space, not underscore, which is what norm_county_key()
produces; a naive lower(county)='st_johns' filter against the view returns 0 rows and
is a trap for future sessions). This confirms the documented E<=I dependency: I is
currently 100% gated by E for this county -- fixing E would auto-resolve I with zero
extra work, IF a real parcel_id is recovered.

The 5 blocked rows: CA25-0128, CA25-0351, CA25-0475, CA25-1757, CC25-4817
  All 5 share:
    - property_address IS NULL (no address at all -- not even a partial one)
    - parcel_id IS NULL
    - plaintiff, owner_name, judgment_amount, clerk_url, source_url, realforeclose_url,
      acclaimweb_url, legal_description all NULL
    - data_source = 'calendar_sweep_mca_v3', tier1_authoritative = false
    - identical placeholder lat/long (29.8943, -81.3145) -- a generic county centroid,
      not a real per-parcel geocode (this satisfies the E/I lat/lng NOT NULL check but
      is NOT evidence of a real address; flagging honestly, not exploiting it further)
    - assessed_value is a suspicious round/repeated placeholder ($200000.00 for 4 of 5
      rows, $47212.24 for the 5th) -- these look like seed/backfill defaults, not
      appraiser-sourced values. Not touched this session (would need independent source
      to correct, out of scope for this pass).
    - auction_date: 2026-08-13 (x4), 2026-08-20 (x1) -- future auctions

ATTEMPTED LIVE RECOVERY PATHS (all failed to produce real data, in order tried):
  1. St Johns Property Appraiser (sjcpa.us -> redirects sjcpa.gov) -- no native GIS/
     ArcGIS FeatureServer; property search is outsourced to qPublic (Schneider Corp).
     qPublic search fields are owner/address/parcel-ID only -- no case-number search,
     and these 5 rows have no address to search by. qpublic.schneidercorp.com direct
     hit returned HTTP 403 (bot-blocked) when probed anyway.
  2. RealForeclose AJAX harvest (reused scripts/shard2_run2450_ajax_realforeclose_harvest.py
     verbatim, the proven pattern from shard10/shard11/shard6 sessions): confirmed
     https://stjohns.realforeclose.com is a live, valid RealAuction subdomain (PREVIEW
     page returns HTTP 200), BUT the AJAX endpoint
     (zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=...) returns the full HTML shell page
     instead of the expected JSON {"rlist":...,"retHTML":...} payload -- this county's
     RealAuction deployment is running a newer frontend version than pinellas/lee/
     santa_rosa/leon (confirmed: 0 "AITEM_" markers in the static PREVIEW HTML, no
     fetch()/ajax() calls discoverable in the page, and /includes/scripts/app.js
     returned 404 so the bundle is served from an undiscovered path). Tried both target
     auction dates (08/13/2026, 08/20/2026) -- both parsed 0 items. This is a genuine
     site-architecture mismatch, not a transient failure; reverse-engineering the new
     frontend's real data endpoint is out of scope for this bounded pass (would need a
     headless-browser trace of the live page's network requests).
  3. St Johns Clerk of Court (sjcclerk.com) -- public site is a JS-rendered SPA;
     WebFetch/curl both returned empty/minimal shell content for onlinerecords and
     Court-Records pages. onr.sjcclerk.com (typical OnCore/Acclaim clerk portal
     subdomain guess) did not resolve (TLS SNI rejection). No case-search API
     discoverable without a browser-driven session, which is out of scope this pass.

CONCLUSION: Genuinely blocked. No real data source could be reached in this bounded
pass that would let us resolve a parcel_id (or even a property_address) for these 5
case numbers without fabrication. Per campaign rules, left unlinked -- NOT patched
with a placeholder/guessed parcel_id. Zero writes made to multi_county_auctions this
session.

NEXT SESSION NEEDS (to actually close this gap):
  (a) A browser-driven trace (Playwright/Firecrawl-browser) of
      https://stjohns.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=08/13/2026
      to capture the real XHR/fetch request the modern frontend issues for auction-item
      data, then port that into a stjohns-specific harvester (do NOT force-fit the
      legacy AJAX shorthand decoder -- confirmed not applicable to this deployment).
  (b) Alternatively, an authenticated or JS-capable fetch of sjcclerk.com's online
      records tool to search these 5 case numbers directly by case number and pull
      the property address off the case docket, then feed that address into qPublic's
      address-search flow to get a real parcel STRAP.
  (c) Once a real property_address+parcel_id lands for any of the 5, re-run this
      diagnostic (SQL below) to confirm both E and I move together as predicted.

DIAGNOSTIC QUERIES USED THIS SESSION (paste-ready):

-- E gap identification (dispatch brief's query, verbatim):
SELECT case_number, property_address, parcel_id, latitude, po_latitude, longitude,
       po_longitude, assessed_value, market_value
FROM multi_county_auctions
WHERE lower(county)='st_johns'
  AND (COALESCE(data_source,'')<>'propertyonion' OR COALESCE(tier1_authoritative,false)=true)
  AND parcel_id IS NULL;

-- I gap cross-check (note the view uses norm_county_key -> 'st johns' with a space,
-- NOT lower(county)='st_johns' -- a naive underscore match against the view is a trap):
WITH zc AS (
  SELECT DISTINCT parcel_id, tax_account
  FROM v_zoning_gold_standard_card
  WHERE lower(county) = 'st johns' AND zone_code IS NOT NULL
)
SELECT a2.case_number, a2.parcel_id,
       (a2.property_address IS NOT NULL) AS has_addr,
       (COALESCE(a2.latitude, a2.po_latitude::double precision) IS NOT NULL) AS has_lat,
       (COALESCE(a2.longitude, a2.po_longitude::double precision) IS NOT NULL) AS has_lng,
       (COALESCE(a2.assessed_value, a2.market_value) IS NOT NULL) AS has_val,
       (a2.parcel_id IN (SELECT parcel_id FROM zc)
        OR a2.parcel_id IN (SELECT tax_account FROM zc WHERE tax_account IS NOT NULL)) AS in_zoning_card
FROM multi_county_auctions a2
WHERE lower(a2.county) = 'st_johns'
  AND (COALESCE(a2.data_source,'') <> 'propertyonion' OR COALESCE(a2.tier1_authoritative,false) = true)
ORDER BY a2.case_number;
"""

# No executable code this session -- investigation only, zero writes made.
# See docstring above for full findings, attempted paths, and next-session plan.

if __name__ == "__main__":
    print(__doc__)
