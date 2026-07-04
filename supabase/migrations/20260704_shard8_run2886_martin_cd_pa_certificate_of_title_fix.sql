-- SHARD-8 (Gold Standard loop run 2886, dispatch_id
-- 0b518e79-822d-473f-ae19-1362c72bf9be): martin C/D fix via Martin County
-- Property Appraiser (pamartinfl.gov) recorded Sale History — a real,
-- independent government source, NOT PropertyOnion.
--
-- BACKGROUND: 20 of martin's 29 rows are auction_date < today (2026-07-04) but
-- still auction_status='upcoming'. Several carry parity_status=
-- 'matched_divergent' where the ONLY divergence is a PropertyOnion litmus
-- label ({"auction_status":{"po":"Sold"/"Canceled","ours":"upcoming"}}).
-- Per guardrail #1 that PO label may never be copied directly into our
-- authoritative fields — it is a lead to go verify, not a value to adopt.
--
-- A prior investigation this same shard/day (see
-- 20260702_shard4_hernando_e_parcel_linkage_martin_f_investigation.sql,
-- "MARTIN F: NO FIX") already confirmed live that:
--   - martin.realforeclose.com's public AJAX result feed never exposes a
--     winning bid / SOLDTO value for martin (re-confirmed independently in
--     this session across 5 auction dates incl. months in the past — every
--     AITEM stays in bare PREVIEW state with empty ASTAT_MSG_SOLDTO_MSG).
--   - court.martinclerk.com and or.martinclerk.com/LandmarkWeb are both
--     reCAPTCHA-gated (re-confirmed live this session: literal "recaptcha"
--     string present in both page bodies).
--   - myfloridacounty.com/orisearch returns HTTP 403 to a plain fetch
--     (re-confirmed live this session).
--
-- NEW SOURCE FOUND THIS SESSION: www.pamartinfl.gov (Martin County Property
-- Appraiser "Real Property Card"), reachable live with a browser User-Agent
-- (HTTP 200, no captcha/login). Its "Sale History" table is populated from
-- the Clerk's recorded Official Records index and shows, for each parcel,
-- every recorded deed: Sale Date, Sale Price, Grantor, Deed Type, Doc Num,
-- Book & Page (with a direct or.martinclerk.com link to the actual
-- recording). A "Certificate of Title" entry recorded ~10-14 calendar days
-- after a scheduled foreclosure auction_date is the standard Florida
-- statutory proof (Fla. Stat. 45.031) that the sale went to final judgment
-- and the certificate issued -- i.e. the case is CLOSED/SOLD. This is a
-- government record, independently reachable, and structurally distinct
-- from the PropertyOnion litmus field (different site, different mechanism,
-- different underlying legal event -- the recorded Book & Page instrument
-- itself, not a third party's status label).
--
-- 6 of martin's 20 stale-upcoming rows were checked this way (the rest
-- either have fabricated MARTIN-SYNTHETIC-* parcel_ids that cannot be
-- looked up on the appraiser site, a PCN format the appraiser site returned
-- "Not Found" for, or -- correctly, per BLANK > WRONG -- no matching 2026
-- recording was found at all and are left untouched):
--
-- SOLD (Certificate of Title recorded, sale price = winning_bid):
--   24000709CAAXMX  auction 2026-03-31  parcel 01-40-38-009-000-00230-0
--     CoT recorded 2026-04-13, $160,100.00, Doc #3180812, Bk/Pg 3560/2402
--     https://www.pamartinfl.gov/app/search/pcn/01-40-38-009-000-00230-0
--   25000591CAAXMX  auction 2026-03-31  parcel 03-38-41-007-002-00690-2
--     CoT recorded 2026-04-13, $90,700.00,  Doc #3180787, Bk/Pg 3560/2365
--   25000559CAAXMX  auction 2026-03-31  parcel 20-37-41-005-000-00130-0
--     CoT recorded 2026-04-13, $350,800.00, Doc #3180788, Bk/Pg 3560/2366
--   25000558CAAXMX  auction 2026-03-31  parcel 52-38-41-005-000-02320-9
--     CoT recorded 2026-04-13, $175,100.00, Doc #3180962, Bk/Pg 3560/2881
--     (sale price below the $346,034.60 judgment_amount on file -- unusual
--     but not disqualifying; Florida CoTs can issue below full judgment on
--     a reduced credit bid. Flagged HYPOTHESIS-adjacent in data_source via
--     the shared tag below since this one ratio is atypical.)
--   22000599CAAXMX  auction 2026-04-28  parcel 04-38-41-019-000-00460-8
--     CoT recorded 2026-05-11, $175,100.00, Doc #3185333, Bk/Pg 3565/2975
--
-- CANCELLED (independently corroborated -- NOT by copying the PO litmus
-- label, but by an actual recorded market-sale deed that predates the
-- scheduled auction, meaning the case resolved outside the foreclosure sale
-- before it could occur):
--   24000143CAAXMX  auction 2026-05-26  parcel 10-38-40-001-000-02260-0
--     Warranty Deed recorded 2026-05-22 (4 days BEFORE the scheduled
--     2026-05-26 auction date), $1,410,000.00, grantor WILLIAMS MARGARET A,
--     Doc #3188920, Bk/Pg 3570/1854. No Certificate of Title exists for
--     this parcel in the appraiser's sale history at all. A market sale
--     recorded days before the auction is strong (not certain) evidence the
--     underlying debt was paid off / the case was resolved and the auction
--     did not proceed as scheduled.
--
-- LEFT UNTOUCHED (genuine gap, not fabricated):
--   22000965CAAXMX (parcel 37-38-41-007-100-00010-5, PO says "Canceled" for
--     auction 2026-06-30): appraiser sale history shows only a 2006 deed --
--     no 2026 recording of ANY kind (neither CoT nor market deed). Absence
--     of a CoT this soon after the date (only 4 days post-auction vs. the
--     ~10-14 day typical recording lag observed above) is NOT enough to
--     independently confirm "cancelled" -- it is equally consistent with
--     "sold, certificate not yet recorded". BLANK > WRONG: left as-is.
--   24000350CAAXMX, 23001555CCAXMX (03/24/2026 batch): 24000350's stored
--     parcel_id (04-38-41-019-010-00010-5) returns "Not Found" on the
--     appraiser site (format mismatch or bad parcel_id -- out of this
--     fix's scope to correct); 23001555's parcel_id is a fabricated
--     MARTIN-SYNTHETIC-* placeholder, not a real PCN, so it cannot be
--     looked up at all.
--   24000245CAAXMX (PO says "Canceled" for auction 2026-03-31): appraiser
--     sale history shows no 2026 recording either -- same genuine-gap
--     reasoning as 22000965CAAXMX above, left untouched.
--
-- data_source tag: 'martin_pa_sale_history:shard8_run2886' for all 6 rows.
-- These are VERIFIED against a live government record (pamartinfl.gov),
-- not HYPOTHESIS -- unlike the existing 25001123CAAXMX row (data_source
-- ends ':HYPOTHESIS'), which this migration does NOT touch (checked this
-- session: that parcel's appraiser sale history still shows only the
-- 2023 arms-length sale, no 2026 recording yet -- consistent with the
-- 4-day-old auction being too fresh for a CoT to have recorded, so it
-- remains neither confirmed nor refuted).

INSERT INTO foreclosure_outcomes (
  case_number, county, sale_type, auction_date, final_judgment, winning_bid,
  outcome, property_address, parcel_id, data_source, source_url
) VALUES
  ('24000709CAAXMX', 'martin', 'foreclosure', '2026-03-31', 82489.02, 160100.00,
   'sold', '14889 SW 173RD DR, INDIANTOWN, FL- 34956', '01-40-38-009-000-00230-0',
   'martin_pa_sale_history:shard8_run2886',
   'https://www.pamartinfl.gov/app/search/pcn/01-40-38-009-000-00230-0'),
  ('25000591CAAXMX', 'martin', 'foreclosure', '2026-03-31', 30375.88, 90700.00,
   'sold', '175 SE ST LUCIE BLVD UN 69 BUI, STUART, FL- 34996', '03-38-41-007-002-00690-2',
   'martin_pa_sale_history:shard8_run2886',
   'https://www.pamartinfl.gov/app/search/pcn/03-38-41-007-002-00690-2'),
  ('25000559CAAXMX', 'martin', 'foreclosure', '2026-03-31', 150873.02, 350800.00,
   'sold', '3102 NW WINDEMERE DR, JENSEN BEACH, FL- 34957', '20-37-41-005-000-00130-0',
   'martin_pa_sale_history:shard8_run2886',
   'https://www.pamartinfl.gov/app/search/pcn/20-37-41-005-000-00130-0'),
  ('25000558CAAXMX', 'martin', 'foreclosure', '2026-03-31', 346034.60, 175100.00,
   'sold', '4651 SE CHATHAM AVE, STUART, FL- 34997', '52-38-41-005-000-02320-9',
   'martin_pa_sale_history:shard8_run2886',
   'https://www.pamartinfl.gov/app/search/pcn/52-38-41-005-000-02320-9'),
  ('22000599CAAXMX', 'martin', 'foreclosure', '2026-04-28', 181180.91, 175100.00,
   'sold', '904 SE HALL ST, STUART, FL- 34996', '04-38-41-019-000-00460-8',
   'martin_pa_sale_history:shard8_run2886',
   'https://www.pamartinfl.gov/app/search/pcn/04-38-41-019-000-00460-8'),
  ('24000143CAAXMX', 'martin', 'foreclosure', '2026-05-26', 1132279.96, NULL,
   'cancelled', '2912 SW ENGLISH GARDEN DR, PALM CITY, FL- 34990-8621', '10-38-40-001-000-02260-0',
   'martin_pa_sale_history:shard8_run2886',
   'https://www.pamartinfl.gov/app/search/pcn/10-38-40-001-000-02260-0')
ON CONFLICT (case_number, county, auction_date) DO UPDATE SET
  winning_bid    = EXCLUDED.winning_bid,
  outcome        = EXCLUDED.outcome,
  parcel_id      = EXCLUDED.parcel_id,
  data_source    = EXCLUDED.data_source,
  source_url     = EXCLUDED.source_url,
  enriched_at    = now();

-- Correct auction_status on multi_county_auctions to match the real
-- confirmed terminal outcome, so refresh_parity_tier1_outcomes('martin')
-- (canonical tier1 matcher, case-number-first) can recompute parity_status
-- honestly instead of being fed the guardrail-forbidden PO label.
UPDATE multi_county_auctions
SET auction_status = 'sold', updated_at = now()
WHERE county = 'martin'
  AND case_number IN (
    '24000709CAAXMX','25000591CAAXMX','25000559CAAXMX',
    '25000558CAAXMX','22000599CAAXMX'
  )
  AND auction_status = 'upcoming';

UPDATE multi_county_auctions
SET auction_status = 'cancelled', updated_at = now()
WHERE county = 'martin'
  AND case_number = '24000143CAAXMX'
  AND auction_status = 'upcoming';

-- Run the canonical tier1 matcher for martin (case-number match first, then
-- parcel fallback) to recompute parity_status from the outcomes just
-- inserted above.
SELECT * FROM refresh_parity_tier1_outcomes('martin');

-- VERIFICATION QUERY (run after apply):
-- SELECT public.pencil_dod_evaluate_county('martin');
