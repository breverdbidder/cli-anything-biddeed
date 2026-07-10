-- SHARD-7: marion SYN- fabricated parcel_id cleanup
-- dispatch_id: b890c19b-cabd-46fe-9331-43e121db40f3
-- Session: architect-20260702T000000
--
-- ROOT CAUSE (VERIFIED live 2026-07-02): a prior ULTRALOOP adversarial audit
-- (gold_standard_ultraloop_audit, created_at 2026-07-02T09:43:18Z) refuted
-- marion criterion C 2-of-3 votes on grounds of undisclosed double-counting:
-- 5 case_numbers in the 312-row non-propertyonion denominator each had 2
-- rows. Investigating those 5 pairs directly turned up something worse than
-- duplicate ingestion: 3 of the 5 "duplicate" rows (id e8701cf2, b9b1a713,
-- 596df213 -- data_source='realauction') carried parcel_id values
-- 'SYN-MAR-FC-001'/'003'/'004' and property_address literally
-- 'Marion County, FL (address pending)' -- placeholder/synthetic values,
-- not real scraped data -- while parity_status was fraudulently stamped
-- 'matched_clean'. Each had a genuine duplicate row from data_source=
-- 'realforeclose' with a real numeric parcel_id and a real street address
-- for the SAME case_number. A 4th row (id 9d4c9475, case
-- 422024CA001846CAAXMX) carried parcel_id='SYN-MAR-FC-002' with NO real
-- counterpart row at all -- a standalone fabricated parcel linkage on an
-- otherwise real auction listing (real address, real case, real judgment
-- amount from realauction's own scrape).
--
-- This directly violates the standing HONESTY PROTOCOL / HARD GUARDRAILS:
-- "NEVER invent numbers", fabricated matched_clean status inflated
-- marion's C/D/E/I numerators (and denominator, for the 3 duplicate rows)
-- with data that was never independently verified.
--
-- SCOPE NOTE: a broader sweep (parcel_id ILIKE 'SYN-%') found 118 such rows
-- across 10 counties total (marion=4, brevard=94, alachua=5, seminole=5,
-- glades=2, hardee=2, lafayette=2, okaloosa=2, franklin=1, monroe=1).
-- orange and levy (this shard's other two counties) are clean -- verified
-- zero SYN- rows in both. The other 7 counties are OUT OF SHARD-7 SCOPE
-- (owned by other parallel shards per PARALLEL-FLEET RULES) and are
-- deliberately NOT touched here; flagged in the session close-out report
-- for the owning shards / AI Architect to action, especially brevard (94
-- rows -- material risk to brevard's B/C/D/E/I certification validity).
--
-- FIX:
--   1. DELETE the 3 rows that are pure duplicates of a real realforeclose
--      row for the same case_number AND carry a fabricated parcel_id.
--   2. NULL parcel_id + parity_status on the 1 standalone fabricated row
--      (does not delete the row -- the underlying auction listing itself
--      is real; only the parcel linkage was synthetic. Deleting would lose
--      a real auction record; nulling correctly demotes it to
--      "not yet parcel-linked" for E purposes).
--
-- Applied live 2026-07-02T10:5x UTC via PostgREST (service role) --
-- this migration documents and reproduces that change.
--
-- VERIFIED live via pencil_dod_evaluate_county before/after:
--   auctions_total 312 -> 309
--   C 98.1 -> 97.7   D 98.4 -> 98.1   E 99.7 -> 99.4   I 98.1 -> 97.7
--   (all still >= 95% threshold; marion remains 10/10 PASS on all letters,
--    now on honest data instead of fabricated matched_clean rows)
--   A/B/F/G/J unaffected (confirmed no regression).
--
-- Two further duplicate case_number pairs were found in the same 312-row
-- set (422023CA002680CAAXXX, 422024CA002455CAAXMX) where BOTH rows carry
-- real (non-SYN) parcel_ids but different auction_date values (2026-06-08
-- vs 2025-11-26; 2026-06-02 vs 2026-04-09). Unlike the 3 same-date SYN
-- pairs above, this is ambiguous -- could be legitimate reschedule/relist
-- history (a case continued to a later docket keeps its case_number) or
-- could be a second duplicate-ingestion bug. NOT resolved in this
-- migration per BLANK > WRONG -- flagged for the next marion session to
-- investigate with the county clerk docket before deleting real data.

DELETE FROM multi_county_auctions
WHERE id IN (
  'e8701cf2-a61e-4cc8-8f82-104965b29129',  -- SYN-MAR-FC-004, dup of case 422025CA000637CAAXMX
  'b9b1a713-12e4-4dae-937c-461e2085da45',  -- SYN-MAR-FC-001, dup of case 422025CA000706CAAXMX
  '596df213-0c3c-4758-9c62-97a3065902cb'   -- SYN-MAR-FC-003, dup of case 422025CA000765CAAXMX
);

UPDATE multi_county_auctions
SET parcel_id = NULL, parity_status = NULL
WHERE id = '9d4c9475-6d5f-4026-b962-98f33915906a';  -- SYN-MAR-FC-002, case 422024CA001846CAAXMX, no real counterpart
