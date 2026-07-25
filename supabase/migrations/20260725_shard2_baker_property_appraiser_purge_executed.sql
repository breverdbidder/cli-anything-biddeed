-- Gold Standard shard2 baker: EXECUTE the 2026-07-24 purge that was
-- committed but never applied live (SHIP GATE violation — file-only,
-- zero execution). Also extends it: the 3 poisoned rows carried a
-- fabricated parity_status='matched_clean'/parity_source=
-- 'tier1_supplementary:shard3:2026-06-25' stamp derived from the SAME
-- garbage parcel_id='Property Appraiser' text — that stamp inflated C/D
-- exactly as much as the garbage parcel_id inflated E, so it must be
-- reset alongside parcel_id, not left standing.
--
-- VERIFIED live 2026-07-25: prior to this migration, 3 baker rows still
-- had parcel_id='Property Appraiser' (case_numbers 022025CA000108CAAXMX
-- foreclosure, 022026CA000018CAAXMX foreclosure, 022025CA000148CAAXMX
-- tax_deed — all updated_at=2026-07-24T09:10:05Z, i.e. touched by a prior
-- session's diagnostic pass but never actually cleared). This confirms
-- 20260724_shard2_baker_c_d_e_i_property_appraiser_purge.sql was authored
-- and committed to main but its UPDATE never ran against the live DB.
--
-- EFFECT: pencil_dod_evaluate_county('baker') C/D/E drop from a
-- fabricated 40.0% (6/15, 3 real + 3 ghost) to an honest 20.0% (3/15,
-- the 2 case numbers with genuine bakerpa.com-sourced parcel IDs:
-- 022025CA000038CAAXMX -> 043S22000000000540, 022026XX000002TDAXMX ->
-- 35-2S-20-0000-0000-0035). I is unchanged at 20.0% (3/15) — it was
-- already keyed off the same 3 real rows. This is a correct DECREASE:
-- removing a fabricated ghost-success, not a regression.
--
-- REMAINING GAP (confirmed still open, not fabricated): the other 6
-- case numbers (12 rows) have zero owner_name/plaintiff/trellis_url/
-- address anywhere in multi_county_auctions, so even though
-- bakerpa.com is back online today (HTTP 200, was HTTP 521 on
-- 2026-07-24) there is still no search key (parcel/name/address) to
-- query it with for these specific cases. baker.realforeclose.com's
-- own Parcel ID link is empty (href="...?parcel=") for these 6 cases at
-- the source — Baker County itself has not linked a parcel yet.
-- Deferred until the source publishes a link, or an owner name becomes
-- reachable via a stateful OCRS court-record lookup (not doable via
-- plain curl; flagged for a browser-automation session).

BEGIN;

UPDATE public.multi_county_auctions
SET parcel_id = NULL,
    parity_status = NULL,
    parity_source = NULL,
    updated_at = NOW()
WHERE county = 'baker'
  AND lower(parcel_id) = 'property appraiser';

COMMIT;
