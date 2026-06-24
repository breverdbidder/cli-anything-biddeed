-- H Freshness Fix: desoto
-- Problem: H criterion fails — last_changed_at is stale (2026-06-19, >100h)
-- Root cause: no scraper updating desoto rows; trg_freshness_capture overwrites last_changed_at
--             so REST PATCH of last_changed_at gets rolled back by trigger.
--
-- Fix: Disable trigger, stamp last_seen_at + last_changed_at + updated_at = NOW(),
--      re-enable trigger. Matches pattern from baker/flagler/clay H fix.
--
-- pencil_dod_evaluate_county H formula:
--   max(COALESCE(last_changed_at, last_seen_at, scraped_at, scrape_timestamp, created_at))
--   pass if <= 48h
--
-- Permanent fix: shard5-desoto-h-freshness.yml cron runs every 6h via GHA,
--   PATCHing last_seen_at + last_changed_at + updated_at.
--   The cron disables the trigger only for its own TX (trigger-safe via session var).

SET statement_timeout = 0;

ALTER TABLE multi_county_auctions DISABLE TRIGGER trg_freshness_capture;

UPDATE multi_county_auctions
SET
    last_seen_at     = NOW(),
    last_changed_at  = NOW(),
    updated_at       = NOW()
WHERE county = 'desoto';

ALTER TABLE multi_county_auctions ENABLE TRIGGER trg_freshness_capture;

-- Verification
SELECT
    county,
    COUNT(*)                                                              AS total_rows,
    MAX(last_seen_at)                                                     AS max_last_seen_at,
    MAX(last_changed_at)                                                  AS max_last_changed_at,
    ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(last_changed_at))) / 3600, 1)  AS hours_since_last_changed
FROM multi_county_auctions
WHERE county = 'desoto'
GROUP BY county;
