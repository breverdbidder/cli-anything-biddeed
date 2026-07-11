-- GOLD STANDARD SHARD-1 (duval/gadsden/okeechobee/columbia) — dispatch a1f33d10, 3rd firing
-- Columbia G/I: real unincorporated-Columbia-County zoning via the county's live
-- ArcGIS Enterprise Portal (gis.columbiacountyfla.com/portal), discovered fresh this
-- session (the previously-tried gis.columbiacountyfla.com/arcgis path was a dead
-- default-IIS landing page — genuinely different, working host path).
--
-- Source: https://gis.columbiacountyfla.com/hosting/rest/services/Zoning_Atlas/FeatureServer/1
-- (live ArcGIS FeatureServer, field FinalZng = zone code, MinLotSizeInAcres,
-- SetbackFront/Rear/Sides). Every parcel_zones and zone_standards row below was
-- independently adversarially re-verified this session (re-queried live, not
-- trusted from a single fetch) — see gold_standard_ultraloop_audit rows for this
-- dispatch_id, letter G/I, county columbia.
--
-- max_density_du_acre is DERIVED from the verified MinLotSizeInAcres (1 dwelling
-- unit per minimum lot = standard single-family/agricultural density convention),
-- the same "min-lot-area density derivation" methodology already used elsewhere in
-- this campaign (e.g. jefferson G, hendry G). NOT a guess: min_lot_sqft itself is
-- the independently-verified GIS value; only the 1-unit-per-lot arithmetic is
-- applied. far_regulated is left NULL (not asserted false) — these are
-- agricultural/residential districts where v_zoning_district_applicability's
-- default (FAR not applicable unless commercial/industrial/mixed-use) already
-- correctly excludes them from the FAR denominator; we did not independently
-- source a text ordinance confirming "no FAR" the way Okeechobee's AG district was.
--
-- 5 of 15 Columbia target parcels (02123-027, 04236-236, 00312-008, 00130-000,
-- 04232-001) returned a plausible A-3 zone_code from the same GIS query pattern
-- but FAILED independent adversarial re-verification this session (refuter could
-- not reproduce the specific spatial-intersect result) — deliberately NOT written.
-- 1 parcel (04023-000) is confirmed to sit inside the Town of Ft. White's own
-- municipal boundary, not unincorporated Columbia — genuinely no zone data source
-- yet, correctly left unzoned pending a Ft. White jurisdiction/ordinance session.
-- 1 parcel-half ("00130-001" of the composite case 2025-63-CA parcel_id "00130-000
-- AND 00130-001") does not resolve to any ParcelNo in the GIS layer — left alone.

BEGIN;

INSERT INTO jurisdictions (name, county, county_name, state, data_source, active)
VALUES ('Unincorporated Columbia County', 'Columbia', 'Columbia', 'FL',
        'gis.columbiacountyfla.com/hosting/rest/services (ArcGIS Enterprise Portal, verified live)', true)
RETURNING id;

-- capture the new jurisdiction id for the inserts below
DO $$
DECLARE v_jid bigint;
BEGIN
  SELECT id INTO v_jid FROM jurisdictions WHERE name = 'Unincorporated Columbia County' AND county_name = 'Columbia';

  INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, density_regulated)
  VALUES
    (v_jid, 'A-1', 'Agricultural-1',              'agricultural', 'Land Development Regulations Art. 4 Zoning Regulations Sec. 4.5 (nodeId PTILADERE_ART4ZORE_S4.5AG)', true),
    (v_jid, 'A-3', 'Agricultural-3',               'agricultural', 'Land Development Regulations Art. 4 Zoning Regulations Sec. 4.5 (nodeId PTILADERE_ART4ZORE_S4.5AG)', true),
    (v_jid, 'RSF-2', 'Residential Single-Family-2', 'residential',  'Land Development Regulations Art. 4 Zoning Regulations Sec. 4.7 (nodeId PTILADERE_ART4ZORE_S4.7RSRESIFA)', true),
    (v_jid, 'RSF/MH-2', 'Residential Single-Family/Mobile Home-2', 'residential', 'Land Development Regulations Art. 4 Zoning Regulations Sec. 4.8 (nodeId PTILADERE_ART4ZORE_S4.8RSMHREMISIFAMOHO)', true);

  INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, front_setback_ft, rear_setback_ft, side_setback_ft, max_density_du_acre, source_url, ordinance_section, confidence_score)
  SELECT zd.id, v.min_lot_sqft, v.front, v.rear, v.side, v.density,
         'https://gis.columbiacountyfla.com/hosting/rest/services/Zoning_Atlas/FeatureServer/1',
         zd.ordinance_section, 0.85
  FROM zoning_districts zd
  JOIN (VALUES
    ('A-1', 871200::numeric, 30::numeric, 25::numeric, 25::numeric, 0.05::numeric),
    ('A-3', 217800, 30, 25, 25, 0.20),
    ('RSF-2', 20000, 25, 15, 10, 2.18),
    ('RSF/MH-2', 20000, 25, 15, 10, 2.18)
  ) AS v(code, min_lot_sqft, front, rear, side, density) ON v.code = zd.code
  WHERE zd.jurisdiction_id = v_jid;

  INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
  VALUES
    ('09198-001', '10-5S-17-09198-001', v_jid, 'A-3', 'Agricultural-3', 'gis.columbiacountyfla.com_zoning_atlas_spatial_intersect_verified'),
    ('05217-001', '20-3S-17-05217-001', v_jid, 'RSF/MH-2', 'Residential Single-Family/Mobile Home-2', 'gis.columbiacountyfla.com_zoning_atlas_spatial_intersect_verified'),
    ('28-1S-17-04576-002', '28-1S-17-04576-002', v_jid, 'A-1', 'Agricultural-1', 'gis.columbiacountyfla.com_zoning_atlas_spatial_intersect_verified'),
    ('02911-104', '11-4S-16-02911-104', v_jid, 'RSF-2', 'Residential Single-Family-2', 'gis.columbiacountyfla.com_zoning_atlas_spatial_intersect_verified'),
    ('02434-101', '33-3S-16-02434-101', v_jid, 'RSF-2', 'Residential Single-Family-2', 'gis.columbiacountyfla.com_zoning_atlas_spatial_intersect_verified'),
    ('02162-004', '17-3S-16-02162-004', v_jid, 'A-3', 'Agricultural-3', 'gis.columbiacountyfla.com_zoning_atlas_spatial_intersect_verified'),
    ('05345-000', '20-3S-17-05345-000', v_jid, 'RSF/MH-2', 'Residential Single-Family/Mobile Home-2', 'gis.columbiacountyfla.com_zoning_atlas_spatial_intersect_verified'),
    ('09621-216', '07-6S-17-09621-216', v_jid, 'A-3', 'Agricultural-3', 'gis.columbiacountyfla.com_zoning_atlas_spatial_intersect_verified'),
    ('02055-015', '10-3S-16-02055-015', v_jid, 'A-3', 'Agricultural-3', 'gis.columbiacountyfla.com_zoning_atlas_spatial_intersect_verified');
END $$;

COMMIT;
