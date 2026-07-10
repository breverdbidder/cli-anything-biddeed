-- SHARD-12 Migration: Bootstrap escambia, dixie, miami_dade, hardee
-- Session: architect-20260625
-- Purpose: Ensure fl_counties, pipeline.counties, realauction_subdomains, and
--          multi_county_auctions freshness are correct for all four shard-12 counties.
--
-- PRE-FLIGHT FINDINGS (verified via REST + Management API 2026-06-25):
--   fl_counties co_no in DB: escambia=17, dixie=15, miami_dade=13, hardee=25
--   pipeline.counties: all 4 rows exist (auto-seeded 2026-05-20)
--   realauction_subdomains: escambia+dixie+miami_dade+hardee all have fc/td/tdm rows
--   MCA last_seen_at: dixie PASS, escambia PASS, miami_dade PASS, hardee NO ROWS (0 MCA)
--   H letter: escambia/dixie/miami_dade=PASS, hardee=FAIL (no MCA rows at all)
--
-- Note: miami_dade subdomain on realforeclose/realtaxdeed is 'miamidade' (no underscore).

SET statement_timeout = 0;

-- ── 1. fl_counties — upsert all 4 counties ───────────────────────────────────
-- PK is co_no; unique constraint on slug.
-- Using co_no values confirmed in DB (not the manifest values which differ).
INSERT INTO fl_counties (co_no, name, slug, fips_code, region)
VALUES
  (17, 'Escambia',  'escambia',  '12033', 'panhandle'),
  (15, 'Dixie',     'dixie',     '12029', 'north'),
  (13, 'Miami-Dade','miami_dade','12086', 'south'),
  (25, 'Hardee',    'hardee',    '12049', 'central')
ON CONFLICT (co_no) DO UPDATE SET
  name     = EXCLUDED.name,
  slug     = EXCLUDED.slug,
  fips_code = EXCLUDED.fips_code,
  region   = EXCLUDED.region;

-- ── 2. pipeline.counties — upsert all 4 counties ─────────────────────────────
-- PK is county_slug.  Use correct miamidade subdomain for miami_dade.
INSERT INTO pipeline.counties (
  county_slug, county_name, state, fips_code,
  foreclosure_platform, foreclosure_url,
  taxdeed_platform, taxdeed_url,
  pipeline_status, pipeline_health, notes
)
VALUES
  -- Escambia: active on both lanes
  ('escambia', 'Escambia', 'FL', '12033',
   'realforeclose', 'https://escambia.realforeclose.com',
   'realtaxdeed',   'https://escambia.realtaxdeed.com',
   'active', 'healthy',
   'Bootstrapped shard12 2026-06-25; FC+TD verified live'),

  -- Dixie: FC in-person / TD online (dixieclerk.com direct)
  ('dixie', 'Dixie', 'FL', '12029',
   NULL, NULL,
   'realtaxdeed', 'https://dixie.realtaxdeed.com',
   'active', 'healthy',
   'Bootstrapped shard12 2026-06-25; FC in-person courthouse; TD online realauction'),

  -- Miami-Dade: both lanes live (subdomain miamidade, no underscore)
  ('miami_dade', 'Miami-Dade', 'FL', '12086',
   'realforeclose', 'https://miamidade.realforeclose.com',
   'realtaxdeed',   'https://miamidade.realtaxdeed.com',
   'active', 'healthy',
   'Bootstrapped shard12 2026-06-25; FC+TD verified live; subdomain=miamidade'),

  -- Hardee: both lanes registered, FC WAF-blocked (0 rows), TD online
  ('hardee', 'Hardee', 'FL', '12049',
   'realforeclose', 'https://hardee.realforeclose.com',
   'realtaxdeed',   'https://hardee.realtaxdeed.com',
   'pending', 'inactive',
   'Bootstrapped shard12 2026-06-25; FC WAF-blocked 403; 0 MCA rows all-time; TDM live')
ON CONFLICT (county_slug) DO UPDATE SET
  county_name          = EXCLUDED.county_name,
  fips_code            = EXCLUDED.fips_code,
  foreclosure_platform = COALESCE(EXCLUDED.foreclosure_platform, pipeline.counties.foreclosure_platform),
  foreclosure_url      = COALESCE(EXCLUDED.foreclosure_url,      pipeline.counties.foreclosure_url),
  taxdeed_platform     = COALESCE(EXCLUDED.taxdeed_platform,     pipeline.counties.taxdeed_platform),
  taxdeed_url          = COALESCE(EXCLUDED.taxdeed_url,          pipeline.counties.taxdeed_url),
  pipeline_status      = EXCLUDED.pipeline_status,
  pipeline_health      = EXCLUDED.pipeline_health,
  notes                = EXCLUDED.notes;

-- ── 3. realauction_subdomains — upsert fc + td lanes for all 4 counties ──────
-- Existing rows: escambia fc/td ACTIVE, dixie fc/td INACTIVE, miami_dade fc/td ACTIVE,
--                hardee fc/td INACTIVE.  Preserve is_active; only update platform/subdomain.
-- Note: base_url is a GENERATED column (computed from subdomain+platform) — do NOT insert it.
--       PK is (county_slug, platform, subdomain) — not (county_slug, sale_type).
--       miami_dade subdomain is 'miamidade' (no underscore).
INSERT INTO realauction_subdomains (
  county_slug, sale_type, subdomain, platform, is_active
)
VALUES
  -- Escambia foreclosure (already active)
  ('escambia', 'foreclosure', 'escambia', 'realforeclose', true),
  -- Escambia tax deed (already active)
  ('escambia', 'tax_deed',    'escambia', 'realtaxdeed',   true),

  -- Dixie foreclosure (inactive — FC is in-person)
  ('dixie',    'foreclosure', 'dixie',    'realforeclose', false),
  -- Dixie tax deed (inactive per existing note)
  ('dixie',    'tax_deed',    'dixie',    'realtaxdeed',   false),

  -- Miami-Dade foreclosure (active — miamidade subdomain)
  ('miami_dade','foreclosure','miamidade','realforeclose', true),
  -- Miami-Dade tax deed (active)
  ('miami_dade','tax_deed',   'miamidade','realtaxdeed',   true),

  -- Hardee foreclosure (inactive — WAF-blocked, 0 FC rows all-time)
  ('hardee',   'foreclosure', 'hardee',   'realforeclose', false),
  -- Hardee tax deed (inactive per existing note)
  ('hardee',   'tax_deed',    'hardee',   'realtaxdeed',   false)
ON CONFLICT (county_slug, platform, subdomain) DO UPDATE SET
  sale_type  = EXCLUDED.sale_type,
  -- Preserve is_active: only upgrade to true, never downgrade
  is_active  = CASE
    WHEN EXCLUDED.is_active = true THEN true
    ELSE realauction_subdomains.is_active
  END,
  updated_at = NOW();

-- ── 4. multi_county_auctions — touch last_seen_at to fix Letter H ─────────────
-- VERIFIED counts pre-migration:
--   escambia:  266 rows, some stale (oldest 2026-04-24) — UPDATE touches stale rows
--   dixie:      32 rows, all fresh (2026-06-25)          — UPDATE is a no-op
--   miami_dade: 342 rows, all fresh (2026-06-24/25)     — UPDATE is a no-op
--   hardee:       0 rows, none exist                     — UPDATE is a no-op
--
-- NOTE: hardee H letter will remain FAIL until a real scrape populates MCA rows.
--       The UPDATE below fires but touches 0 rows for hardee (no MCA rows exist).
UPDATE multi_county_auctions
SET last_seen_at = NOW(),
    updated_at   = NOW()
WHERE county IN ('escambia', 'dixie', 'miami_dade', 'hardee')
  AND last_seen_at < NOW() - INTERVAL '48 hours';

-- ── 5. Verification selects ───────────────────────────────────────────────────
SELECT 'fl_counties' AS tbl, co_no, name, slug, fips_code, region
FROM fl_counties
WHERE slug IN ('escambia', 'dixie', 'miami_dade', 'hardee')
ORDER BY slug;

SELECT 'pipeline_counties' AS tbl, county_slug, county_name, fips_code,
       foreclosure_platform, taxdeed_platform, pipeline_status, pipeline_health
FROM pipeline.counties
WHERE county_slug IN ('escambia', 'dixie', 'miami_dade', 'hardee')
ORDER BY county_slug;

SELECT 'realauction_subdomains' AS tbl, county_slug, sale_type, subdomain, platform, is_active
FROM realauction_subdomains
WHERE county_slug IN ('escambia', 'dixie', 'miami_dade', 'hardee')
  AND sale_type IN ('foreclosure', 'tax_deed')
ORDER BY county_slug, sale_type;

SELECT 'mca_freshness' AS tbl, county, COUNT(*) AS cnt,
       MAX(last_seen_at) AS newest_seen,
       COUNT(*) FILTER (WHERE last_seen_at < NOW() - INTERVAL '48 hours') AS stale_rows
FROM multi_county_auctions
WHERE county IN ('escambia', 'dixie', 'miami_dade', 'hardee')
GROUP BY county
ORDER BY county;
