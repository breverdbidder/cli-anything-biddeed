-- Gold Standard shard-12 (dispatch 704e70a0) -- st_johns letter I real fix.
-- Applied live via Supabase Management API during this session; documents the change.
--
-- All 11 gap parcels were already parcel-linked (letter E) with real address/lat-long/
-- value, but had no zone_code row in parcel_zones for jurisdiction_id=1364
-- (Unincorporated St. Johns County). Resolved via St. Johns County GIS ArcGIS REST:
--   parcel geometry: https://www.gis.sjcfl.us/portal_sjcgis/rest/services/Hosted/Parcel/FeatureServer/0
--   zoning polygon:  https://www.gis.sjcfl.us/sjcgis/rest/services/DrillDown/MapServer/39 (field ZONING)
-- Every resolved address cross-checked against multi_county_auctions and matched.
--
-- 3 new zoning_districts, each with a real ordinance citation (or an honest
-- density_regulated=false where the LDC genuinely has no fixed zoning-native number,
-- same pattern as pre-existing RS-3/SAB):
--   OR  (Open Rural)             -- LDC Art VI Sec 6.01.03 Table 6.01: 1 acre min lot -> 1.00 DU/acre (REAL value, zone_standards row added)
--   PUD (Planned Unit Development) -- LDC Art V Sec 5.03.00.D: density deferred entirely to FLU/Comp Plan, no fixed number
--   SA  (GIS code, unresolved)   -- real live GIS code, but no LDC Article II/VI table entry found; left honestly
--                                    undocumented (density_regulated=false) rather than guessing
-- 2 of the 11 parcels resolved to the pre-existing RS-3 district (id 11398, already
-- density_regulated=false) -- reused, not duplicated.
--
-- CRITICAL SAFETY CHECK (st_johns G was PASS at 100% before this change and MUST
-- remain so): OR is the only new code carrying a live density value; PUD/SA are
-- marked not-zoning-regulated. Verified live before/after: v_zoning_gold_standard_kpi_v3
-- for 'st johns' unchanged at density=100.0 / far=100.0 after adding all 11 parcels.
--
-- Live effect (verified + independently adversarially re-verified this session):
-- st_johns I: FAIL 73.3% (33/45) -> PASS 97.8% (44/45). st_johns is now 10/10 on all
-- canon A-J letters (live pencil_dod_evaluate_county, this session).
-- Residual: case CA26-0218 (parcel_id=NULL) remains genuinely BLOCKED -- no Final
-- Judgment recorded yet, clerk case search is CAPTCHA-gated. 1 of 45 rows, does not
-- block the 95.6% threshold.

DO $$
DECLARE
  v_or_id bigint;
  v_pud_id bigint;
  v_sa_id bigint;
  v_rs3_id bigint;
BEGIN
  SELECT id INTO v_or_id FROM zoning_districts WHERE jurisdiction_id = 1364 AND code = 'OR';
  IF v_or_id IS NULL THEN
    INSERT INTO zoning_districts (jurisdiction_id, code, name, category, density_regulated, far_regulated, pk1000_regulated, ordinance_section)
    VALUES (1364, 'OR', 'Open Rural', 'Residential', true, false, false,
            'LDC Article VI Sec 6.01.03 Table 6.01 (OR Single Family Dwelling/Mobile Home: 1 acre min lot)')
    RETURNING id INTO v_or_id;
  END IF;

  INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, max_height_ft, front_setback_ft, side_setback_ft, rear_setback_ft, max_density_du_acre, source_url, ordinance_section, scraped_at)
  SELECT v_or_id, 43560, 35, 25.00, 10.00, 10.00, 1.00,
         'https://www.sjcfl.us/wp-content/uploads/2024/01/article-vi.pdf',
         'LDC Article VI Sec 6.01.03 Table 6.01, OR - Single Family Dwelling or Mobile Home row (1 acre min lot => 1.00 DU/acre)',
         now()
   WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = v_or_id);

  SELECT id INTO v_pud_id FROM zoning_districts WHERE jurisdiction_id = 1364 AND code = 'PUD';
  IF v_pud_id IS NULL THEN
    INSERT INTO zoning_districts (jurisdiction_id, code, name, category, density_regulated, far_regulated, pk1000_regulated, ordinance_section)
    VALUES (1364, 'PUD', 'Planned Unit Development', 'PUD', false, false, false,
            'LDC Article V Sec 5.03.00.D (PUD max density deferred to Future Land Use Map / Comprehensive Plan, no fixed zoning-native density)')
    RETURNING id INTO v_pud_id;
  END IF;

  SELECT id INTO v_sa_id FROM zoning_districts WHERE jurisdiction_id = 1364 AND code = 'SA';
  IF v_sa_id IS NULL THEN
    INSERT INTO zoning_districts (jurisdiction_id, code, name, category, density_regulated, far_regulated, pk1000_regulated, ordinance_section)
    VALUES (1364, 'SA', 'SA (GIS zoning code, no LDC Article II/VI table entry located)', 'Unclassified', false, false, false,
            'GIS Zoning layer DrillDown/MapServer/39 ZONING=SA; not found in Article II Sec 2.01.02 official district list nor Article VI Table 6.01 dimensional table; density_regulated=false pending confirmed LDC citation')
    RETURNING id INTO v_sa_id;
  END IF;

  SELECT id INTO v_rs3_id FROM zoning_districts WHERE jurisdiction_id = 1364 AND code = 'RS-3';

  INSERT INTO parcel_zones (jurisdiction_id, parcel_id, zone_code, source)
  SELECT 1364, p.parcel_id, p.zone_code, 'shard12_run4870_stjohns_arcgis:https://www.gis.sjcfl.us/sjcgis/rest/services/DrillDown/MapServer/39'
    FROM (VALUES
      ('0179700061','OR'),
      ('1012500150','OR'),
      ('0290500080','OR'),
      ('0653200000','OR'),
      ('1011811030','PUD'),
      ('1027641050','PUD'),
      ('0265522570','PUD'),
      ('0232412200','PUD'),
      ('0760900410','RS-3'),
      ('0428800000','RS-3'),
      ('1028241020','SA')
    ) AS p(parcel_id, zone_code)
   WHERE NOT EXISTS (
     SELECT 1 FROM parcel_zones pz WHERE pz.jurisdiction_id = 1364 AND pz.parcel_id = p.parcel_id
   );
END $$;
