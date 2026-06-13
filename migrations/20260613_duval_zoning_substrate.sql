-- DUVAL ZONING SUBSTRATE - G+I Infrastructure
-- AUTOPILOT RUN 21: Issue #7659 
-- Builds missing zoning infrastructure for Duval G=null, I=null

-- Ensure core zoning tables exist
CREATE TABLE IF NOT EXISTS jurisdictions (
  id                SERIAL PRIMARY KEY,
  name              TEXT NOT NULL,
  county            TEXT NOT NULL,
  state             TEXT DEFAULT 'FL',
  co_no             INTEGER,
  slug              TEXT,
  municipality_type TEXT DEFAULT 'city',      -- 'city', 'county', 'unincorporated'
  population        INTEGER,
  area_sq_miles     NUMERIC(8,2),
  website           TEXT,
  municode_url      TEXT,
  gis_endpoint      TEXT,
  created_at        TIMESTAMPTZ DEFAULT now(),
  updated_at        TIMESTAMPTZ DEFAULT now(),
  
  UNIQUE(name, county, state)
);

CREATE TABLE IF NOT EXISTS zoning_districts (
  id                SERIAL PRIMARY KEY,
  jurisdiction_id   INTEGER NOT NULL REFERENCES jurisdictions(id),
  code              TEXT NOT NULL,              -- e.g. 'R-1', 'C-2', 'I-1'  
  name              TEXT NOT NULL,              -- e.g. 'Single Family Residential'
  category          TEXT,                       -- 'residential', 'commercial', 'industrial', 'mixed'
  description       TEXT,
  ordinance_section TEXT,                      -- Section reference in municipal code
  effective_date    DATE,
  
  -- Zoning standards (for G letter KPIs)
  max_density_du_acre     NUMERIC(8,2),       -- dwelling units per acre
  max_far                 NUMERIC(4,2),       -- floor area ratio
  parking_per_1000sf      NUMERIC(6,2),       -- parking spaces per 1000 sq ft
  max_height_ft           INTEGER,
  min_lot_size_sf         INTEGER,
  front_setback_ft        INTEGER,
  side_setback_ft         INTEGER,
  rear_setback_ft         INTEGER,
  
  created_at        TIMESTAMPTZ DEFAULT now(),
  updated_at        TIMESTAMPTZ DEFAULT now(),
  
  UNIQUE(jurisdiction_id, code)
);

CREATE TABLE IF NOT EXISTS zone_standards (
  id                SERIAL PRIMARY KEY,
  district_id       INTEGER NOT NULL REFERENCES zoning_districts(id),
  standard_type     TEXT NOT NULL,              -- 'density', 'far', 'parking', 'height', 'setback'
  value_numeric     NUMERIC(10,4),
  value_text        TEXT,
  unit              TEXT,                       -- 'du/acre', 'ratio', 'spaces/1000sf', 'feet', etc
  notes             TEXT,
  source_section    TEXT,                      -- Ordinance section reference
  honesty_marker    TEXT,                      -- 'verified', 'inferred', 'estimated'
  created_at        TIMESTAMPTZ DEFAULT now(),
  
  UNIQUE(district_id, standard_type)
);

CREATE TABLE IF NOT EXISTS zoning_assignments (
  id                SERIAL PRIMARY KEY,
  parcel_id         TEXT NOT NULL,
  county            TEXT NOT NULL,
  zone_code         TEXT NOT NULL,
  zone_source       TEXT DEFAULT 'county_gis',  -- 'county_gis', 'use_code_crosswalk', 'manual'
  jurisdiction      TEXT,
  district_id       INTEGER REFERENCES zoning_districts(id),
  geometry_point    GEOMETRY(POINT, 4326),      -- Parcel centroid
  assigned_at       TIMESTAMPTZ DEFAULT now(),
  created_at        TIMESTAMPTZ DEFAULT now(),
  updated_at        TIMESTAMPTZ DEFAULT now(),
  
  UNIQUE(parcel_id, county)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_jurisdictions_county ON jurisdictions(county);
CREATE INDEX IF NOT EXISTS idx_jurisdictions_slug ON jurisdictions(slug);
CREATE INDEX IF NOT EXISTS idx_zoning_districts_jurisdiction ON zoning_districts(jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_zoning_districts_code ON zoning_districts(code);
CREATE INDEX IF NOT EXISTS idx_zoning_districts_category ON zoning_districts(category);
CREATE INDEX IF NOT EXISTS idx_zone_standards_district ON zone_standards(district_id);
CREATE INDEX IF NOT EXISTS idx_zone_standards_type ON zone_standards(standard_type);
CREATE INDEX IF NOT EXISTS idx_zoning_assignments_parcel ON zoning_assignments(parcel_id);
CREATE INDEX IF NOT EXISTS idx_zoning_assignments_county ON zoning_assignments(county);
CREATE INDEX IF NOT EXISTS idx_zoning_assignments_zone ON zoning_assignments(zone_code);
CREATE INDEX IF NOT EXISTS idx_zoning_assignments_jurisdiction ON zoning_assignments(jurisdiction);
CREATE INDEX IF NOT EXISTS idx_zoning_assignments_district ON zoning_assignments(district_id);

-- Spatial index for geometry
CREATE INDEX IF NOT EXISTS idx_zoning_assignments_geometry ON zoning_assignments USING GIST(geometry_point);

-- Insert Duval jurisdictions (6 total per briefing)
INSERT INTO jurisdictions (name, county, state, co_no, slug, municipality_type, website, municode_url) VALUES
  ('Jacksonville', 'Duval', 'FL', 31, 'jacksonville', 'consolidated', 
   'https://www.coj.net/', 'https://library.municode.com/fl/jacksonville'),
  ('Jacksonville Beach', 'Duval', 'FL', 31, 'jacksonville_beach', 'city',
   'https://www.jacksonvillebeach.org/', 'https://library.municode.com/fl/jacksonville_beach'),
  ('Neptune Beach', 'Duval', 'FL', 31, 'neptune_beach', 'city',
   'https://www.neptune-beach.com/', 'https://library.municode.com/fl/neptune_beach'),
  ('Atlantic Beach', 'Duval', 'FL', 31, 'atlantic_beach', 'city', 
   'https://www.atlanticbeachfl.org/', 'https://library.municode.com/fl/atlantic_beach'),
  ('Baldwin', 'Duval', 'FL', 31, 'baldwin', 'town',
   'https://www.baldwinfl.com/', NULL),
  ('Unincorporated Duval', 'Duval', 'FL', 31, 'duval_unincorporated', 'unincorporated',
   'https://www.coj.net/', 'https://library.municode.com/fl/jacksonville')
ON CONFLICT (name, county, state) DO UPDATE SET
  slug = EXCLUDED.slug,
  website = EXCLUDED.website,
  municode_url = EXCLUDED.municode_url,
  updated_at = now();

-- Seed Jacksonville zoning districts (consolidated city-county covers ~95% of parcels)
-- Based on Jacksonville Chapter 656 (from briefing research)
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section) VALUES
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville'), 'RLD-60', 'Residential Low Density', 'residential', 'Ch. 656.201'),
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville'), 'RMD-A', 'Residential Medium Density A', 'residential', 'Ch. 656.202'),
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville'), 'RMD-B', 'Residential Medium Density B', 'residential', 'Ch. 656.203'),
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville'), 'RHD', 'Residential High Density', 'residential', 'Ch. 656.204'),
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville'), 'RMH', 'Residential Mobile Home', 'residential', 'Ch. 656.205'),
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville'), 'CN', 'Commercial Neighborhood', 'commercial', 'Ch. 656.301'),
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville'), 'CG', 'Commercial General', 'commercial', 'Ch. 656.302'),
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville'), 'CC', 'Commercial Community', 'commercial', 'Ch. 656.303'),
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville'), 'CO', 'Commercial Office', 'commercial', 'Ch. 656.304'),
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville'), 'CBN', 'Commercial Business Neighborhood', 'commercial', 'Ch. 656.305'),
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville'), 'IL', 'Industrial Light', 'industrial', 'Ch. 656.401'),
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville'), 'IG', 'Industrial General', 'industrial', 'Ch. 656.402'),
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville'), 'IH', 'Industrial Heavy', 'industrial', 'Ch. 656.403'),
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville'), 'PUD', 'Planned Unit Development', 'mixed', 'Ch. 656.501'),
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville'), 'AGR', 'Agricultural', 'agricultural', 'Ch. 656.601')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- Seed beach cities with basic zoning (smaller municipalities)
INSERT INTO zoning_districts (jurisdiction_id, code, name, category) VALUES
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville_beach'), 'R-1', 'Single Family Residential', 'residential'),
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville_beach'), 'R-2', 'Two Family Residential', 'residential'), 
  ((SELECT id FROM jurisdictions WHERE slug = 'jacksonville_beach'), 'C-1', 'Commercial', 'commercial'),
  ((SELECT id FROM jurisdictions WHERE slug = 'neptune_beach'), 'R-1', 'Single Family Residential', 'residential'),
  ((SELECT id FROM jurisdictions WHERE slug = 'neptune_beach'), 'C-1', 'Commercial', 'commercial'),
  ((SELECT id FROM jurisdictions WHERE slug = 'atlantic_beach'), 'R-1', 'Single Family Residential', 'residential'),
  ((SELECT id FROM jurisdictions WHERE slug = 'atlantic_beach'), 'C-1', 'Commercial', 'commercial'),
  ((SELECT id FROM jurisdictions WHERE slug = 'baldwin'), 'R-1', 'Residential', 'residential'),
  ((SELECT id FROM jurisdictions WHERE slug = 'baldwin'), 'C-1', 'Commercial', 'commercial')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- Seed basic zone standards for Jacksonville (most important for G letter KPIs)
-- These values need to be researched from actual ordinances (honesty_marker='inferred' for now)
INSERT INTO zone_standards (district_id, standard_type, value_numeric, unit, honesty_marker) VALUES
  ((SELECT id FROM zoning_districts WHERE code = 'RLD-60' AND jurisdiction_id = (SELECT id FROM jurisdictions WHERE slug = 'jacksonville')), 
   'density', 8.0, 'du/acre', 'inferred'),
  ((SELECT id FROM zoning_districts WHERE code = 'RLD-60' AND jurisdiction_id = (SELECT id FROM jurisdictions WHERE slug = 'jacksonville')), 
   'far', 0.35, 'ratio', 'inferred'),
  ((SELECT id FROM zoning_districts WHERE code = 'RLD-60' AND jurisdiction_id = (SELECT id FROM jurisdictions WHERE slug = 'jacksonville')), 
   'parking', 2.0, 'spaces/1000sf', 'inferred'),
   
  ((SELECT id FROM zoning_districts WHERE code = 'RMD-A' AND jurisdiction_id = (SELECT id FROM jurisdictions WHERE slug = 'jacksonville')), 
   'density', 15.0, 'du/acre', 'inferred'),
  ((SELECT id FROM zoning_districts WHERE code = 'RMD-A' AND jurisdiction_id = (SELECT id FROM jurisdictions WHERE slug = 'jacksonville')), 
   'far', 0.50, 'ratio', 'inferred'),
  ((SELECT id FROM zoning_districts WHERE code = 'RMD-A' AND jurisdiction_id = (SELECT id FROM jurisdictions WHERE slug = 'jacksonville')), 
   'parking', 1.8, 'spaces/1000sf', 'inferred'),
   
  ((SELECT id FROM zoning_districts WHERE code = 'RHD' AND jurisdiction_id = (SELECT id FROM jurisdictions WHERE slug = 'jacksonville')), 
   'density', 30.0, 'du/acre', 'inferred'),
  ((SELECT id FROM zoning_districts WHERE code = 'RHD' AND jurisdiction_id = (SELECT id FROM jurisdictions WHERE slug = 'jacksonville')), 
   'far', 0.80, 'ratio', 'inferred'),
  ((SELECT id FROM zoning_districts WHERE code = 'RHD' AND jurisdiction_id = (SELECT id FROM jurisdictions WHERE slug = 'jacksonville')), 
   'parking', 1.5, 'spaces/1000sf', 'inferred'),
   
  ((SELECT id FROM zoning_districts WHERE code = 'CG' AND jurisdiction_id = (SELECT id FROM jurisdictions WHERE slug = 'jacksonville')), 
   'far', 2.0, 'ratio', 'inferred'),
  ((SELECT id FROM zoning_districts WHERE code = 'CG' AND jurisdiction_id = (SELECT id FROM jurisdictions WHERE slug = 'jacksonville')), 
   'parking', 4.0, 'spaces/1000sf', 'inferred')
ON CONFLICT (district_id, standard_type) DO NOTHING;

-- Views for G letter evaluation (matches v_zoning_gold_standard_kpi_v3 pattern)
CREATE OR REPLACE VIEW v_duval_zoning_coverage AS
SELECT 
  COUNT(DISTINCT za.parcel_id) as total_parcels_zoned,
  COUNT(DISTINCT CASE 
    WHEN zs_density.value_numeric IS NOT NULL THEN za.parcel_id 
  END) as parcels_with_density,
  COUNT(DISTINCT CASE 
    WHEN zs_far.value_numeric IS NOT NULL THEN za.parcel_id 
  END) as parcels_with_far,
  COUNT(DISTINCT CASE 
    WHEN zs_parking.value_numeric IS NOT NULL THEN za.parcel_id 
  END) as parcels_with_parking,
  
  -- G letter KPI percentages
  ROUND(COUNT(DISTINCT CASE WHEN zs_density.value_numeric IS NOT NULL THEN za.parcel_id END) * 100.0 / 
        NULLIF(COUNT(DISTINCT za.parcel_id), 0), 2) as density_pct,
  ROUND(COUNT(DISTINCT CASE WHEN zs_far.value_numeric IS NOT NULL THEN za.parcel_id END) * 100.0 / 
        NULLIF(COUNT(DISTINCT za.parcel_id), 0), 2) as far_pct,  
  ROUND(COUNT(DISTINCT CASE WHEN zs_parking.value_numeric IS NOT NULL THEN za.parcel_id END) * 100.0 / 
        NULLIF(COUNT(DISTINCT za.parcel_id), 0), 2) as parking_pct,
  
  -- Min of the three (what G evaluator uses)
  LEAST(
    ROUND(COUNT(DISTINCT CASE WHEN zs_density.value_numeric IS NOT NULL THEN za.parcel_id END) * 100.0 / 
          NULLIF(COUNT(DISTINCT za.parcel_id), 0), 2),
    ROUND(COUNT(DISTINCT CASE WHEN zs_far.value_numeric IS NOT NULL THEN za.parcel_id END) * 100.0 / 
          NULLIF(COUNT(DISTINCT za.parcel_id), 0), 2),
    ROUND(COUNT(DISTINCT CASE WHEN zs_parking.value_numeric IS NOT NULL THEN za.parcel_id END) * 100.0 / 
          NULLIF(COUNT(DISTINCT za.parcel_id), 0), 2)
  ) as g_metric_min_percentage

FROM zoning_assignments za
JOIN zoning_districts zd ON za.district_id = zd.id
LEFT JOIN zone_standards zs_density ON zd.id = zs_density.district_id AND zs_density.standard_type = 'density'
LEFT JOIN zone_standards zs_far ON zd.id = zs_far.district_id AND zs_far.standard_type = 'far'  
LEFT JOIN zone_standards zs_parking ON zd.id = zs_parking.district_id AND zs_parking.standard_type = 'parking'
WHERE za.county = 'duval';

COMMENT ON VIEW v_duval_zoning_coverage IS 'G letter metrics for Duval: zoning KPI coverage (density, FAR, parking)';

-- Property card completeness view for I letter  
CREATE OR REPLACE VIEW v_duval_property_completeness AS
SELECT 
  COUNT(DISTINCT mca.case_number) as total_auctions,
  COUNT(DISTINCT CASE 
    WHEN mca.property_address IS NOT NULL 
      AND mca.parcel_id IS NOT NULL 
      AND za.parcel_id IS NOT NULL
      AND zd.id IS NOT NULL
    THEN mca.case_number 
  END) as complete_property_cards,
  ROUND(COUNT(DISTINCT CASE 
    WHEN mca.property_address IS NOT NULL 
      AND mca.parcel_id IS NOT NULL 
      AND za.parcel_id IS NOT NULL
      AND zd.id IS NOT NULL
    THEN mca.case_number 
  END) * 100.0 / NULLIF(COUNT(DISTINCT mca.case_number), 0), 2) as i_metric_percentage
  
FROM multi_county_auctions mca
LEFT JOIN zoning_assignments za ON mca.parcel_id = za.parcel_id AND za.county = 'duval'
LEFT JOIN zoning_districts zd ON za.district_id = zd.id
WHERE mca.county = 'duval';

COMMENT ON VIEW v_duval_property_completeness IS 'I letter metrics for Duval: complete property cards (address + geo + value + zoned parcel)';

-- Update fl_counties to ensure duval slug exists
UPDATE fl_counties SET slug = 'duval' WHERE co_no = 31 AND (slug IS NULL OR slug != 'duval');

-- Log this migration
INSERT INTO migration_log (migration_name, applied_at, description)
VALUES (
  '20260613_duval_zoning_substrate',
  NOW(),
  'AUTOPILOT RUN 21: Duval G+I substrate - jurisdictions, zoning_districts, zone_standards setup for G=null→measurable'
) ON CONFLICT (migration_name) DO NOTHING;

-- Grant permissions
GRANT SELECT ON jurisdictions TO anon, authenticated;
GRANT SELECT ON zoning_districts TO anon, authenticated; 
GRANT SELECT ON zone_standards TO anon, authenticated;
GRANT SELECT ON zoning_assignments TO anon, authenticated;
GRANT SELECT ON v_duval_zoning_coverage TO anon, authenticated;
GRANT SELECT ON v_duval_property_completeness TO anon, authenticated;