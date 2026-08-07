-- Gold Standard shard-5 (dispatch 5d40a513-fb55-4c9c-ad49-be84afb8388f), county:
-- baker ONLY, letters C/D/E/I/J (+ G regression guard).
--
-- BEFORE (VERIFIED live via pencil_dod_evaluate_county('baker') at session start):
--   A=PASS(8, fc=9 td=8) B=PASS(100, verified=1 closed_sold=1)
--   C=FAIL(41.2, matched_clean=7 of 17) D=FAIL(41.2, matched_any=7 of 17)
--   E=FAIL(47.1, parcel_linked=8 of 17) F=PASS(100, tier1_sold=1 closed_sold=1)
--   G=PASS(100, density=100 far=100 pk1000=100) H=PASS(0.0h)
--   I=FAIL(41.2, card_complete=7 of 17) J=FAIL(88.2, deal_complete=15 of 17)
--   auctions_total=17. 5/10 pass.
--
-- ROOT CAUSE (confirmed via full 17-row dump this session, matches the dispatch
-- brief exactly): 7 rows across 4 case numbers (022025CA000038CAAXMX x2,
-- 022025CA000148CAAXMX x2, 022026CA000018CAAXMX x2, 022026XX000002TDAXMX x1)
-- already carry real parcel_id/address/geo/assessed_value/parity from prior
-- sessions' tier1_baker_realforeclose_bakerpa_v1 pipeline. The remaining 10
-- rows (6 case numbers) split into: fully blank (022025CA000002CAAXMX,
-- 022025CA000117CAAXMX x2, 022025CA000124CAAXMX x2, 022025CC000132CCAXMX,
-- 022026CA000007CAAXMX-td) and partial (022025CA000108CAAXMX-fc had address
-- only; 022026CA000007CAAXMX-fc had parcel_id+address+assessed_value but no
-- lat/long/parity).
--
-- LIVE RESEARCH THIS SESSION (2026-08-07, all via plain HTTP -- Firecrawl
-- confirmed OUT OF CREDIT this session, contradicting the dispatch brief's
-- assumption; worked around it with direct requests + the RealAuction JSON
-- UPDATE endpoint + bakerpa.com's real "Parcel #, Name, or Address"
-- quick-search + Baker County's public ArcGIS parcels_web2 FeatureServer):
--
--   1. baker.realforeclose.com + baker.realtaxdeed.com PREVIEW/UPDATE JSON
--      endpoint, session-warmed cookies, swept dates 2026-07-02 through
--      2026-09-03 (widened +/-14d around the 3 discovered dates plus a
--      90-day forward sweep): 5 of 6 gap case numbers ARE live on the
--      calendar. 022025CA000117CAAXMX is NOT found on any date in a 90-day
--      forward window nor the widened backward window, and has zero row in
--      foreclosure_outcomes/tax_deed_outcomes -- genuinely off the docket,
--      confirmed a 4th time across sessions (2026-07-05, -07-10 x2, -07-11,
--      -08-03, this session).
--   2. Of the 5 found: 022025CA000002CAAXMX, 022025CA000124CAAXMX,
--      022025CC000132CCAXMX show the EXACT same ghost-anchor pattern
--      documented in 3 prior sessions -- "Parcel ID:" field literally
--      renders as the anchor text "Property Appraiser" with an empty
--      href parcel= param, and the card exposes ONLY Auction Type/Case #/
--      Final Judgment Amount/Parcel ID(ghost)/Plaintiff max bid(Hidden) --
--      no address, no owner/plaintiff name field at all. Confirmed NOT a
--      scraper artifact -- raw JSON UPDATE response inspected directly.
--      Left untouched, reported as residual (source-exhausted, would
--      require fabrication to close).
--   3. 022025CA000108CAAXMX and 022026CA000007CAAXMX DO carry a real
--      parcel_id/address on the source card. Cross-referenced against
--      bakerpa.com (Timothy P. Sweat, Baker County Property Appraiser --
--      confirmed back up, HTTP 200, same recovery noted 2026-08-03):
--        - 022025CA000108CAAXMX address "11018 AARON FISH ROAD" ->
--          bakerpa.com/searchresults.php?criteria=AARON+FISH (street-name-
--          only query; directional+suffix query returned zero results) ->
--          exact match: Parcel 321S21000000000087, Owner KENDALL SARAH,
--          Site Address "11018 AARON FISH RD GLEN ST MARY", Property Use
--          MOBILE HOME. propertydetails.php?parcel=321S21000000000087 ->
--          Total Just Value $244,641 (2025 Certified).
--        - 022026CA000007CAAXMX already had parcel_id 063S22004100040100 in
--          our DB; propertydetails.php confirms Owner SOUTHARD FRANCES N,
--          Site Address "9999 PERSIMMON RD MACCLENNY", Total Just Value
--          $165,762 (matches our pre-existing assessed_value exactly).
--      VALUE CONVENTION: cross-checked the 3 already-matched_clean parcels
--      (043S22000000000540=$208,956, 073S22023800000290=$273,339,
--      121S20000000000021=$154,741) against bakerpa.com propertydetails --
--      all 3 match "Total Just Value", NOT "Assessed Value-Non School".
--      Followed the same established convention for 321S21000000000087
--      ($244,641 Total Just Value, not the $178,428 Assessed Value-Non
--      School figure).
--   4. Lat/long: bakerpa.com's own embedded map JS only exposes a generic
--      county-wide zoom-10 center point ([-82.23, 30.32], identical for
--      every parcel) -- explicitly NOT used (would be a fabricated-default
--      value, same anti-pattern flagged in this dispatch's pinellas-I
--      warning). Instead queried Baker County's public ArcGIS REST
--      FeatureServer directly (services6.arcgis.com/.../parcels_web2,
--      field PARCELNO) for each parcel's real polygon geometry and computed
--      the ring centroid:
--        321S21000000000087 -> lat=30.37082987216325, lon=-82.22229323342418
--        063S22004100040100 -> lat=30.265590002770626, lon=-82.14407368792544
--   5. Zoning: the same ArcGIS FeatureServer layer exposes a `Zoning` field
--      directly. 321S21000000000087 -> "AG 7.5" (already an existing baker
--      zoning_districts row, jurisdiction_id=1664 Unincorporated Baker).
--      063S22004100040100 -> "RCMH 1", a new code not yet in our table.
--      Confirmed via WebSearch + zoneomics.com/code/baker-county-
--      unincorporated-FL/chapter_4 (mirrors Baker County Code of Ordinances
--      Ch.24 Art.III Div.4 Sec.24-193): "RCMH 1 Residential Conventional and
--      Mobile Home District" -- density "One unit per acre", min lot width
--      100ft/area 1 acre, max height 35ft, front/side/rear setback 25ft.
--      This is the SAME source_url pattern already used for baker's
--      existing AG 7.5 zone_standards row (zoneomics.com .../chapter_4).
--
-- WRITES THIS SESSION (all live via Management API SQL endpoint):
--   1. multi_county_auctions: parcel_id/lat/long/assessed_value backfill for
--      022025CA000108CAAXMX (both sale_type rows) and lat/long backfill +
--      tax_deed-row field mirroring for 022026CA000007CAAXMX (both rows).
--   2. multi_county_auctions: parity_status='matched_clean',
--      parity_source='tier1_baker_realforeclose_bakerpa_v1:baker:20260807_shard5_5d40a513'
--      for both case numbers -- same hand-verified-match convention already
--      established for this county across 2 prior sessions (2026-08-03
--      ":baker:20260803_cdgap" suffix). NOT written via
--      refresh_parity_tier1_outcomes() because that function only matches
--      against foreclosure_outcomes/tax_deed_outcomes rows with a completed/
--      sold/redeemed/cancelled auction_status -- these 2 cases have no
--      outcome-table row (still upcoming), so the RPC has nothing to match;
--      the existing tier1_baker_realforeclose_bakerpa_v1 direct-verification
--      pattern is baker's actual established mechanism for this scenario.
--   3. zoning_districts: 1 new row (jurisdiction_id=1664, code='RCMH 1').
--   4. parcel_zones: 2 new rows (321S21000000000087->AG 7.5,
--      063S22004100040100->RCMH 1), sourced
--      'baker_county_gis_arcgis_parcels_web2_live_2026-08-07'.
--   5. zone_standards: 1 new row for the RCMH 1 district (max_density_du_acre
--      =1.0, max_height_ft=35, front/side/rear_setback_ft=25,
--      min_lot_sqft=43560) -- added mid-session after discovering step 3-4
--      transiently dropped G's density metric from 100.0 to 66.7 (new
--      zoning_districts row with no zone_standards row, default-applicable).
--      Re-verified G=PASS(100.0) after this fix -- NOT a net regression.
--
-- NOT TOUCHED (confirmed source-exhausted, reported as residual, zero
-- fabrication): 022025CA000002CAAXMX, 022025CA000117CAAXMX,
-- 022025CA000124CAAXMX, 022025CC000132CCAXMX (6 rows across these 4 case
-- numbers). J's 2 target rows (022025CA000002CAAXMX, 022025CC000132CCAXMX)
-- checked live for bid_decisions -- zero rows, both before and after this
-- session. Checked refresh_levy_bid_decisions() (hardcoded county='levy',
-- would use a fabricated $50,000 ARV fallback for a null-parcel row -- NOT
-- invoked) and gen_valuations_comps_batch() (requires a parcels row joined
-- to fl_parcels by parcel_id -- nothing to operate on for a null-parcel
-- case) -- neither is a legitimate path to close J for these 2 rows without
-- first resolving E, which remains source-exhausted for them.
--
-- AFTER (VERIFIED live, same session, immediately before writing this file):
--   A=PASS(8) B=PASS(100) C=FAIL(64.7, matched_clean=11 of 17)
--   D=FAIL(64.7, matched_any=11 of 17) E=FAIL(64.7, parcel_linked=11 of 17)
--   F=PASS(100) G=PASS(100.0, density=100 far=100 pk1000=100 -- unregressed)
--   H=PASS(0.0h) I=FAIL(64.7, card_complete=11 of 17)
--   J=FAIL(88.2, deal_complete=15 of 17 -- unchanged, genuine residual)
--   auctions_total=17. Still 5/10 pass -- C/D/E/I moved materially closer to
--   the 95% threshold (+23.5 points each, 7->11 of 17) but did not cross it;
--   4 case numbers (6 rows) remain genuinely source-exhausted.
--
-- ADVERSARIAL AUDIT TRAIL: 6 rows inserted live into
-- gold_standard_ultraloop_audit (dispatch_id=5d40a513-fb55-4c9c-ad49-
-- be84afb8388f, county_slug='baker', letters C/D/E/I/G/J), ids 13323-13328.

-- SQL VERIFICATION (run 2026-08-07, this session, live Management API):
--
-- SELECT public.pencil_dod_evaluate_county('baker');
--   See BEFORE/AFTER blocks above -- both captured live via the RPC.
--
-- SELECT case_number, sale_type, parcel_id, property_address, latitude,
--   longitude, assessed_value, parity_status, parity_source
-- FROM multi_county_auctions WHERE county='baker' ORDER BY case_number, sale_type;
--   17 rows total. 11 with parity_status='matched_clean' AND
--   parity_source LIKE 'tier1%'. 6 rows (4 case numbers) still fully NULL
--   on parcel_id/property_address/latitude/longitude/assessed_value/parity.
--
-- SELECT parcel_id, tax_account, zone_code FROM v_zoning_gold_standard_card
-- WHERE lower(county)='baker' AND parcel_id IN
--   ('321S21000000000087','063S22004100040100');
--   -> ('321S21000000000087', NULL, 'AG 7.5'), ('063S22004100040100', NULL, 'RCMH 1')
--   both resolve, confirming I's card-completeness join condition is met.

-- Idempotent mirror of the live writes (safe to re-run; every write is
-- either a targeted case_number UPDATE or an INSERT ... WHERE NOT EXISTS).

-- 1. Backfill 022025CA000108CAAXMX (both sale_type rows) with real bakerpa.com
--    parcel data (KENDALL SARAH, 321S21000000000087, Total Just Value $244,641).
UPDATE public.multi_county_auctions
SET parcel_id = '321S21000000000087',
    latitude = 30.37082987216325,
    longitude = -82.22229323342418,
    assessed_value = 244641.00,
    updated_at = now()
WHERE county = 'baker' AND case_number = '022025CA000108CAAXMX';

UPDATE public.multi_county_auctions
SET property_address = '11018 AARON FISH ROAD, GLEN ST. MARY, FL- 32040',
    updated_at = now()
WHERE county = 'baker' AND case_number = '022025CA000108CAAXMX' AND sale_type = 'tax_deed'
  AND property_address IS NULL;

-- 2. Backfill 022026CA000007CAAXMX lat/long (both rows) + mirror parcel_id/
--    address/assessed_value onto the tax_deed row (same case/property, was
--    only present on the foreclosure row pre-session).
UPDATE public.multi_county_auctions
SET latitude = 30.265590002770626,
    longitude = -82.14407368792544,
    updated_at = now()
WHERE county = 'baker' AND case_number = '022026CA000007CAAXMX';

UPDATE public.multi_county_auctions
SET parcel_id = '063S22004100040100',
    property_address = '9999 PERSIMMON RD, MACCLENNY, FL- 32063',
    assessed_value = 165762.00,
    updated_at = now()
WHERE county = 'baker' AND case_number = '022026CA000007CAAXMX' AND sale_type = 'tax_deed'
  AND parcel_id IS NULL;

-- 3. Parity backfill, matching the established tier1_baker_realforeclose_bakerpa_v1
--    convention (hand-verified direct match, not an outcome-table match --
--    see narrative above for why refresh_parity_tier1_outcomes() does not
--    apply to these 2 still-upcoming cases).
UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1_baker_realforeclose_bakerpa_v1:baker:20260807_shard5_5d40a513',
    parity_confidence = 0.95,
    parity_checked_at = now(),
    last_parity_check = now()
WHERE county = 'baker' AND case_number IN ('022025CA000108CAAXMX', '022026CA000007CAAXMX')
  AND (parity_status IS NULL OR parity_source IS NULL);

-- 4. New zoning district: RCMH 1 (Residential Conventional and Mobile Home
--    District), Baker County Code of Ordinances Ch.24 Art.III Div.4
--    Sec.24-193, Unincorporated Baker jurisdiction (id=1664).
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category)
SELECT 1664, 'RCMH 1', 'Residential Conventional and Mobile Home District: RCMH 1 (Sec. 24-193)', 'Residential'
WHERE NOT EXISTS (SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id=1664 AND code='RCMH 1');

-- 5. parcel_zones: AG 7.5 for 321S21000000000087 (verified live via ArcGIS
--    parcels_web2 Zoning field).
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '321S21000000000087', 1664, 'AG 7.5',
       'Agricultural District: AG 7.5 (Sec. 24-191) - Baker County GIS parcels_web2 layer',
       'baker_county_gis_arcgis_parcels_web2_live_2026-08-07'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id='321S21000000000087');

-- 6. parcel_zones: RCMH 1 for 063S22004100040100 (verified live via ArcGIS
--    parcels_web2 Zoning field).
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '063S22004100040100', 1664, 'RCMH 1',
       'Residential Conventional and Mobile Home District: RCMH 1 (Sec. 24-193) - Baker County GIS parcels_web2 layer',
       'baker_county_gis_arcgis_parcels_web2_live_2026-08-07'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id='063S22004100040100');

-- 7. zone_standards for the new RCMH 1 district (G regression guard --
--    real sourced dimensional standards from Sec. 24-193, not placeholders).
INSERT INTO public.zone_standards (
  zoning_district_id, max_height_ft, front_setback_ft, side_setback_ft, rear_setback_ft,
  max_lot_coverage_pct, min_lot_sqft, max_density_du_acre, source_url, ordinance_section
)
SELECT d.id, 35, 25, 25, 25, NULL, 43560, 1.0,
       'https://www.zoneomics.com/code/baker-county-unincorporated-FL/chapter_4',
       'Sec. 24-193'
FROM public.zoning_districts d
WHERE d.jurisdiction_id = 1664 AND d.code = 'RCMH 1'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards WHERE zoning_district_id = d.id);
