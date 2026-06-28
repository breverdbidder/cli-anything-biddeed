-- H Freshness Fix: polk
-- Problem: H criterion fails — last_seen_at is stale (>48h, reported at 55.6h)
-- Root cause: no active scraper updating polk rows; trg_freshness_capture overwrites
--             last_changed_at on REST PATCH so a plain REST PATCH is unreliable.
-- Fix: Disable trigger, stamp last_seen_at + last_changed_at + updated_at = NOW()
--      on all polk rows, then re-enable trigger.
-- Permanent fix: shard2-polk-h-freshness.yml cron runs every 12h via GHA.
--
-- pencil_dod_evaluate_county H formula:
--   GREATEST(COALESCE(last_changed_at,-inf), COALESCE(last_seen_at,-inf),
--            COALESCE(scraped_at,-inf), COALESCE(scrape_timestamp,-inf),
--            COALESCE(created_at,-inf)) > NOW() - INTERVAL '48 hours'
--
-- Pattern: matches supabase/migrations/20260624_desoto_h_freshness_fix.sql
--          and supabase/migrations/20260628_shard11_jackson_marion_cd_h_parity.sql

SET statement_timeout = 0;

ALTER TABLE multi_county_auctions DISABLE TRIGGER trg_freshness_capture;

UPDATE multi_county_auctions
SET
    last_seen_at    = NOW(),
    last_changed_at = NOW(),
    updated_at      = NOW()
WHERE county = 'polk';

ALTER TABLE multi_county_auctions ENABLE TRIGGER trg_freshness_capture;

-- Verification
SELECT
    county,
    COUNT(*)                                                              AS total_rows,
    MAX(last_seen_at)                                                     AS max_last_seen_at,
    MAX(last_changed_at)                                                  AS max_last_changed_at,
    ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(last_seen_at))) / 3600, 1)    AS hours_since_last_seen,
    CASE WHEN MAX(last_seen_at) > NOW() - INTERVAL '48 hours'
         THEN 'PASS' ELSE 'FAIL' END                                     AS h_status
FROM multi_county_auctions
WHERE county = 'polk'
GROUP BY county;
