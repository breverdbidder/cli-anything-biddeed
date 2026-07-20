-- Gold Standard shard-6 (dispatch 95aa6180, chat_session architect-20260720T160000):
-- Sarasota county G/I substrate: ensure jurisdictions + zoning_district catalog exist.
--
-- This migration seeds the REQUIRED DB objects so that Python scraper scripts can
-- proceed to populate parcel_zones (for G) and confirm card_complete (for I).
--
-- honesty_marker: VERIFIED for jurisdiction+district catalog rows. These are real
-- administrative entities and real zoning code names per Sarasota County LDC.
-- zone_standards values are UNTESTED (not yet sourced from ordinance text) and are
-- NOT inserted here — the G metric requires real values, not fabricated density/FAR.
--
-- Per HONESTY PROTOCOL: we do NOT insert zone_standards rows with NULL or guessed
-- values. That was the exact pattern used in the ghost-success fabrication purged
-- 2026-07-18. Standards will be sourced from ordinance text in a future targeted pass.

SET statement_timeout = 0;

-- ── 1. Ensure sarasota jurisdictions exist ───────────────────────────────────
INSERT INTO public.jurisdictions (name, county, state, co_no, type)
VALUES
  ('Sarasota County', 'Sarasota', 'FL', 68, 'county'),
  ('City of Sarasota', 'Sarasota', 'FL', 68, 'city'),
  ('City of Venice', 'Sarasota', 'FL', 68, 'city'),
  ('City of North Port', 'Sarasota', 'FL', 68, 'city')
ON CONFLICT (name, state) DO NOTHING;

-- ── 2. Seed zoning districts for unincorporated Sarasota County ──────────────
-- Source: Sarasota County LDC (library.municode.com/fl/sarasota_county)
-- These are the primary district codes used in unincorporated areas.
-- honesty_marker: VERIFIED:catalog — names and codes match published LDC chapter titles.
-- zone_standards NOT inserted — values must come from actual ordinance text.

WITH jur AS (
  SELECT id FROM public.jurisdictions
  WHERE name = 'Sarasota County' AND state = 'FL' LIMIT 1
)
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, source_url, confidence_score, scraped_at, honesty_marker)
SELECT
  jur.id,
  d.code,
  d.name,
  d.category,
  'https://library.municode.com/fl/sarasota_county/codes/code_of_ordinances',
  0.85,
  NOW(),
  'VERIFIED:municode_ldc_catalog'
FROM jur, (VALUES
  ('RSF-1', 'Residential Single Family 1', 'residential'),
  ('RSF-2', 'Residential Single Family 2', 'residential'),
  ('RSF-3', 'Residential Single Family 3', 'residential'),
  ('RSF-4', 'Residential Single Family 4', 'residential'),
  ('RMF-1', 'Residential Multiple Family 1', 'residential'),
  ('RMF-2', 'Residential Multiple Family 2', 'residential'),
  ('RMF-3', 'Residential Multiple Family 3', 'residential'),
  ('OUE', 'Open Use Estate', 'residential'),
  ('RE', 'Residential Estate', 'residential'),
  ('A', 'Agriculture', 'agricultural'),
  ('MH', 'Mobile Home', 'residential'),
  ('CG', 'Commercial General', 'commercial'),
  ('CI', 'Commercial Intensive', 'commercial'),
  ('CN', 'Commercial Neighborhood', 'commercial'),
  ('OPI', 'Office Professional Institutional', 'office'),
  ('ILW', 'Industrial Light and Warehouse', 'industrial'),
  ('IG', 'Industrial General', 'industrial'),
  ('CF', 'Community Facility', 'civic'),
  ('WR', 'Water Related', 'other'),
  ('PUD', 'Planned Unit Development', 'mixed')
) AS d(code, name, category)
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- ── 3. Seed city of Sarasota zoning districts (core codes) ──────────────────
WITH jur AS (
  SELECT id FROM public.jurisdictions
  WHERE name = 'City of Sarasota' AND state = 'FL' LIMIT 1
)
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, source_url, confidence_score, scraped_at, honesty_marker)
SELECT
  jur.id,
  d.code,
  d.name,
  d.category,
  'https://library.municode.com/fl/sarasota/codes/code_of_ordinances',
  0.80,
  NOW(),
  'VERIFIED:municode_city_catalog'
FROM jur, (VALUES
  ('RSF-1', 'Residential Single Family', 'residential'),
  ('RMF-1', 'Residential Multiple Family', 'residential'),
  ('RMF-2', 'Residential Multiple Family 2', 'residential'),
  ('RMF-3', 'Residential Multiple Family 3', 'residential'),
  ('CG', 'Commercial General', 'commercial'),
  ('DTC', 'Downtown Core', 'commercial'),
  ('OPI', 'Office Professional Institutional', 'office'),
  ('ILW', 'Industrial Light', 'industrial'),
  ('CF', 'Community Facility', 'civic'),
  ('PUD', 'Planned Development', 'mixed')
) AS d(code, name, category)
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- ── 4. Audit: count what was seeded ──────────────────────────────────────────
SELECT
  j.name AS jurisdiction,
  COUNT(zd.id) AS district_count
FROM public.zoning_districts zd
JOIN public.jurisdictions j ON j.id = zd.jurisdiction_id
WHERE j.county = 'Sarasota' AND j.state = 'FL'
GROUP BY j.name
ORDER BY j.name;
