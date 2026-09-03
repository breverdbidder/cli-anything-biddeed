-- Gold Standard, DOD letter I (property_card_complete)
-- County: pinellas
--
-- BEFORE (live pencil_dod_evaluate_county): card_complete=447/476 (93.9%) — FAIL (need >=453/476, 95.0%)
-- AFTER  (live pencil_dod_evaluate_county): card_complete=451/476 (94.7%) — still FAIL, +4 rows
--
-- Root cause: rows already had property_address, latitude/longitude, and
-- assessed_value/market_value populated in multi_county_auctions, and had a
-- real (non-placeholder) parcel_id. The ONLY missing requirement was a
-- zone_code link via parcel_zones -> v_zoning_gold_standard_card.
--
-- Method: for each candidate row (parcel_id present, address present, no zone
-- match in v_zoning_gold_standard_card), queried the parcel's live lat/lon
-- against the correct jurisdiction's real public zoning GIS ArcGIS REST
-- endpoint (point-in-polygon, geometryType=esriGeometryPoint, inSR=4326,
-- spatialRel=esriSpatialRelIntersects). All 4 codes below are real, current
-- zoning classifications returned live by the respective jurisdiction's own
-- authoritative zoning layer -- none fabricated.
--
-- Row 1: case 522022CA000823XXCICI, parcel_id 163126896760020050,
--   address "1551 31ST ST S, ST PETERSBURG, FL- 33712" (27.754516, -82.675516)
--   Source: City of St. Petersburg egis, ServicesDSD/Zoning MapServer, layer 2
--     "Zoning Districts": https://egis.stpete.org/arcgis/rest/services/ServicesDSD/Zoning/MapServer/2/query
--   Result: ZONECLASS="NTM-1", ZONEDESC="NEIGHBORHOOD TRADITIONAL MIXED-RESIDENTIAL"
--   jurisdiction_id 814 = "St. Petersburg" per public.jurisdictions
--
-- Row 2: case 522026CC000678XXCOCO, parcel_id 152811358530020270,
--   address "455 ALT 19 S # 27, PALM HARBOR, FL- 34683" (28.062785, -82.774121)
--   Palm Harbor has no separate municipal government (unincorporated) -- confirmed
--   no "Palm Harbor" row exists in public.jurisdictions; zoning authority is
--   Pinellas County itself.
--   Source: Pinellas County egis, PublicWebGIS/Landuse_Zoning MapServer, layer 1
--     "Zoning - Unincorporated": https://egis.pinellas.gov/gis/rest/services/PublicWebGIS/Landuse_Zoning/MapServer/1/query
--   Result: ZONECLASS="RPD", ZONEDESC="RPD"
--   jurisdiction_id 635 = "Pinellas County (Unincorporated)" per public.jurisdictions
--
-- Row 3: case 522026CA003221XXCICI, parcel_id 162918242460050100,
--   address "61 BAYWOOD AVE, CLEARWATER, FL- 33765" (27.965728, -82.739017)
--   Source: City of Clearwater GIS, ArcGISMapServices/Zoning_WGS84 MapServer, layer 1
--     "Zoning": https://gis.myclearwater.com/arcgis/rest/services/ArcGISMapServices/Zoning_WGS84/MapServer/1/query
--   Result: ZONING="LMDR", ZONING_DESC="Low Medium Density Residential"
--   jurisdiction_id 856 = "Clearwater" per public.jurisdictions
--
-- Row 4: case 522024CA003970XXCICI, parcel_id 152936455040001850,
--   address "500 HILLCREST DR, LARGO, FL- 33771" (27.9, -82.72) -- postal city
--   "Largo" but this coordinate falls OUTSIDE Largo's municipal boundary
--   (confirmed: point-in-polygon query against Pinellas County's unincorporated
--   zoning layer returned a match, meaning the parcel is unincorporated).
--   Source: Pinellas County egis, PublicWebGIS/Landuse_Zoning MapServer, layer 1
--     "Zoning - Unincorporated" (same endpoint as Row 2)
--   Result: ZONECLASS="RMH", ZONEDESC="RMH"
--   jurisdiction_id 635 = "Pinellas County (Unincorporated)" per public.jurisdictions
--
-- BLOCKED (documented, not fabricated) -- 16 remaining I-gap rows for pinellas,
-- ~45min budget reached before resolution:
--   - 1 row: case 522026CC002773XXCOCO has parcel_id literal string
--     "Property Appraiser" (garbage placeholder, not a real parcel ID) --
--     not fixable without deeper docket research to find the real parcel.
--   - 12 rows: postal-city "LARGO" addresses that ARE inside Largo's actual
--     municipal boundary (confirmed via negative point-in-polygon hit against
--     the county's unincorporated zoning layer). City of Largo's own GIS
--     (maps.largo.com/arcgis/rest/services) requires an ArcGIS token
--     ("Token Required", code 499) on every folder checked
--     (Geodatabase_Features, geodatabase_layers) and its one open MapServer
--     (Largo_GIS_Viewer_Map) does not publish a base zoning polygon layer
--     (only overlay/CRD/activity-center layers). No public unauthenticated
--     Largo zoning REST endpoint was found after checking maps.largo.com,
--     gis.largo.com (unresolvable), and web search for hosted/open-data
--     FeatureServer alternatives.
--   - 2 rows: "PINELLAS PARK" postal addresses, also inside that city's
--     municipal boundary (negative hit against county unincorporated layer).
--     No public ArcGIS REST endpoint found for gis.pinellas-park.com /
--     gis.pinellaspark.gov (both non-resolving); the city's public zoning
--     viewer is an ArcGIS Online webappviewer (id 0e17a532289848c4b7fcc2de3c993771)
--     whose underlying item is inaccessible via the AGOL sharing API
--     ("Item does not exist or is inaccessible").
--   - 1 row: "NORTH REDINGTON BEACH" -- Pinellas County's AGO/PPC_Data
--     MapServer (which hosts per-municipality zoning layers for several small
--     beach cities, e.g. Seminole, Indian Rocks Beach, Indian Shores) returned
--     "Service AGO/PPC_Data/MapServer not started" (HTTP 500) on every retry
--     across this session -- service appears to be stopped/deprecated on the
--     county's ArcGIS Server, not a transient cold-start.
--
-- Next step for a future session: either (a) obtain an ArcGIS token for
-- maps.largo.com's Geodatabase_Features service and locate its zoning layer
-- ID, (b) find Pinellas Park's zoning REST endpoint through a different
-- channel (e.g. contacting the city's IT dept per pinellas-park.com/1430),
-- or (c) ask Pinellas County GIS admin to restart the AGO/PPC_Data service,
-- which would likely resolve the North Redington Beach row directly.

INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES
  (
    '163126896760020050',
    NULL,
    814,
    'NTM-1',
    'NEIGHBORHOOD TRADITIONAL MIXED-RESIDENTIAL',
    'stpete_egis_ServicesDSD_Zoning_layer2'
  ),
  (
    '152811358530020270',
    NULL,
    635,
    'RPD',
    'RPD',
    'pinellas_egis_PublicWebGIS_Landuse_Zoning_layer1'
  ),
  (
    '162918242460050100',
    NULL,
    856,
    'LMDR',
    'Low Medium Density Residential',
    'myclearwater_gis_ArcGISMapServices_Zoning_WGS84_layer1'
  ),
  (
    '152936455040001850',
    NULL,
    635,
    'RMH',
    'RMH',
    'pinellas_egis_PublicWebGIS_Landuse_Zoning_layer1'
  )
ON CONFLICT DO NOTHING;
