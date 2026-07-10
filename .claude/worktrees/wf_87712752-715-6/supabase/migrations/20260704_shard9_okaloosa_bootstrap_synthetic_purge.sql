-- SHARD-9 (st_johns/okaloosa/monroe/hernando/madison): okaloosa ghost-success purge
-- dispatch_id: 738fd0f7-3f69-4f68-9d56-7e8e397ee602
-- Session: architect-20260704T080000

-- HEADLINE FINDING: okaloosa's C/D=0.0% (matched_clean=0 of 5) was masking a worse underlying
-- problem -- 3 of okaloosa's 5 multi_county_auctions rows are entirely fabricated fixture
-- data, of the same "ghost-success" class already caught and reverted this campaign for
-- osceola, monroe, madison, calhoun, sumter, highlands, charlotte, lake.
--
-- VERIFIED live 2026-07-04 (Management API SQL exec, direct psql pooler auth fails in this
-- sandbox -- same documented constraint as every prior shard session):
--
-- 1. Rows OKALOOSA-FC-PAST-001, OKALOOSA-FC-PAST-002, OKALOOSA-TD-PAST-001 share the
--    IDENTICAL created_at microsecond timestamp 2026-06-26 08:38:22.248386+00 (a single
--    batch insert, not three independently-scraped auctions).
-- 2. case_number values ('OKALOOSA-FC-PAST-001' etc) and parcel_id values ('OKA-FO-0001',
--    'OKA-FO-0002', 'OKA-TA-0001') are synthetic fixture-naming conventions -- not real
--    Okaloosa Clerk case numbers or Okaloosa Property Appraiser parcel IDs.
-- 3. The two FC rows share the EXACT SAME latitude/longitude (30.4059/-86.6098) despite
--    having different street addresses -- a single static placeholder coordinate copy-pasted
--    across "different" properties, not real per-parcel geocoding.
-- 4. data_source is NULL and plaintiff/winning_bidder are NULL on all 3 rows, yet sold_amount
--    is populated (142000.0 / 187500.0 / 74000.0) with zero backing in tax_deed_outcomes or
--    foreclosure_outcomes (both tables have 0 real okaloosa rows -- confirmed via direct
--    query). This synthetic sold_amount is the entire fabricated backing for okaloosa's
--    B=100% (verified=3 closed_sold=3) and F=100% (tier1_sold=3 closed_sold=3) claims in the
--    dispatch brief -- both fabricated, same as the osceola precedent.
-- 5. The 2 genuinely-scraped rows (2024-CA-000470 foreclosure, 2024-TDD-000089 tax deed,
--    provenance='primary_scrape') are both auction_status='upcoming' with sold_amount IS
--    NULL -- i.e. okaloosa has ZERO real closed sales with verifiable outcomes yet. B and F
--    are correctly UNDEFINED (no closed_sold denominator), not 100%.
--
-- NOT touched: the 2 real primary_scrape rows are left exactly as-is. County_auction_config
-- for okaloosa (fc_method=in_person, td_method=null, daily_scrape_enabled=false) is a
-- separate, already-honest finding documented in the session report -- not fabricated, just
-- unconfigured for ongoing ingestion. Not modified here.
--
-- ACTION: delete the 3 fully-fabricated bootstrap_synthetic rows. This corrects:
--   A: fc=3->1, td=2->1 (LEAST stays >=1, A remains PASS -- both lanes still represented by
--      real rows)
--   B: 100.0 (fabricated) -> null/undefined (0 real closed sales) -- HONEST regression
--   C/D: 0.0 of 5 (partly explained by fake rows that could never match) -> null/undefined of
--      2 (both remaining rows are upcoming/unsold, correctly un-matchable yet, same
--      structural-ceiling pattern as monroe's 22 upcoming tax-deed rows)
--   F: 100.0 (fabricated) -> null/undefined -- HONEST regression
--   I: expected to drop from 100% (5 of 5) since the 3 deleted rows carried the fabricated
--      lat/long/value fields that satisfied the card-complete gate; real card completeness
--      for the 2 remaining rows depends on the actual okaloosa zoning parcel join.
--
-- This is a scoreboard REGRESSION on B/C/D/F/I for okaloosa. It is the correct action per the
-- HONESTY PROTOCOL and the fleet's own established ghost-success-revert precedent: an
-- anomalous PASS built on fabricated data is not a PASS.

BEGIN;

DELETE FROM multi_county_auctions
WHERE lower(county) = 'okaloosa'
  AND provenance = 'bootstrap_synthetic'
  AND case_number IN ('OKALOOSA-FC-PAST-001', 'OKALOOSA-FC-PAST-002', 'OKALOOSA-TD-PAST-001');

COMMIT;
