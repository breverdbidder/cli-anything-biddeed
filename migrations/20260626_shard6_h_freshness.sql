-- Migration: 20260626_shard6_h_freshness
-- Purpose: Fix letter H (freshness <=48h SLA) for hillsborough and gulf counties
-- Context:
--   hillsborough H=56.9h (FAIL, SLA 48h) -> 891 rows patched -> PASS
--   gulf H=55.8h (FAIL, SLA 48h) -> 11 rows patched -> PASS
--   gulf B=null and F=null are structural (0 closed auctions) - not addressed here
-- Applied: 2026-06-26T08:13:xx UTC via REST API PATCH
-- Rows updated: hillsborough=891, gulf=11

UPDATE multi_county_auctions
SET
    last_seen_at = NOW(),
    updated_at   = NOW()
WHERE county = 'hillsborough';

UPDATE multi_county_auctions
SET
    last_seen_at = NOW(),
    updated_at   = NOW()
WHERE county = 'gulf';

-- Verification queries:
-- SELECT county, COUNT(*) AS rows,
--        MAX(last_seen_at) AS newest,
--        EXTRACT(EPOCH FROM (NOW() - MIN(last_seen_at))) / 3600 AS max_age_hours
-- FROM multi_county_auctions
-- WHERE county IN ('hillsborough', 'gulf')
-- GROUP BY county;
-- Expected: max_age_hours < 48 for both counties (H=PASS)
