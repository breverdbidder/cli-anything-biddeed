-- GOLD STANDARD shard-2 (jackson/citrus/clay/gadsden/hamilton), dispatch bca41e8b-a306-444b-a860-b0f5c34e605a
-- All statements below were already executed live via the Supabase Management API during this
-- session (direct psql/pooler auth was broken in the CI sandbox this run); this file is the
-- audit-trail record per "Schema changes via Supabase migrations only". Idempotent guards added
-- so a re-run is a no-op.

-- ============================================================
-- CITRUS: E fix (parcel linkage 76.2% -> 96.3%, PASS)
-- 38 of 45 null-parcel_id rows resolved via SWFWMD ArcGIS FeatureServer
-- (BaseVector/parcel_search/MapServer/2, ALTKEY field matched to property_address).
-- 7 left NULL (6 rows have no address/legal description in our DB at all; 1 is a
-- "0 NO ACCESS" landlocked notation matching 6 ambiguous candidate parcels) -- BLANK > WRONG.
-- ============================================================
UPDATE multi_county_auctions SET parcel_id='1437237' WHERE county='citrus' AND case_number='2026-0112TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1438519' WHERE county='citrus' AND case_number='2026-0113TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1635241' WHERE county='citrus' AND case_number='2026-0114TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1635781' WHERE county='citrus' AND case_number='2026-0115TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1428521' WHERE county='citrus' AND case_number='2026-0116TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1430101' WHERE county='citrus' AND case_number='2026-0117TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1432383' WHERE county='citrus' AND case_number='2026-0118TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1433673' WHERE county='citrus' AND case_number='2026-0119TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1635110' WHERE county='citrus' AND case_number='2026-0121TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1643422' WHERE county='citrus' AND case_number='2026-0122TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1634954' WHERE county='citrus' AND case_number='2026-0123TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='2749164' WHERE county='citrus' AND case_number='2026-0124TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1442621' WHERE county='citrus' AND case_number='2026-0125TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1637198' WHERE county='citrus' AND case_number='2026-0128TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1646081' WHERE county='citrus' AND case_number='2026-0129TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1649382' WHERE county='citrus' AND case_number='2026-0130TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1646308' WHERE county='citrus' AND case_number='2026-0131TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1644305' WHERE county='citrus' AND case_number='2026-0132TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='2948647' WHERE county='citrus' AND case_number='2026-0135TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1643163' WHERE county='citrus' AND case_number='2026-0136TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1646260' WHERE county='citrus' AND case_number='2026-0137TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1648483' WHERE county='citrus' AND case_number='2026-0138TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1650437' WHERE county='citrus' AND case_number='2026-0139TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1650941' WHERE county='citrus' AND case_number='2026-0140TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1649790' WHERE county='citrus' AND case_number='2026-0141TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='3316592' WHERE county='citrus' AND case_number='2026-0142TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1588782' WHERE county='citrus' AND case_number='2026-0143TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1112044' WHERE county='citrus' AND case_number='2026-0144TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='3526121' WHERE county='citrus' AND case_number='2026-0145TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1199611' WHERE county='citrus' AND case_number='2026-0147TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1658900' WHERE county='citrus' AND case_number='2026-0148TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1657407' WHERE county='citrus' AND case_number='2026-0149TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1527082' WHERE county='citrus' AND case_number='2026-0150TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1657423' WHERE county='citrus' AND case_number='2026-0151TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1482585' WHERE county='citrus' AND case_number='2026-0152TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1517494' WHERE county='citrus' AND case_number='2026-0153TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='3220777' WHERE county='citrus' AND case_number='2026-0156TD' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='1665001' WHERE county='citrus' AND case_number='2026-0158TD' AND parcel_id IS NULL;
-- Residual: citrus I still fails (75.7%, up from 74.1%) -- gated by near-empty Citrus
-- zonewise coverage (0 zoning_assignments rows, only 214 parcel_zones rows countywide).
-- Requires a Phase 3/4 zonewise ingestion for Citrus (jurisdiction seeding + municode/GIS
-- zoning scrape), out of scope for a parcel-linkage fix. Flagged for the next session.

-- ============================================================
-- CLAY: C/D/I fix (92.1% -> 100.0% each) + G fix (regressed to 87.7%, recovered to 97.6%)
-- Root cause C/D: 11 rows with parity_status IS NULL were simply never run through the
-- existing parity harvester (scripts/shard_gs_clay_okeechobee_cd_parity.py) because their
-- auction_date fell outside its last-run window -- re-ran it scoped to the 5 missing dates
-- against clay.realforeclose.com / clay.realtaxdeed.com, all 11 matched clean.
-- Root cause I on the same 11 rows: missing lat/long + parcel_zones. Backfilled via Clay
-- County's own ArcGIS Parcel + Zoning MapServers (maps.claycountygov.com:6443/arcgis/rest/services).
-- ============================================================
INSERT INTO zoning_districts (jurisdiction_id, code, name)
SELECT 1195, v.code, v.name FROM (VALUES
  ('BFPUD', 'Branan Field Planned Unit Development'),
  ('RB', 'Single-Family Residential District'),
  ('AR-2', 'Rural Estates District'),
  ('LA MPC', 'Lake Asbury Master Planned Community')
) AS v(code, name)
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts d WHERE d.jurisdiction_id = 1195 AND d.code = v.code);

INSERT INTO parcel_zones (jurisdiction_id, parcel_id, zone_code, zone_name, source)
SELECT * FROM (VALUES
  (1195, '05-05-25-009016-009-29', 'BFPUD', 'Branan Field Planned Unit Development', 'clay_county_gis_zoning_mapserver_20260718'),
  (1195, '09-05-24-005953-117-00', 'AR', 'Agricultural Residential', 'clay_county_gis_zoning_mapserver_20260718'),
  (1195, '29-05-26-014446-004-05', 'PUD', 'Planned Unit Development', 'clay_county_gis_zoning_mapserver_20260718'),
  (1195, '26-04-24-005606-142-00', 'BFPUD', 'Branan Field Planned Unit Development', 'clay_county_gis_zoning_mapserver_20260718'),
  (1195, '18-04-26-020264-076-00', 'RB', 'Single-Family Residential District', 'clay_county_gis_zoning_mapserver_20260718'),
  (1195, '34-04-25-008154-002-02', 'AR', 'Agricultural Residential', 'clay_county_gis_zoning_mapserver_20260718'),
  (1195, '17-07-27-016083-001-42', 'AR', 'Agricultural Residential', 'clay_county_gis_zoning_mapserver_20260718'),
  (1195, '01-04-25-011621-000-00', 'RB', 'Single-Family Residential District', 'clay_county_gis_zoning_mapserver_20260718'),
  (1195, '11-08-23-001229-000-00', 'AR-2', 'Rural Estates District', 'clay_county_gis_zoning_mapserver_20260718'),
  (1195, '39-05-25-010097-010-45', 'LA MPC', 'Lake Asbury Master Planned Community', 'clay_county_gis_zoning_mapserver_20260718'),
  (1195, '25-07-26-015972-001-00', 'AR', 'Agricultural Residential', 'clay_county_gis_zoning_mapserver_20260718')
) AS v(jurisdiction_id, parcel_id, zone_code, zone_name, source)
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v.jurisdiction_id);

-- G recovery: real sourced density values for the 3 gap-causing districts (Clay County LDC +
-- Lake Asbury Comp Plan), and a structural N/A flag for the process-only generic PUD district.
-- AR-2 (Rural Estates) and BFPUD (Branan Field, sub-classification-dependent 1u/5ac-20du/ac
-- range too wide to collapse into one scalar) intentionally left without zone_standards rows --
-- no fabrication, real values not locatable / not representable in this schema.
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
SELECT zd.id, 2.00,
  'https://claycounty.novusagenda.com/agendapublic/AttachmentViewer.ashx?AttachmentID=1103&ItemID=738',
  'Clay County LDC Sec. 3-13(e) - Agricultural/Residential District (Zone AR); density tiered by FLU overlay 1u/20ac (Agriculture) to 2u/ac (Urban Fringe/Urban Core ceiling); value stored is the ceiling of a tiered table, not a flat district-wide max',
  0.60, now()
FROM zoning_districts zd WHERE zd.jurisdiction_id = 1195 AND zd.code = 'AR'
  AND NOT EXISTS (SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id);

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
SELECT zd.id, 6.00,
  'https://claycounty.novusagenda.com/agendapublic/AttachmentViewer.ashx?AttachmentID=1339&ItemID=876',
  'Clay County LDC Sec. 3-17(e) - Single-Family Residential District (Zone RB); density tiered by FLU overlay 1u/ac (Rural Fringe) to 6u/ac (Urban Core + central water/sewer ceiling); max_far/parking intentionally NULL: RB regulates bulk via 30% max lot coverage instead of FAR, parking is keyed to use-type not zoning district',
  0.60, now()
FROM zoning_districts zd WHERE zd.jurisdiction_id = 1195 AND zd.code = 'RB'
  AND NOT EXISTS (SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id);

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
SELECT zd.id, 3.00,
  'https://claycounty.novusagenda.com/agendapublic/DisplayAgendaPDF.ashx?MinutesMeetingID=1035',
  'Lake Asbury Future Land Use Element Policy 1.4.10 (Clay County Comp Plan), per Planning Commission staff density analysis at CPA 2021-11 hearing: "LA MPC - Single-Detached - 3 units per acre" (single-family attached sub-type is 6-10 du/ac, not stored here as this district code applies to detached parcels)',
  0.75, now()
FROM zoning_districts zd WHERE zd.jurisdiction_id = 1195 AND zd.code = 'LA MPC'
  AND NOT EXISTS (SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id);

UPDATE zoning_districts SET density_regulated = false, far_regulated = false
WHERE jurisdiction_id = 1195 AND code = 'PUD';

-- ============================================================
-- GADSDEN: no letter flipped this session (honest null result). One real data-quality
-- fix landed: Chattahoochee R-2 zone_standards row now carries a real municode citation
-- instead of being unsourced.
-- ============================================================
UPDATE zone_standards
SET max_density_du_acre = 6.00, max_lot_coverage_pct = 60.0,
    source_url = 'http://chattahoochee.elaws.us/code/chii',
    ordinance_section = '§ 2.02.02.C',
    confidence_score = 0.95, scraped_at = now()
WHERE id = 1826;
