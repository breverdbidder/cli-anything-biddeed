-- ZONEWISE DATA LAKE — SUMMIT DATA-001
-- Migration: Add MapWise-parity columns + new spatial tables
-- Execute via: psql $DATABASE_URL -f migrations/20260403_data_lake_v1.sql
-- Date: April 3, 2026

BEGIN;

-- ============================================================
-- 1. ENHANCE fl_parcels with MapWise-parity columns
-- ============================================================

-- Geometry column (PostGIS)
DO $$ BEGIN
  ALTER TABLE fl_parcels ADD COLUMN geom geometry(MultiPolygon, 4326);
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Centroid coordinates (if not exists)
DO $$ BEGIN
  ALTER TABLE fl_parcels ADD COLUMN centroid_lat NUMERIC(10,6);
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
  ALTER TABLE fl_parcels ADD COLUMN centroid_lng NUMERIC(10,6);
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- MapWise-equivalent fields we're missing
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN acres_gis NUMERIC(12,4); EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN luse_desc TEXT; EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN zone_desc TEXT; EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN flu_desc TEXT; EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN sale_date DATE; EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN sale_amount NUMERIC(14,2); EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN sale_type TEXT; EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN sale_book TEXT; EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN sale_page TEXT; EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN baths_full INTEGER; EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN baths_half INTEGER; EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN beds INTEGER; EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN stories NUMERIC(4,1); EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN subdivision TEXT; EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN is_condo BOOLEAN DEFAULT FALSE; EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN val_building NUMERIC(14,2); EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN val_exempt NUMERIC(14,2); EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN pa_pin_link TEXT; EXCEPTION WHEN duplicate_column THEN NULL; END $$;

-- Auction linkage
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN auction_status TEXT; EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN auction_date DATE; EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN auction_case_no TEXT; EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN ml_score NUMERIC(5,2); EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN bid_recommend TEXT; EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fl_parcels ADD COLUMN max_bid NUMERIC(14,2); EXCEPTION WHEN duplicate_column THEN NULL; END $$;

-- Critical indexes for MapWise-parity queries
CREATE INDEX IF NOT EXISTS idx_fl_parcels_geom ON fl_parcels USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_fl_parcels_own ON fl_parcels(own_name);
CREATE INDEX IF NOT EXISTS idx_fl_parcels_addr ON fl_parcels(phy_addr1);
CREATE INDEX IF NOT EXISTS idx_fl_parcels_zone ON fl_parcels(zone_code);
CREATE INDEX IF NOT EXISTS idx_fl_parcels_city ON fl_parcels(phy_city);
CREATE INDEX IF NOT EXISTS idx_fl_parcels_zip ON fl_parcels(phy_zipcd);
CREATE INDEX IF NOT EXISTS idx_fl_parcels_dor ON fl_parcels(dor_uc);
CREATE INDEX IF NOT EXISTS idx_fl_parcels_co ON fl_parcels(co_no);
CREATE INDEX IF NOT EXISTS idx_fl_parcels_sale ON fl_parcels(sale_date);
CREATE INDEX IF NOT EXISTS idx_fl_parcels_jv ON fl_parcels(jv);
CREATE INDEX IF NOT EXISTS idx_fl_parcels_acres ON fl_parcels(lnd_sqfoot);
CREATE INDEX IF NOT EXISTS idx_fl_parcels_auction ON fl_parcels(auction_status) WHERE auction_status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fl_parcels_lat ON fl_parcels(centroid_lat);
CREATE INDEX IF NOT EXISTS idx_fl_parcels_pid ON fl_parcels(parcel_id);

-- Full text search
CREATE INDEX IF NOT EXISTS idx_fl_parcels_fts ON fl_parcels USING GIN(
  to_tsvector('english',
    COALESCE(own_name,'') || ' ' ||
    COALESCE(phy_addr1,'') || ' ' ||
    COALESCE(phy_city,'') || ' ' ||
    COALESCE(subdivision,'')
  )
);

-- ============================================================
-- 2. FLOOD ZONES TABLE (FEMA DFIRM)
-- ============================================================

CREATE TABLE IF NOT EXISTS flood_zones (
  id              BIGSERIAL PRIMARY KEY,
  fld_zone        TEXT,
  zone_subtype    TEXT,
  bfe             NUMERIC(8,2),
  static_bfe      NUMERIC(8,2),
  dfirm_id        TEXT,
  panel           TEXT,
  eff_date        DATE,
  geom            geometry(MultiPolygon, 4326),
  county          TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flood_geom ON flood_zones USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_flood_zone ON flood_zones(fld_zone);
CREATE INDEX IF NOT EXISTS idx_flood_county ON flood_zones(county);

-- ============================================================
-- 3. SOILS TABLE (USDA SSURGO)
-- ============================================================

CREATE TABLE IF NOT EXISTS soils (
  id              BIGSERIAL PRIMARY KEY,
  musym           TEXT,
  muname          TEXT,
  mukey           TEXT,
  compname        TEXT,
  is_hydric       BOOLEAN DEFAULT FALSE,
  drain_class     TEXT,
  geom            geometry(MultiPolygon, 4326),
  county          TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_soils_geom ON soils USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_soils_hydric ON soils(is_hydric);
CREATE INDEX IF NOT EXISTS idx_soils_county ON soils(county);

-- ============================================================
-- 4. WETLANDS TABLE (NWI + FL DEP)
-- ============================================================

CREATE TABLE IF NOT EXISTS wetlands (
  id              BIGSERIAL PRIMARY KEY,
  wetland_type    TEXT,
  attribute       TEXT,
  source          TEXT DEFAULT 'NWI',
  geom            geometry(MultiPolygon, 4326),
  county          TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wetlands_geom ON wetlands USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_wetlands_county ON wetlands(county);

-- ============================================================
-- 5. FUTURE LAND USE TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS future_land_use (
  id              BIGSERIAL PRIMARY KEY,
  flu_code        TEXT,
  flu_desc        TEXT,
  jurisdiction    TEXT,
  max_density     TEXT,
  geom            geometry(MultiPolygon, 4326),
  county          TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flu_geom ON future_land_use USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_flu_county ON future_land_use(county);

-- ============================================================
-- 6. LAND COVER TABLE (FL DEP 2023)
-- ============================================================

CREATE TABLE IF NOT EXISTS land_cover (
  id              BIGSERIAL PRIMARY KEY,
  fluccs_code     TEXT,
  fluccs_desc     TEXT,
  category        TEXT,
  year            INTEGER DEFAULT 2023,
  geom            geometry(MultiPolygon, 4326),
  county          TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lcover_geom ON land_cover USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_lcover_county ON land_cover(county);

-- ============================================================
-- 7. ZONING CODES MASTER TABLE (decoded descriptions)
-- ============================================================

CREATE TABLE IF NOT EXISTS zoning_codes (
  id              SERIAL PRIMARY KEY,
  county          TEXT NOT NULL,
  jurisdiction    TEXT,
  zoning_code     TEXT NOT NULL,
  zoning_desc     TEXT,
  category        TEXT,
  permitted_uses  JSONB,
  max_height_ft   INTEGER,
  max_density     TEXT,
  min_lot_size    TEXT,
  setbacks        JSONB,
  municode_url    TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(county, jurisdiction, zoning_code)
);

CREATE INDEX IF NOT EXISTS idx_zc_county ON zoning_codes(county);
CREATE INDEX IF NOT EXISTS idx_zc_code ON zoning_codes(zoning_code);
CREATE INDEX IF NOT EXISTS idx_zc_cat ON zoning_codes(category);

-- ============================================================
-- 8. PARCEL SALES HISTORY (all historical, not just recent)
-- ============================================================

CREATE TABLE IF NOT EXISTS parcel_sales_history (
  id              BIGSERIAL PRIMARY KEY,
  co_no           INTEGER,
  parcel_id       TEXT NOT NULL,
  sale_date       DATE,
  sale_amount     NUMERIC(14,2),
  sale_type       TEXT,
  sale_qual       TEXT,
  sale_vac        TEXT,
  sale_book       TEXT,
  sale_page       TEXT,
  sale_docnum     TEXT,
  grantor         TEXT,
  grantee         TEXT,
  county          TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_psh_parcel ON parcel_sales_history(parcel_id);
CREATE INDEX IF NOT EXISTS idx_psh_co ON parcel_sales_history(co_no);
CREATE INDEX IF NOT EXISTS idx_psh_date ON parcel_sales_history(sale_date);
CREATE INDEX IF NOT EXISTS idx_psh_county ON parcel_sales_history(county);

-- ============================================================
-- 9. DOR LAND USE CODE REFERENCE TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS dor_land_use_codes (
  dor_uc          TEXT PRIMARY KEY,
  description     TEXT NOT NULL,
  category        TEXT,
  dor_2digit      TEXT,
  dor_2digit_desc TEXT
);

-- Populate DOR codes (FL Dept of Revenue standard)
INSERT INTO dor_land_use_codes (dor_uc, description, category, dor_2digit, dor_2digit_desc) VALUES
('000', 'Vacant Residential', 'RESIDENTIAL', '00', 'Vacant Residential'),
('001', 'Single Family', 'RESIDENTIAL', '01', 'Single Family Residential'),
('002', 'Mobile Home', 'RESIDENTIAL', '02', 'Mobile Homes'),
('003', 'Multi-Family (10+)', 'RESIDENTIAL', '03', 'Multi-Family (10+ units)'),
('004', 'Condominium', 'RESIDENTIAL', '04', 'Condominiums'),
('005', 'Cooperatives', 'RESIDENTIAL', '05', 'Cooperatives'),
('006', 'Retirement Homes', 'RESIDENTIAL', '06', 'Retirement Homes'),
('007', 'Miscellaneous Residential', 'RESIDENTIAL', '07', 'Misc Residential'),
('008', 'Multi-Family (2-9)', 'RESIDENTIAL', '08', 'Multi-Family (<10 units)'),
('009', 'Residential Common Elements', 'RESIDENTIAL', '09', 'Residential Common'),
('010', 'Vacant Commercial', 'COMMERCIAL', '10', 'Vacant Commercial'),
('011', 'Stores/One Story', 'COMMERCIAL', '11', 'Stores'),
('012', 'Mixed Use Store/Office', 'COMMERCIAL', '12', 'Mixed Use'),
('013', 'Department Store', 'COMMERCIAL', '13', 'Department Stores'),
('014', 'Supermarket', 'COMMERCIAL', '14', 'Supermarkets'),
('015', 'Regional Shopping Center', 'COMMERCIAL', '15', 'Shopping Centers'),
('016', 'Community Shopping Center', 'COMMERCIAL', '16', 'Community Shopping'),
('017', 'Office One Story', 'COMMERCIAL', '17', 'Office Buildings'),
('018', 'Office Multi-Story', 'COMMERCIAL', '18', 'Office Multi-Story'),
('019', 'Professional Service Building', 'COMMERCIAL', '19', 'Professional Service'),
('020', 'Vacant Industrial', 'INDUSTRIAL', '20', 'Vacant Industrial'),
('021', 'Light Manufacturing', 'INDUSTRIAL', '21', 'Light Manufacturing'),
('022', 'Heavy Manufacturing', 'INDUSTRIAL', '22', 'Heavy Manufacturing'),
('023', 'Lumber Yards', 'INDUSTRIAL', '23', 'Lumber/Building Materials'),
('024', 'Packing Plants', 'INDUSTRIAL', '24', 'Packing/Processing'),
('025', 'Cateries', 'INDUSTRIAL', '25', 'Cateries/Mining'),
('026', 'Other Food Processing', 'INDUSTRIAL', '26', 'Food Processing'),
('027', 'Mineral Processing', 'INDUSTRIAL', '27', 'Mineral Processing'),
('028', 'Warehouse/Distribution', 'INDUSTRIAL', '28', 'Warehousing'),
('029', 'Industrial Common Elements', 'INDUSTRIAL', '29', 'Industrial Common'),
('030', 'Vacant Agricultural', 'AGRICULTURAL', '30', 'Vacant Agricultural'),
('039', 'Hotels/Motels', 'COMMERCIAL', '39', 'Hotels/Motels'),
('048', 'Warehousing/Distribution', 'INDUSTRIAL', '48', 'Warehousing'),
('060', 'Grazing Land', 'AGRICULTURAL', '60', 'Grazing'),
('070', 'Vacant Institutional', 'INSTITUTIONAL', '70', 'Vacant Institutional'),
('071', 'Churches', 'INSTITUTIONAL', '71', 'Churches/Religious'),
('072', 'Private Schools', 'INSTITUTIONAL', '72', 'Private Schools'),
('073', 'Private Hospital', 'INSTITUTIONAL', '73', 'Private Hospitals'),
('074', 'Homes for the Aged', 'INSTITUTIONAL', '74', 'Homes for Aged'),
('075', 'Orphanages', 'INSTITUTIONAL', '75', 'Orphanages'),
('076', 'Mortuaries/Cemeteries', 'INSTITUTIONAL', '76', 'Mortuaries'),
('077', 'Clubs/Lodges/Union Halls', 'INSTITUTIONAL', '77', 'Clubs/Lodges'),
('080', 'Undefined', 'GOVERNMENT', '80', 'Government (undefined)'),
('081', 'Military', 'GOVERNMENT', '81', 'Military'),
('082', 'Forest/Parks/Rec (Fed)', 'GOVERNMENT', '82', 'Federal Parks'),
('083', 'Public Schools', 'GOVERNMENT', '83', 'Public Schools'),
('084', 'Public Colleges', 'GOVERNMENT', '84', 'Public Colleges'),
('085', 'Public Hospitals', 'GOVERNMENT', '85', 'Public Hospitals'),
('086', 'County', 'GOVERNMENT', '86', 'County Government'),
('087', 'State', 'GOVERNMENT', '87', 'State Government'),
('088', 'Federal', 'GOVERNMENT', '88', 'Federal Government'),
('089', 'Municipal', 'GOVERNMENT', '89', 'Municipal Government'),
('090', 'Leasehold Interests', 'OTHER', '90', 'Leasehold'),
('091', 'Utility/Gas/Electric', 'OTHER', '91', 'Utilities'),
('092', 'Mining/Petroleum', 'OTHER', '92', 'Mining/Petroleum'),
('093', 'Subsurface Rights', 'OTHER', '93', 'Subsurface Rights'),
('094', 'Right-of-Way', 'OTHER', '94', 'Right-of-Way'),
('095', 'Rivers/Lakes/Submerged', 'OTHER', '95', 'Water/Submerged'),
('096', 'Sewage Disposal/Waste', 'OTHER', '96', 'Sewage/Waste'),
('097', 'Outdoor Recreation', 'OTHER', '97', 'Outdoor Recreation'),
('099', 'Non-Agricultural Acreage', 'OTHER', '99', 'Non-Ag Acreage')
ON CONFLICT (dor_uc) DO NOTHING;

-- ============================================================
-- 10. COMPETITIVE INTEL TABLE (track MapWise + others)
-- ============================================================

CREATE TABLE IF NOT EXISTS competitive_intel (
  id              SERIAL PRIMARY KEY,
  competitor      TEXT NOT NULL,
  feature         TEXT NOT NULL,
  our_status      TEXT,
  their_status    TEXT,
  gap_owner       TEXT,
  priority        TEXT,
  notes           TEXT,
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 11. RPC FUNCTIONS FOR SPATIAL QUERIES
-- ============================================================

-- Parcel lookup by lat/lon (point-in-polygon)
CREATE OR REPLACE FUNCTION parcels_at_point(lat NUMERIC, lon NUMERIC)
RETURNS SETOF fl_parcels AS $$
  SELECT * FROM fl_parcels
  WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(lon, lat), 4326))
  LIMIT 10;
$$ LANGUAGE sql STABLE;

-- Parcels within bounding box
CREATE OR REPLACE FUNCTION parcels_in_bbox(
  xmin NUMERIC, ymin NUMERIC, xmax NUMERIC, ymax NUMERIC
)
RETURNS SETOF fl_parcels AS $$
  SELECT * FROM fl_parcels
  WHERE geom && ST_MakeEnvelope(xmin, ymin, xmax, ymax, 4326)
  LIMIT 100;
$$ LANGUAGE sql STABLE;

-- Flood zone check for a point
CREATE OR REPLACE FUNCTION flood_zone_at_point(lat NUMERIC, lon NUMERIC)
RETURNS TABLE(fld_zone TEXT, zone_subtype TEXT, bfe NUMERIC, panel TEXT) AS $$
  SELECT fld_zone, zone_subtype, bfe, panel
  FROM flood_zones
  WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(lon, lat), 4326))
  LIMIT 5;
$$ LANGUAGE sql STABLE;

-- Full property report (parcel + zoning decoded + flood)
CREATE OR REPLACE FUNCTION property_report(p_parcel_id TEXT, p_co_no INTEGER)
RETURNS JSON AS $$
DECLARE
  result JSON;
BEGIN
  SELECT json_build_object(
    'parcel', row_to_json(p.*),
    'zoning', (
      SELECT row_to_json(z.*)
      FROM zoning_codes z
      WHERE z.county = LOWER((SELECT county FROM fl_counties WHERE co_no = p_co_no LIMIT 1))
        AND z.zoning_code = p.zone_code
      LIMIT 1
    ),
    'dor_land_use', (
      SELECT row_to_json(d.*)
      FROM dor_land_use_codes d
      WHERE d.dor_uc = LPAD(p.dor_uc, 3, '0')
      LIMIT 1
    ),
    'sales_history', (
      SELECT json_agg(row_to_json(s.*))
      FROM parcel_sales_history s
      WHERE s.parcel_id = p.parcel_id AND s.co_no = p.co_no
      ORDER BY s.sale_date DESC
      LIMIT 10
    )
  ) INTO result
  FROM fl_parcels p
  WHERE p.parcel_id = p_parcel_id AND p.co_no = p_co_no
  LIMIT 1;
  
  RETURN result;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- 12. UPDATE fl_parcels WITH DOR DESCRIPTIONS (backfill)
-- ============================================================

UPDATE fl_parcels p
SET luse_desc = d.description
FROM dor_land_use_codes d
WHERE LPAD(p.dor_uc, 3, '0') = d.dor_uc
AND p.luse_desc IS NULL;

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================
-- SELECT count(*) FROM fl_parcels;
-- SELECT count(*) FROM fl_parcels WHERE luse_desc IS NOT NULL;
-- SELECT count(*) FROM zoning_codes;
-- SELECT count(*) FROM dor_land_use_codes;
-- SELECT count(*) FROM flood_zones;
-- SELECT * FROM property_report('25 3613-CR-*-9', 5);
