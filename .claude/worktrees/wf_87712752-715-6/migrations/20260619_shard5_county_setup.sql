-- SHARD-5 Migration: County setup for hillsborough, collier, gulf, desoto, madison
-- Session: architect-20260619-shard5
-- Purpose: Ensure bid_decisions table exists, fl_counties rows, and pipeline.counties
--          for shard-5 counties (H, A, C, D, E, I, J gold standard fixes)

SET statement_timeout = 0;

-- ── bid_decisions table (idempotent) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bid_decisions (
    id              SERIAL PRIMARY KEY,
    case_number     TEXT NOT NULL UNIQUE,
    county_slug     TEXT NOT NULL,
    parcel_id       TEXT,
    arv             NUMERIC(12,2),
    max_bid         NUMERIC(12,2),
    ml_score        NUMERIC(5,4),
    ml_model_version TEXT,
    factors         JSONB,
    repair_estimate NUMERIC(12,2),
    profit_potential NUMERIC(12,2),
    deal_grade      TEXT,
    confidence_score NUMERIC(3,2),
    data_sources    TEXT[],
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bid_decisions_county   ON bid_decisions (county_slug);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_parcel   ON bid_decisions (parcel_id);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_grade    ON bid_decisions (deal_grade);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_ml_score ON bid_decisions (ml_score DESC);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_created  ON bid_decisions (created_at DESC);

-- ── fl_counties rows ──────────────────────────────────────────────────────────
INSERT INTO fl_counties (county_name, county_slug, co_no, state)
VALUES
  ('Hillsborough', 'hillsborough', 29, 'FL'),
  ('Collier',      'collier',      21, 'FL'),
  ('Gulf',         'gulf',         23, 'FL'),
  ('DeSoto',       'desoto',       27, 'FL'),
  ('Madison',      'madison',      40, 'FL')
ON CONFLICT (county_slug) DO UPDATE SET
  co_no      = EXCLUDED.co_no,
  updated_at = NOW();

-- ── pipeline.counties rows ────────────────────────────────────────────────────
INSERT INTO pipeline.counties (
  county_slug, display_name, co_no,
  foreclosure_platform, foreclosure_url,
  tax_deed_platform,    tax_deed_url,
  is_active, last_scrape_at
)
VALUES
  -- Hillsborough: RealForeclosure + RealTaxDeed
  ('hillsborough', 'Hillsborough County', 29,
   'realforeclose', 'https://hillsborough.realforeclose.com',
   'realtaxdeed',   'https://hillsborough.realtaxdeed.com',
   true, NULL),

  -- Collier: RealForeclosure + RealTaxDeed
  ('collier', 'Collier County', 21,
   'realforeclose', 'https://collier.realforeclose.com',
   'realtaxdeed',   'https://collier.realtaxdeed.com',
   true, NULL),

  -- Gulf: RealForeclosure + RealTaxDeed
  ('gulf', 'Gulf County', 23,
   'realforeclose', 'https://gulf.realforeclose.com',
   'realtaxdeed',   'https://www.realtaxdeed.com',
   true, NULL),

  -- DeSoto: RealForeclosure + RealTaxDeed
  ('desoto', 'DeSoto County', 27,
   'realforeclose', 'https://desoto.realforeclose.com',
   'realtaxdeed',   'https://desoto.realtaxdeed.com',
   true, NULL),

  -- Madison: RealForeclosure + RealTaxDeed
  ('madison', 'Madison County', 40,
   'realforeclose', 'https://madison.realforeclose.com',
   'realtaxdeed',   'https://madison.realtaxdeed.com',
   true, NULL)
ON CONFLICT (county_slug) DO UPDATE SET
  foreclosure_platform = EXCLUDED.foreclosure_platform,
  foreclosure_url      = EXCLUDED.foreclosure_url,
  tax_deed_platform    = EXCLUDED.tax_deed_platform,
  tax_deed_url         = EXCLUDED.tax_deed_url,
  is_active            = EXCLUDED.is_active,
  updated_at           = NOW();

-- ── Verification ─────────────────────────────────────────────────────────────
SELECT county_slug, display_name, co_no, foreclosure_platform, tax_deed_platform
FROM pipeline.counties
WHERE county_slug IN ('hillsborough', 'collier', 'gulf', 'desoto', 'madison')
ORDER BY county_slug;
