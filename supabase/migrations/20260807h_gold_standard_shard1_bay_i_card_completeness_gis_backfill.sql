-- GOLD STANDARD shard-1, county=bay, letter=I (property card completeness)
--
-- BASELINE (live, re-verified this session before any change):
--   SELECT public.pencil_dod_evaluate_county('bay') -> I: pass=false,
--   card_complete=186 of 199 (93.5%), threshold >=95% (>=190). FAIL.
--
-- DIAGNOSIS (live, re-verified this session):
--   13 card_rows failed the I predicate:
--     property_address IS NOT NULL
--     AND COALESCE(latitude, po_latitude) IS NOT NULL
--     AND COALESCE(longitude, po_longitude) IS NOT NULL
--     AND COALESCE(assessed_value, market_value) IS NOT NULL
--     AND parcel_id IN (SELECT parcel_id FROM v_zoning_gold_standard_card
--                        WHERE county=bay AND zone_code IS NOT NULL)
--   Breakdown:
--     - 9 rows had address + assessed_value OK but no lat/lng, and their
--       parcel_id had no row in parcel_zones (so zoned_ok=false too):
--       2026-5115TD, 23001332CA, 25001171CA, 25000969CA, 26000088CA,
--       25001088CA, 2026-4014TD (this one WAS already geo-complete --
--       pure zoning-linkage gap), 2026-5042TD, 2026-5951TD.
--     - 4 rows had NO address and NO parcel_id at all: 25001176CA
--       (parcel_id literally the placeholder string 'TIMESHARE'),
--       25000412CA, 26000161CA, 23001239CA (parcel_id NULL).
--
-- SOURCE USED (real, live, cited -- v_zoning_gold_standard_card is built on
-- parcel_zones joined to jurisdictions; NOT a live-GIS view, so the fix is a
-- parcel_zones INSERT, not a v_zoning_gold_standard_card UPDATE):
--   1. gis.baycountyfl.gov ArcGIS REST, BasicLayers/MapServer/3 ("Parcels"
--      layer). Queried live by A1RENUM=<parcel_id> (Bay's Property
--      Appraiser "real estate number" == our parcel_id, matched 1:1
--      including DSITEADDR agreeing with our stored property_address for
--      all 8 rows below). Returned polygon geometry (outSR=4326); lat/lng
--      taken as the simple average of the exterior ring vertices (parcel
--      centroid approximation -- acceptable precision for a card-level
--      lat/lng field, consistent with prior sessions' use of this same
--      layer per parcel_zones.source history for bay).
--   2. gis.baycountyfl.gov ArcGIS REST, LandUsePlanning/MapServer/1
--      ("Zoning" layer, description: "Depicts the zoning for unincorporated
--      Bay County, Panama City, Panama City Beach, Lynn Haven, Callaway and
--      Mexico Beach"). Point-in-polygon query at each parcel's centroid
--      (from step 1) returned live ZONING + SUB_ZONING + ORD_NUM. This
--      layer carries no parcel_id field -- it is a pure zoning-geometry
--      layer, hence the point-in-polygon approach (already the established
--      pattern for bay per prior parcel_zones.source rows, e.g.
--      "gis.baycountyfl.gov Land_Use_Planning MapServer/1 (live fetch
--      2026-07-10)").
--   3. Jurisdiction crosswalk taken directly from the LandUsePlanning/
--      MapServer/1 layer's own published SUB_ZONING code list:
--        1 Bay County (unincorporated) -> jurisdiction_id 1332
--        2 Callaway                    -> jurisdiction_id 983
--        3 Lynn Haven                  -> jurisdiction_id 873
--        4 Mexico Beach                -> jurisdiction_id 985
--        5 Panama City                 -> jurisdiction_id 884
--        6 Panama City Beach           -> jurisdiction_id 907
--      SUB_ZONING=7 (for parcel 25539-020-000 / case 2026-4014TD) is
--      undocumented in the layer's own description but was already
--      resolved by a prior session (gold-standard shard-4 bay,
--      2026-07-29) as "SUB_ZONING=7 -> Label=See FLU(PKR) -> Parker",
--      i.e. jurisdiction_id 1588. Reused that precedent rather than
--      re-deriving it.
--   Note: two parcels (07228-016-000, 06773-049-000) point-matched into
--   SUB_ZONING=2 (Callaway) even though their stored property_address
--   postal city reads "PANAMA CITY" -- this is expected/normal FL Panhandle
--   addressing (many Callaway/unincorporated addresses use the "Panama
--   City" postal city) and the spatial match against the county's own
--   authoritative polygon layer is trusted over the postal city string.
--
-- ROWS FIXED (9 of 13): all 9 rows with a real parcel_id above. For each,
-- inserted a parcel_zones row (closing the zoning-linkage gap that fails I
-- via v_zoning_gold_standard_card) and, for the 8 that lacked coordinates,
-- backfilled multi_county_auctions.latitude/longitude from the same live
-- GIS parcel-centroid lookup. 2026-4014TD (parcel 25539-020-000) needed only
-- the parcel_zones insert -- it was already geo-complete.
--
-- ROWS LEFT UNTOUCHED (4 of 13, documented exhaustion -- BLANK > WRONG):
--   23001239CA, 25000412CA, 25001176CA, 26000161CA -- all have NULL (or,
--   for 25001176CA, the data-quality placeholder 'TIMESHARE') parcel_id and
--   NULL property_address in multi_county_auctions, so there is nothing to
--   geocode or zone-link against. Sourcing attempted this session, all
--   exhausted:
--     - bay.realforeclose.com case detail pages (source_url on file for
--       23001239CA AID=1499969 and 25000412CA AID=1489757): both return the
--       site's public splash/login page, not case detail -- realforeclose
--       gates case-level detail behind account login.
--     - Bay Clerk's public case search (court.baycoclerk.com/BenchmarkWeb2)
--       is reCAPTCHA-gated (data-sitekey present on the search form); not
--       scriptable from this session's tooling.
--     - Firecrawl API: HTTP 402 "Insufficient credits" (account exhausted
--       this session; would have been the tool of choice to render the
--       reCAPTCHA-gated / JS-heavy pages above).
--     - browser-use CLI: not installed in this sandbox (`command not
--       found`), so no scripted-browser fallback was available either.
--     - Bay Clerk's public weekly "Circuit Civil Foreclosure Sales" PDF
--       (apps.baycoclerk.com/Downloads/ForeclosureSales.pdf, fetched live,
--       20 pages, current as of 2026-08-07 10:39 CST): none of the 4 case
--       numbers appear on the current active-sale calendar, and the report
--       does not carry property addresses or parcel IDs for any case
--       despite its own header claiming it would.
--     - WebSearch for each case number by itself: zero hits for all 4.
--   No real, citable source was found for these 4 rows this session. Per
--   this project's Honesty Protocol this is a fully acceptable, expected
--   outcome (mirrors the "hamilton I source exhaustion" pattern already
--   used successfully elsewhere in this campaign) -- no data was
--   fabricated or guessed for them.
--
-- RESULT (live, re-verified after applying the SQL below):
--   SELECT public.pencil_dod_evaluate_county('bay') -> I: pass=true,
--   card_complete=195 of 199 (98.0%). PASS (>=95%, i.e. >=190). Up from
--   186/199 (93.5%) / FAIL. 9 rows fixed against a target of 4 to flip the
--   letter -- exceeded the minimum bar.
--   A-H/J unaffected by this change except G, which independently reads
--   pass=false / 94.4% (density=97.1 far=97.7 pk1000=94.4) in the same live
--   call -- down from 97.0% recorded at session start in the prior brief.
--   This session made ZERO writes to zoning_districts/zone_standards or any
--   other G-relevant table (only parcel_zones inserts + lat/lng backfills
--   above), so this is pre-existing drift unrelated to this change, flagged
--   here per HONESTY PROTOCOL rather than silently omitted. Out of scope
--   for this dispatch's I-letter mandate.

BEGIN;

-- Zoning linkage: parcel_zones rows for the 9 real-parcel_id failing rows,
-- sourced from gis.baycountyfl.gov live GIS as described above.
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source, effective_date)
VALUES
  ('25539-020-000', '25539-020-000', 1588, 'See FLU', NULL,
   'gis.baycountyfl.gov LandUsePlanning MapServer/1 (Zoning point-in-polygon lookup, live fetch, centroid -85.61345,30.13415 from parcel polygon ring for 25539-020-000, SUB_ZONING=7 -> Parker per prior-session crosswalk precedent "SUB_ZONING=7 -> Label=See FLU(PKR) -> Parker" gold-standard shard-4 bay session 2026-07-29) -- gold-standard shard-1 bay session 2026-08-07',
   CURRENT_DATE),
  ('34133-010-000', '34133-010-000', 907,  'R-1c',    NULL,
   'gis.baycountyfl.gov BasicLayers/MapServer/3 (Parcels, A1RENUM lookup) + LandUsePlanning/MapServer/1 (Zoning point-in-polygon at parcel centroid, SUB_ZONING=6->Panama City Beach, ORD_NUM=1233) -- gold-standard shard-1 bay session 2026-08-07',
   CURRENT_DATE),
  ('07228-016-000', '07228-016-000', 983,  'R-9',     NULL,
   'gis.baycountyfl.gov BasicLayers/MapServer/3 (Parcels, A1RENUM lookup) + LandUsePlanning/MapServer/1 (Zoning point-in-polygon at parcel centroid, SUB_ZONING=2->Callaway) -- gold-standard shard-1 bay session 2026-08-07',
   CURRENT_DATE),
  ('06773-049-000', '06773-049-000', 983,  'R-MF',    NULL,
   'gis.baycountyfl.gov BasicLayers/MapServer/3 (Parcels, A1RENUM lookup) + LandUsePlanning/MapServer/1 (Zoning point-in-polygon at parcel centroid, SUB_ZONING=2->Callaway) -- gold-standard shard-1 bay session 2026-08-07',
   CURRENT_DATE),
  ('08991-000-000', '08991-000-000', 873,  'See FLU', NULL,
   'gis.baycountyfl.gov BasicLayers/MapServer/3 (Parcels, A1RENUM lookup) + LandUsePlanning/MapServer/1 (Zoning point-in-polygon at parcel centroid, SUB_ZONING=3->Lynn Haven) -- gold-standard shard-1 bay session 2026-08-07',
   CURRENT_DATE),
  ('07899-650-195', '07899-650-195', 1332, 'R-2',     NULL,
   'gis.baycountyfl.gov BasicLayers/MapServer/3 (Parcels, A1RENUM lookup) + LandUsePlanning/MapServer/1 (Zoning point-in-polygon at parcel centroid, SUB_ZONING=1->Unincorporated Bay County) -- gold-standard shard-1 bay session 2026-08-07',
   CURRENT_DATE),
  ('22331-978-000', '22331-978-000', 884,  'NG',      NULL,
   'gis.baycountyfl.gov BasicLayers/MapServer/3 (Parcels, A1RENUM lookup) + LandUsePlanning/MapServer/1 (Zoning point-in-polygon at parcel centroid, SUB_ZONING=5->Panama City, ORD_NUM=3223.2) -- gold-standard shard-1 bay session 2026-08-07',
   CURRENT_DATE),
  ('33802-106-000', '33802-106-000', 907,  'CH',      NULL,
   'gis.baycountyfl.gov BasicLayers/MapServer/3 (Parcels, A1RENUM lookup) + LandUsePlanning/MapServer/1 (Zoning point-in-polygon at parcel centroid, SUB_ZONING=6->Panama City Beach, ORD_NUM=1233) -- gold-standard shard-1 bay session 2026-08-07',
   CURRENT_DATE),
  ('40000-950-253', '40000-950-253', 907,  'CH',      NULL,
   'gis.baycountyfl.gov BasicLayers/MapServer/3 (Parcels, A1RENUM lookup) + LandUsePlanning/MapServer/1 (Zoning point-in-polygon at parcel centroid, SUB_ZONING=6->Panama City Beach, ORD_NUM=1233) -- gold-standard shard-1 bay session 2026-08-07',
   CURRENT_DATE)
ON CONFLICT DO NOTHING;

-- lat/lng backfill for the 8 rows that lacked coordinates (2026-4014TD
-- excluded -- it was already geo-complete). Source: parcel centroid from
-- gis.baycountyfl.gov BasicLayers/MapServer/3 (Parcels), A1RENUM match,
-- outSR=4326, as described above.
UPDATE public.multi_county_auctions SET
  latitude = 30.199244606009643, longitude = -85.84277633791142
WHERE case_number = '2026-5115TD' AND lower(county) = public.norm_county_key('bay') AND parcel_id = '34133-010-000';

UPDATE public.multi_county_auctions SET
  latitude = 30.127337234531716, longitude = -85.58087220861191
WHERE case_number = '23001332CA' AND lower(county) = public.norm_county_key('bay') AND parcel_id = '07228-016-000';

UPDATE public.multi_county_auctions SET
  latitude = 30.141867126012237, longitude = -85.56841694851033
WHERE case_number = '25001171CA' AND lower(county) = public.norm_county_key('bay') AND parcel_id = '06773-049-000';

UPDATE public.multi_county_auctions SET
  latitude = 30.254536313743916, longitude = -85.65335074711159
WHERE case_number = '25000969CA' AND lower(county) = public.norm_county_key('bay') AND parcel_id = '08991-000-000';

UPDATE public.multi_county_auctions SET
  latitude = 30.279174625547956, longitude = -85.60915032693117
WHERE case_number = '26000088CA' AND lower(county) = public.norm_county_key('bay') AND parcel_id = '07899-650-195';

UPDATE public.multi_county_auctions SET
  latitude = 30.15706562908157, longitude = -85.64168261090649
WHERE case_number = '25001088CA' AND lower(county) = public.norm_county_key('bay') AND parcel_id = '22331-978-000';

UPDATE public.multi_county_auctions SET
  latitude = 30.21044524570553, longitude = -85.8680655707239
WHERE case_number = '2026-5042TD' AND lower(county) = public.norm_county_key('bay') AND parcel_id = '33802-106-000';

UPDATE public.multi_county_auctions SET
  latitude = 30.220185503493248, longitude = -85.88689752607617
WHERE case_number = '2026-5951TD' AND lower(county) = public.norm_county_key('bay') AND parcel_id = '40000-950-253';

COMMIT;
