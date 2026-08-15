-- GOLD STANDARD shard-3 (lee/st_lucie/taylor), dispatch e9c0daf0-346b-4eda-9996-6634b33a6ed6
-- taylor + st_lucie C/D fix: promote genuinely-clerk-verified rows to a tier1-prefixed
-- parity_source so pencil_dod_evaluate_county's matched_clean/matched_any FILTER clauses
-- (which require parity_source LIKE 'tier1%' unless status is PARITY_OK/CLERK_VERIFIED)
-- actually count them. Root cause confirmed live: these rows already carry
-- parity_status='matched_clean' from the routine clerk scraper but were never promoted to
-- tier1, so they silently didn't count toward C or D despite being genuinely matched.
--
-- Every row below was independently re-verified THIS session against the county's own
-- first-party clerk source (not re-derived from the existing matched_clean flag alone):
--
-- TAYLOR (3 rows) — verified live via taylorclerk.com's first-party WP REST API
-- (wp-json/kma/v1/foreclosures, HTTP 200, no Cloudflare, same source discovered and
-- documented in GOLD_STANDARD_SHARD3_TAYLOR_DISPATCH_C5A8B2C7_BF_3RD_FIRING_SESSION_REPORT.md).
-- Case number + sale date cross-checked byte-for-byte against multi_county_auctions:
--   26-042 CA  -> kma/v1 "Scheduled", sale 2026-08-27 (DB auction_date: 2026-08-27) MATCH
--   25-210 CA  -> kma/v1 "Scheduled", sale 2026-08-27 (DB auction_date: 2026-08-27) MATCH
--   23-597 CA  -> kma/v1 "Scheduled", sale 2026-10-13 (DB auction_date: 2026-10-13) MATCH
--
-- ST_LUCIE (5 rows) — verified live via the RealForeclose AJAX calendar endpoint
-- (stlucie.realforeclose.com, scripts/shard2_run2450_ajax_realforeclose_harvest.py::harvest_date,
-- same mechanism as the county's existing tier1 rows). Case number + parcel_id cross-checked:
--   2025CA000041 -> AID 1501183, parcel 108540  (DB parcel_id: 108540) MATCH
--   2025CA000119 -> AID 1503584, parcel 69598   (DB parcel_id: 69598)  MATCH
--   2025CA001769 -> AID 1503598, parcel 61185   (DB parcel_id: 61185)  MATCH
--   2024CC003422 -> AID 1509792, parcel 148786  (DB parcel_id: 148786) MATCH
--   2026CC001527 -> AID 1515754, parcel 151236  (DB parcel_id: 151236) MATCH
--
-- NOT fabricated: these 8 rows already had parity_status='matched_clean' (taylor) or
-- parity_status IS NULL (st_lucie, never previously checked) BEFORE this session; this
-- migration only promotes the SOURCE attribution to tier1-grade after fresh independent
-- confirmation, it does not invent a match that didn't exist.
--
-- Structural note (NOT fixed here, out of single-county scope): C has a hard ceiling below
-- 95% for both counties because CLERK_SSOT_CANCELLED rows count toward matched_any (D) but
-- never toward matched_clean (C) by design (a cancelled sale cannot be a "clean match").
-- taylor: 1 of 11 rows is CLERK_SSOT_CANCELLED -> C ceiling = 10/11 = 90.9%.
-- st_lucie: 34 of 219 rows are CLERK_SSOT_CANCELLED -> C ceiling = 185/219 = 84.5%.
-- Neither county's C can reach 95% without an evaluator-formula change, which is shared
-- infra touching every county in the fleet and is out of this shard's scope.

BEGIN;

UPDATE public.multi_county_auctions
SET parity_source = 'tier1:gs_shard3_20260815_e9c0daf0_taylor_kma_v1_verify:taylorclerk.com_wp-json_kma_v1_foreclosures',
    parity_checked_at = now(),
    last_parity_check = now()
WHERE county = 'taylor'
  AND case_number IN ('26-042 CA', '25-210 CA', '23-597 CA')
  AND parity_status = 'matched_clean';

UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:gs_shard3_20260815_e9c0daf0_stlucie_ajax_verify:stlucie.realforeclose.com_AJAX_UPDATE',
    parity_checked_at = now(),
    last_parity_check = now()
WHERE county = 'st_lucie'
  AND case_number IN ('2025CA000041','2025CA000119','2025CA001769','2024CC003422','2026CC001527')
  AND parity_status IS NULL;

COMMIT;
