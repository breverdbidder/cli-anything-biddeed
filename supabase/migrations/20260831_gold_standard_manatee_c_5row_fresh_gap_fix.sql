-- GOLD STANDARD manatee: letter C fresh-gap investigation and fix (2026-08-31).
--
-- CONTEXT: manatee C was FAIL at 89.5% (matched_clean=154 of 172). Three
-- prior sessions (2026-08-24, 2026-08-26, 2026-08-30) confirmed the
-- documented ceiling: 13 CLERK_SSOT_CANCELLED rows are structurally
-- excluded from the C numerator (GOLD_STANDARD_C_STRUCTURAL_BLOCK_
-- CROSS_COUNTY_FINDING_20260827.md), giving a hard floor of 159/172=92.4%,
-- itself still below the 95% threshold. This session re-diagnosed the
-- CURRENT gap composition fresh rather than re-litigating that finding.
--
-- FRESH FINDING (VERIFIED live 2026-08-31): the 18-row gap was NOT purely
-- the known 13 cancelled rows. 5 additional rows had appeared since the
-- last session, none of them cancellations:
--   1. 412025CA003113CAAXMA (foreclosure, PHANTOM_NOT_ON_CLERK) -- same
--      duplicate-pair shape as the 2026-08-23 precedent fix
--      (20260823_manatee_letter_c_phantom_reschedule_fix.sql): a long-form
--      pre-continuance case number for a real-world case already tracked
--      cleanly under its short form (2025CA003113AX, parity_status=
--      PARITY_OK, same parcel_id 401646309). VERIFIED live against
--      records.manateeclerk.com/CourtRecords/Search/ForeclosureSales
--      (fetched this session): 2025CA003113AX appears under the "Wednesday,
--      October 7, 2026" sale-date panel with status "PENDING ONLINE" --
--      a genuine reschedule, not a phantom, not cancelled. The row's own
--      tier1_sale_status was already independently set to 'RESCHEDULED',
--      corroborating this. Fixed by setting parity_status=PARITY_OK,
--      parity_source=manatee_clerk_foreclosure (auction_date left untouched
--      at 2026-09-02 to avoid colliding with the sibling's 2026-10-07 slot
--      under uq_mca_county_sale_date_parcel, matching the 2026-08-23
--      precedent's exact reasoning).
--   2. 4 tax_deed rows (2026TD000094, 2026TD000100, 2026TD000101,
--      2026TD000107), auction_date=2026-08-31 (today), parity_status IS
--      NULL. Manatee's clerk-based reconciler (scripts/clerk_ssot/parsers/
--      manatee.py) explicitly does NOT cover tax_deed -- the clerk's own
--      tax-deed page states there is no clerk-hosted list, only a pointer
--      to manatee.realforeclose.com. Reused the established evidentiary
--      precedent from 20260802 dispatch a00c589b (scripts/
--      gold_standard_shard1_run8166_manatee_cd_fix.py): the accepted tier1
--      bar for manatee C/D is "case appears on the live manatee.
--      realforeclose.com AJAX auction calendar for its own sale_type/
--      auction_date", not "sale independently verified closed" (every
--      existing tier1:*_ajax_harvest* matched_clean row in this table has
--      sold_amount=NULL). VERIFIED live this session: harvesting
--      manatee.realforeclose.com's 08/31/2026 calendar via
--      shard2_run2450_ajax_realforeclose_harvest.py returned all 4 target
--      case numbers verbatim, each with parcel_id matching the DB row
--      exactly (2112500000, 2468800004, 2516500002, 2634500009). Promoted
--      via exact case_number + parcel_id match, matched_clean +
--      parity_source='tier1:gold_standard_manatee_c_live_recheck_
--      20260831_ajax_harvest:tax_deed:2026-08-31'.
--
-- RESULT (VERIFIED live via SELECT public.pencil_dod_evaluate_county
-- ('manatee') before/after):
--   BEFORE: C FAIL matched_clean=154/172 (89.5%)
--   AFTER:  C FAIL matched_clean=159/172 (92.4%)  [documented ceiling, exact]
--           D PASS matched_any=172/172 (100%, was 167/172=97.1%)
-- Remaining 13-row gap re-confirmed live this session as 100%
-- CLERK_SSOT_CANCELLED (Counter query on full 172-row denominator returned
-- ONLY that one status for the gap set) -- the known Options A/B/C
-- architect-decision floor, not this session's to resolve. No fabrication:
-- every status change above is backed by a live source fetched THIS
-- session (records.manateeclerk.com HTML panel text, or
-- manatee.realforeclose.com AJAX calendar JSON with parcel_id
-- cross-match), not by inference or reuse of prior sessions' claims.
--
-- This migration is a record of the fix already applied live via
-- REST PATCH during this session; statements below are idempotent
-- (WHERE-scoped by current parity_status) and safe to replay.

UPDATE public.multi_county_auctions
SET parity_status = 'PARITY_OK',
    parity_source = 'manatee_clerk_foreclosure'
WHERE lower(county) = 'manatee'
  AND sale_type = 'foreclosure'
  AND case_number = '412025CA003113CAAXMA'
  AND parity_status = 'PHANTOM_NOT_ON_CLERK';

UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:gold_standard_manatee_c_live_recheck_20260831_ajax_harvest:tax_deed:2026-08-31'
WHERE lower(county) = 'manatee'
  AND sale_type = 'tax_deed'
  AND case_number IN ('2026TD000094', '2026TD000100', '2026TD000101', '2026TD000107')
  AND parity_status IS NULL;
