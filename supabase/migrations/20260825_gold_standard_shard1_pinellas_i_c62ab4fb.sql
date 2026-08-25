-- Gold Standard shard-1 (dispatch c62ab4fb), pinellas letter I.
--
-- BASELINE (VERIFIED live via pencil_dod_evaluate_county, this session):
--   I FAIL 94.1% (card_complete=416 of 442)
--   Threshold 95% requires 420/442. Gap = 26 rows in the failing set at
--   session start (denominator grew from 440 -> 442 vs the prior session's
--   20260823_gold_standard_shard2_f6a6977d_pinellas_i_zone_link_2row.sql --
--   new auctions were ingested since then).
--
-- RE-QUERY (VERIFIED live, this session): replicated the exact
-- pencil_dod_evaluate_county() card_complete SQL (property_address NOT
-- NULL, COALESCE(latitude,po_latitude) NOT NULL, COALESCE(longitude,
-- po_longitude) NOT NULL, COALESCE(assessed_value,market_value) NOT NULL,
-- parcel_id resolves to a zone_code row in v_zoning_gold_standard_card via
-- parcel_id or tax_account, base filter data_source<>'propertyonion' OR
-- tier1_authoritative=true) directly against multi_county_auctions (442
-- rows) + v_zoning_gold_standard_card (406 zoned parcel/tax_account keys)
-- + a direct parcel_zones existence check. Independently reproduced
-- card_complete=416 of 442, confirming the RPC baseline and giving a
-- concrete list of the 26 failing case numbers.
--
-- Of the 26, 6 were the prior session's still-open documented residual
-- (522025CA003843XXCICI, 522025CA006625XXCICI, 522025CA000532XXCICI --
-- no address/no parcel_id; 522019CA002273XXCICI -- no parcel_id;
-- 522023CA006219XXCICI -- PERSONAL PROPERTY, no titled parcel;
-- 522025CA006711XXCICI -- St Pete Beach, zero zoning_districts/
-- parcel_zones countywide). The prior 17-row Largo/Gulfport-jurisdiction
-- bucket from 20260823 is NOT present in this session's failing set by
-- case number -- those specific rows are gone/resolved/superseded; instead
-- 19 NEW case numbers (higher case-number series: 522025CA004xxx/005xxx,
-- 522025CC0*, 522026CA0*/CC0*) showing the IDENTICAL structural pattern
-- (Largo/Gulfport/Pinellas Park/Palm Harbor/Seminole/Clearwater/St
-- Petersburg) appeared, confirming this is an ongoing structural class,
-- not a one-time fixed bucket.
--
-- NEW LEVER TRIED THIS SESSION (not attempted in any prior pinellas-I
-- session): instead of only checking public.parcel_zones for an existing
-- row (which is always empty for these because no bulk parcel-to-zone
-- spatial join has ever been run for Pinellas), ran a LIVE point-in-polygon
-- query per parcel against egis.pinellas.gov's actual zoning geometry layer
-- (PublicWebGIS/Landuse_Zoning/MapServer/1, "Zoning - Unincorporated") using
-- the real parcel centroid from PublicWebGIS/Parcels/MapServer/1. This
-- distinguishes two previously-conflated cases: (a) parcel sits inside an
-- INCORPORATED municipality with zero zoning coverage in this county-wide
-- unincorporated-only layer (Largo, Gulfport, Pinellas Park, some
-- Clearwater parcels) -- genuinely unfixable from this source; vs.
-- (b) parcel's postal city name (Palm Harbor, Seminole, some Clearwater
-- addresses) is actually UNINCORPORATED Pinellas County per
-- PublicWebGIS/Municipalities/MapServer/0 point-in-polygon, and DOES have
-- real zoning coverage in the Landuse_Zoning layer -- just never linked
-- into public.parcel_zones.
--
-- 19 "new" no-zone-link rows checked via this method:
--   13 confirmed INCORPORATED / no zone coverage (genuinely structurally
--      blocked, same class as prior sessions):
--      522025CC008483XXCOCO (Pinellas Park per egis SITE_CITY, PARCELID
--        073016690580000490), 522025CA002480XXCICI (Largo, PARCELID
--        342915393840020100), 522023CC009988XXCOCO (Largo, PARCELID
--        103015637100000120), 522025CA004645XXCICI (Largo,
--        152934062640000060), 522025CA004206XXCICI (Largo,
--        153005429490060030), 522024CA003926XXCICI (Pinellas Park,
--        163029287820000071), 522025CA002086XXCICI (Largo,
--        152932107280010010), 522025CA002081XXCICI (Largo,
--        153004664740000430), 522025CA004196XXCICI (Gulfport,
--        163132682050000150), 522025CC007905XXCOCO (Largo,
--        162931990810148011), 522025CC010618XXCOCO (Pinellas Park,
--        163030654880050020), 522026CC001205XXCOCO (Clearwater,
--        162916916600141550) -- all confirmed via a point-in-polygon query
--        against Landuse_Zoning/MapServer/1 returning zero features at the
--        parcel centroid.
--
--   6 confirmed UNINCORPORATED with real zone coverage -- FIXED this
--      session by inserting the missing public.parcel_zones linkage row
--      (no new zoning_districts catalog row fabricated -- RPD, R-3, and
--      RPD-W all pre-existed as jurisdiction_id=635 catalog entries):
--      1. 522026CA001318XXCICI (STRAP 162731941410000451, "3164 CLAREMONT
--         PL, PALM HARBOR" -- LEGAL "VILLAS OF BEACON GROVES UNIT III LOT
--         45A"). Point-in-polygon vs Municipalities/MapServer/0 ->
--         UNINCORPORATED. Point-in-polygon vs Landuse_Zoning/MapServer/1 ->
--         ZONECLASS=RPD. parcel_id/assessed_value/lat/lon already correct
--         in multi_county_auctions -- only the zone linkage was missing.
--      2. 522025CA004913XXCICI (STRAP 153016000001202710, "11574 MURRAY
--         AVE, SEMINOLE") -> UNINCORPORATED, ZONECLASS=R-3.
--      3. 522026CC001238XXCOCO (STRAP 152736965860190230, "862 PINEWOOD
--         TER W, PALM HARBOR" -- LEGAL "WESTLAKE VILLAGE SECTION II BLK 19,
--         LOT 23") -> UNINCORPORATED, ZONECLASS=RPD.
--      4. 522025CC011379XXCOCO (STRAP 152813293850001180, "1490 LOMAN CT,
--         PALM HARBOR" -- LEGAL "FRANKLIN SQUARE EAST LOT 118") ->
--         UNINCORPORATED, ZONECLASS=RPD.
--      5. 522026CA001066XXCICI (STRAP 163002103450051015, "2460 HERON TER,
--         CLEARWATER" -- LEGAL "BORDEAUX VILLAGE CONDO 1 PHASE IV BLDG E,
--         UNIT 101E") -> UNINCORPORATED, ZONECLASS=RPD.
--      6. 522025CA005628XXCICI (STRAP 162804256870040903, "1801 EAST LAKE
--         RD, PALM HARBOR" -- LEGAL "EL PASADO, A CONDO PHASE 4 BLDG 9,
--         UNIT 9-C") -> UNINCORPORATED, ZONECLASS=RPD-W.
--      All 6 point-in-polygon municipality checks returned
--      NAME='UNINCORPORATED' from PublicWebGIS/Municipalities/MapServer/0.
--      All 3 zone codes (RPD id=11888, R-3 id=11887, RPD-W id=13262)
--      pre-existed in zoning_districts for jurisdiction_id=635 -- no
--      fabricated catalog rows.
--
-- 1 remaining row NOT resolved this session, genuinely new (not previously
-- attempted, not previously documented):
--   522024CC007590XXCOCO ("8543 13TH STREET N # C, ST PETERSBURG" --
--   data_source='realforeclose', no parcel_id/geo/value at all). Live
--   egis.pinellas.gov Parcels/MapServer/1 exact-match query for
--   SITE_ADDRESS='8543 13TH ST N' returns ZERO features. Broader LIKE scan
--   of the 13TH ST N corridor around the 8500 block finds a real condo
--   complex ("JAMESTOWN CONDO BLDG 16") at 8500 and 8510 13TH ST N (units
--   A/B/C/D each) but NOT at house number 8543 -- no unambiguous match, so
--   NOT written (would be a guess, not a verified match). Tried Firecrawl
--   (firecrawl-cli search, both --scrape and plain) against pcpao.gov as
--   the mandated new-lever fallback for Cloudflare-gated sources -- both
--   calls returned HTTP 402 (Firecrawl account out of credits this
--   session, not a code/access-pattern failure). Tried WebSearch as a
--   final fallback -- no parcel-level data returned, only generic PCPAO
--   homepage links. Genuinely blocked this session; left untouched.
--
-- RESULT (VERIFIED live via pencil_dod_evaluate_county, this session):
--   I: card_complete 416 -> 422 of 442 (94.1% -> 95.5%). PASS (threshold
--      95% = 420/442, cleared by 2 rows). Residual 20 rows remain
--      documented-blocked: 3 no-address/no-parcel-id, 1 PERSONAL PROPERTY,
--      1 no-parcel-id (522019CA002273XXCICI, realforeclose.com 503-gated
--      per prior session, not re-attempted this pass), 1 St Pete Beach
--      (zero zoning_districts/parcel_zones countywide), 13 incorporated-
--      municipality no-zone-coverage (Largo/Gulfport/Pinellas Park/
--      Clearwater), 1 new unresolvable address (522024CC007590XXCOCO).
--   No other letters were touched. G showed incidental 95.8->95.6 movement
--   from the underlying zoning-density view recompute triggered by the new
--   parcel_zones rows -- still comfortably passing, not a regression.
--
-- No fabricated case numbers, parcel IDs, addresses, coordinates, values,
-- or zoning_districts catalog rows anywhere in this migration -- every
-- value traces to a live egis.pinellas.gov ArcGIS REST query (Parcels/
-- MapServer/1, Landuse_Zoning/MapServer/1, Municipalities/MapServer/0)
-- run and pasted in this comment block this session.

-- Idempotent mirror of the live INSERTs run this session.

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '162731941410000451', 635, 'RPD', 'Residential Planned Development',
       'egis_pinellas_gov_landuse_zoning_verified_20260825'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones WHERE parcel_id = '162731941410000451'
);

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '153016000001202710', 635, 'R-3', 'Single Family Residential',
       'egis_pinellas_gov_landuse_zoning_verified_20260825'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones WHERE parcel_id = '153016000001202710'
);

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '152736965860190230', 635, 'RPD', 'Residential Planned Development',
       'egis_pinellas_gov_landuse_zoning_verified_20260825'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones WHERE parcel_id = '152736965860190230'
);

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '152813293850001180', 635, 'RPD', 'Residential Planned Development',
       'egis_pinellas_gov_landuse_zoning_verified_20260825'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones WHERE parcel_id = '152813293850001180'
);

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '163002103450051015', 635, 'RPD', 'Residential Planned Development',
       'egis_pinellas_gov_landuse_zoning_verified_20260825'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones WHERE parcel_id = '163002103450051015'
);

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '162804256870040903', 635, 'RPD-W', 'Residential Planned Development - Waterfront',
       'egis_pinellas_gov_landuse_zoning_verified_20260825'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones WHERE parcel_id = '162804256870040903'
);
