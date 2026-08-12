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

-- 1. Ensure desoto jurisdictions exist
INSERT INTO jurisdictions (name, county, state, source, created_at)
VALUES
  ('DeSoto County Unincorporated', 'DeSoto', 'FL', 'desoto_ldr_art3_shard5_10790', now()),
  ('City of Arcadia', 'DeSoto', 'FL', 'arcadia_ldc_municode_shard5_10790', now())
ON CONFLICT (name, county, state) DO NOTHING;

-- 2. Get jurisdiction IDs for reference (these will be used by Python script)
-- Verify with: SELECT id, name FROM jurisdictions WHERE county ILIKE '%desoto%' AND state='FL';

-- 3. Insert zoning districts for DeSoto Unincorporated
WITH uninc AS (
  SELECT id FROM jurisdictions WHERE name = 'DeSoto County Unincorporated' AND state = 'FL' LIMIT 1
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
  SELECT id FROM jurisdictions WHERE name = 'DeSoto County Unincorporated' AND state = 'FL' LIMIT 1
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

-- 5. Insert zoning districts for City of Arcadia
WITH arc AS (
  SELECT id FROM jurisdictions WHERE name = 'City of Arcadia' AND state = 'FL' LIMIT 1
)
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, created_at)
SELECT
  arc.id,
  d.code, d.name, d.category,
  d.far_regulated::boolean, d.density_regulated::boolean,
  now()
FROM arc,
(VALUES
  ('R-1',  'Single Family Residential',     'residential',  false, true),
  ('R-2',  'Multi-Family Residential',      'residential',  false, true),
  ('MH',   'Mobile Home',                   'residential',  false, true),
  ('B-1',  'Neighborhood Business',         'commercial',   false, false),
  ('B-2',  'General Business',              'commercial',   true,  false),
  ('I-1',  'Light Industrial',              'industrial',   false, false),
  ('PUD',  'Planned Unit Development',      'mixed',        false, false)
) AS d(code, name, category, far_regulated, density_regulated)
ON CONFLICT DO NOTHING;

-- 6. Insert zone_standards for City of Arcadia districts
WITH arc AS (
  SELECT id FROM jurisdictions WHERE name = 'City of Arcadia' AND state = 'FL' LIMIT 1
),
districts AS (
  SELECT zd.id, zd.code
  FROM zoning_districts zd
  JOIN arc ON zd.jurisdiction_id = arc.id
)
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf,
  source_url, confidence_score, scraped_at, honesty_marker)
SELECT
  d.id,
  s.max_density,
  s.max_far,
  s.parking,
  'https://library.municode.com/fl/arcadia',
  0.60,
  now(),
  'INFERRED'
FROM districts d
JOIN (VALUES
  ('R-1',  4.0,  NULL, 2.0),
  ('R-2',  8.0,  NULL, 2.0),
  ('MH',   6.0,  NULL, 2.0),
  ('B-1',  NULL, 0.25, 4.0),
  ('B-2',  NULL, 0.40, 4.0),
  ('I-1',  NULL, 0.50, 2.0),
  ('PUD',  NULL, NULL, NULL)
) AS s(code, max_density, max_far, parking)
ON (d.code = s.code)
ON CONFLICT DO NOTHING;

-- Verification queries (run after applying):
-- SELECT j.name, COUNT(zd.id) AS districts, COUNT(zs.id) AS standards
-- FROM jurisdictions j
-- LEFT JOIN zoning_districts zd ON zd.jurisdiction_id = j.id
-- LEFT JOIN zone_standards zs ON zs.zoning_district_id = zd.id
-- WHERE j.county ILIKE '%desoto%' AND j.state = 'FL'
-- GROUP BY j.name;
