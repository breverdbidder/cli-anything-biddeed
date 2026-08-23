-- Gold Standard shard-5 (dispatch 79ee1554): CLAY county criterion I (property card
-- completeness) backfill.
--
-- Diagnosis (pre-verified, not re-derived here): all 20 target auction rows already have
-- complete property_address + lat/long + assessed_value in multi_county_auctions. The
-- ONLY missing element is zoning linkage: their parcel_id was absent from parcel_zones,
-- which v_zoning_gold_standard_card / pencil_dod_evaluate_county's I-criterion requires
-- (a matching row in parcel_zones with non-null zone_code, matched on parcel_id OR
-- tax_account).
--
-- Sourcing (live, spatial point-in-polygon queries against public GIS, run 2026-08-23):
--   17 parcels: Clay County GIS "Zoning" FeatureServer/0
--     https://maps.claycountygov.com/server/rest/services/Zoning/FeatureServer/0
--     Queried by (longitude,latitude) from multi_county_auctions.longitude/latitude via
--     esriGeometryPoint intersects. Zone code taken from the `Zoning` field, which is
--     the field driving the service's published unique-value legend (verified via the
--     FeatureServer's drawingInfo.renderer). zone_name = the legend label text for that
--     code (e.g. BFPUD -> "Brannan Field PUD", AR -> "Agricultural/Residential").
--   2 parcels (Green Cove Springs municipal boundary): the county layer returns the
--     placeholder code "GCSMUNI" ("Municipalities") for parcels inside incorporated
--     Green Cove Springs, meaning county zoning does not apply. Sourced instead from the
--     City of Green Cove Springs' own live ArcGIS Feature Service
--     "GreenCoveSpringsPlanning" (owner lawalsh_GCS, item 5e48abc2d0904321801bbbf7bcf8a38c),
--     layer 3 "Zoning(Old)" -- the only Zoning layer present in that service --
--     https://services2.arcgis.com/R0MaBWycrb80Pvlu/arcgis/rest/services/GreenCoveSpringsPlanning/FeatureServer/3
--     Matched by spatial point query AND cross-checked against the layer's own PIN and
--     HOUSE_NO/STREET/ST_MD fields, which matched our parcel_id suffix and
--     property_address exactly for both rows (PIN 017007-001-24 = 435 MELROSE AVE;
--     PIN 018400-001-03 = 1505 NORTH ST). Zone = "R2" (city Single-Family Residential).
--   jurisdiction_id 1195 = "Clay County (Unincorporated)" (existing row, used for all
--     county-GIS-sourced parcels including those in un-annexed enclaves like Brannan
--     Field PUD which is itself an unincorporated PUD, not a municipality).
--   jurisdiction_id 886 = "Green Cove Springs" (existing row, used for the 2 GCS parcels).
--
-- Residual / NOT fixed in this migration (reported, not fabricated):
--   2026-0042TD / parcel_id 410426-020240-000-00 (1932 GLEN ST, Orange Park) -- the
--   county GIS layer returns "OPMUNI" (Orange Park municipal boundary placeholder). No
--   live ArcGIS REST zoning FeatureServer could be found for the Town of Orange Park
--   (searched arcgis.com item search, the town's Planning & Zoning page, and general
--   web search); the town only publishes a static 10MB zoning-map PDF
--   (cdn.saffire.com/files.ashx?...OP_Zoning_24x36...pdf) with no parcel-level lookup.
--   Extracting a parcel-precise zone from a raster/vector map image without a
--   verifiable coordinate match would risk fabricating a value, which is prohibited.
--   Left NULL / unlinked. This is the only remaining gap after this migration
--   (185 of 186 = 99.5%, still clears the >=95% I-criterion threshold).

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('36-04-24-005924-007-62', '360424-005924-007-62', 1195, 'BFPUD', 'Brannan Field PUD', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('32-04-25-009016-011-98', '320425-009016-011-98', 1195, 'BFPUD', 'Brannan Field PUD', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('30-04-25-008069-008-80', '300425-008069-008-80', 1195, 'BFPUD', 'Brannan Field PUD', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('17-08-23-001799-003-00', '170823-001799-003-00', 1195, 'BB', 'Intermediate Business', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('22-05-25-010109-004-83', '220525-010109-004-83', 1195, 'PUD', 'Planned Unit Development', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('42-04-25-008814-244-60', '420425-008814-244-60', 1195, 'RB', 'Single-Family Residential', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('330823-005230-000-00', '330823-005230-000-00', 1195, 'AR', 'Agricultural/Residential', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('080425-007876-002-83', '080425-007876-002-83', 1195, 'BFPUD', 'Brannan Field PUD', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('230425-020570-003-00', '230425-020570-003-00', 1195, 'AR', 'Agricultural/Residential', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('130425-007914-000-00', '130425-007914-000-00', 1195, 'RB', 'Single-Family Residential', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('240524-006567-001-00', '240524-006567-001-00', 1195, 'LA RC', 'LA RC', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('130524-021388-054-98', '130524-021388-054-98', 1195, 'PUD', 'Planned Unit Development', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('030824-006919-447-00', '030824-006919-447-00', 1195, 'AR', 'Agricultural/Residential', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('080524-005951-005-37', '080524-005951-005-37', 1195, 'AR', 'Agricultural/Residential', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('080425-007873-004-30', '080425-007873-004-30', 1195, 'BFPUD', 'Brannan Field PUD', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('37-05-26-014609-136-00', '370526-014609-136-00', 1195, 'RB', 'Single-Family Residential', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('11-08-23-001171-000-00', '110823-001171-000-00', 1195, 'AR-2', 'Rural Estates', 'clay_county_gis_zoning_featureserver_20260823_spatial'),
  ('38-06-26-017007-001-24', '380626-017007-001-24', 886, 'R2', 'Single Family Residential (R2, GCS Planning)', 'greencovesprings_arcgis_zoning_20260823_spatial'),
  ('38-06-26-018400-001-03', '380626-018400-001-03', 886, 'R2', 'Single Family Residential (R2, GCS Planning)', 'greencovesprings_arcgis_zoning_20260823_spatial')
ON CONFLICT DO NOTHING;
