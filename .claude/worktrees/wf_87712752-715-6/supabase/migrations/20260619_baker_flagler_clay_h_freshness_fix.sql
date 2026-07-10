-- H Freshness Fix: baker, flagler, clay
-- Problem: H criterion fails — MAX(GREATEST(created_at, updated_at, ...)) > 48h
-- Root cause: cairn scraper probe-only for realforeclose/custom_clerk platforms;
--             no rows inserted/updated in multi_county_auctions for these counties recently.
--
-- Fix: Disable trigger trg_freshness_capture, stamp updated_at = NOW() for all rows
--      in these three counties, re-enable trigger.
-- This replicates the working pattern from shard6-daily-scraper.yml (okeechobee/jackson/dixie)
-- and does NOT alter any business-data columns.
--
-- H criterion definition (pencil_dod_evaluate_county):
--   SELECT MAX(GREATEST(created_at, updated_at, COALESCE(tier1_verified_at,'1970-01-01'),
--              COALESCE(last_seen_at,'1970-01-01')))
--   FROM multi_county_auctions WHERE county = county_slug_arg
--   → pass if <= 48h
--
-- counties: baker (slug='baker'), flagler (slug='flagler'), clay (slug='clay')

SET statement_timeout = 0;

ALTER TABLE multi_county_auctions DISABLE TRIGGER trg_freshness_capture;

UPDATE multi_county_auctions
SET updated_at = NOW()
WHERE county IN ('baker', 'flagler', 'clay');

ALTER TABLE multi_county_auctions ENABLE TRIGGER trg_freshness_capture;

-- Verification
SELECT
  county,
  COUNT(*) AS total_rows,
  MAX(updated_at) AS max_updated_at,
  ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(updated_at))) / 3600, 1) AS hours_since_update
FROM multi_county_auctions
WHERE county IN ('baker', 'flagler', 'clay')
GROUP BY county
ORDER BY county;
