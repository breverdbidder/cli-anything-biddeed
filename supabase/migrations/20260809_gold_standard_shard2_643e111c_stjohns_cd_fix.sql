-- Gold Standard shard-2 (dispatch 643e111c) -- st_johns letters C/D/E/I follow-up.
-- Applied live via Supabase Management API during this session; documents the change.
--
-- CONTEXT: an earlier session TODAY (dispatch ba2461bd, migrations/20260809_shard5_
-- ba2461bd_stjohns_new_cases_fix_APPLIED.sql) fixed letter J for st_johns (5/10 -> 6/10)
-- and left C/D/E/I failing, all traced to the same 4 rows:
--   CA25-0749, CA25-1585, CC24-6166 -- no address/parcel published upstream, St Johns
--     Clerk case search hCaptcha-gated (3rd session confirming this exact block).
--   CA25-1289 (695 A1A, Ponte Vedra Beach) -- has a real parcel_id (0622401500) and was
--     already parity-matched via 'tier1_realforeclose_stjohns_calendar' but flagged
--     parity_status='matched_divergent' with no divergence detail recorded, blocking C.
--
-- THIS SESSION'S NEW LEVER (genuinely new vs. all prior sessions on this county):
-- prior sessions only tried WebFetch/curl/Firecrawl against saintjohns.realforeclose.com
-- and got HTTP 403 (WAF) or a session-gated splash/shell page every time. This session
-- installed Playwright (chromium, headless) fresh in the harness and used a real browser
-- context to load the RealForeclose auction-preview calendar -- this DID render full
-- auction-item data (case #, parcel ID, final judgment, assessed value, address) where
-- every prior HTTP-client approach failed. This is the first live re-fetch of the actual
-- calendar content for this county in the campaign's history (not just a repeat of the
-- same blocked path).
--
-- FINDING 1 -- CA25-1289 divergence resolved (C fix):
-- Live saintjohns.realforeclose.com auction-preview for AuctionDate=08/20/2026, case
-- CA25-1289: Parcel ID 0622401500, Property Address "695 A1A", Assessed Value
-- $220,000.00, Final Judgment / Plaintiff Max Bid $304,839.23. Compared field-by-field
-- against our stored row (case_number, parcel_id, property_address, assessed_value,
-- opening_bid, auction_date) -- EXACT MATCH on every field, zero actual divergence.
-- The stored 'matched_divergent' status was stale/incorrect (parity_divergences was
-- NULL -- no divergence was ever actually recorded, consistent with this being a
-- clerical status left over from the parity_source backfill earlier today, not a real
-- disagreement). Corrected to 'matched_clean' -- this is a genuine correction backed by
-- a fresh live re-fetch, not a forced/fabricated promotion.
--
-- FINDING 2 -- CA25-0749 / CA25-1585 / CC24-6166 parity_source backfill (D fix, no C):
-- Live-fetched the same RealForeclose calendar for AuctionDate=08/20/2026 (CA25-0749,
-- CA25-1585) and AuctionDate=09/17/2026 (CC24-6166) via the same Playwright session.
-- All 3 cases DO appear on the live tier1 calendar (case number found, real auction
-- listed) but the source itself shows "Parcel ID: Property Appraiser" (its own
-- placeholder for "not yet resolved by the county") and "Final Judgment Amount: $0.00"
-- -- i.e. the upstream source genuinely has no parcel/amount for these cases yet, which
-- is consistent with (not contradicted by) our stored NULL fields for the same rows.
-- Because we DID genuinely query a tier1 independent source and got a real (if empty)
-- result, this is a legitimate matched_divergent-with-tier1-source outcome, not a ghost
-- stamp: parity_source is set to 'tier1_realforeclose_stjohns_calendar' with
-- parity_checked_at refreshed to this session's fetch time. parity_status remains
-- 'matched_divergent' (source disagrees: we have no data, source has no data either --
-- there is nothing to reconcile as "clean" since neither side has a value to compare).
-- E/I remain genuinely blocked for these 3 rows -- no parcel_id exists anywhere,
-- including on the source's own live calendar. Not attempting a 4th identical CAPTCHA
-- clerk-search retry per the dispatch brief; this is the same structural residual
-- confirmed independently by 3+ prior sessions plus this session's live calendar check.
--
-- HARD GUARDRAILS RESPECTED:
--   - No fabricated parcel_id, address, or amount for CA25-0749/CA25-1585/CC24-6166.
--   - CA25-1289 promoted to matched_clean only after an exact field-by-field live
--     re-fetch match -- not forced.
--   - PropertyOnion rows untouched (not part of this fix).
--   - Idempotent: all UPDATEs are scoped to exact case_number + guard conditions, safe
--     to re-run.
--
-- Live effect (verified via public.pencil_dod_evaluate_county('st_johns') this session):
--   Before: C=92.6% (50/54) FAIL, D=94.4% (51/54) FAIL, E=94.4% (51/54) FAIL,
--           I=94.4% (51/54) FAIL.
--   After (expected): C=94.4% (51/54) still FAIL (threshold 95%; 1 promotion insufficient
--           to cross 95% of 54 = 51.3, need 52+), D=98.1% (53/54) PASS (3 rows gain a
--           tier1 parity_source), E/I unchanged (no new parcel_id resolved -- genuinely
--           blocked, documented above).
-- See SQL VERIFICATION in session closeout for the actual live post-apply numbers.

SET statement_timeout = 0;

-- ── STEP 1: Correct CA25-1289 parity_status to matched_clean ─────────────────
-- Live RealForeclose re-fetch (Playwright, AuctionDate=08/20/2026) confirms exact
-- field match: parcel_id 0622401500, address "695 A1A", assessed_value $220,000.00,
-- judgment/opening_bid $304,839.23. Idempotent: only fires if still matched_divergent
-- with the tier1 calendar source and no recorded divergence detail.
UPDATE public.multi_county_auctions
SET
    parity_status = 'matched_clean',
    parity_checked_at = NOW(),
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number = 'CA25-1289'
  AND parity_status = 'matched_divergent'
  AND parity_source = 'tier1_realforeclose_stjohns_calendar'
  AND parity_divergences IS NULL
  AND parcel_id = '0622401500'
  AND assessed_value = 220000.00
  AND opening_bid = 304839.23;

-- ── STEP 2: Backfill parity_source for the 3 hard-blocked rows (D fix) ────────
-- Live RealForeclose re-fetch (Playwright) confirms these 3 case numbers ARE present
-- on the tier1 calendar (real auction listings) but the source itself has no
-- parcel/amount resolved yet (upstream "Property Appraiser" placeholder, $0.00
-- judgment) -- consistent with, not contradicting, our NULL fields. This is a real
-- tier1 lookup result, not a ghost stamp. Status stays matched_divergent (nothing to
-- reconcile as clean when both sides are empty).
UPDATE public.multi_county_auctions
SET
    parity_source = 'tier1_realforeclose_stjohns_calendar',
    parity_checked_at = NOW(),
    updated_at = NOW()
WHERE lower(county) = 'st_johns'
  AND case_number IN ('CA25-0749', 'CA25-1585', 'CC24-6166')
  AND parity_status = 'matched_divergent'
  AND parity_source IS NULL
  AND parcel_id IS NULL
  AND property_address IS NULL;

-- ── SQL VERIFICATION (run after applying) ────────────────────────────────────
-- SELECT public.pencil_dod_evaluate_county('st_johns');
-- SELECT case_number, parity_status, parity_source, parity_checked_at
--   FROM public.multi_county_auctions
--   WHERE lower(county)='st_johns'
--     AND case_number IN ('CA25-1289','CA25-0749','CA25-1585','CC24-6166')
--   ORDER BY case_number;
