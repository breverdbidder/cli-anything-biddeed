-- Gold Standard dispatch 487365d5-71dc-4492-b06a-a58da6810cb8: dixie C/D
-- refutation + real fix. Documents the actual SQL applied live via REST
-- (this file mirrors those PATCH/INSERT/RPC calls for the repo record; the
-- live effect already happened via Supabase REST during this session).
--
-- CONTEXT: a prior firing of this SAME dispatch (commit b93ad64f, branch
-- origin/claude/issue-12747-20260718-1601, never merged) claimed dixie C/D
-- had a "structural ceiling of 30/32=93.75%" and that no further action was
-- possible. That claim's own arithmetic was inconsistent: it simultaneously
-- said 2 future auctions + 6 Aug-2025 gap rows (8 total) were unmatchable
-- out of a 32-row denominator, which implies a ceiling of 24/32=75.0% (where
-- the county already was), not 30/32. The 30/32 number was never reconciled
-- against the county's own stated facts and was wrong.
--
-- INDEPENDENT RE-VERIFICATION (this session, live):
--   1. Fetched https://dixieclerk.com/departments-services/court-services/
--      tax-deed-sales/ directly and decoded the embedded Vue
--      `<tax-deed-sales :taxdeeds="[...]">` HTML-entity-encoded JSON
--      (31 records). The row the prior claim counted as "future" --
--      2026-07-13, parcel 01-10-13-4512-0000-0820 -- has in fact ALREADY
--      RESOLVED: status=sold, sold_amount=$36,600.00, cert_holder=
--      Jesus Santana, cert=2021/776, modified=2026-07-13T16:00:53Z. This was
--      genuinely future when the prior session checked around Jul 10-11, but
--      today is 2026-07-18 -- the prior claim was stale, not wrong when made.
--   2. Independently re-checked the 6 Aug-2025 gap rows (parcels
--      30-13-12-2994-0003-5550, 36-09-13-4502-0000-0330,
--      12-09-13-4030-0007-0050, 12-09-13-4030-0005-0170,
--      36-10-13-5665-0008-0330, 13-09-13-4051-0000-0490) via the same live
--      JSON payload: all 6 confirmed status='scheduled', sold_amount=null,
--      `modified` timestamp frozen at 2025-08-11 (original posting date,
--      never updated in 11+ months despite the sale date itself being 11
--      months in the past). qPublic property-appraiser lookups 403-blocked
--      bot traffic; no official-records-search endpoint found. No
--      independent source produces a real disposition for these 6 --
--      genuinely unresolved on the clerk's own site. Prior claim CORRECT
--      on these 6 rows.
--   3. 15-2023-CA-57 (2026-07-21 foreclosure) independently re-confirmed via
--      the live foreclosure-sales page: status='scheduled', sale date 3 days
--      out from today (2026-07-18). Genuinely unresolved. Prior claim
--      CORRECT on this row.
--   4. While reconciling row 1's real outcome via the sanctioned
--      refresh_parity_tier1_outcomes('dixie') matcher, surfaced a SEPARATE
--      pre-existing latent bug: 9 of the 24 already-matched_clean rows have
--      tax_deed_outcomes.outcome='redeemed' but multi_county_auctions.
--      auction_status='sold' (never updated to 'redeemed' when the real
--      redemption outcome was harvested on 2026-07-10). Because the matcher
--      compares MCA auction_status against the outcome table's disposition,
--      this mismatch caused those 9 rows to be reclassified
--      'matched_divergent' the moment the function was re-invoked --
--      an honest bug fix, not a new fabrication: those 9 outcomes were
--      already real (data_source='dixieclerk_tax_deed_page_live_v1',
--      inserted 2026-07-10), only the auction_status label was stale.
--
-- ACTIONS APPLIED LIVE (via Supabase REST during this session):
--   a. INSERT INTO tax_deed_outcomes: real sold outcome for
--      DIXIE-SYNTH-01-10-13-4512-0000-0820 (cert 2021/776, sold $36,600.00,
--      cert_holder Jesus Santana), data_source=
--      'dixieclerk_tax_deed_page_live_v1', source_url=dixieclerk.com
--      tax-deed-sales page.
--   b. UPDATE multi_county_auctions SET auction_status='sold',
--      sold_amount=36600.00, sold_amount_source=
--      'dixieclerk_tax_deed_page_live_v1' for that same row.
--   c. UPDATE multi_county_auctions SET auction_status='redeemed' for the 9
--      rows found in finding #4, correcting the stale 'sold' label to match
--      their real recorded outcome (case_numbers: DIXIE-SYNTH-
--      13-09-13-4053-0041-0040, 25-10-13-4970-00D6-0140,
--      25-10-13-4970-00C3-0320, 31-10-14-5665-0017-0390,
--      34-09-13-4495-0000-0080, 36-10-13-5665-0022-0340,
--      12-09-13-4030-0018-0010, 23-11-13-6778-000D-0280,
--      30-10-14-0000-7006-0100).
--   d. SELECT * FROM refresh_parity_tier1_outcomes('dixie') -- re-ran the
--      sanctioned canonical matcher after (a)-(c); result:
--      matched_clean=25, matched_divergent=0.
--   e. UPDATE multi_county_auctions SET tier1_sold_amount, tier1_sale_status,
--      tier1_verified_at for the newly-matched row, matching the
--      established pattern from the 2026-07-10 harvest migration.
--   f. Logged corrected gold_standard_ultraloop_audit rows (ids 6774, 6775)
--      refuting the prior session's 30/32 claim with this evidence.
--
-- RESULT (live pencil_dod_evaluate_county('dixie') before/after):
--   BEFORE: C matched_clean=24 (75.0%) FAIL | D matched_any=24 (75.0%) FAIL
--   AFTER:  C matched_clean=25 (78.1%) FAIL | D matched_any=25 (78.1%) FAIL
--           (clean -- zero matched_divergent)
--
-- STILL FAILING: both letters remain below the 95% (31/32) threshold. The
-- true achievable ceiling this session is 25/32=78.1%, not the prior
-- session's claimed 93.75%. The 7 rows still blocking full parity are:
--   - 15-2023-CA-57 (2026-07-21): genuinely future, 3 days out. Re-check
--     after 2026-07-21.
--   - 6 Aug-2025 gap rows: dixieclerk.com itself has never published a real
--     disposition in 11+ months. No independently-verifiable alternative
--     source found this session (qPublic 403s bots; no official-records-
--     search endpoint). Per Honesty Protocol (BLANK > WRONG), these remain
--     UNKNOWN/unmatched rather than guessed. Re-check periodically in case
--     the clerk site is ever updated, or pursue a phone/in-person records
--     request as a non-automatable fallback (out of scope for this session).
--
-- This file is a documentation-only record of REST calls already applied
-- live. Re-running it is safe/idempotent (all statements are the same
-- idempotent patterns used elsewhere in this campaign) but not required.
-- ============================================================================

-- (a) real outcome for the previously-mislabeled "future" row
INSERT INTO public.tax_deed_outcomes
  (case_number, county, auction_date, cert_number, cert_holder, opening_bid,
   winning_bid, outcome, parcel_id, data_source, source_url, enriched_at)
SELECT 'DIXIE-SYNTH-01-10-13-4512-0000-0820', 'dixie', '2026-07-13', '2021/776',
       'Jesus Santana', 6368.73, 36600.00, 'sold', '01-10-13-4512-0000-0820',
       'dixieclerk_tax_deed_page_live_v1',
       'https://dixieclerk.com/departments-services/court-services/tax-deed-sales/',
       now()
WHERE NOT EXISTS (
  SELECT 1 FROM public.tax_deed_outcomes
  WHERE case_number = 'DIXIE-SYNTH-01-10-13-4512-0000-0820' AND county = 'dixie'
);

-- (b) mirror onto multi_county_auctions
UPDATE public.multi_county_auctions
SET auction_status = 'sold',
    sold_amount = 36600.00,
    sold_amount_source = 'dixieclerk_tax_deed_page_live_v1',
    sold_amount_captured_at = now(),
    updated_at = now()
WHERE lower(county) = 'dixie'
  AND case_number = 'DIXIE-SYNTH-01-10-13-4512-0000-0820';

-- (c) fix stale auction_status='sold' -> 'redeemed' on the 9 rows whose real
-- tax_deed_outcomes disposition is 'redeemed' (bug pre-dates this session;
-- surfaced by re-invoking refresh_parity_tier1_outcomes).
UPDATE public.multi_county_auctions
SET auction_status = 'redeemed',
    updated_at = now()
WHERE lower(county) = 'dixie'
  AND case_number IN (
    'DIXIE-SYNTH-13-09-13-4053-0041-0040',
    'DIXIE-SYNTH-25-10-13-4970-00D6-0140',
    'DIXIE-SYNTH-25-10-13-4970-00C3-0320',
    'DIXIE-SYNTH-31-10-14-5665-0017-0390',
    'DIXIE-SYNTH-34-09-13-4495-0000-0080',
    'DIXIE-SYNTH-36-10-13-5665-0022-0340',
    'DIXIE-SYNTH-12-09-13-4030-0018-0010',
    'DIXIE-SYNTH-23-11-13-6778-000D-0280',
    'DIXIE-SYNTH-30-10-14-0000-7006-0100'
  );

-- (d) re-run the sanctioned canonical matcher
SELECT * FROM public.refresh_parity_tier1_outcomes('dixie');

-- (e) backfill tier1_sold_amount for the newly-matched row
UPDATE public.multi_county_auctions
SET tier1_sold_amount = 36600.00,
    tier1_sale_status = 'SOLD',
    tier1_verified_at = now()
WHERE lower(county) = 'dixie'
  AND case_number = 'DIXIE-SYNTH-01-10-13-4512-0000-0820'
  AND tier1_sold_amount IS NULL;

-- Verification: SELECT public.pencil_dod_evaluate_county('dixie');
-- Expected C: matched_clean=25 (78.1%) -- still FAIL, below 95% threshold
-- Expected D: matched_any=25 (78.1%) -- still FAIL, below 95% threshold
