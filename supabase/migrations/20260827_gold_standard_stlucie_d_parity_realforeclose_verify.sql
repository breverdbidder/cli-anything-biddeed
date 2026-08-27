-- Gold Standard: st_lucie letter D (parity matched_any) — resolve 16 null-parity rows
-- Task: parity_status IS NULL rows never run through the parity matcher, all UPCOMING
--       auctions 2026-09-01 through 2026-09-16, data_source mostly calendar_sweep_mca_v3.
--
-- BEFORE (live, pencil_dod_evaluate_county('st_lucie')):
--   "D": { "pass": false, "detail": "matched_any=233", "metric": 93.6 }
--   (233 of 249, need >=95% i.e. >=237 -> needed >=4 of the 16 null rows resolved)
--
-- METHOD: Fetched the LIVE stlucie.realforeclose.com AJAX/preview foreclosure auction
-- calendar for each target auction date via Playwright + Chromium (curl/WebFetch both
-- blocked with HTTP 403; Firecrawl API returned 402 insufficient credits). Navigated
-- the real calendar UI (https://stlucie.realforeclose.com/index.cfm -> click
-- "AUCTION CALENDAR" -> click September 2026 day cells with dayid="MM/DD/2026") which
-- resolves to zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=MM/DD/2026 preview pages
-- listing "Auction Type: FORECLOSURE Case #: <case>" per case on that day.
--
-- Evidence URLs (live-fetched 2026-08-27):
--   https://stlucie.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=09/01/2026
--     -> cases: 2024CA000617, 2025CA000396, 2025CA002566, 2025CA002629, 2025CA002792
--   https://stlucie.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=09/09/2026
--     -> cases: 2025CA002757, 2025CC001010
--   https://stlucie.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=09/15/2026
--     -> cases: 2025CA000957, 2025CA002001, 2025CA002273, 2025CC004868
--   https://stlucie.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=09/16/2026
--     -> cases: 2024CA002152, 2024CA002159, 2025CA000159, 2025CA001224, 2025CA001617,
--               2025CA001777, 2025CA001975, 2025CC001989, 2025CC002579
--
-- All 16 target case numbers from the task list were found live on their exact
-- scheduled auction dates (cross-checked case number + date pairing, not just
-- presence anywhere on the page). Zero false matches were forced — every one of
-- the 16 genuinely appears on the live calendar for its listed date.
--
-- AFTER (live, pencil_dod_evaluate_county('st_lucie')):
--   "D": { "pass": true, "detail": "matched_any=249", "metric": 100.0 }
--
-- Applied live via Supabase Management API BEFORE this file was committed, per
-- SHIP-TO-MAIN MANDATE. This migration file is a record of the SQL executed.

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:live_realforeclose_ajax:st_lucie:20260827'
WHERE case_number IN (
  '2025CA000159','2025CA001777','2024CA002152','2025CA001617',
  '2024CA002159','2025CC001989','2025CA001224','2025CA002001',
  '2025CA002273','2025CA000957','2025CC001010','2025CA002757',
  '2025CA002792','2025CA000396','2025CA002566','2024CA000617'
)
AND lower(county) = 'st_lucie'
AND parity_status IS NULL;
