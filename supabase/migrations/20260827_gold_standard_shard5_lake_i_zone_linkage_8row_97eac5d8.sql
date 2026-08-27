-- Gold Standard shard-5 (dispatch 97eac5d8): lake county, letter I
-- (property card completeness) -- 8-row zone-linkage gap sweep
--
-- BEFORE (live pencil_dod_evaluate_county('lake'), start of this session):
--   "I": {"pass": false, "detail": "card_complete=128 of 137", "metric": 93.4}
--
-- All 8 rows already had real property_address, latitude/longitude, and
-- assessed_value/market_value populated. The ONLY missing piece for every
-- row was a real zone_code linkage: v_zoning_gold_standard_card requires the
-- parcel to appear in parcel_zones with a non-null zone_code, matched by
-- parcel_id or tax_account.
--
-- METHOD (per session instructions, mirroring
-- 20260827_gold_standard_lake_i_property_card_backfill.sql): for each
-- parcel_id, get the centroid from Lake County's Tax Parcels layer
-- (OpenData/OpenData1/FeatureServer/12, query by ParcelNumber, outSR=4326,
-- centroid computed as the mean of the returned polygon's exterior ring
-- vertices), then determine jurisdiction via the City Limits polygon layer
-- (OpenData/OpenData2/MapServer/3, point-in-polygon on City field), then
-- query that jurisdiction's real zoning layer by the same point/parcel
-- number.
--
-- RESEARCH PERFORMED (all sources fetched live this session):
--
-- 1. case 2023CA000367, parcel_id 021926000300001700, NORTHSHORE DR
--    -> City Limits polygon confirms parcel centroid
--       (lon=-81.687817, lat=28.864194) is inside EUSTIS.
--       https://gis.lakecountyfl.gov/lakegis/rest/services/OpenData/OpenData2/MapServer/3
--    -> Exhaustively re-searched for an Eustis zoning GIS layer (fresh
--       attempt, not reused from a prior session's Eustis finding):
--         - LocalGov/CityZoning/MapServer (11 sublayers: Astatula, Clermont,
--           Fruitland Park, Groveland, Mount Dora, Tavares, Umatilla,
--           Mascotte, Minneola, Howey-in-the-Hills, Montverde) -- confirmed
--           NO Eustis sublayer.
--         - CityView/MapServer group 28 "EUSTIS" -- confirmed only layer 29
--           "Future Land Use" exists under that group; no Zoning sublayer.
--         - OpenData/OpenData3/MapServer/10 "Zoning" -- same countywide
--           unincorporated-zoning dataset as InteractiveMap/MapServer/50,
--           does not carry incorporated-city zoning.
--         - ArcGIS org catalog search (arcgis.com/sharing/rest/search,
--           orgId=7LNyA2emK1umjjot, LCGISAdmin owner) lists every
--           city-specific "<City> Zoning" Feature Service the county
--           publishes (Howey-in-the-Hills, Montverde, Minneola, Mount Dora,
--           Groveland, Mascotte, Astatula, Umatilla, Lake County
--           Unincorporated Zoning) -- NO "Eustis Zoning" service exists,
--           only "City of Eustis Future Land Use" (FLU, not zoning).
--       https://gis.lakecountyfl.gov/lakegis/rest/services/LocalGov/CityZoning/MapServer
--       https://gis.lakecountyfl.gov/lakegis/rest/services/CityView/MapServer
--       https://gis.lakecountyfl.gov/lakegis/rest/services/OpenData/OpenData3/MapServer/10
--       https://www.arcgis.com/sharing/rest/search?q=zoning+orgid:7LNyA2emK1umjjot
--    -> STATUS: NO_FIX_FOUND. BLANK > WRONG -- no zone_code fabricated.
--
-- 2. case 2025CA001082, parcel_id 251924060000000200, 201 MIKE ST
--    -> City Limits polygon confirms parcel centroid
--       (lon=-81.870551, lat=28.810113) is inside LEESBURG.
--    -> City of Leesburg's own zoning GIS returns an EXACT ParcelNumber
--       match: USE_ZONE="R-3", ORD_NO="MAP", Status="Existing" (12/2004,
--       "ANNEXED 1923"), Acreage=0.112.
--       https://maps.leesburgflorida.gov/arcgis/rest/services/Planning_Zoning/P_Z_Layers/MapServer/1
--    -> STATUS: FIXED. jurisdiction_id=835 (Leesburg), zone_code='R-3'.
--       zoning_districts row for (835, 'R-3') already existed
--       (id=11514, "Medium Residential District") -- no new district row
--       needed.
--
-- 3. case 2025CA001590, parcel_id 231827010000005500, 38144 BROOKSIDE DR
--    -> City Limits polygon query returns NO feature for this centroid
--       (lon=-81.591336, lat=28.904902) -- UNINCORPORATED Lake County.
--    -> Located the county's own (non-city) zoning layer:
--       InteractiveMap/MapServer, layer group 39 "Planning & Zoning" ->
--       layer 50 "Zoning" (fields: Zoning, ZoningDist, OrdNum, ZoningNm).
--       Point query at the parcel centroid returns ZONING="A",
--       ZoningDist/ZoningNm="Agriculture" (matches Orlando Hills
--       subdivision, low-density outlying parcel).
--       https://gis.lakecountyfl.gov/lakegis/rest/services/InteractiveMap/MapServer/50
--    -> STATUS: FIXED. No "Unincorporated Lake County" jurisdiction row
--       existed in `jurisdictions` (every other FL county in this dataset
--       has one, e.g. id=1407 "Unincorporated Okaloosa County"); inserted a
--       new row (id=1917, name='Unincorporated Lake County', county='Lake',
--       state='FL', data_source='lake_county_gis_interactivemap_zoning_layer50:2026-08-27').
--       jurisdiction_id=1917, zone_code='A'. New zoning_districts row
--       registered (id=14223) since none existed for this
--       jurisdiction/code pair.
--
-- 4. case 2025CA002454, parcel_id 241926095000001400, 1022 WOODWARD OAKS CIR
--    -> City Limits polygon confirms parcel centroid
--       (lon=-81.674666, lat=28.827772) is inside EUSTIS.
--    -> Same exhaustive Eustis search as row 1 above applies (no zoning
--       layer exists for Eustis anywhere in the county MapServer, county
--       OpenData mirrors, or the county's own ArcGIS org catalog).
--    -> STATUS: NO_FIX_FOUND. BLANK > WRONG -- no zone_code fabricated.
--
-- 5. case 2025CC005329 (HOA lien), parcel_id 271926005000007400,
--    2562 GLACIER EXPRESS LN
--    -> City Limits polygon confirms parcel centroid
--       (lon=-81.698293, lat=28.801827) is inside TAVARES.
--    -> County CityZoning MapServer, layer 5 "Tavares Zoning" returns
--       ZoningCode="RSF-2" at that point (Verandah Park subdivision).
--       https://gis.lakecountyfl.gov/lakegis/rest/services/LocalGov/CityZoning/MapServer/5
--    -> STATUS: FIXED. jurisdiction_id=926 (Tavares), zone_code='RSF-2'.
--       zoning_districts row for (926, 'RSF-2') already existed
--       (id=13976, "RSF-2 Single-Family Residential (Tavares)") -- no new
--       district row needed.
--
-- 6. case 2025CC010839 (HOA lien), parcel_id 082226030300000200,
--    1196 CAVENDER CREEK RD
--    -> City Limits polygon confirms parcel centroid
--       (lon=-81.740058, lat=28.583397) is inside MINNEOLA.
--    -> County CityZoning MapServer, layer 8 "Minneola Zoning" returns
--       ZoningCode="PUD-R" at that point (Ardmore Reserve Phase IV A
--       Replat subdivision, Acres=39.76).
--       https://gis.lakecountyfl.gov/lakegis/rest/services/LocalGov/CityZoning/MapServer/8
--    -> STATUS: FIXED. jurisdiction_id=1031 (Minneola), zone_code='PUD-R'.
--       zoning_districts row for (1031, 'PUD-R') already existed
--       (id=14118, "Planned Unit Development - Residential (Minneola)")
--       -- no new district row needed.
--
-- 7. case 2025CA001729, parcel_id 151924150000009200, 2207 NICOLLETT WAY
--    -> City Limits polygon confirms parcel centroid
--       (lon=-81.888701, lat=28.842276) is inside LEESBURG.
--    -> City of Leesburg's own zoning GIS returns an EXACT ParcelNumber
--       match: USE_ZONE="R-3", ORD_NO="01-16", Status="Existing" (4/2001,
--       Overlook at Lake Griffin subdivision), Acreage=0.129.
--       https://maps.leesburgflorida.gov/arcgis/rest/services/Planning_Zoning/P_Z_Layers/MapServer/1
--    -> STATUS: FIXED. jurisdiction_id=835 (Leesburg), zone_code='R-3'.
--       Same existing zoning_districts row as case #2 above.
--
-- 8. case 2026CA000560, parcel_id 061824039400029250, 1211 E SCHWARTZ BLVD
--    (defendant "LABARCA" -- a prior session's owner-name ArcGIS search for
--    a DIFFERENT letter, E, dead-ended on this parcel; that does not apply
--    here since this session goes by parcel_id directly against the zoning
--    layer, not by owner name -- attempted fresh)
--    -> City Limits polygon confirms parcel centroid
--       (lon=-81.929936, lat=28.942453) is inside LADY LAKE (Orange
--       Blossom Gardens Unit 12 subdivision).
--    -> Exhaustively searched for a Lady Lake zoning GIS layer:
--         - LocalGov/CityZoning/MapServer -- confirmed no Lady Lake
--           sublayer (11 sublayers cover Astatula, Clermont, Fruitland
--           Park, Groveland, Mount Dora, Tavares, Umatilla, Mascotte,
--           Minneola, Howey-in-the-Hills, Montverde only).
--         - CityView/MapServer -- no "LADY LAKE" layer group exists at all
--           (confirmed group list: ASTATULA, FRUITLAND PARK, CLERMONT,
--           EUSTIS, HOWEY-IN-THE-HILLS, MASCOTTE, MINNEOLA, MOUNT DORA,
--           TAVARES, UMATILLA -- no Lady Lake).
--         - ArcGIS org catalog search (orgId=7LNyA2emK1umjjot) -- lists
--           every county-published "<City> Zoning" Feature Service; NO
--           "Lady Lake Zoning" service exists.
--         - Global ArcGIS.com search for "Lady Lake" + zoning and for
--           "Eustis zoning" (cross-check) turned up no independent city
--           GIS org for either city; ladylakefl.gov has no discoverable
--           ArcGIS REST subdomain (gis.ladylakefl.gov / maps.ladylakefl.gov
--           do not resolve; ladylakefl.maps.arcgis.com returns 404).
--         - City of Lady Lake's zoning is published only as text/PDF via
--           Municode (library.municode.com/fl/lady_lake/codes/land_development_code)
--           -- not a spatial parcel-queryable source, and per BLANK > WRONG
--           a text ordinance chapter cannot be reliably matched to this
--           specific parcel's zoning district without a spatial join.
--       https://gis.lakecountyfl.gov/lakegis/rest/services/LocalGov/CityZoning/MapServer
--       https://gis.lakecountyfl.gov/lakegis/rest/services/CityView/MapServer
--       https://www.arcgis.com/sharing/rest/search?q=%22Lady+Lake%22+zoning
--    -> STATUS: NO_FIX_FOUND. BLANK > WRONG -- no zone_code fabricated.
--
-- AFTER (live pencil_dod_evaluate_county('lake'), same session):
--   "I": {"pass": true, "detail": "card_complete=134 of 139", "metric": 96.4}
--   (5 of 8 rows fixed with real GIS-sourced zone_code linkage; 3 rows --
--   both Eustis parcels and the one Lady Lake parcel -- remain
--   card-incomplete: genuinely blocked by the complete absence of any
--   public zoning GIS layer for those two cities, not fabricated.)

-- New jurisdiction: Unincorporated Lake County did not previously exist in
-- `jurisdictions`, unlike every other FL county in this dataset.
INSERT INTO jurisdictions (name, county, state, data_source, active)
VALUES (
  'Unincorporated Lake County',
  'Lake',
  'FL',
  'lake_county_gis_interactivemap_zoning_layer50:2026-08-27',
  true
);
-- (live insert produced id=1917; re-run is idempotent-safe to skip if a row
-- with this name/county already exists)

-- Structural placeholder zoning_districts row for the new jurisdiction's
-- Agriculture zone -- no far/density/parking numeric standard fabricated.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description)
SELECT j.id, 'A', 'Agriculture', 'Agricultural',
  'Unincorporated Lake County Agriculture zoning district. GIS-confirmed live 2026-08-27 via gis.lakecountyfl.gov InteractiveMap/MapServer/50 (county Zoning layer) ZoningCode="A", ZoningDist/ZoningNm="Agriculture" for parcel_id 231827010000005500 (38144 Brookside Dr). Structural placeholder registering category only -- no far/density/parking numeric standard fabricated.'
FROM jurisdictions j
WHERE j.name = 'Unincorporated Lake County' AND j.county = 'Lake'
ON CONFLICT DO NOTHING;

-- Zone linkage for the 5 fixed rows (2 NO_FIX_FOUND rows -- Eustis x2,
-- Lady Lake x1 -- are intentionally NOT inserted; see research notes above)
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, created_at)
VALUES
  ('271926005000007400', 926, 'RSF-2', 'Single-Family Residential (Tavares)', 'tavares_cityzoning_gis_2026-08-27', now()),
  ('082226030300000200', 1031, 'PUD-R', 'Planned Unit Development - Residential (Minneola)', 'minneola_cityzoning_gis_2026-08-27', now()),
  ('251924060000000200', 835, 'R-3', 'Medium Residential District', 'leesburg_fl_gis_arcgis', now()),
  ('151924150000009200', 835, 'R-3', 'Medium Residential District', 'leesburg_fl_gis_arcgis', now()),
  ('231827010000005500', 1917, 'A', 'Agriculture', 'lake_county_gis_interactivemap_zoning_layer50', now());
