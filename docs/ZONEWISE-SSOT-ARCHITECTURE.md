# ZONEWISE SSOT — Single Source of Truth
## MapWise-Validated Schema + ZoneWise Extensions

> **SUMMIT:** ARCH-001 — The Most Important Migration in the Ecosystem
> **Principle:** MapWise proved this schema works for 26 years at #1 on Google.
> **Rule:** ONE table. ONE API. Every tool reads from here. Period.

---

## THE PROBLEM

```
TODAY: 20+ fragmented tables, data scattered everywhere

fl_parcels ──────── 9.4M rows, 57 counties, NO zoning, NO geometry
zoning_assignments ─ 351K rows, Brevard ONLY
brevard_properties ─ duplicate Brevard data
historical_auctions  1,393 rows, separate
foreclosure_auctions separate
parcel_cache ─────── separate
parcel_zones ─────── separate
sales_history ────── separate
building_details ─── separate
lien_results ─────── separate
property_analyses ── separate
```

**Result: Nothing joins. Nothing is complete. No SSOT.**

---

## THE SOLUTION

```
AFTER: ONE table. MapWise schema. Everything joins by (county, pin).

┌─────────────────────────────────────────────────┐
│              zw_parcels (SSOT)                   │
│  10.8M rows × 67 counties × ~80 columns         │
│                                                   │
│  MapWise-compatible fields (proven 26yr schema):  │
│  ├── identifiers (pin, altkey)                   │
│  ├── owner (name, mailing address)               │
│  ├── site (address, city, zip, subdivision)      │
│  ├── land (acres, zoning, land_use + desc)       │
│  ├── building (sqft, year, beds, baths)          │
│  ├── valuation (market, assessed, taxable)       │
│  ├── sales (recent: date, amount, book/page)     │
│  └── geometry (PostGIS, centroid, bbox)           │
│                                                   │
│  ZoneWise extensions (MapWise can't compete):     │
│  ├── zoning_decoded (desc, category, uses)       │
│  ├── auction (status, date, case, judgment)       │
│  ├── ml (score, recommendation, max_bid)          │
│  ├── flood (zone, bfe)                            │
│  └── lien (senior liens, hoa flag)               │
└─────────────────────────────────────────────────┘
         │
         │ Every tool reads from HERE
         ├── ZoneWise Explorer (free)
         ├── ZoneWise Chat / Dify RAG
         ├── BidDeed.AI auction engine
         ├── /api/v1/parcels (public API)
         ├── County pages (programmatic SEO)
         └── YouTube data visualizations
```

---

## SCHEMA: `zw_parcels`

Directly mapped from MapWise API response + our extensions.

```sql
CREATE TABLE zw_parcels (
  -- PRIMARY KEY
  id                BIGSERIAL PRIMARY KEY,
  county            TEXT NOT NULL,         -- "BREVARD" (uppercase, DOR standard)
  co_no             SMALLINT NOT NULL,     -- DOR county number (1-67)
  pin               TEXT NOT NULL,         -- parcel ID (county format)
  pin_clean         TEXT,                  -- normalized (digits only)
  altkey            TEXT,                  -- alt key if exists

  -- OWNER (MapWise: owner.*)
  owner_name        TEXT,                  -- primary owner
  owner_name2       TEXT,                  -- secondary
  owner_addr1       TEXT,                  -- mailing line 1
  owner_addr2       TEXT,                  -- mailing line 2
  owner_city        TEXT,
  owner_state       TEXT,
  owner_zip         TEXT,

  -- SITE (MapWise: site.*)
  site_addr         TEXT,                  -- physical address
  site_city         TEXT,
  site_zip          TEXT,
  subdivision       TEXT,
  is_condo          BOOLEAN DEFAULT FALSE,

  -- LAND (MapWise: land.*)
  acres_deed        NUMERIC(12,4),
  acres_gis         NUMERIC(12,4),
  zoning_code       TEXT,                  -- raw code: "RU-1-13"
  zoning_desc       TEXT,                  -- decoded: "Single-Family Residential"
  zoning_category   TEXT,                  -- RESIDENTIAL/COMMERCIAL/etc
  luse_code         TEXT,                  -- DOR land use code
  luse_desc         TEXT,                  -- "Single Family"
  flu_code          TEXT,                  -- future land use
  flu_desc          TEXT,

  -- BUILDING (MapWise: building.*)
  num_buildings     SMALLINT,
  stories           NUMERIC(4,1),
  sqft_heated       INTEGER,
  sqft_total        INTEGER,
  year_built        SMALLINT,
  year_built_eff    SMALLINT,
  beds              SMALLINT,
  baths_full        SMALLINT,
  baths_half        SMALLINT,

  -- VALUATION (MapWise: valuation.*)
  val_market        INTEGER,               -- total market value
  val_land          INTEGER,
  val_building      INTEGER,
  val_assessed      INTEGER,
  val_taxable       INTEGER,
  val_exempt        INTEGER,

  -- SALES (MapWise: sales.recent.*)
  sale_date         DATE,
  sale_price        INTEGER,
  sale_type         TEXT,
  sale_qual         TEXT,
  sale_book         TEXT,
  sale_page         TEXT,
  sale_grantor      TEXT,

  -- GEOMETRY (MapWise: geometry.*)
  geom              GEOMETRY(MultiPolygon, 4326),
  centroid_lat      NUMERIC(10,6),
  centroid_lon      NUMERIC(10,6),

  -- === ZONEWISE EXTENSIONS (what makes us better) ===

  -- ZONING DECODED
  zoning_permitted  JSONB,                 -- {"single_family":true,"duplex":false}
  zoning_max_ht     SMALLINT,              -- max height ft
  zoning_min_lot    TEXT,                   -- "7500 sqft"
  zoning_setbacks   JSONB,                 -- {"front":25,"side":10,"rear":20}
  zoning_jurisdiction TEXT,                 -- "satellite beach"

  -- AUCTION INTELLIGENCE
  auction_status    TEXT,                   -- FORECLOSURE/TAX_DEED/NONE
  auction_date      DATE,
  auction_case_no   TEXT,
  auction_plaintiff TEXT,
  judgment_amt      INTEGER,
  opening_bid       INTEGER,
  final_bid         INTEGER,

  -- ML PREDICTIONS
  ml_score          NUMERIC(5,2),
  ml_recommendation TEXT,                  -- BID/REVIEW/SKIP
  ml_max_bid        INTEGER,

  -- FLOOD
  flood_zone        TEXT,                   -- A/AE/V/X
  flood_bfe         NUMERIC(8,2),

  -- LIENS
  senior_liens      JSONB,
  is_hoa_foreclosure BOOLEAN,

  -- META
  pa_link           TEXT,                   -- county PA direct link
  photo_url         TEXT,
  data_source       TEXT,                   -- FL_GIO/BCPAO/COUNTY_PA
  extracted_at      DATE,
  updated_at        TIMESTAMPTZ DEFAULT NOW(),
  created_at        TIMESTAMPTZ DEFAULT NOW(),

  -- CONSTRAINTS
  UNIQUE(co_no, pin)
);

-- === INDEXES (MapWise-equivalent query patterns) ===
CREATE INDEX idx_zw_county      ON zw_parcels(county);
CREATE INDEX idx_zw_co_no       ON zw_parcels(co_no);
CREATE INDEX idx_zw_pin         ON zw_parcels(pin);
CREATE INDEX idx_zw_pin_clean   ON zw_parcels(pin_clean);
CREATE INDEX idx_zw_owner       ON zw_parcels(owner_name);
CREATE INDEX idx_zw_owner_city  ON zw_parcels(owner_city);
CREATE INDEX idx_zw_owner_state ON zw_parcels(owner_state);
CREATE INDEX idx_zw_owner_zip   ON zw_parcels(owner_zip);
CREATE INDEX idx_zw_site_addr   ON zw_parcels(site_addr);
CREATE INDEX idx_zw_site_city   ON zw_parcels(site_city);
CREATE INDEX idx_zw_site_zip    ON zw_parcels(site_zip);
CREATE INDEX idx_zw_zoning      ON zw_parcels(zoning_code);
CREATE INDEX idx_zw_zoning_cat  ON zw_parcels(zoning_category);
CREATE INDEX idx_zw_luse        ON zw_parcels(luse_code);
CREATE INDEX idx_zw_acres       ON zw_parcels(acres_gis);
CREATE INDEX idx_zw_sale_date   ON zw_parcels(sale_date);
CREATE INDEX idx_zw_sale_price  ON zw_parcels(sale_price);
CREATE INDEX idx_zw_val         ON zw_parcels(val_market);
CREATE INDEX idx_zw_year        ON zw_parcels(year_built);
CREATE INDEX idx_zw_auction     ON zw_parcels(auction_status)
  WHERE auction_status IS NOT NULL;
CREATE INDEX idx_zw_flood       ON zw_parcels(flood_zone)
  WHERE flood_zone IS NOT NULL;
CREATE INDEX idx_zw_geom        ON zw_parcels USING GIST(geom);
CREATE INDEX idx_zw_subdivision ON zw_parcels(subdivision);

-- Full text search (owner + address + subdivision)
CREATE INDEX idx_zw_fts ON zw_parcels USING GIN(
  to_tsvector('english',
    COALESCE(owner_name,'') || ' ' ||
    COALESCE(owner_addr1,'') || ' ' ||
    COALESCE(site_addr,'') || ' ' ||
    COALESCE(site_city,'') || ' ' ||
    COALESCE(subdivision,'')
  )
);

-- === CONSOLIDATION: Merge all fragmented tables ===

-- Step 1: fl_parcels → zw_parcels (9.4M rows, bulk)
INSERT INTO zw_parcels (
  co_no, county, pin, pin_clean,
  owner_name, owner_addr1, owner_city, owner_state, owner_zip,
  site_addr, site_city, site_zip, subdivision,
  luse_code, num_buildings, sqft_heated, year_built, year_built_eff,
  val_market, val_land, val_assessed, val_taxable,
  sale_price, acres_gis, photo_url, extracted_at
)
SELECT
  co_no,
  UPPER(COALESCE(
    (SELECT name FROM fl_counties WHERE fl_counties.co_no = fp.co_no LIMIT 1),
    'COUNTY_' || co_no
  )),
  parcel_id,
  REGEXP_REPLACE(parcel_id, '[^0-9]', '', 'g'),
  own_name, own_addr1, own_city, own_state, own_zipcd,
  phy_addr1, phy_city, phy_zipcd, NULL,
  dor_uc, no_buldng, tot_lvg_ar, act_yr_blt, eff_yr_blt,
  jv, lnd_val, av_sd, tv_sd,
  sale_prc1, lnd_sqfoot::numeric / 43560.0, photo_url, scraped_at::date
FROM fl_parcels fp
ON CONFLICT (co_no, pin) DO UPDATE SET
  owner_name = EXCLUDED.owner_name,
  val_market = EXCLUDED.val_market,
  updated_at = NOW();

-- Step 2: Backfill zoning from zoning_assignments (351K Brevard)
UPDATE zw_parcels z
SET
  zoning_code = za.zone_code,
  zoning_jurisdiction = za.jurisdiction,
  photo_url = COALESCE(z.photo_url, za.photo_url)
FROM zoning_assignments za
WHERE z.co_no = za.co_no
  AND z.pin = za.parcel_id
  AND za.zone_code IS NOT NULL;

-- Step 3: Backfill decoded zoning from zoning_codes
UPDATE zw_parcels z
SET
  zoning_desc = zc.zoning_desc,
  zoning_category = zc.category,
  zoning_permitted = zc.permitted_uses::jsonb,
  zoning_max_ht = zc.max_height_ft,
  zoning_min_lot = zc.min_lot_size,
  zoning_setbacks = zc.setbacks::jsonb
FROM zoning_codes zc
WHERE LOWER(z.county) = zc.county
  AND LOWER(COALESCE(z.zoning_jurisdiction, 'unincorporated')) = zc.jurisdiction
  AND z.zoning_code = zc.zoning_code;

-- Step 4: Backfill DOR land use descriptions
UPDATE zw_parcels z
SET luse_desc = d.description
FROM dor_land_use_codes d
WHERE LPAD(z.luse_code, 3, '0') = d.dor_uc
  AND z.luse_desc IS NULL;

-- Step 5: Backfill auction data from foreclosure_auctions
UPDATE zw_parcels z
SET
  auction_status = 'FORECLOSURE',
  auction_date = fa.auction_date,
  auction_case_no = fa.case_number,
  judgment_amt = fa.judgment_amount::integer
FROM foreclosure_auctions fa
WHERE z.co_no = 5 -- Brevard
  AND z.pin = fa.parcel_id
  AND fa.status IN ('SCHEDULED', 'ACTIVE');

-- Step 6: Backfill flood zones (spatial join — requires geometry)
-- This runs AFTER geometry is loaded
-- UPDATE zw_parcels z
-- SET flood_zone = f.fld_zone, flood_bfe = f.bfe
-- FROM flood_zones f
-- WHERE ST_Intersects(z.geom, f.geom);

-- === API FUNCTIONS (MapWise-compatible) ===

-- Parcel search (mirrors MapWise /api_v2/parcels)
CREATE OR REPLACE FUNCTION zw_search_parcels(
  p_county TEXT DEFAULT NULL,
  p_owner TEXT DEFAULT NULL,
  p_pin TEXT DEFAULT NULL,
  p_address TEXT DEFAULT NULL,
  p_city TEXT DEFAULT NULL,
  p_zip TEXT DEFAULT NULL,
  p_zoning TEXT DEFAULT NULL,
  p_acres_min NUMERIC DEFAULT NULL,
  p_acres_max NUMERIC DEFAULT NULL,
  p_sale_min NUMERIC DEFAULT NULL,
  p_sale_max NUMERIC DEFAULT NULL,
  p_limit INTEGER DEFAULT 50,
  p_offset INTEGER DEFAULT 0
)
RETURNS SETOF zw_parcels AS $$
  SELECT * FROM zw_parcels
  WHERE
    (p_county IS NULL OR UPPER(county) = UPPER(p_county))
    AND (p_owner IS NULL OR owner_name ILIKE '%' || p_owner || '%')
    AND (p_pin IS NULL OR pin LIKE '%' || p_pin || '%')
    AND (p_address IS NULL OR site_addr ILIKE '%' || p_address || '%')
    AND (p_city IS NULL OR site_city ILIKE '%' || p_city || '%')
    AND (p_zip IS NULL OR site_zip LIKE p_zip || '%')
    AND (p_zoning IS NULL OR zoning_code = p_zoning)
    AND (p_acres_min IS NULL OR acres_gis >= p_acres_min)
    AND (p_acres_max IS NULL OR acres_gis <= p_acres_max)
    AND (p_sale_min IS NULL OR sale_price >= p_sale_min)
    AND (p_sale_max IS NULL OR sale_price <= p_sale_max)
  ORDER BY county, pin
  LIMIT p_limit OFFSET p_offset;
$$ LANGUAGE sql STABLE;

-- Point-in-polygon lookup
CREATE OR REPLACE FUNCTION zw_parcel_at_point(lat NUMERIC, lon NUMERIC)
RETURNS SETOF zw_parcels AS $$
  SELECT * FROM zw_parcels
  WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(lon, lat), 4326))
  LIMIT 5;
$$ LANGUAGE sql STABLE;

-- Bounding box search
CREATE OR REPLACE FUNCTION zw_parcels_in_bbox(
  xmin NUMERIC, ymin NUMERIC, xmax NUMERIC, ymax NUMERIC,
  p_limit INTEGER DEFAULT 100
)
RETURNS SETOF zw_parcels AS $$
  SELECT * FROM zw_parcels
  WHERE geom && ST_MakeEnvelope(xmin, ymin, xmax, ymax, 4326)
  LIMIT p_limit;
$$ LANGUAGE sql STABLE;

-- County statistics (for programmatic SEO pages)
CREATE OR REPLACE FUNCTION zw_county_stats(p_county TEXT)
RETURNS JSON AS $$
  SELECT json_build_object(
    'county', p_county,
    'total_parcels', COUNT(*),
    'with_zoning', COUNT(zoning_code),
    'zoning_pct', ROUND(COUNT(zoning_code)::numeric / NULLIF(COUNT(*),0) * 100, 1),
    'median_value', PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY val_market),
    'avg_acres', ROUND(AVG(acres_gis)::numeric, 2),
    'active_auctions', COUNT(*) FILTER (WHERE auction_status IS NOT NULL),
    'top_zoning_codes', (
      SELECT json_agg(row_to_json(t))
      FROM (
        SELECT zoning_code, zoning_desc, COUNT(*) as cnt
        FROM zw_parcels WHERE UPPER(county) = UPPER(p_county) AND zoning_code IS NOT NULL
        GROUP BY zoning_code, zoning_desc ORDER BY cnt DESC LIMIT 10
      ) t
    )
  )
  FROM zw_parcels WHERE UPPER(county) = UPPER(p_county);
$$ LANGUAGE sql STABLE;
```

---

## DATA PIPELINE: 67-County Ingestion

```yaml
# Runs on Hetzner via CC or GHA
# Sources: FL GIO (parcels), County GIS (zoning), FEMA (flood)

pipeline:
  stage_1_parcels:
    source: FL GIO ArcGIS REST API
    url: "https://services1.arcgis.com/.../Florida_Statewide_Parcels/FeatureServer/0"
    method: Query by county, 2000 records/batch, with geometry
    target: zw_parcels (INSERT with geometry + centroid computation)
    rows: 10.8M
    estimate: 4-6 hours on Hetzner
    
  stage_2_zoning_backfill:
    source: zoning_assignments (existing 351K Brevard)
    method: UPDATE zw_parcels SET zoning_code = za.zone_code
    then: County GIS APIs for remaining 66 counties
    estimate: 1 hour for Brevard, 2-4 hours for others
    
  stage_3_zoning_decode:
    source: zoning_codes master (existing 7,531 codes)
    method: JOIN on (county, jurisdiction, zoning_code)
    backfill: zoning_desc, category, permitted_uses, setbacks
    estimate: 30 min
    
  stage_4_flood:
    source: FEMA NFHL ArcGIS REST API
    method: Spatial join (ST_Intersects) 
    target: zw_parcels.flood_zone, flood_bfe
    estimate: 2-3 hours
    
  stage_5_auctions:
    source: foreclosure_auctions + historical_auctions
    method: JOIN on (co_no, pin)
    backfill: auction_status, date, case_no, judgment
    estimate: 15 min
    
  stage_6_verify:
    method: County-by-county completeness audit
    threshold: 85% = enterprise, 50% = partial, <50% = needs work
    output: Supabase county_data_quality table
```

---

## WHAT THIS ENABLES

After consolidation, ONE API call returns everything:

```json
GET /api/v1/parcels?county=BREVARD&pin=25-37-22-01-00001.0

{
  "county": "BREVARD",
  "pin": "25-37-22-01-00001.0",
  "owner_name": "SMITH, JOHN",
  "site_addr": "123 OCEAN AVE",
  "site_city": "SATELLITE BEACH",
  "zoning_code": "R-1",
  "zoning_desc": "Single-Family Residential",
  "zoning_category": "RESIDENTIAL",
  "zoning_permitted": {"single_family": true, "duplex": false},
  "zoning_max_ht": 35,
  "zoning_setbacks": {"front": 25, "side": 10, "rear": 20},
  "luse_desc": "Single Family",
  "val_market": 425000,
  "year_built": 1985,
  "sqft_heated": 1800,
  "beds": 3,
  "baths_full": 2,
  "acres_gis": 0.23,
  "sale_date": "2022-06-15",
  "sale_price": 380000,
  "auction_status": null,
  "flood_zone": "X",
  "centroid_lat": 28.1834,
  "centroid_lon": -80.5901
}
```

**MapWise charges $89/mo for this. We give basics free, charge $99/mo for AI.**
