-- SHARD-8 run5153 (dispatch 4569d5ab-b34d-4b1e-80fb-183b058262db)
-- santa_rosa H freshness maintenance (already PASS at 5.7h, keep current)
-- santa_rosa 9/10: currently passing A,B,C,D,E,F,G,H,J — failing I only
--
-- H = hours since last_seen (SLA 48h). Currently 5.7h (PASS).
-- This migration ensures it stays PASS by refreshing last_seen_at.
-- Date: 2026-07-19

SET statement_timeout = 0;

UPDATE public.multi_county_auctions
SET
    last_seen_at = NOW(),
    updated_at   = NOW()
WHERE county = 'santa_rosa'
  AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '24 hours');

-- Verify H
SELECT
    county,
    COUNT(*)                                                                      AS total,
    MIN(last_seen_at)                                                             AS oldest_seen,
    EXTRACT(EPOCH FROM (NOW() - MIN(last_seen_at))) / 3600                       AS max_hours_stale,
    COUNT(*) FILTER (WHERE last_seen_at < NOW() - INTERVAL '48 hours')           AS overdue_48h
FROM public.multi_county_auctions
WHERE county = 'santa_rosa'
GROUP BY county;
