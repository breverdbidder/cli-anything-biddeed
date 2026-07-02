-- SHARD-7: orange "Property Appraiser" placeholder cleanup + case_number dedup
-- dispatch_id: b890c19b-cabd-46fe-9331-43e121db40f3
-- Session: architect-20260702T000000
--
-- ROOT CAUSE (VERIFIED live 2026-07-02): while re-checking orange after the
-- marion SYN- fabrication fix (20260702_shard7_marion_syn_fabrication_cleanup.sql),
-- swept for other non-numeric parcel_id patterns. Found 15 orange rows with
-- parcel_id LITERALLY equal to the string 'Property Appraiser' -- the label
-- text of a UI link on the RealForeclose result page, not a real parcel
-- number, yet stamped parity_status='matched_clean' (fake linkage, same
-- fabrication pattern as the SYN- rows, different mechanism -- scraper
-- artifact rather than synthetic test data).
--
-- Deeper investigation showed these 15 rows are actually 7 real cases each
-- DUPLICATED under two case_number formats by two separate scraper passes
-- ~20-25 seconds apart (e.g. '2025-CA-003507-O' raw court format vs
-- '48-2024-CA-000579' canonical co_no-prefixed format). Confirmed via: same
-- auction_date for every pair, AND the dollar figure in one row's
-- judgment_amount column exactly equals the paired row's opening_bid column
-- (e.g. 266857.31 in both) -- one scraper run populated judgment_amount,
-- the other populated opening_bid for the identical case, both falling back
-- to the 'Property Appraiser' placeholder because neither successfully
-- resolved a real parcel_id for these condo/timeshare-unit addresses. An
-- 8th row (case 2018-CA-007877-O, 2408 MAYER ST) had no duplicate pair --
-- left as a standalone unresolved case (parcel_id/parity nulled, not
-- deleted).
--
-- FIX:
--   1. Null parcel_id + parity_status on all 15 'Property Appraiser' rows
--      (demotes fake-linked -> honestly not-yet-linked).
--   2. For the 7 confirmed duplicate pairs: merge judgment_amount into the
--      canonical '48-'-prefixed row (which already carried opening_bid for
--      the same case), then delete the raw-court-format duplicate row.
--      No data lost -- both columns now populated on the single surviving
--      row.
--
-- NOT touched (ambiguous, flagged for next session): 27 orange rows with
-- parcel_id='TIMESHARE' and 4 with parcel_id='MULTIPLE PARCELS' -- these
-- could be legitimate categorical descriptions RealForeclose itself shows
-- for non-standard properties (as opposed to 'Property Appraiser', which is
-- unambiguously a scraped UI label). Needs verification against the live
-- source before any fix. Same pattern exists in marion (2 MULTIPLE PARCELS,
-- 1 MOBILE HOME, left untouched for the same reason) and was NOT swept in
-- other shards' counties (out of shard-7 scope).
--
-- Applied live 2026-07-02T11:0x UTC via PostgREST (service role) -- this
-- migration documents and reproduces that change.
--
-- VERIFIED live via pencil_dod_evaluate_county before/after (chained after
-- the marion SYN- fix and the earlier propertyonion contamination cleanup):
--   auctions_total 859 -> 852 (7 duplicate rows removed)
--   C 97.7->96.7  D 97.7->96.7  E 100.0->99.1  I 95.9->95.4
--   IMPORTANT: nulling the 15 fabricated rows alone (before dedup) dropped I
--   from 95.9 to 94.6 (a genuine FAIL) -- I was previously passing only
--   because of the fabricated linkage. The dedup step (removing 7 junk rows
--   from the denominator without removing any genuinely-complete row from
--   the numerator) honestly restored I to 95.4, still >=95%. This sequence
--   is preserved here for the record: fabrication removal first exposed a
--   real gap, a legitimate structural fix (not re-fabrication) closed it.
--   A/B/F/G/H/J unaffected (confirmed no regression). Orange remains 10/10.

UPDATE multi_county_auctions
SET parcel_id = NULL, parity_status = NULL
WHERE lower(county) = 'orange' AND parcel_id = 'Property Appraiser';

UPDATE multi_county_auctions
SET judgment_amount = 266857.31 WHERE case_number = '48-2024-CA-000579';
UPDATE multi_county_auctions
SET judgment_amount = 26709.23  WHERE case_number = '48-2023-CA-000773';
UPDATE multi_county_auctions
SET judgment_amount = 363973.82 WHERE case_number = '48-2022-CA-000157';
UPDATE multi_county_auctions
SET judgment_amount = 19305.16  WHERE case_number = '48-2022-CA-000622';
UPDATE multi_county_auctions
SET judgment_amount = 31733.40  WHERE case_number = '48-2023-CA-000785';
UPDATE multi_county_auctions
SET judgment_amount = 110469.33 WHERE case_number = '48-2022-CA-000031';
UPDATE multi_county_auctions
SET judgment_amount = 1461521.40 WHERE case_number = '48-2022-CA-000274';

DELETE FROM multi_county_auctions
WHERE case_number IN (
  '2025-CA-003507-O', '2023-CC-007103-O', '2025-CA-010072-O',
  '2022-CC-014013-O', '2025-CA-009057-O', '2022-CA-005532-O',
  '2017-CA-000599-O'
);

-- marion parcel_id='Property Appraiser' cleanup (4 rows, no duplicate pairs
-- found for these -- standalone unresolved cases, nulled not deleted).
UPDATE multi_county_auctions
SET parcel_id = NULL, parity_status = NULL
WHERE lower(county) = 'marion' AND parcel_id = 'Property Appraiser';
