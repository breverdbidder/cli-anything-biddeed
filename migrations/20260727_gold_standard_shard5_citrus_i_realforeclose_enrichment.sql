-- Gold Standard shard-5 citrus, letter I (property card completeness)
-- dispatch a308fac7, loop run 6871
--
-- Source: live anonymous AJAX harvest of citrus.realforeclose.com auction
-- calendar (scripts/realforeclose_aids_paginated_harvest.py, proven pattern
-- from prior shard sessions). VERIFIED against realforeclose_aids staging
-- table row for case "2025 CA 000569 A", parcel 3523039 confirmed present
-- in v_zoning_gold_standard_card with zone_code='LDR'.
--
-- Of the 12 citrus rows failing the I criterion at session start, only this
-- one had real, sourced address+parcel data available live. The remaining
-- 11 are genuine dead ends today, not scraper bugs:
--   - 2 cases ("MULTIPLE PARCELS") span multiple parcels per case; the I
--     evaluator's single-parcel_id model can't represent them without a
--     multi-parcel schema change (out of scope for this fix).
--   - 5 cases carry Final Judgment Amount = $0.00 on the live RealForeclose
--     calendar (auction_date 2026-08-20/08-27/09-03) -- no judgment entered
--     yet, so the county has not published parcel/address for them.
--   - The rest resolve only via scanned (non-OCR'able) clerk PDFs or a
--     CAPTCHA-gated case search; no reliable automated source today.
-- No fabricated values were written for any of the 11.

UPDATE multi_county_auctions
SET property_address = '10806 E IRENE ST, INVERNESS, FL 34450',
    parcel_id = '3523039'
WHERE county = 'citrus' AND case_number = '2025 CA 000569 A';
