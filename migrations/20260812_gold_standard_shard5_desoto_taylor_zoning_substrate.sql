-- Gold Standard SHARD-5 (run 10790, dispatch 5d78eb23): desoto zoning substrate
-- Taylor: no zoning work needed (G already PASS 100%)
-- DeSoto: I criterion requires zone_code in v_zoning_gold_standard_card via parcel_zones
--
-- STRATEGY (INFERRED from DeSoto County LDR — no public ArcGIS REST service found):
--   DeSoto County has one incorporated municipality: City of Arcadia (zip 34266)
--   All other areas are unincorporated DeSoto County.
--   Base zone: A-1 (Agricultural) for unincorporated; R-1 (Residential) for Arcadia.
--   Source: DeSoto County Land Development Regulations Art. 3, 4
--           City of Arcadia LDC (library.municode.com/fl/arcadia)
--
-- HONESTY: All zone assignments are INFERRED defaults, not GIS-verified.
--          honesty_marker = 'INFERRED' — count toward I only if v_zoning_gold_standard_card
--          also requires geo+value (separately backfilled by the Python script).
--
-- CORRECTION (2026-08-12, concurrent session on this same dispatch): the two
-- jurisdiction names below did NOT match the jurisdictions rows that actually
-- already exist for DeSoto ('Unincorporated DeSoto County' id=1406, 'Arcadia'
-- id=829 -- confirmed live this session). As originally written, the INSERT's
-- ON CONFLICT (name, county, state) would NOT have matched those existing
-- rows (different name string) and would have silently created two DUPLICATE
-- jurisdictions, each with their own divergent zoning_districts/zone_standards
-- -- fragmenting the substrate and risking exactly the kind of G-criterion
-- regression documented in GOLD_STANDARD_SHARD3_WALTON_LEON_TAYLOR_DISPATCH_
-- C5A8B2C7_SESSION_REPORT.md (orphaned/duplicate zoning rows dragging density/
-- FAR/parking applicable-but-unmeasured denominators down). Fixed the name to
-- match the existing row exactly. The 'City of Arcadia' section (5/6 below) is
-- REMOVED entirely: the existing 'Arcadia' jurisdiction already has 24 real,
-- municode-sourced zone codes (R-1A/B/C, R-2A/B, R-3, R-4, MHP, P-1, RPB, B-1,
-- B-1A, B-2, B-3, C-1, M-1, M-2, PUD, PBG, ROS, CON) -- this migration's crude
-- 7-code generic fallback (R-1/R-2/MH/B-1/B-2/I-1/PUD) would have been
-- strictly inferior, redundant, and risked the same jurisdiction-fragmentation
-- problem. Only the Unincorporated DeSoto additions are kept (as genuinely
-- additive codes not already present: A-1, RE, RM-1, RM-2, MH, COM, IND, PUD
-- -- existing unincorporated codes are RSF-1/2/4/5, per live check).

-- 1. Ensure desoto jurisdiction exists (matches existing row exactly, not a duplicate)
INSERT INTO jurisdictions (name, county, state, source, created_at)
VALUES
  ('Unincorporated DeSoto County', 'DeSoto', 'FL', 'desoto_ldr_art3_shard5_10790', now())
ON CONFLICT (name, county, state) DO NOTHING;

-- 2. Get jurisdiction IDs for reference (these will be used by Python script)
-- Verify with: SELECT id, name FROM jurisdictions WHERE county ILIKE '%desoto%' AND state='FL';

-- 3. Insert zoning districts for DeSoto Unincorporated
WITH uninc AS (
  SELECT id FROM jurisdictions WHERE name = 'Unincorporated DeSoto County' AND state = 'FL' LIMIT 1
)
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, created_at)
SELECT
  uninc.id,
  d.code, d.name, d.category,
  d.far_regulated::boolean, d.density_regulated::boolean,
  now()
FROM uninc,
(VALUES
  ('A-1',   'Agricultural',                        'agricultural', false, false),
  ('RE',    'Rural Estates',                       'residential',  false, true),
  ('RSF-1', 'Residential Single Family 1 du/ac',   'residential',  false, true),
  ('RSF-2', 'Residential Single Family 2 du/ac',   'residential',  false, true),
  ('RM-1',  'Residential Multi-Family Low',        'residential',  false, true),
  ('RM-2',  'Residential Multi-Family Medium',     'residential',  false, true),
  ('MH',    'Mobile Home Park',                    'residential',  false, true),
  ('COM',   'Commercial General',                  'commercial',   false, false),
  ('IND',   'Industrial',                          'industrial',   false, false),
  ('PUD',   'Planned Unit Development',            'mixed',        false, false)
) AS d(code, name, category, far_regulated, density_regulated)
ON CONFLICT DO NOTHING;

-- 4. Insert zone_standards for DeSoto Unincorporated districts
WITH uninc AS (
  SELECT id FROM jurisdictions WHERE name = 'Unincorporated DeSoto County' AND state = 'FL' LIMIT 1
),
districts AS (
  SELECT zd.id, zd.code
  FROM zoning_districts zd
  JOIN uninc ON zd.jurisdiction_id = uninc.id
)
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf,
  source_url, confidence_score, scraped_at, honesty_marker)
SELECT
  d.id,
  s.max_density,
  s.max_far,
  s.parking,
  'https://library.municode.com/fl/desoto_county',
  0.55,  -- INFERRED confidence (default from ordinance, not GIS-verified)
  now(),
  'INFERRED'
FROM districts d
JOIN (VALUES
  ('A-1',   1.0,  NULL,  NULL),
  ('RE',    1.0,  NULL,  NULL),
  ('RSF-1', 1.0,  NULL,  2.0),
  ('RSF-2', 2.0,  NULL,  2.0),
  ('RM-1',  4.0,  NULL,  2.0),
  ('RM-2',  8.0,  NULL,  2.0),
  ('MH',    6.0,  NULL,  2.0),
  ('COM',   NULL, 0.30,  4.0),
  ('IND',   NULL, 0.50,  2.0),
  ('PUD',   NULL, NULL,  NULL)
) AS s(code, max_density, max_far, parking)
ON (d.code = s.code)
ON CONFLICT DO NOTHING;

-- 5/6. City of Arcadia sections REMOVED (see correction note above) -- the
-- existing 'Arcadia' jurisdiction (id=829) already has a real, 24-code
-- municode-sourced zoning substrate. Do not insert a second, cruder set here.

-- Verification queries (run after applying):
-- SELECT j.name, COUNT(zd.id) AS districts, COUNT(zs.id) AS standards
-- FROM jurisdictions j
-- LEFT JOIN zoning_districts zd ON zd.jurisdiction_id = j.id
-- LEFT JOIN zone_standards zs ON zs.zoning_district_id = zd.id
-- WHERE j.county ILIKE '%desoto%' AND j.state = 'FL'
-- GROUP BY j.name;
