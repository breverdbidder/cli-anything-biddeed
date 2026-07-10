-- SHARD-11 (dispatch dd396ee4-e383-45ea-8953-5ad92fb1c1af), county=hendry
-- PURGE two fabricated foreclosure placeholder rows: HENDRY-FC-2026-001, HENDRY-FC-2026-002
--
-- Evidence these are NOT real cases (BLANK > WRONG, precedent: hardee ghost-success
-- purge in commit 397c3393):
--   1. Case number format "HENDRY-FC-2026-NNN" does not match real FL 20th Judicial
--      Circuit case number convention (should resemble "26-CA-000123"). Zero web
--      search hits for the exact string "HENDRY-FC-2026-001/002" anywhere.
--   2. Both rows already carry parity_scope annotations from TWO prior sessions that
--      independently caught and reverted fabricated litmus attempts on these exact
--      rows:
--        - "reverted_shard11_run3534_hendry_placeholder_not_independent"
--        - "reverted_shard14_false_litmus_calendar_sweep_placeholder_not_independent"
--      (see scripts/shard14_run2753c_hendry_cd_revert.py, commit 203b7fe0)
--   3. county_auction_config confirms hendry foreclosures are fc_method='in_person'
--      with fc_url=NULL -- there is no online RealForeclose/RealAuction calendar to
--      litmus-match a foreclosure case against for this county.
--   4. Zero rows in foreclosure_outcomes or tax_deed_outcomes for county='hendry'
--      anywhere in the DB -- no independent verification of the $58,000 sold_amount
--      on HENDRY-FC-2026-001 exists.
--   5. Both rows share the exact same placeholder lat/long (26.7298,-81.0352 --
--      LaBelle town centroid) as all 19 hendry rows, and identical batch
--      created_at/updated_at = 2026-06-25T08:16:10 (single synthetic insert, not an
--      independently-scraped record).
--   6. bid_decisions rows for these case numbers exist with round/synthetic-looking
--      derived values (arv_source='assessed_value_factor', pipeline_version=
--      'shard3-j-generator-v1') -- internally generated, not sourced from a real
--      clerk record.
--
-- Effect: auctions_total 19->17, closed_sold 1->0 for hendry. This DROPS B's
-- denominator to 0 (pass becomes vacuously true/NULL per evaluator's NULLIF guard --
-- see verification below) and removes the two card_complete-eligible rows that could
-- never be genuinely completed (no independent parcel/zoning source either, since
-- 100/200 S Main St LaBelle also had no confirmed real parcel_id mapping beyond the
-- coincidental section-28-43-A0 lookup shared with unrelated real Montura Ranches
-- parcels).
--
-- Also removes the two orphaned bid_decisions rows (ids 17525, 17526) referencing
-- these case numbers, since J (deal_complete) must reflect real, resolvable auctions
-- only.

SET statement_timeout = 0;

BEGIN;

DELETE FROM public.bid_decisions
WHERE case_number IN ('HENDRY-FC-2026-001', 'HENDRY-FC-2026-002');

DELETE FROM public.multi_county_auctions
WHERE lower(county) = 'hendry'
  AND case_number IN ('HENDRY-FC-2026-001', 'HENDRY-FC-2026-002');

COMMIT;
