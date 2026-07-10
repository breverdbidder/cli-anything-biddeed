-- ARCH-001: Create zw_parcels SSOT table
BEGIN;

CREATE TABLE IF NOT EXISTS zw_parcels (
  id                BIGSERIAL PRIMARY KEY,
  county            TEXT NOT NULL,
  co_no             SMALLINT NOT NULL,
  pin               TEXT NOT NULL,
  pin_clean         TEXT,
  altkey            TEXT,
  owner_name        TEXT,
  owner_name2       TEXT,
  owner_addr1       TEXT,
  owner_addr2       TEXT,
  owner_city        TEXT,
  owner_state       TEXT,
  owner_zip         TEXT,
  site_addr         TEXT,
  site_city         TEXT,
  site_zip          TEXT,
  subdivision       TEXT,
  is_condo          BOOLEAN DEFAULT FALSE,
  acres_deed        NUMERIC(12,4),
  acres_gis         NUMERIC(12,4),
  zoning_code       TEXT,
  zoning_desc       TEXT,
  zoning_category   TEXT,
  luse_code         TEXT,
  luse_desc         TEXT,
  flu_code          TEXT,
  flu_desc          TEXT,
  num_buildings     SMALLINT,
  stories           NUMERIC(4,1),
  sqft_heated       INTEGER,
  sqft_total        INTEGER,
  year_built        SMALLINT,
  year_built_eff    SMALLINT,
  beds              SMALLINT,
  baths_full        SMALLINT,
  baths_half        SMALLINT,
  val_market        INTEGER,
  val_land          INTEGER,
  val_building      INTEGER,
  val_assessed      INTEGER,
  val_taxable       INTEGER,
  val_exempt        INTEGER,
  sale_date         DATE,
  sale_price        INTEGER,
  sale_type         TEXT,
  sale_qual         TEXT,
  sale_book         TEXT,
  sale_page         TEXT,
  sale_grantor      TEXT,
  geom              GEOMETRY(MultiPolygon, 4326),
  centroid_lat      NUMERIC(10,6),
  centroid_lon      NUMERIC(10,6),
  zoning_permitted  JSONB,
  zoning_max_ht     SMALLINT,
  zoning_min_lot    TEXT,
  zoning_setbacks   JSONB,
  zoning_jurisdiction TEXT,
  auction_status    TEXT,
  auction_date      DATE,
  auction_case_no   TEXT,
  auction_plaintiff TEXT,
  judgment_amt      INTEGER,
  opening_bid       INTEGER,
  final_bid         INTEGER,
  ml_score          NUMERIC(5,2),
  ml_recommendation TEXT,
  ml_max_bid        INTEGER,
  flood_zone        TEXT,
  flood_bfe         NUMERIC(8,2),
  senior_liens      JSONB,
  is_hoa_foreclosure BOOLEAN,
  pa_link           TEXT,
  photo_url         TEXT,
  data_source       TEXT DEFAULT 'FL_GIO',
  extracted_at      DATE,
  updated_at        TIMESTAMPTZ DEFAULT NOW(),
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(co_no, pin)
);

CREATE INDEX IF NOT EXISTS idx_zw_county ON zw_parcels(county);
CREATE INDEX IF NOT EXISTS idx_zw_co_no ON zw_parcels(co_no);
CREATE INDEX IF NOT EXISTS idx_zw_pin ON zw_parcels(pin);
CREATE INDEX IF NOT EXISTS idx_zw_owner ON zw_parcels(owner_name);
CREATE INDEX IF NOT EXISTS idx_zw_owner_zip ON zw_parcels(owner_zip);
CREATE INDEX IF NOT EXISTS idx_zw_site_addr ON zw_parcels(site_addr);
CREATE INDEX IF NOT EXISTS idx_zw_site_city ON zw_parcels(site_city);
CREATE INDEX IF NOT EXISTS idx_zw_site_zip ON zw_parcels(site_zip);
CREATE INDEX IF NOT EXISTS idx_zw_zoning ON zw_parcels(zoning_code);
CREATE INDEX IF NOT EXISTS idx_zw_zoning_cat ON zw_parcels(zoning_category);
CREATE INDEX IF NOT EXISTS idx_zw_luse ON zw_parcels(luse_code);
CREATE INDEX IF NOT EXISTS idx_zw_sale_date ON zw_parcels(sale_date);
CREATE INDEX IF NOT EXISTS idx_zw_sale_price ON zw_parcels(sale_price);
CREATE INDEX IF NOT EXISTS idx_zw_val ON zw_parcels(val_market);
CREATE INDEX IF NOT EXISTS idx_zw_year ON zw_parcels(year_built);
CREATE INDEX IF NOT EXISTS idx_zw_auction ON zw_parcels(auction_status) WHERE auction_status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_zw_flood ON zw_parcels(flood_zone) WHERE flood_zone IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_zw_geom ON zw_parcels USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_zw_subdivision ON zw_parcels(subdivision);
CREATE INDEX IF NOT EXISTS idx_zw_fts ON zw_parcels USING GIN(
  to_tsvector('english',
    COALESCE(owner_name,'') || ' ' ||
    COALESCE(site_addr,'') || ' ' ||
    COALESCE(site_city,'') || ' ' ||
    COALESCE(subdivision,'')
  )
);

-- Search function (MapWise-compatible)
CREATE OR REPLACE FUNCTION zw_search_parcels(
  p_county TEXT DEFAULT NULL, p_owner TEXT DEFAULT NULL,
  p_pin TEXT DEFAULT NULL, p_address TEXT DEFAULT NULL,
  p_city TEXT DEFAULT NULL, p_zip TEXT DEFAULT NULL,
  p_zoning TEXT DEFAULT NULL,
  p_limit INTEGER DEFAULT 50, p_offset INTEGER DEFAULT 0
) RETURNS SETOF zw_parcels AS $$
  SELECT * FROM zw_parcels WHERE
    (p_county IS NULL OR UPPER(county) = UPPER(p_county))
    AND (p_owner IS NULL OR owner_name ILIKE '%' || p_owner || '%')
    AND (p_pin IS NULL OR pin LIKE '%' || p_pin || '%')
    AND (p_address IS NULL OR site_addr ILIKE '%' || p_address || '%')
    AND (p_city IS NULL OR site_city ILIKE '%' || p_city || '%')
    AND (p_zip IS NULL OR site_zip LIKE p_zip || '%')
    AND (p_zoning IS NULL OR zoning_code = p_zoning)
  ORDER BY county, pin LIMIT p_limit OFFSET p_offset;
$$ LANGUAGE sql STABLE;

-- County stats function (for SEO pages)
CREATE OR REPLACE FUNCTION zw_county_stats(p_county TEXT)
RETURNS JSON AS $$
  SELECT json_build_object(
    'county', p_county,
    'total_parcels', COUNT(*),
    'with_zoning', COUNT(zoning_code),
    'median_value', PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY val_market),
    'active_auctions', COUNT(*) FILTER (WHERE auction_status IS NOT NULL)
  ) FROM zw_parcels WHERE UPPER(county) = UPPER(p_county);
$$ LANGUAGE sql STABLE;

COMMIT;
