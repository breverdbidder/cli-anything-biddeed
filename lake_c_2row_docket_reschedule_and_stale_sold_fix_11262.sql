-- Gold Standard shard-1 (dispatch 7bcb4434, loop run 11262): Lake County letter C
-- (matched_clean) — fresh re-verification of the prior "genuine ceiling" diagnosis.
-- Date: 2026-09-02
--
-- TASK: The recon pass flagged lake C (127/147 = 86.4%) as "genuinely-cancelled
-- auctions correctly excluded, escalated as a fleet-wide policy question, not
-- fixable via more scraping." This session was told NOT to trust that summary
-- and to re-verify against CURRENT data first.
--
-- VERIFICATION METHOD:
--   1. Queried pencil_dod_evaluate_county('lake') live: C = matched_clean=127/147
--      (86.4%), confirming the stated baseline is current, not stale.
--   2. Reconstructed the evaluator's exact C-scope (data_source <> 'propertyonion'
--      OR data_source IS NULL) -> 147 rows, matching auctions_total exactly.
--      C-credit bucket = parity_status IN ('matched_clean','PARITY_OK',
--      'CLERK_VERIFIED') = 39+86+2 = 127, matching the metric exactly.
--   3. The 20 non-credited rows = 19x CLERK_SSOT_CANCELLED + 1x
--      PHANTOM_NOT_ON_CLERK. Pulled full row detail (parity_checked_at,
--      parity_source) for all 20 -- found ALL 20 had parity_checked_at no
--      later than 2026-08-03, i.e. NOT rechecked in a full month, despite a
--      prior script (scripts/lake_c_showcaseweb_docket_recheck_5f3a88a5.py)
--      claiming to have already re-run this exact check. 14 of the 19
--      CLERK_SSOT_CANCELLED rows carried only the original bulk-scrape
--      parity_source ('lake_clerk_foreclosure'), never an individual
--      manual_recheck marker -- these are net-new rows added to the
--      denominator since the last actual recheck ran, not previously
--      adjudicated cases being re-litigated.
--   4. Re-ran the courtrecords.lakecountyclerk.org/sci docket API (the lever
--      documented in scripts/lake_c_showcaseweb_docket_reconcile_7bcb4434.py)
--      fresh against all 19 CLERK_SSOT_CANCELLED rows, ordering each case's
--      docket entries chronologically (the existing recheck script's keyword
--      match does NOT check ordering/recency, which produces false positives
--      -- see below) and inspecting the literal MOST RECENT entry per case.
--   5. Independently cross-checked candidates against the live public
--      calendar (https://foreclosurecalendar.lakecountyclerkfl.gov/default.aspx)
--      as a second source.
--
-- RESULT OF FRESH VERIFICATION: 2 of the 20 non-credited rows ARE fixable
-- (stale record, same pattern as lake_c_15_stale_parity_reconciliation_backfill.sql
-- and lake_c_3row_new_clerk_calendar_parity_fix.sql). 18 are a confirmed
-- genuine structural ceiling (re-verified fresh, not just trusted from the
-- prior recon summary).
--
-- FIXABLE ROW 1 (case 2026CC001266): docket shows FORECLOSURE SALE CANCELLED
--   on 2026-08-11, but a NEWER entry on 2026-09-01 reads "ORDER
--   RESETTING/RESCHEDULING FORECLOSURE SALE" -- this is the most recent
--   docket event, i.e. a genuine reopen after our last check. Independently
--   confirmed on the live public calendar: case now appears under class
--   'pscalendar-foreclosure' (NOT 'pscalendar-cancelled'), new sale date
--   Tue 10/20/2026, new sale_details id=20619 (old id was 20528). Two
--   independent tier1 sources agree -- not a fabrication.
--
-- FIXABLE ROW 2 (case 2025CA001392, was parity_status=PHANTOM_NOT_ON_CLERK,
--   NOT covered by the existing CLERK_SSOT_CANCELLED-only recheck script):
--   our DB had this stuck at auction_status='scheduled', auction_date=
--   2026-09-01 (the forward-looking calendar sweep never found it because it
--   had already resolved). The docket API shows caseStatus=CLOSED with
--   "CERTIFICATE OF SALE ISSUED TO BOOK 6697 PAGE 2207-2210" (2026-03-10) and
--   "CERTIFICATE OF TITLE ISSUED TO" (2026-04-21) -- the property sold at
--   auction back in March 2026 and our record never got updated off
--   "scheduled". sold_amount is intentionally left NULL: the docket API does
--   not expose a structured dollar figure for the bid sheet (scanned document
--   image only, same limitation documented for case 2023CA000414 in the
--   prior 7bcb4434 session) -- not fabricated, flagged as a future B/F lever
--   IF sci/case/document/{requestKey} can be read.
--
-- FALSE-POSITIVE CANDIDATES CAUGHT (would have been wrongly "fixed" by a
-- naive keyword-only match -- rejected after chronological review):
--   2016CA002108: docket contains "ORDER RESETTING/RESCHEDULING" (2026-08-04)
--     but the LITERAL LAST docket entry is "FORECLOSURE SALE CANCELLED"
--     (2026-08-18) -- rescheduled, then cancelled again. Still genuinely
--     cancelled. (parity_checked_at was NULL for this row, so the recheck
--     script's cutoff logic returned its entire 2016-2026 docket history,
--     matching an old "NOTICE OF SALE" phrase from unrelated case stages --
--     a second reason this one is a script false-positive, not a real lead.)
--   2025CA002647: docket contains "NOTICE OF FORECLOSURE SALE ISSUED AND"
--     (2026-08-10, matched the RESCHEDULE_KEYWORDS list) but the actual last
--     event chronologically is "FORECLOSURE SALE CANCELLED" (2026-09-01,
--     AFTER the notice). Still genuinely cancelled.
--
-- REMAINING 18 CLERK_SSOT_CANCELLED ROWS (16 classified still_cancelled by
-- the recheck script + the 2 false positives above) -- individually
-- confirmed via chronological docket review: every single one's docket
-- history ends with "FORECLOSURE SALE CANCELLED" followed only by
-- administrative closeout entries (clerk's letter, certified mail returns,
-- satisfaction of judgment, refund requests, erecorded order copies) with NO
-- subsequent reschedule/reopen/new-notice-of-sale entry. Several
-- (2025CA002869, 2025CA001432) show "SATISFACTION OF JUDGMENT" immediately
-- after cancellation -- strong corroborating evidence the underlying debt was
-- resolved outside the auction (payoff/modification), i.e. genuinely
-- terminal, not stale. Case numbers: 2025CA001183, 2026CC002482,
-- 2025CA002869, 2022CA001381, 2025CC004659, 2025CA001578, 2025CA002626,
-- 2025CA001432, 2024CA000105, 2025CA002239, 2025CA000481, 2025CA002782,
-- 2024CA001040, 2025CA001532, 2025CA002732, 2025CA001088, 2016CA002108,
-- 2025CA002647.
--
-- parity_checked_at refreshed to 2026-09-02 on all 18 confirmed-cancelled
-- rows (parity_source suffixed ..._recheck_confirmed_cancelled) so the fact
-- that this session looked and confirmed is itself recorded -- no status
-- field changed on these 18, only the freshness stamp.
--
-- EXPECTED IMPACT: matched_clean 127 -> 129 of 147, C metric 86.4% -> 87.8%.
-- STILL FAILS the >=95% bar (140/147 needed, i.e. <=7 non-clean rows
-- tolerated; 18 remain). This is a genuine, re-verified structural ceiling
-- for the residual 18 -- NOT fixable via more scraping, matching (and now
-- independently re-confirming with fresh chronological docket evidence) the
-- prior recon pass's conclusion for those 18, while correcting the 2 rows
-- the prior recon pass had NOT actually re-verified this cycle.
--
-- OBSERVED SIDE EFFECT (informational, out of scope for this fix): after
-- this PATCH, letter G (zoning density/FAR/parking coverage) dropped from
-- 96.0% to 66.7% and letter I (card_complete) rose from 91.2% to 95.9%,
-- purely as a denominator-composition effect of correcting these 2 rows'
-- auction_status (both have complete card data: parcel_id, lat/long,
-- assessed_value, address -- explains I's rise). G's drop was NOT
-- investigated this session (out of scope: assigned letter is C only) --
-- flagged for a future G-focused session on lake.

-- Row 1: genuine reschedule caught via courtrecords.lakecountyclerk.org
-- docket API + independently confirmed on the live public calendar.
UPDATE public.multi_county_auctions
SET auction_status = 'scheduled',
    auction_date = '2026-10-20',
    clerk_url = 'https://foreclosurecalendar.lakecountyclerkfl.gov/sale_details.aspx?id=20619',
    parity_status = 'CLERK_VERIFIED',
    parity_source = 'lake_courtrecords_docket:gs_shard1_run11262_recheck',
    parity_checked_at = '2026-09-02T00:00:00Z'
WHERE lower(county) = 'lake'
  AND case_number = '2026CC001266'
  AND parity_status = 'CLERK_SSOT_CANCELLED';

-- Row 2: stale "scheduled" record for a case that actually sold in March
-- 2026 per docket Certificate of Sale/Title; sold_amount intentionally NOT
-- populated (not exposed by this API -- see docstring above).
UPDATE public.multi_county_auctions
SET auction_status = 'sold',
    parity_status = 'CLERK_VERIFIED',
    parity_source = 'lake_courtrecords_docket:gs_shard1_run11262_recheck',
    parity_checked_at = '2026-09-02T00:00:00Z'
WHERE lower(county) = 'lake'
  AND case_number = '2025CA001392'
  AND parity_status = 'PHANTOM_NOT_ON_CLERK';

-- Freshness-only stamp on the 18 rows individually re-confirmed genuinely
-- cancelled this session (no status field changed).
UPDATE public.multi_county_auctions
SET parity_checked_at = '2026-09-02T00:00:00Z',
    parity_source = 'lake_courtrecords_docket:gs_shard1_run11262_recheck_confirmed_cancelled'
WHERE lower(county) = 'lake'
  AND parity_status = 'CLERK_SSOT_CANCELLED'
  AND case_number IN (
    '2025CA001183','2026CC002482','2025CA002869','2022CA001381','2025CC004659',
    '2025CA001578','2025CA002626','2025CA001432','2024CA000105','2025CA002239',
    '2025CA000481','2025CA002782','2024CA001040','2025CA001532','2025CA002732',
    '2025CA001088','2016CA002108','2025CA002647'
  );
