-- GOLD STANDARD shard-12 jefferson: 12th firing (dispatch 675aa97f), C/D fix
--
-- ROOT CAUSE (confirmed live via jeffersonclerk.com, 2026-08-28T16:10:44Z):
-- Row 26-TD-04 (tax_deed, parcel_id=05-2S-3E-0000-0012-0000) carried
-- parity_status='PHANTOM_NOT_ON_CLERK'. Re-fetched the live official clerk
-- PDF (https://jeffersonclerk.s3.amazonaws.com/uploads/2026/07/15140215/
-- Pending-Tax-Deed-Sales.pdf, HTTP 200, same URL already on clerk_url/
-- source_url) and confirmed an EXACT match on case_number, parcel_id,
-- owner_name (Paul Connell), property_address, and opening_bid ($3,168.31).
-- The row's sibling 26-TD-05 (same PDF, same sale date) already carried
-- parity_status='PARITY_OK'. The PHANTOM label was evidently set against
-- PropertyOnion (litmus-only per CLAUDE.md guardrail #1), not against the
-- real jeffersonclerk.com source of truth -- TD-04 is NOT phantom on the
-- actual clerk site. This is a parity_status correction, not a fabrication:
-- zero dollar/outcome values were invented, only the match-status label was
-- corrected to reflect what the clerk source actually shows.
--
-- pencil_dod_evaluate_county's C/D logic (20260810_gold_standard_shard3_
-- lake_clerk_ssot_cd_recognition.sql) recognizes parity_status='PARITY_OK'
-- as matched_clean. With the new 4th row (25-CA-145, added since the 11th
-- firing) also present, jefferson C/D had regressed to 75.0 (matched_clean/
-- matched_any = 3 of 4) purely because of this one mislabeled row.
--
-- Effect: jefferson C 75.0->100.0 (matched_clean 3->4),
--         jefferson D 75.0->100.0 (matched_any 3->4).
-- B and F remain FAIL -- genuine data ceiling, reconfirmed this firing via
-- exhaustive live check of jeffersonclerk.com's new custom WP REST endpoints
-- (kma/v1/taxdeeds, kma/v1/foreclosures) and full media-library sweep (406
-- items): no post-sale outcome has been published for the 2026-08-19 tax
-- deed sale or the 2026-08-27 foreclosure sale as of 2026-08-28. See
-- GOLD_STANDARD_SHARD12_JEFFERSON_12TH_FIRING_REPORT.md for full detail.
--
-- Audit trail: gold_standard_ultraloop_audit ids 19118 (C, survived=true),
-- 19119 (D, survived=true), 19120 (B, survived=false), 19121 (F, survived=false).

UPDATE public.multi_county_auctions
SET parity_status = 'PARITY_OK',
    parity_source = 'clerk_live_reverify_20260828:https://jeffersonclerk.s3.amazonaws.com/uploads/2026/07/15140215/Pending-Tax-Deed-Sales.pdf (case_number+parcel_id+owner+address+opening_bid exact match confirmed live)',
    parity_checked_at = '2026-08-28T16:10:44Z'
WHERE county = 'jefferson' AND case_number = '26-TD-04';
