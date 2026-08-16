-- Gold Standard flagler C/D: litmus-harvest the 8 parity_status=NULL rows
-- (denominator grew 148->159 since flagler's 2026-07-24 10/10 certification;
-- see GOLD_STANDARD_SHARD7_DIXIE_FLAGLER_DISPATCH_EA6AF08A_4TH_PASS_SESSION_REPORT.md).
--
-- Source of truth for these values: live PostgREST harvest run via
-- scripts/gold_standard_flagler_cd_8gap_litmus_fix.py on 2026-08-16, which
-- queried flagler.realtdm.com (county clerk tax-deed portal) and the
-- RealForeclose AJAX calendar (county foreclosure auction platform) --
-- PropertyOnion is never the source, per HARD GUARDRAILS #1 (litmus-only).
--
-- 3 tax_deed rows (25-032/25-031/25-026 TDC) confirmed REDEEMED (tax
-- certificate paid off before sale, legitimate non-sale) with an exact
-- parcel-number prefix match against the live realtdm case card ->
-- CLERK_SSOT_CANCELLED (counts for D/matched_any only, correctly excluded
-- from C/matched_clean per the evaluator SQL, same rule as the charlotte
-- CD refuter-fix precedent).
--
-- 1 tax_deed row (26-076 TDC) confirmed ACTIVE with an exact full parcel_id
-- match -> matched_clean.
--
-- 4 foreclosure rows confirmed present on the live RealForeclose AJAX
-- calendar for their respective auction dates with exact parcel_id matches
-- -> matched_clean.
--
-- This DB write already executed live via PostgREST; this migration file
-- documents/replays the same data change per HARD GUARDRAILS #3.

SET statement_timeout = 0;

UPDATE public.multi_county_auctions
SET parity_status = 'CLERK_SSOT_CANCELLED',
    parity_source = 'tier1:gold_standard_flagler_8gap_litmus:realtdm'
WHERE id IN (
    '4d6bf5d2-6aaf-42f2-b58e-7e8d080c0ef2',  -- 25-032 TDC, redeemed
    '891967a0-0ca1-4973-a6f3-3041563bf4af',  -- 25-031 TDC, redeemed
    'ba115d77-7924-4a85-b44c-648ab5f254cc'   -- 25-026 TDC, redeemed
);

UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:gold_standard_flagler_8gap_litmus:realtdm'
WHERE id = '148a2580-1294-477e-814b-6b8a0ea09a1a';  -- 26-076 TDC, active, exact parcel match

UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:gold_standard_flagler_8gap_litmus:realforeclose_ajax'
WHERE id IN (
    'fa706ae9-acca-4495-b0f4-8b06b0b8e309',  -- 2025 CA 000656
    '7c6013d5-1130-4c29-a93b-8217c4a1cf33',  -- 2025 CA 000462
    '2e7aef04-be0d-43c7-93cf-3d74ffedd3f6',  -- 2024 CC 000454
    'a817ed79-5509-4108-b370-3d1c18408384'   -- 2025 CA 000505
);
