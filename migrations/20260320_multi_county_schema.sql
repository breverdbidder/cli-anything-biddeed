-- ============================================================
-- ZONEWISE MULTI-COUNTY SCHEMA
-- Migration: 20260320_multi_county_schema.sql
-- Supports all 67 Florida counties with jurisdiction tracking
-- ============================================================

-- Florida counties reference table (immutable)
CREATE TABLE IF NOT EXISTS fl_counties (
  co_no         INTEGER PRIMARY KEY,          -- FL DOR county number (1-67)
  name          TEXT NOT NULL UNIQUE,          -- e.g. "Brevard"
  fips_code     TEXT NOT NULL UNIQUE,          -- e.g. "12009"
  slug          TEXT NOT NULL UNIQUE,          -- e.g. "brevard"
  region        TEXT NOT NULL DEFAULT 'other', -- central, south, north, panhandle, other
  total_parcels INTEGER DEFAULT 0,            -- from FL GIO statewide API
  appraiser_url TEXT,                          -- county property appraiser website
  gis_endpoint  TEXT,                          -- ArcGIS/GIS REST endpoint if known
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- County conquest status tracking
CREATE TABLE IF NOT EXISTS county_conquest_status (
  co_no               INTEGER PRIMARY KEY REFERENCES fl_counties(co_no),
  parcels_ingested     INTEGER DEFAULT 0,    -- rows in zoning_assignments for this county
  parcels_with_zone    INTEGER DEFAULT 0,    -- rows with non-null zone_code
  parcels_from_gis     INTEGER DEFAULT 0,    -- zone_source = municipal GIS
  parcels_from_usecode INTEGER DEFAULT 0,    -- zone_source = use_code_crosswalk
  parcels_from_spatial INTEGER DEFAULT 0,    -- zone_source = spatial_join
  jurisdictions_total  INTEGER DEFAULT 0,    -- how many municipalities
  jurisdictions_done   INTEGER DEFAULT 0,    -- municipalities at >95%
  coverage_pct         NUMERIC(5,1) DEFAULT 0.0,
  status               TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'ingesting', 'in_progress', 'complete', 'error')),
  last_updated         TIMESTAMPTZ DEFAULT now(),
  notes                TEXT
);

-- County jurisdictions (municipalities within each county)
CREATE TABLE IF NOT EXISTS county_jurisdictions (
  id              SERIAL PRIMARY KEY,
  co_no           INTEGER NOT NULL REFERENCES fl_counties(co_no),
  jurisdiction    TEXT NOT NULL,               -- canonical slug e.g. "palm_bay"
  display_name    TEXT NOT NULL,               -- e.g. "Palm Bay"
  is_incorporated BOOLEAN DEFAULT true,
  total_parcels   INTEGER DEFAULT 0,           -- from county appraiser
  zoned_parcels   INTEGER DEFAULT 0,           -- in zoning_assignments
  coverage_pct    NUMERIC(5,1) DEFAULT 0.0,
  gis_endpoint    TEXT,                        -- municipality-specific GIS if available
  zone_source     TEXT,                        -- primary source: gis, usecode, spatial, firecrawl
  last_updated    TIMESTAMPTZ DEFAULT now(),
  UNIQUE(co_no, jurisdiction)
);

-- Add county column to zoning_assignments if not exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'zoning_assignments' AND column_name = 'co_no'
  ) THEN
    ALTER TABLE zoning_assignments ADD COLUMN co_no INTEGER DEFAULT 5;  -- Default to Brevard for existing data
    CREATE INDEX IF NOT EXISTS idx_za_co_no ON zoning_assignments(co_no);
  END IF;
  
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'zoning_assignments' AND column_name = 'zone_source'
  ) THEN
    ALTER TABLE zoning_assignments ADD COLUMN zone_source TEXT;
  END IF;
  
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'zoning_assignments' AND column_name = 'zone_confidence'
  ) THEN
    ALTER TABLE zoning_assignments ADD COLUMN zone_confidence TEXT;
  END IF;
  
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'zoning_assignments' AND column_name = 'dor_uc'
  ) THEN
    ALTER TABLE zoning_assignments ADD COLUMN dor_uc TEXT;  -- FL DOR use code for cross-reference
  END IF;
END $$;

-- Add co_no to sample_properties if not exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'sample_properties' AND column_name = 'co_no'
  ) THEN
    ALTER TABLE sample_properties ADD COLUMN co_no INTEGER DEFAULT 5;
    CREATE INDEX IF NOT EXISTS idx_sp_co_no ON sample_properties(co_no);
  END IF;
END $$;

-- ============================================================
-- INSERT ALL 67 FLORIDA COUNTIES
-- ============================================================
INSERT INTO fl_counties (co_no, name, fips_code, slug, region) VALUES
(1,  'Alachua',       '12001', 'alachua',       'north'),
(2,  'Baker',         '12003', 'baker',         'north'),
(3,  'Bay',           '12005', 'bay',           'panhandle'),
(4,  'Bradford',      '12007', 'bradford',      'north'),
(5,  'Brevard',       '12009', 'brevard',       'central'),
(6,  'Broward',       '12011', 'broward',       'south'),
(7,  'Calhoun',       '12013', 'calhoun',       'panhandle'),
(8,  'Charlotte',     '12015', 'charlotte',     'south'),
(9,  'Citrus',        '12017', 'citrus',        'central'),
(10, 'Clay',          '12019', 'clay',          'north'),
(11, 'Collier',       '12021', 'collier',       'south'),
(12, 'Columbia',      '12023', 'columbia',      'north'),
(13, 'Miami-Dade',    '12086', 'miami_dade',    'south'),
(14, 'DeSoto',        '12027', 'desoto',        'central'),
(15, 'Dixie',         '12029', 'dixie',         'north'),
(16, 'Duval',         '12031', 'duval',         'north'),
(17, 'Escambia',      '12033', 'escambia',      'panhandle'),
(18, 'Flagler',       '12035', 'flagler',       'north'),
(19, 'Franklin',      '12037', 'franklin',      'panhandle'),
(20, 'Gadsden',       '12039', 'gadsden',       'panhandle'),
(21, 'Gilchrist',     '12041', 'gilchrist',     'north'),
(22, 'Glades',        '12043', 'glades',        'south'),
(23, 'Gulf',          '12045', 'gulf',          'panhandle'),
(24, 'Hamilton',      '12047', 'hamilton',      'north'),
(25, 'Hardee',        '12049', 'hardee',        'central'),
(26, 'Hendry',        '12051', 'hendry',        'south'),
(27, 'Hernando',      '12053', 'hernando',      'central'),
(28, 'Highlands',     '12055', 'highlands',     'central'),
(29, 'Hillsborough',  '12057', 'hillsborough',  'central'),
(30, 'Holmes',        '12059', 'holmes',        'panhandle'),
(31, 'Indian River',  '12061', 'indian_river',  'central'),
(32, 'Jackson',       '12063', 'jackson',       'panhandle'),
(33, 'Jefferson',     '12065', 'jefferson',     'panhandle'),
(34, 'Lafayette',     '12067', 'lafayette',     'north'),
(35, 'Lake',          '12069', 'lake',          'central'),
(36, 'Lee',           '12071', 'lee',           'south'),
(37, 'Leon',          '12073', 'leon',          'panhandle'),
(38, 'Levy',          '12075', 'levy',          'north'),
(39, 'Liberty',       '12077', 'liberty',       'panhandle'),
(40, 'Madison',       '12079', 'madison',       'north'),
(41, 'Manatee',       '12081', 'manatee',       'central'),
(42, 'Marion',        '12083', 'marion',        'central'),
(43, 'Martin',        '12085', 'martin',        'south'),
(44, 'Monroe',        '12087', 'monroe',        'south'),
(45, 'Nassau',        '12089', 'nassau',        'north'),
(46, 'Okaloosa',      '12091', 'okaloosa',      'panhandle'),
(47, 'Okeechobee',    '12093', 'okeechobee',    'south'),
(48, 'Orange',        '12095', 'orange',        'central'),
(49, 'Osceola',       '12097', 'osceola',       'central'),
(50, 'Palm Beach',    '12099', 'palm_beach',    'south'),
(51, 'Pasco',         '12101', 'pasco',         'central'),
(52, 'Pinellas',      '12103', 'pinellas',      'central'),
(53, 'Polk',          '12105', 'polk',          'central'),
(54, 'Putnam',        '12107', 'putnam',        'north'),
(55, 'St. Johns',     '12109', 'st_johns',      'north'),
(56, 'St. Lucie',     '12111', 'st_lucie',      'central'),
(57, 'Santa Rosa',    '12113', 'santa_rosa',    'panhandle'),
(58, 'Sarasota',      '12115', 'sarasota',      'central'),
(59, 'Seminole',      '12117', 'seminole',      'central'),
(60, 'Sumter',        '12119', 'sumter',        'central'),
(61, 'Suwannee',      '12121', 'suwannee',      'north'),
(62, 'Taylor',        '12123', 'taylor',        'north'),
(63, 'Union',         '12125', 'union',         'north'),
(64, 'Volusia',       '12127', 'volusia',       'central'),
(65, 'Wakulla',       '12129', 'wakulla',       'panhandle'),
(66, 'Walton',        '12131', 'walton',        'panhandle'),
(67, 'Washington',    '12133', 'washington',    'panhandle')
ON CONFLICT (co_no) DO NOTHING;

-- Set Brevard as complete with known data
UPDATE fl_counties SET total_parcels = 351424, 
  appraiser_url = 'https://www.bcpao.us',
  gis_endpoint = 'https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5'
WHERE co_no = 5;

-- Initialize Brevard conquest status
INSERT INTO county_conquest_status (co_no, parcels_ingested, parcels_with_zone, coverage_pct, status, jurisdictions_total, jurisdictions_done)
VALUES (5, 327882, 327882, 93.3, 'in_progress', 17, 12)
ON CONFLICT (co_no) DO UPDATE SET
  parcels_ingested = EXCLUDED.parcels_ingested,
  parcels_with_zone = EXCLUDED.parcels_with_zone,
  coverage_pct = EXCLUDED.coverage_pct,
  status = EXCLUDED.status,
  last_updated = now();

-- RPC function: get county dashboard data
CREATE OR REPLACE FUNCTION get_county_dashboard(p_co_no INTEGER DEFAULT NULL)
RETURNS JSON AS $$
DECLARE
  result JSON;
BEGIN
  IF p_co_no IS NULL THEN
    -- Return all counties summary
    SELECT json_agg(row_to_json(t)) INTO result FROM (
      SELECT c.co_no, c.name, c.slug, c.region, c.total_parcels,
             COALESCE(s.parcels_with_zone, 0) as zoned_parcels,
             COALESCE(s.coverage_pct, 0) as coverage_pct,
             COALESCE(s.status, 'pending') as status,
             COALESCE(s.jurisdictions_total, 0) as jurisdictions_total,
             COALESCE(s.jurisdictions_done, 0) as jurisdictions_done
      FROM fl_counties c
      LEFT JOIN county_conquest_status s ON c.co_no = s.co_no
      ORDER BY c.name
    ) t;
  ELSE
    -- Return specific county with jurisdictions
    SELECT json_build_object(
      'county', (SELECT row_to_json(t) FROM (
        SELECT c.co_no, c.name, c.slug, c.region, c.total_parcels, c.gis_endpoint,
               COALESCE(s.parcels_with_zone, 0) as zoned_parcels,
               COALESCE(s.coverage_pct, 0) as coverage_pct,
               COALESCE(s.status, 'pending') as status
        FROM fl_counties c
        LEFT JOIN county_conquest_status s ON c.co_no = s.co_no
        WHERE c.co_no = p_co_no
      ) t),
      'jurisdictions', (SELECT json_agg(row_to_json(j)) FROM (
        SELECT jurisdiction, display_name, is_incorporated,
               total_parcels, zoned_parcels, coverage_pct, zone_source
        FROM county_jurisdictions
        WHERE co_no = p_co_no
        ORDER BY total_parcels DESC
      ) j)
    ) INTO result;
  END IF;
  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- RPC function: refresh county stats from zoning_assignments
CREATE OR REPLACE FUNCTION refresh_county_stats(p_co_no INTEGER)
RETURNS VOID AS $$
BEGIN
  -- Update county_conquest_status
  UPDATE county_conquest_status SET
    parcels_ingested = (SELECT COUNT(*) FROM zoning_assignments WHERE co_no = p_co_no),
    parcels_with_zone = (SELECT COUNT(*) FROM zoning_assignments WHERE co_no = p_co_no AND zone_code IS NOT NULL),
    parcels_from_gis = (SELECT COUNT(*) FROM zoning_assignments WHERE co_no = p_co_no AND zone_source = 'gis'),
    parcels_from_usecode = (SELECT COUNT(*) FROM zoning_assignments WHERE co_no = p_co_no AND zone_source = 'use_code_crosswalk'),
    parcels_from_spatial = (SELECT COUNT(*) FROM zoning_assignments WHERE co_no = p_co_no AND zone_source = 'spatial_join'),
    coverage_pct = ROUND(
      (SELECT COUNT(*) FROM zoning_assignments WHERE co_no = p_co_no AND zone_code IS NOT NULL)::numeric /
      NULLIF((SELECT total_parcels FROM fl_counties WHERE co_no = p_co_no), 0) * 100, 1
    ),
    last_updated = now()
  WHERE co_no = p_co_no;
  
  -- Update jurisdiction-level stats
  UPDATE county_jurisdictions j SET
    zoned_parcels = sub.cnt,
    coverage_pct = ROUND(sub.cnt::numeric / NULLIF(j.total_parcels, 0) * 100, 1),
    last_updated = now()
  FROM (
    SELECT jurisdiction, COUNT(*) as cnt
    FROM zoning_assignments
    WHERE co_no = p_co_no AND zone_code IS NOT NULL
    GROUP BY jurisdiction
  ) sub
  WHERE j.co_no = p_co_no AND j.jurisdiction = sub.jurisdiction;
  
  -- Update jurisdictions_done count
  UPDATE county_conquest_status SET
    jurisdictions_done = (
      SELECT COUNT(*) FROM county_jurisdictions 
      WHERE co_no = p_co_no AND coverage_pct >= 95.0
    )
  WHERE co_no = p_co_no;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- RLS policies
ALTER TABLE fl_counties ENABLE ROW LEVEL SECURITY;
ALTER TABLE county_conquest_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE county_jurisdictions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "fl_counties_read" ON fl_counties FOR SELECT USING (true);
CREATE POLICY "county_conquest_read" ON county_conquest_status FOR SELECT USING (true);
CREATE POLICY "county_jurisdictions_read" ON county_jurisdictions FOR SELECT USING (true);

-- Service role can do everything
CREATE POLICY "fl_counties_admin" ON fl_counties FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "county_conquest_admin" ON county_conquest_status FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "county_jurisdictions_admin" ON county_jurisdictions FOR ALL USING (true) WITH CHECK (true);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_cj_co_no ON county_jurisdictions(co_no);
CREATE INDEX IF NOT EXISTS idx_cj_jurisdiction ON county_jurisdictions(jurisdiction);
