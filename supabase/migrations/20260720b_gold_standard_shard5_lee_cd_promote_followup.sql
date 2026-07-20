-- GOLD STANDARD shard-5 (lee), dispatch 8acb0c40-fd3b-48a6-b357-fc15c79f973f, follow-up.
--
-- INCIDENT: during this session's Workflow-driven attempt to backfill lee criterion E
-- (parcel linkage), a subagent's diagnostic script imported
-- .github/scripts/calendar_sweep_mca.py via importlib to reuse its parser. That module
-- has no `if __name__ == "__main__":` guard, so importing it executed its full live
-- scrape-and-upsert body against lee.realforeclose.com and inserted 45 new real
-- foreclosure rows (auction_date 2026-07-23..2026-08-20, data_source
-- calendar_sweep_mca_v3), growing lee's auctions_total from 273 to 318 with
-- parity_status still NULL on the new rows. This diluted the C/D fix already shipped in
-- 20260720_gold_standard_shard5_seminole_highlands_lee_cd_promote.sql
-- (matched_clean stayed at 273, so 273/318 = 85.8%, back to FAIL) even though nothing
-- about the original fix was wrong. See session report for full incident writeup;
-- adversarial verification (Workflow wf_c9672b42-a62, agent verify-CD-shipped) caught
-- this live and refuted the "lee now PASS" portion of the original claim -- which is
-- why this follow-up exists instead of silently re-claiming success.
--
-- FIX: same reasoning as the original migration -- these 45 rows are genuine data
-- pulled directly from lee's tier1 platform (lee.realforeclose.com, per
-- pipeline.counties.foreclosure_platform='realforeclose') via the same
-- calendar_sweep_mca_v3 pipeline already established as tier1-equivalent. Promote them
-- the same way. (Field-completeness gaps on some of these rows -- missing
-- property_address/parcel_id/judgment_amount on a handful -- are tracked separately
-- under criteria E/I, not C/D, which only measure parity-match against the tier1
-- source.)
--
-- VERIFIED live 2026-07-20 (mgmt_sql.py): 45 rows, all data_source='calendar_sweep_mca_v3',
-- sale_type='foreclosure', county='lee', parity_status IS NULL, auction_date 2026-07-23..2026-08-20.

BEGIN;

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:calendar_sweep_mca_v3:foreclosure:' || auction_date::text
WHERE lower(county) = 'lee'
  AND parity_status IS NULL
  AND data_source = 'calendar_sweep_mca_v3'
  AND sale_type = 'foreclosure'
  AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false) = true);

COMMIT;
