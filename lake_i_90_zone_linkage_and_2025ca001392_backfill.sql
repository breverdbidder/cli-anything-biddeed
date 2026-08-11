-- Gold Standard letter I fix for county=lake
-- Root causes fixed (from live diagnosis, metric 90.76% = 108/119):
--   (A) 2025CA001392: parcel_id/property_address/lat/lon/assessed_value were all NULL
--       (foreclosure calendar row with no legal description). Resolved via Lake County
--       Property Appraiser GIS owner-name search (OwnerName LIKE '%DUHAMEL%') which
--       matched "DUHAMELL ASHLY" (case defendant "ASHLY DUHAMELL, ET AL") to parcel
--       271924170000O00800, 110 S CHESTER ST, Leesburg FL 34748.
--       Source: https://gis.lakecountyfl.gov/lakegis/rest/services/PropertyAppraiser/FieldMap/MapServer/0
--               query: ParcelNumber='271924170000O00800'
--   (B) 6 rows had parcel_id + address/geo/value populated but NO row in parcel_zones
--       (Lake county's parcel_zones table only had a 107-row seed, none of these 6
--       section-township-range parcels were in it). Resolved by querying the live
--       jurisdiction zoning GIS layer for each parcel's centroid:
--         - 241925030000C01100 (2026CA000288)  -> Tavares  R-6  (Urban Residential)
--         - 271926005000008000 (2025CA002620)  -> Tavares  RSF-2
--           source: https://gis.lakecountyfl.gov/lakegis/rest/services/PropertyAppraiser/FieldMap/MapServer/35
--                   (CityZoning layer, City=5=Tavares); RSF-2 confirmed as a real Tavares
--                   zoning district per Tavares LDC Appendix A Ch.8 (Municode)
--         - 121926130000A01200 (2025CA001795)   -> Eustis    SR (Suburban Residential)
--         - 101926040000002300 (2025CA002017)   -> Eustis    SR (Suburban Residential)
--           source: https://gis.lakecountyfl.gov/lakegis/rest/services/LocalGov/CityFLU/MapServer/2
--                   (Eustis has no traditional zoning districts -- it regulates via Future
--                   Land Use / Land Use Districts per Eustis LDR Ch.109-110; SR = Suburban
--                   Residential, max density 5 du/acre, confirmed via official City of
--                   Eustis SR district handout)
--         - 271924170000N00200 (2025CA001078)   -> Leesburg  R-2
--         - 221924040000000F04 (2025CA001198)   -> Leesburg  R-2
--           source: https://maps.leesburgflorida.gov/arcgis/rest/services/Planning_Zoning/P_Z_Layers/MapServer/1
--                   (live Leesburg Planning & Zoning GIS, field USE_ZONE, exact ParcelNumber match)
--       Also added 271924170000O00800 (Leesburg, R-1) for the newly-backfilled 2025CA001392.
--
-- NOT fixed in this pass (genuinely blocked, no real source found -- left as-is, no
-- fabricated data written):
--   2023CA000367 (BUILD REI LLC / PRIDE FUNDING LLC)      -- no parcel/legal-desc on clerk
--     sale_details page; owner-name search on Lake GIS returned no plausible match.
--   2024CA002312 (WFK & ASSOCIATES II LLP / MAUREEN A DALY ET AL) -- same; "Daly" search on
--     Lake GIS OwnerName returned zero rows containing "Maureen"; likely already transferred
--     off the pre-foreclosure defendant's name.
--   2025CA001729 (U.S. BANK / TIFFANY MONIQUE CARTWRIGHT ET AL) -- "Cartwright" search
--     returned 13 unrelated Cartwright-family parcels, none first-name "Tiffany".
--   2026CA000560 (U.S. BANK / MARYLINDA LABARCA ET AL)     -- "Labarca" search on Lake GIS
--     OwnerName returned zero rows.
--   Court-record / official-records name search (officialrecords.lakecountyclerk.org) and
--   qPublic (qpublic.schneidercorp.com) both require an interactive JS session that was not
--   available in this environment (qPublic returns 403 to scripted fetches; official records
--   site issues a redirect requiring session state). No browser-automation tool was available
--   in this session (browser-use CLI not installed). These 4 rows remain as-is.
--
-- Net effect: 108/119 (90.76%) -> 115/119 (96.64%) card_complete, clears the 95% pass bar.

BEGIN;

-- (A) Backfill 2025CA001392 auction row: parcel_id, property_address, geo, assessed_value
UPDATE multi_county_auctions
SET parcel_id = '271924170000O00800',
    property_address = '110 S CHESTER ST',
    city = 'LEESBURG',
    zip = '34748',
    latitude = 28.81062352445972,
    longitude = -81.89373006691162,
    assessed_value = 113395,
    assessed_value_source = 'lake_county_property_appraiser_gis_2026-08-11'
WHERE case_number = '2025CA001392'
  AND lower(county) = 'lake';

-- (B) Insert parcel_zones rows for the 6 previously-unlinked parcels + the newly backfilled one
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source, effective_date)
VALUES
  -- Tavares
  ('24-19-25-030000C01100', '241925030000C01100', 926, 'R-6',   'Urban Residential',      'tavares_cityzoning_gis_2026-08-11', CURRENT_DATE),
  ('27-19-26-005000008000', '271926005000008000', 926, 'RSF-2', 'Single-Family Residential (Tavares)', 'tavares_cityzoning_gis_2026-08-11', CURRENT_DATE),
  -- Eustis (Future Land Use / Land Use District, no traditional zoning per Eustis LDR Ch.109)
  ('12-19-26-130000A01200', '121926130000A01200', 969, 'SR',    'Suburban Residential (Eustis FLU district)', 'eustis_cityflu_gis_2026-08-11', CURRENT_DATE),
  ('10-19-26-040000002300', '101926040000002300', 969, 'SR',    'Suburban Residential (Eustis FLU district)', 'eustis_cityflu_gis_2026-08-11', CURRENT_DATE),
  -- Leesburg
  ('27-19-24-170000N00200', '271924170000N00200', 835, 'R-2',   'R-2 Medium Density Residential District (Leesburg)', 'leesburg_planning_zoning_gis_2026-08-11', CURRENT_DATE),
  ('22-19-24-040000000F04', '221924040000000F04', 835, 'R-2',   'R-2 Medium Density Residential District (Leesburg)', 'leesburg_planning_zoning_gis_2026-08-11', CURRENT_DATE),
  ('27-19-24-170000O00800', '271924170000O00800', 835, 'R-1',   'Rural Residential (Leesburg)', 'leesburg_planning_zoning_gis_2026-08-11', CURRENT_DATE)
ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

COMMIT;
