-- Gold Standard shard-9, dispatch f8de10ec-e7af-4ac2-9af7-6b7dd80c3809
-- WORK-PACKAGE 1: okaloosa fabrication guard (I criterion)
--
-- ROOT CAUSE: scripts/shard4_run472_main_executor.py phase_i_property_cards()
-- carries a hardcoded county_median dict with "okaloosa": 310000. It bulk
-- PATCHes multi_county_auctions SET assessed_value=310000,
-- market_value=325500.0 (310000*1.05) on ANY okaloosa row where
-- assessed_value IS NULL. This function is wired to a LIVE daily cron
-- (.github/workflows/gold-standard-shard4-run472.yml, 08:05 UTC daily).
--
-- Same bug pattern already caught + fixed for "bradford" 2026-07-10 (see
-- 20260703_shard13_..._bradford_i_honesty_fix.sql). okaloosa (and
-- clay/nassau/flagler, out of scope for this shard) were never excluded.
--
-- CONFIRMED LIVE (2026-07-24, this session):
--   SELECT count(*) FROM multi_county_auctions
--   WHERE county='okaloosa' AND assessed_value=310000 AND market_value=325500.0;
--   => 19 rows (created 2026-07-05 through 2026-07-23)
--
-- These 19 rows currently also lack geo, so I's card_complete metric is NOT
-- inflated by this fabrication today (63.2%, 36/57 real completes). But the
-- fake financial values would silently ghost-pass I the moment a later
-- work-package adds real geo to these rows, unless purged first.
--
-- FIX: purge the fabricated values back to NULL so any future geo backfill
-- does not accidentally combine with fake financial data to pass card_complete.
-- Code fix (companion, same commit): scripts/shard4_run472_main_executor.py
-- phase_i_property_cards() now skips "okaloosa" the same way it already
-- skips "bradford".

UPDATE multi_county_auctions
SET assessed_value = NULL,
    market_value = NULL
WHERE county = 'okaloosa'
  AND assessed_value = 310000
  AND market_value = 325500.0;

-- Expected: 19 rows affected. Verify via:
--   SELECT count(*) FROM multi_county_auctions
--   WHERE county='okaloosa' AND assessed_value=310000 AND market_value=325500.0;
--   => must be 0 after this migration.
