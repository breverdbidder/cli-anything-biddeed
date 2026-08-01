-- Pinellas C/D 21-row parity gap closure (2026-08-01)
--
-- Applied live via pinellas_cd_21row_parity_backfill.py (see that file's
-- module docstring for the full RealAuction verification methodology and
-- evidence trail). This file documents the exact writes that script
-- performed against the LIVE multi_county_auctions table -- it is a record
-- of what ran, not a script meant to be re-applied blindly (re-running the
-- .py is idempotent and re-verifies live; this .sql is NOT re-idempotent
-- since it hardcodes the case_number -> outcome mapping from that one run).
--
-- BEFORE: pinellas C (matched_clean) = 94.9% (390/411), D (matched_any) = 94.9% (390/411)
-- AFTER:  pinellas C = 100.0% (411/411), D = 100.0% (411/411)  -- both PASS
--
-- Verified live via: SELECT public.pencil_dod_evaluate_county('pinellas');

-- 9 rows confirmed SOLD via the Pinellas Clerk's own "Auction Results Report"
-- (report_id=18 on pinellas.realforeclose.com), auction_status literally
-- 'Sold' in that report, winning_bid taken from the report's own grid.
UPDATE multi_county_auctions SET
  parity_status = 'matched_clean',
  parity_source = 'tier1_realforeclose_results_report:pinellas:20260801_cd21gap',
  parity_confidence = 0.98,
  parity_checked_at = '2026-08-01T16:26:43Z',
  last_parity_check = '2026-08-01T16:26:43Z',
  sold_amount = v.sold_amount,
  sold_amount_source = 'tier1_realforeclose_results_report:pinellas:20260801_cd21gap',
  sold_amount_captured_at = '2026-08-01T16:26:43Z',
  tier1_sold_amount = v.sold_amount,
  tier1_sale_status = 'sold',
  tier1_authoritative = true,
  tier1_verified_at = '2026-08-01T16:26:43Z',
  auction_status = 'completed'
FROM (VALUES
  ('522019CA006299XXCICI', 350100.00),
  ('522023CC009988XXCOCO', 16900.00),
  ('522024CA005092XXCICI', 425100.00),
  ('522025CA000496XXCICI', 600.00),
  ('522025CA001203XXCICI', 44000.00),
  ('522025CA003770XXCICI', 368600.00),
  ('522025CA004720XXCICI', 286400.00),
  ('522025CA005221XXCICI', 100.00),
  ('522026CC003183XXCOCO', 53100.00)
) AS v(case_number, sold_amount)
WHERE multi_county_auctions.county = 'pinellas'
  AND multi_county_auctions.case_number = v.case_number;

-- 7 rows confirmed CANCELED via the live per-day "DAYLIST" auction calendar
-- page (index.cfm?zaction=AUCTION&Zmethod=DAYLIST&AUCTIONDATE=MM/DD/YYYY),
-- "Auctions Closed or Canceled" section, case_number + property address
-- matched against our record, platform's own cancellation reason noted.
UPDATE multi_county_auctions SET
  parity_status = 'matched_clean',
  parity_source = 'tier1_realforeclose_daylist:pinellas:20260801_cd21gap',
  parity_confidence = 0.95,
  parity_checked_at = '2026-08-01T16:26:43Z',
  last_parity_check = '2026-08-01T16:26:43Z',
  auction_status = 'canceled'
WHERE county = 'pinellas' AND case_number IN (
  '522025CA003877XXCICI',  -- Canceled per Order      (07/13/2026)
  '522025CA001504XXCICI',  -- Canceled per Bankruptcy (07/14/2026)
  '522026CC001281XXCOCO',  -- Canceled per Order      (07/16/2026)
  '522025CC002113XXCOCO',  -- Canceled per Order      (07/16/2026)
  '522025CA000404XXCICI',  -- Canceled per Order      (07/21/2026)
  '522025CA005643XXCICI',  -- Canceled per Order      (07/23/2026)
  '522026CC000983XXCOCO'   -- Canceled per County     (07/23/2026)
);

-- 5 rows confirmed still UPCOMING/SCHEDULED via the same live DAYLIST page,
-- "Auctions Waiting" section, case_number + property address matched.
-- Includes the 2 previously-suspicious 'manual_live_recheck_20260801' rows
-- (522024CA003791XXCICI, 522025CA004206XXCICI), independently re-verified
-- here rather than trusted blindly -- both check out as genuine.
UPDATE multi_county_auctions SET
  parity_status = 'matched_clean',
  parity_source = 'tier1_realforeclose_daylist:pinellas:20260801_cd21gap',
  parity_confidence = 0.95,
  parity_checked_at = '2026-08-01T16:26:43Z',
  last_parity_check = '2026-08-01T16:26:43Z'
WHERE county = 'pinellas' AND case_number IN (
  '522024CA003926XXCICI',  -- 08/05/2026, 8115 61ST ST N, PINELLAS PARK
  '522025CA001662XXCICI',  -- 08/05/2026, 1450 CAROLYN LN, CLEARWATER
  '522026CA000876XXCICI',  -- 08/05/2026, 1511 RIDGE AVE, CLEARWATER
  '522024CA003791XXCICI',  -- 08/05/2026, 2048 LOMA LINDA WAY S, CLEARWATER (was manual_live_recheck_20260801)
  '522025CA004206XXCICI'   -- 08/04/2026, 3376 21ST PL SW, LARGO (was manual_live_recheck_20260801)
);
