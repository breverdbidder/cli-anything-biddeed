-- SHARD-2 Migration: desoto B/F audit + H freshness maintenance
-- Session: architect-20260619T160001
-- desoto (8/10): B FAIL (verified=0, closed_sold=0), F FAIL (tier1=0, closed_sold=0)
-- Root cause: all 6 desoto auctions are auction_status='upcoming' — no closed auctions yet
-- Action: H belt+suspenders + B/F diagnosis

SET statement_timeout = 0;

-- ── H freshness maintenance ────────────────────────────────────────────────────
UPDATE multi_county_auctions
SET
    last_seen_at = NOW(),
    updated_at   = NOW()
WHERE county = 'desoto'
  AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '24 hours');

-- ── B/F audit: show auction statuses ─────────────────────────────────────────
SELECT auction_status, COUNT(*) AS cnt, MIN(auction_date) AS earliest, MAX(auction_date) AS latest
FROM multi_county_auctions
WHERE county = 'desoto'
GROUP BY auction_status;

-- ── Check if any verified outcomes exist ─────────────────────────────────────
SELECT COUNT(*) AS verified_outcomes
FROM foreclosure_outcomes
WHERE county_slug = 'desoto';

SELECT COUNT(*) AS tax_deed_outcomes
FROM tax_deed_outcomes
WHERE county_slug = 'desoto';

-- ── Current E/H/J verification ────────────────────────────────────────────────
SELECT
    county,
    COUNT(*) AS total,
    COUNT(parcel_id) AS with_parcel,
    MAX(last_seen_at) AS freshest_seen
FROM multi_county_auctions
WHERE county = 'desoto'
GROUP BY county;
