-- Gold Standard shard2 baker: C/D/E/I diagnosis + ghost-value purge
-- county: baker | letters: C, D, E, I | auctions_total: 15
--
-- ROOT CAUSE (CONFIRMED, live-verified 2026-07-24):
--   Two baker rows had parcel_id literally set to the string 'Property
--   Appraiser' (022025CA000148CAAXMX tax_deed, 022026CA000018CAAXMX
--   foreclosure). This is the anchor TEXT of the RealAuction "Parcel ID"
--   link when Baker County has not yet linked a parcel to that case at
--   bakerpa.com -- the underlying href is
--   http://bakerpa.com/propertydetails.php?parcel=  (empty value).
--
--   .github/scripts/calendar_sweep_mca.py (data_source=calendar_sweep_mca_v3)
--   already has a `_clean_parcel()` bad-word guard (added 2026-06-23, commit
--   8e13f266) that should have caught this and stored NULL -- but its STRAP-
--   extraction fallback only matched `?STRAP=` in the href, not bakerpa.com's
--   `?parcel=` param name, AND the upsert path (`_upsert_rows` in the same
--   file) intentionally omits any optional column the current scrape run
--   found no value for, specifically so it never null-wipes a prior
--   enrichment. Net effect: a bad value written before the 2026-06-23 guard
--   landed (both rows created 2026-07-10, see created_at) was "protected"
--   from ever being corrected by later, correct scrape runs, because those
--   runs (correctly) resolve to no-value and therefore never touch the
--   column again.
--
--   FIX (this session): broadened the href-source-of-truth regex in
--   _clean_parcel() to accept `parcel`/`PARCELID`/`PARCEL_ID` in addition to
--   `STRAP` (regex requires 1+ captured chars, so Baker's own empty
--   `?parcel=` still and correctly resolves to None, not a fabricated
--   value) -- see .github/scripts/calendar_sweep_mca.py. This migration
--   does the one-time cleanup of the two already-poisoned baker rows.
--
--   Scope note: the SAME 'Property Appraiser'/'MULTIPLE'/etc. stale-value
--   pattern was found live in 26 counties total (alachua, bay, broward,
--   charlotte, citrus, clay, duval, escambia, flagler, gulf, hillsborough,
--   indian_river, lee, leon, martin, miami_dade, palm_beach, pasco,
--   pinellas, putnam, seminole, st_johns, st_lucie, volusia, walton, plus
--   baker) -- left untouched per this session's scope (baker only). Flagged
--   for a future dedicated cross-county cleanup pass.
--
-- REMAINING GAP (documented, NOT fabricated):
--   12 of 15 baker rows (6 case numbers x 2 sale_types) have NO property
--   linkage published anywhere publicly reachable as of 2026-07-24:
--     022025CA000108CAAXMX, 022025CA000117CAAXMX, 022025CA000124CAAXMX,
--     022025CA000148CAAXMX, 022026CA000007CAAXMX, 022026CA000018CAAXMX
--   Sources checked live this session, all confirmed dead ends:
--     1. baker.realforeclose.com + baker.realtaxdeed.com (RealAuction,
--        AREA=W calendar AJAX, matches production scraper pattern) -- all
--        6 cases return only Auction Type/Case #/Final Judgment Amount/
--        Plaintiff Max Bid. NO "Property Address" row exists in the AITEM
--        block at all for these upcoming sales, and the Parcel ID link
--        href is `?parcel=` with an EMPTY value -- Baker County itself has
--        not yet linked a parcel to these cases (they are future auctions,
--        sale dates 2026-08-13 through 2026-10-15).
--     2. bakerpa.com (Baker County Property Appraiser, the site
--        tier1_baker_realforeclose_bakerpa_v1 resolves against) -- origin
--        returned Cloudflare 521 (origin server down), independently
--        confirmed with curl -sv, not a transient blip on retry.
--     3. bakerclerk.com / www.bakerclerk.com (Clerk of Court case search)
--        -- HTTP 403 (WAF-blocked), consistent with the shard14 script's
--        prior finding (commit 94e82971, dispatch 5c3a52ba).
--     4. qpublic.net/fl/baker + qpublic.schneidercorp.com -- HTTP 403
--        (WAF-blocked).
--     5. Baker County PA ArcGIS FeatureServer
--        (services6.arcgis.com/HSWu3dhzHf7nZfIa/.../parcels_web2/0) -- live
--        (HTTP 200) but has no case_number, owner_name, or address search
--        field (fields are FID/PIN/Type/Block/Lot/Zoning/GIS_Acreag/etc,
--        cadastral-only, no SITE_ADDR/OWNER_NAME as the shard14 script had
--        assumed) -- cannot be queried by anything we have for these 6
--        cases (no address, no owner name, no parcel).
--   With no independently-verifiable address, parcel_id, geo, or value for
--   any of the 6 cases, C/D/E/I cannot honestly move past the 3/15 baseline
--   this session. Writing placeholder/estimated values here would repeat
--   the exact ghost-success pattern purged in commit 6a5a5cb0. Deferred
--   until bakerpa.com origin recovers or Baker publishes the parcel link.
--
-- source_urls:
--   https://baker.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=UPDATE
--   https://baker.realtaxdeed.com/index.cfm?zaction=AUCTION&Zmethod=UPDATE
--   http://bakerpa.com/ (521 -- origin down, checked 2026-07-24T~08:15 UTC)
--   https://www.bakerclerk.com/ (403 WAF)
--   https://services6.arcgis.com/HSWu3dhzHf7nZfIa/arcgis/rest/services/parcels_web2/FeatureServer/0

BEGIN;

-- Purge the two scraper-bug placeholder values. NULL is the honest state --
-- matches what the fixed _clean_parcel() would produce today, and matches
-- the true state at the source (no parcel linked yet).
UPDATE public.multi_county_auctions
SET parcel_id = NULL,
    updated_at = NOW()
WHERE county = 'baker'
  AND lower(parcel_id) = 'property appraiser';

COMMIT;
