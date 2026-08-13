-- Gold Standard baker C/D residual fix: the last 2 non-matched rows
-- (022025CA000117CAAXMX, 022025CC000132CCAXMX) confirmed LIVE this session via a
-- genuinely untried channel -- baker.realforeclose.com's internal AJAX JSON endpoint
-- (zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=W), which is the "Waiting" (currently
-- scheduled, not yet run/closed) auction area on the county's official RealAuction-
-- hosted sale calendar. This endpoint required no login and hit no Cloudflare
-- Turnstile/JS-challenge -- distinct from bakerclerk.com, civitekflorida.com/ocrs, and
-- RealAuction's login-gated pages that 5+ prior sessions correctly avoided.
--
-- 117 (auction date 2026-10-15, area="Waiting", AID=1510237): live JSON returned
-- Case #: 022025CA000117CAAXMX, Final Judgment Amount: $95,618.97, Parcel ID:
-- 341N20000000000014, Property Address: 15985 JACK DOWLING CIR / SANDERSON, FL- 32087,
-- Assessed Value: $274,860.00 -- case number, parcel, address, and judgment_amount all
-- match multi_county_auctions exactly (judgment_amount on file is $95,618.97, not the
-- $111,570.02 figure speculated in the dispatch prompt -- that figure was unverified
-- and is superseded by this live re-check).
--
-- 132 (auction date 2026-08-27, area="Waiting", AID=1514287): live JSON returned
-- Case #: 022025CC000132CCAXMX, Final Judgment Amount: $5,777.86, Parcel ID:
-- 073S22023800001000, Property Address: 8669 NEWNAN LAKE DR / MACCLENNY, FL- 32063,
-- Assessed Value: $279,706.00 -- case number, parcel, address, and judgment_amount all
-- match multi_county_auctions exactly.
--
-- Both cases were in the "W" (Waiting = currently scheduled, not Running/not
-- Closed-or-Canceled) area of the live calendar, confirming they are genuine
-- upcoming foreclosure auctions, not phantom or already-resolved records.
UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:baker_realforeclose_ajax_waiting_area_live_2026-08-13',
    updated_at = now()
WHERE county = 'baker'
  AND case_number IN ('022025CA000117CAAXMX', '022025CC000132CCAXMX')
  AND parity_status IS NULL;
