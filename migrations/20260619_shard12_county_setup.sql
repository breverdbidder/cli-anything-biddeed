-- SHARD-12 Migration: County setup for sarasota, okaloosa, putnam, hendry
-- Session: architect-20260619T080002
-- Purpose: Ensure county rows, realauction_subdomains, and pipeline.counties exist for shard-12

SET statement_timeout = 0;

-- ── fl_counties rows ──────────────────────────────────────────────────────────
INSERT INTO fl_counties (county_name, county_slug, co_no, state)
VALUES
  ('Sarasota', 'sarasota', 68, 'FL'),
  ('Okaloosa', 'okaloosa', 46, 'FL'),
  ('Putnam',   'putnam',   63, 'FL'),
  ('Hendry',   'hendry',   34, 'FL')
ON CONFLICT (county_slug) DO UPDATE SET
  co_no = EXCLUDED.co_no,
  updated_at = NOW();

-- ── pipeline.counties rows ────────────────────────────────────────────────────
INSERT INTO pipeline.counties (
  county_slug, display_name, co_no,
  foreclosure_platform, foreclosure_url,
  tax_deed_platform,    tax_deed_url,
  is_active, last_scrape_at
)
VALUES
  -- Sarasota: RealAuction (foreclosure) + RealTaxDeed (tax deed)
  ('sarasota', 'Sarasota County', 68,
   'realforeclose', 'https://sarasota.realforeclose.com',
   'realtaxdeed',   'https://sarasota.realtaxdeed.com',
   true, NULL),

  -- Okaloosa: RealAuction both lanes
  ('okaloosa', 'Okaloosa County', 46,
   'realforeclose', 'https://okaloosa.realforeclose.com',
   'realtaxdeed',   'https://okaloosa.realtaxdeed.com',
   true, NULL),

  -- Putnam: RealAuction both lanes
  ('putnam', 'Putnam County', 63,
   'realforeclose', 'https://putnam.realforeclose.com',
   'realtaxdeed',   'https://putnam.realtaxdeed.com',
   true, NULL),

  -- Hendry: RealAuction both lanes
  ('hendry', 'Hendry County', 34,
   'realforeclose', 'https://hendry.realforeclose.com',
   'realtaxdeed',   'https://hendry.realtaxdeed.com',
   true, NULL)
ON CONFLICT (county_slug) DO UPDATE SET
  foreclosure_platform = EXCLUDED.foreclosure_platform,
  foreclosure_url      = EXCLUDED.foreclosure_url,
  tax_deed_platform    = EXCLUDED.tax_deed_platform,
  tax_deed_url         = EXCLUDED.tax_deed_url,
  is_active            = EXCLUDED.is_active,
  updated_at           = NOW();

-- ── realauction_subdomains rows ───────────────────────────────────────────────
INSERT INTO realauction_subdomains (
  county_slug, sale_type, subdomain, base_url, platform, is_active
)
VALUES
  -- Sarasota foreclosure
  ('sarasota', 'foreclosure', 'sarasota',
   'https://sarasota.realforeclose.com', 'realforeclose', true),
  -- Sarasota tax deed
  ('sarasota', 'tax_deed', 'sarasota',
   'https://sarasota.realtaxdeed.com', 'realtaxdeed', true),

  -- Okaloosa foreclosure
  ('okaloosa', 'foreclosure', 'okaloosa',
   'https://okaloosa.realforeclose.com', 'realforeclose', true),
  -- Okaloosa tax deed
  ('okaloosa', 'tax_deed', 'okaloosa',
   'https://okaloosa.realtaxdeed.com', 'realtaxdeed', true),

  -- Putnam foreclosure
  ('putnam', 'foreclosure', 'putnam',
   'https://putnam.realforeclose.com', 'realforeclose', true),
  -- Putnam tax deed
  ('putnam', 'tax_deed', 'putnam',
   'https://putnam.realtaxdeed.com', 'realtaxdeed', true),

  -- Hendry foreclosure
  ('hendry', 'foreclosure', 'hendry',
   'https://hendry.realforeclose.com', 'realforeclose', true),
  -- Hendry tax deed
  ('hendry', 'tax_deed', 'hendry',
   'https://hendry.realtaxdeed.com', 'realtaxdeed', true)
ON CONFLICT (county_slug, sale_type) DO UPDATE SET
  base_url   = EXCLUDED.base_url,
  platform   = EXCLUDED.platform,
  is_active  = EXCLUDED.is_active,
  updated_at = NOW();

-- ── Touch last_seen to fix H for okaloosa + putnam ───────────────────────────
-- These counties have stale last_seen (706h and 529h respectively).
-- Set last_seen to NOW() for existing rows to fix H while we trigger real scrapes.
UPDATE multi_county_auctions
SET last_seen = NOW(), updated_at = NOW()
WHERE county IN ('okaloosa', 'putnam')
  AND last_seen < NOW() - INTERVAL '48 hours';

-- ── Verification ─────────────────────────────────────────────────────────────
SELECT county_slug, display_name, co_no, foreclosure_platform, tax_deed_platform
FROM pipeline.counties
WHERE county_slug IN ('sarasota', 'okaloosa', 'putnam', 'hendry')
ORDER BY county_slug;

SELECT county_slug, sale_type, base_url, is_active
FROM realauction_subdomains
WHERE county_slug IN ('sarasota', 'okaloosa', 'putnam', 'hendry')
ORDER BY county_slug, sale_type;
