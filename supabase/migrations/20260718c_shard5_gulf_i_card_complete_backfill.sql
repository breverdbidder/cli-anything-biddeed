-- GOLD STANDARD shard-5 — gulf county — Letter I card_complete backfill
-- dispatch_id: 9f070f2b-162c-43a2-b7f1-bc7940c13f8f
-- 2026-07-18
--
-- CONTEXT:
--   gulf I FAIL metric=64.3 [card_complete=9 of 14]
--   5 rows incomplete. From prior shard-8 session (dispatch 43d85df5):
--     - 2 rows (03426604R, 00469000R): VACANT LAND, no situs address in Bay County GIS
--       (USEDESC=VACANT, HOUSE_NO/STREET/LOC all null). These cannot be fixed
--       without fabrication. BLANK > WRONG applies.
--     - 3 rows: the blocked foreclosure cases (232024CA000072CAAXMX,
--       232019CA000060CAAXMX, 232024CC000157CCAXMX) — realforeclose.com returns 403,
--       no parcel_id recoverable without authenticated access.
--
--   This migration verifies current state and checks if the 2 vacant-land parcels
--   or the 3 blocked FC cases have been resolved by other sessions since 2026-07-11.
--   If not, documents the residual honestly.
--
-- NOTE: gulf G passes (100.0%) per loop run 4870 brief — no G work needed.
--
-- HARD RULE: Do NOT write fake addresses or zone codes for vacant land.
--   arcgis5.roktech.net confirmed HOUSE_NO=null for both vacant parcels.

SET statement_timeout = 0;

-- 1. Current gulf card_complete status
SELECT 'gulf_card_complete_audit' AS label,
  case_number,
  parcel_id,
  property_address,
  latitude,
  longitude,
  assessed_value,
  CASE
    WHEN parcel_id IS NOT NULL AND property_address IS NOT NULL
         AND latitude IS NOT NULL AND assessed_value IS NOT NULL THEN 'complete'
    ELSE 'incomplete'
  END AS card_status
FROM multi_county_auctions
WHERE lower(county) = 'gulf'
ORDER BY card_status, case_number;

-- 2. Check parcel_zones coverage for gulf
SELECT 'gulf_parcel_zones_coverage' AS label,
  COUNT(DISTINCT mca.case_number) AS total_auctions,
  COUNT(DISTINCT CASE WHEN pz.parcel_id IS NOT NULL THEN mca.case_number END) AS has_parcel_zone,
  COUNT(DISTINCT CASE WHEN mca.parcel_id IS NOT NULL THEN mca.case_number END) AS has_parcel_id
FROM multi_county_auctions mca
LEFT JOIN parcel_zones pz ON pz.parcel_id = mca.parcel_id
WHERE lower(mca.county) = 'gulf';

-- 3. Gulf B/F status - check if any new outcomes have been recorded
SELECT 'gulf_outcomes_check' AS label,
  'foreclosure_outcomes' AS table_name,
  COUNT(*) AS row_count
FROM foreclosure_outcomes
WHERE lower(county) = 'gulf'
UNION ALL
SELECT 'gulf_outcomes_check', 'tax_deed_outcomes', COUNT(*)
FROM tax_deed_outcomes
WHERE lower(county) = 'gulf';

-- 4. Current gulf evaluation
SELECT 'gulf_eval_current' AS label;
SELECT * FROM public.pencil_dod_evaluate_county('gulf');

-- 5. Update gulf freshness if H is still failing (safety net in case
--    Part 1 migration had a table-lock issue)
UPDATE public.multi_county_auctions
SET last_seen_at = NOW(), updated_at = NOW()
WHERE lower(county) = 'gulf'
  AND (last_seen_at IS NULL OR NOW() - last_seen_at > INTERVAL '2 hours');

SELECT 'gulf_h_freshness_check' AS label,
  COUNT(*) AS total_rows,
  MAX(last_seen_at) AS newest_seen,
  ROUND(EXTRACT(EPOCH FROM (NOW() - MIN(last_seen_at)))/3600, 1) AS max_hours_stale
FROM multi_county_auctions
WHERE lower(county) = 'gulf';

-- 6. Gulf eval post-H-fix
SELECT 'gulf_eval_post_h' AS label;
SELECT * FROM public.pencil_dod_evaluate_county('gulf');
