-- Gold Standard shard-10 (dispatch 96a9bc5d-bc36-4e5c-904e-b80ae8b1165a): seminole.
-- C/D parity fix via genuine public.realforeclose_aids match (tier1, RealAuction-
-- sourced -- NOT PropertyOnion), applied and verified live 2026-07-31.
--
-- Baseline (VERIFIED via pencil_dod_evaluate_county('seminole'), live 2026-07-31
-- before this change): C=92.5%% (matched_clean=123 of 133), D=92.5%% (matched_any=123
-- of 133). Both need >=95%% (127 of 133).
--
-- Root cause: 10 "calendar_sweep_mca_v3" stub rows (sale_type=foreclosure,
-- auction_date=2026-08-20) had parity_status/parity_source null -- fresh-ingestion
-- lag, the parity-refresh job had not run against them yet. Cross-checked all 10
-- case numbers directly against public.realforeclose_aids (populated by the
-- separate scrape-realauction-county.yml pipeline scraping seminole.realforeclose.com
-- directly, not PropertyOnion). 2 of the 10 have a genuine, independently-sourced
-- match on case_number + parcel_id + property_address:
--   2024CA001430 -> realforeclose_aids parcel_id 10-21-29-507-0000-0020,
--                   "919 GREAT BEND RD, ALTAMONTE SPRINGS, FL 32714", assessed_value 304614.0
--   2025CA001791 -> realforeclose_aids parcel_id 25-19-30-5AG-0505-0010,
--                   "302 S OAK AVE, SANFORD, FL 32771", assessed_value 321803.0
-- Both parcel_id/address pairs match the multi_county_auctions row exactly (matched_clean,
-- not divergent). The remaining 8 stub rows have no realforeclose_aids counterpart yet
-- (auction date is 3 weeks out from this session -- RealAuction has not posted them);
-- those are NOT stamped here (additive-only, never fabricate a match) and are the
-- subject of a same-session Workflow fan-out (see gold_standard_ultraloop_audit for
-- dispatch 96a9bc5d, letters C/D/I/J).
--
-- Result (VERIFIED, re-ran pencil_dod_evaluate_county('seminole') immediately after
-- applying): C 92.5->94.0 (matched_clean 123->125), D 92.5->94.0 (matched_any 123->125).
-- Still 2 short of the 95%% threshold on C/D alone from this fix; remaining gap handed to
-- the parallel research agents in this session's Workflow.

UPDATE multi_county_auctions
SET parity_status='matched_clean',
    parity_source='tier1:realforeclose_aids_live_20260731',
    parity_checked_at=now(),
    assessed_value=COALESCE(assessed_value, 304614.0)
WHERE lower(county)='seminole' AND case_number='2024CA001430';

UPDATE multi_county_auctions
SET parity_status='matched_clean',
    parity_source='tier1:realforeclose_aids_live_20260731',
    parity_checked_at=now(),
    assessed_value=COALESCE(assessed_value, 321803.0)
WHERE lower(county)='seminole' AND case_number='2025CA001791';

SELECT public.pencil_dod_evaluate_county('seminole');
