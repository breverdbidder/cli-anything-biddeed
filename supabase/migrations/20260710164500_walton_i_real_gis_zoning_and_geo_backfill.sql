-- Walton County criterion I (card completeness) real-source backfill
--
-- Target: 7 failing card_complete rows identified live (30/37 -> need >=36/37, 95%).
-- Source of truth for zoning/geometry: Walton County official EnerGov ArcGIS FeatureServer,
--   https://services1.arcgis.com/TaXHPwWfIMuzJ7Ov/arcgis/rest/services/EnerGov/FeatureServer
--   Layer 4  "Parcels"          -- PARCELNO exact match, real polygon geometry (outSR=4326)
--   Layer 19 "Zoning"           -- ZONE_CLASS, real polygon geometry, point-in-polygon against parcel centroid
--   Layer 52 "Municipalities"   -- used to confirm incorporated vs unincorporated status
-- Fetched live via WebFetch/curl during this session (2026-07-10). All PARCELNO values matched
-- exactly 1 real parcel feature each; all centroids matched exactly 1 real zoning polygon each.
--
-- IMPORTANT CORRECTION vs task brief: fl_parcels.co_no=66 is NOT Walton County in this table
-- (verified: co_no=66 rows are Saint Lucie/Fort Pierce addresses). fl_parcels.co_no=76 is the
-- real Walton County partition (verified via unique Santa Rosa Beach zip 32459 -> co_no=76 only).
-- However fl_parcels centroid_lat/centroid_lng and zone_code are NULL for effectively all of
-- Walton (0 of 88,512 rows have zone_code; only 2,451 have a centroid) so fl_parcels could not
-- be used for this backfill -- the real Walton EnerGov ArcGIS service was used instead.
-- Separately, jurisdictions.co_no=66 for DeFuniak Springs uses FL's official DOR county-number
-- scheme, which is a different numbering system than fl_parcels.co_no. Do not conflate the two.
--
-- 5 of 6 geocodable parcels are OUTSIDE any municipality polygon (confirmed via Municipalities
-- layer 52 point-in-polygon) -- i.e. unincorporated Walton County. Only 71 Neeley Ave
-- (25-3N-19-19070-001-895B) falls inside the DeFuniak Springs municipal boundary; the county's
-- own Zoning layer records that parcel as ZONE_CLASS='Municipal' (the county defers zoning
-- authority to the city and does not carry DeFuniak's internal R-1/R-2/C-1 codes in this
-- service). DeFuniak Springs has no public GIS/zoning REST service found. We record the real,
-- sourced value 'Municipal' rather than guessing a DeFuniak municipal district code.
--
-- case 26CA000030 has parcel_id/address/geo/value ALL null in multi_county_auctions and could
-- not be re-scraped from walton.realforeclose.com in this session (no browser-automation source
-- available here); it is explicitly left out of this backfill and remains a card_complete=false
-- row. BLANK > WRONG.

BEGIN;

-- 1. New jurisdiction: Unincorporated Walton County (does not previously exist; only DeFuniak
--    Springs id=842, Freeport id=861, Paxton id=1146 existed).
INSERT INTO jurisdictions (id, name, county, state, county_name, data_source, active, co_no, created_at)
SELECT 1333, 'Unincorporated Walton County', 'Walton', 'FL', 'Walton',
       'EnerGov ArcGIS FeatureServer (services1.arcgis.com/TaXHPwWfIMuzJ7Ov) — live fetch 2026-07-10',
       true, 66, now()
WHERE NOT EXISTS (SELECT 1 FROM jurisdictions WHERE id = 1333);

-- 2. zoning_districts: real ZONE_CLASS values returned by the county Zoning layer (layer 19)
--    for the 5 unincorporated parcels + the 1 DeFuniak 'Municipal' placeholder value.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section)
VALUES
  (1333, 'Rural Low Density',        'Rural Low Density',        'residential', '2018-29'),
  (1333, 'Rural Residential',        'Rural Residential',        'residential', '2018-29'),
  (1333, 'Rural Village',            'Rural Village',             'mixed',      '2018-29'),
  (1333, 'General Agriculture',      'General Agriculture',      'agricultural','2018-29'),
  (1333, 'Residential Preservation', 'Residential Preservation', 'residential', '2018-29')
ON CONFLICT DO NOTHING;

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section)
SELECT 842, 'Municipal', 'Municipal (county-deferred; DeFuniak Springs governs actual district)', 'deferred', '2018-29'
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 842 AND code = 'Municipal');

-- 3. parcel_zones: real point-in-polygon result per parcel (parcel centroid computed from the
--    EnerGov Parcels layer 4 polygon geometry, outSR=4326; intersected against Zoning layer 19).
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, source, effective_date)
VALUES
  ('16-3N-20-28060-022-0260', '16-3N-20-28060-022-0260', 1333, 'Rural Low Density',
   'walton_enerGov_arcgis/point_in_polygon_live_2026-07-10', '2018-12-11'),
  ('15-3N-20-28070-036-0600', '15-3N-20-28070-036-0600', 1333, 'Rural Residential',
   'walton_enerGov_arcgis/point_in_polygon_live_2026-07-10', '2018-12-11'),
  ('01-3N-20-28040-00A-0050', '01-3N-20-28040-00A-0050', 1333, 'Rural Village',
   'walton_enerGov_arcgis/point_in_polygon_live_2026-07-10', '2018-12-11'),
  ('36-3N-20-28000-010-0020', '36-3N-20-28000-010-0020', 1333, 'General Agriculture',
   'walton_enerGov_arcgis/point_in_polygon_live_2026-07-10', '2018-12-11'),
  ('14-3S-19-25040-004-0010', '14-3S-19-25040-004-0010', 1333, 'Residential Preservation',
   'walton_enerGov_arcgis/point_in_polygon_live_2026-07-10', '2018-12-11'),
  ('25-3N-19-19070-001-895B', '25-3N-19-19070-001-895B', 842, 'Municipal',
   'walton_enerGov_arcgis/point_in_polygon_live_2026-07-10', '2018-12-11')
ON CONFLICT DO NOTHING;

-- 4. Backfill lat/lon for the 2 rows with real address+value but missing geo.
--    Coordinates = real parcel centroid computed from EnerGov Parcels layer 4 geometry
--    (outSR=4326), fetched live via PARCELNO exact match, same session as above.
UPDATE multi_county_auctions
SET latitude = 30.751201844826785,
    longitude = -86.25166154261589
WHERE county = 'walton' AND case_number = '2026-0010TD'
  AND parcel_id = '16-3N-20-28060-022-0260'
  AND latitude IS NULL AND longitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 30.752912367933302,
    longitude = -86.23872661614412
WHERE county = 'walton' AND case_number = '2026-0009TD'
  AND parcel_id = '15-3N-20-28070-036-0600'
  AND latitude IS NULL AND longitude IS NULL;

COMMIT;
