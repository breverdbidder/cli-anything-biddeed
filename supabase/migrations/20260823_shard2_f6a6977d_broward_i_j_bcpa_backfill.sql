-- GOLD STANDARD shard-2 (dispatch f6a6977d-0263-42f8-8255-d26612af2a16): broward letters I
-- (card_complete) and J (deal_complete).
--
-- BEFORE (VERIFIED live via pencil_dod_evaluate_county('broward'), 2026-08-23):
--   I: card_complete=737 of 806 (91.4%) -- FAIL
--   J: deal_complete=761 of 806 (94.4%) -- FAIL
--
-- === I diagnosis (VERIFIED live) ===
-- 69 distinct rows failed I's completeness predicate (property_address NOT NULL AND
-- (latitude OR po_latitude) NOT NULL AND (longitude OR po_longitude) NOT NULL AND
-- (assessed_value OR market_value) NOT NULL AND parcel_id present). Breakdown:
-- missing_address=10, missing_geo=17, missing_value=67 (dominant bucket, most already have
-- a parcel_id), missing_parcel=3. No zoning-linkage gap found (v_zoning_gold_standard_card
-- coverage is complete for every broward row that has a parcel_id -- unlike pinellas' same-
-- dispatch finding).
--
-- Live BCPA (Broward County Property Appraiser, bcpa.net/RecInfo.asp -- the classic public
-- parcel-detail page; the newer gisweb-adapters.bcpa.net ArcGIS REST "BCPA_EXTERNAL_JAN26"/
-- "BCPA_EXTERNAL_JAN25" MapServer layers were checked first and confirmed LIVE this session
-- to expose ONLY FOLIO+geometry, no owner/address/valuation fields -- so RecInfo.asp, which
-- does carry real Just Value / Assessed-SOH Value fields, was used instead) lookup was run
-- against all 67 missing_value rows' parcel_id values. 46 of 67 had a genuine BCPA-folio-
-- format parcel_id (13-digit numeric OR digit+letter+digit condo/timeshare alt-key like
-- 494108AH0380) and returned real, current Just Value + Assessed/SOH Value data for 100% of
-- the 46 tested (0 not-found). The remaining 21 rows had a degenerate/placeholder parcel_id
-- (truncated 6-digit stub, or literal "MULTIPLE PARCELS" / "TIMESHARE" / "Property Appraiser"
-- / NULL) -- left untouched, no real BCPA lookup possible for these, reported as residual.
--
-- One additional row (CACE-23-014484, parcel 484226091290) was missing lat/long only; its
-- parcel_id is a plain 13-digit numeric BCPA folio, which DOES match the gisweb-adapters.bcpa.net
-- ArcGIS "Parcels" layer's FOLIO field format, so its real parcel polygon geometry was queried
-- live and the centroid computed for latitude/longitude.
--
-- AFTER writing the 46-row value backfill + 1-row geo fix (fresh SQL re-check, VERIFIED):
-- missing_address=10, missing_geo=16, missing_value=21 (all 21 are the degenerate-parcel-id
-- residual), missing_parcel=3, distinct_failing=35 (down from 69).
-- pencil_dod_evaluate_county('broward') I: card_complete=771 of 806 (95.7%) -- PASS.
--
-- === J diagnosis (VERIFIED live) ===
-- 45 of 806 rows had ZERO bid_decisions row (not partial/incomplete -- confirmed has_bd=False
-- for all 45). These 45 case numbers are an EXACT SUBSET of the original 67 I-gap
-- missing_value rows (0 rows in the J gap outside that set) -- i.e. this was never a cron-
-- scheduling gap, it is a direct input dependency: whatever process populates broward
-- bid_decisions cannot run its CMA/ARV arm without a real assessed_value/market_value input,
-- so it skipped these 45 rows outright.
--
-- A prior gold-standard session on this same dispatch (2026-08-13, commit 064cae75,
-- pipeline_version='broward_j_backfill_v1_shard2_72cb38f7') had already backfilled 44 DIFFERENT
-- broward case numbers to deal_complete via the same Shapira-formula generator pattern used
-- fleet-wide (see scripts/gold_standard_shard2_broward_j_dispatch72cb38f7.py) and claimed J at
-- 100% at the time. Confirmed live this session: those 44 case numbers are FULLY DISJOINT from
-- today's 45-row gap -- new auction rows have entered the 806-row DoD universe since Aug 13 and
-- outpaced that one-time backfill. This is the same coverage/scheduling drift pattern
-- repeating, not a broken pipeline. No cron job named "gen_valuations_comps_batch" or "cron
-- 109" writes bid_decisions directly for broward (confirmed via cron.job listing and
-- pg_get_functiondef search across every function referencing bid_decisions) -- the writer is
-- this session-scoped Python generator script pattern, run manually per gold-standard session,
-- not an automated cron.
--
-- ACTION TAKEN: per the "do NOT build a new J generator" instruction, adapted the existing
-- dispatch72cb38f7 script (scripts/gold_standard_shard2_broward_j_dispatch72cb38f7.py) into a
-- new dispatch-scoped copy (scripts/gold_standard_shard2_broward_j_dispatch_f6a6977d.py) that
-- reuses the identical Shapira-v14 formula/contract, re-queries the gap fresh, and runs against
-- TODAY's 45-row gap. Because this session's I-fix already backfilled real BCPA values for 46
-- of these exact 45 case numbers (the sets overlap 45/45 -- every J-gap row also got a real
-- value in the I-fix above), 45/45 rows in this run were grounded in a real BCPA
-- assessed_value/market_value figure (arv_source='shapira_formula_broward_j_backfill_f6a6977d_bcpa_assessed_value'),
-- a strictly better real-data ratio than the prior run's 19/44. Zero rows fell back to the
-- live-queried county-median (percentile_cont(0.5) over 9,843 real market_value rows =
-- $261,040, re-queried fresh this session) because every remaining gap row already had a real
-- BCPA value from this session's I-fix. All distress-triangle scores and both CMA arms remain
-- formula-derived (not per-parcel comps) and are tagged honesty_marker: INFERRED throughout,
-- matching the established fleet-wide contract.
--
-- AFTER (VERIFIED live via pencil_dod_evaluate_county('broward'), 2026-08-23):
--   I: card_complete=771 of 806 (95.7%) -- PASS (was 91.4% FAIL)
--   J: deal_complete=806 of 806 (100.0%) -- PASS (was 94.4% FAIL)
--   All 10 letters (A-J) PASS.
--
-- RESIDUAL (I, honest, not closed): 21 rows still fail I's value predicate -- their parcel_id
-- is genuinely unusable (truncated stub, "MULTIPLE PARCELS", "TIMESHARE", "Property
-- Appraiser" placeholder text, or NULL). No real BCPA lookup is possible without a correct
-- folio, and the case docket / original scrape did not capture one. Also 10 rows remain
-- missing_address and up to 16 remain missing_geo (condo/timeshare alt-key parcel_ids that do
-- not match the gisweb-adapters.bcpa.net Parcels layer's plain-numeric FOLIO field format --
-- confirmed live, 0 geometry matches for alt-key folios in that layer). Building a scraper
-- against the BCPA condo/timeshare alt-key geometry index (if one exists) is out of scope for
-- this session; documented as residual only, no data was fabricated to close this gap.
--
-- This migration is idempotent (re-running is a no-op once values match) and documents the
-- exact live UPDATE already executed via the Management API SQL endpoint this session.

-- I fix: real BCPA (bcpa.net/RecInfo.asp) Just Value / Assessed-SOH Value, fetched live
-- 2026-08-23, for the 46 broward rows with a valid BCPA-folio-format parcel_id.
UPDATE multi_county_auctions
SET assessed_value = CASE case_number
    WHEN 'CACE-09-033060' THEN 471610
    WHEN 'CACE-17-015398' THEN 268380
    WHEN 'CACE-22-016620' THEN 481280
    WHEN 'CACE-23-014484' THEN 273070
    WHEN 'CACE-23-019709' THEN 456180
    WHEN 'CACE-24-006635' THEN 273900
    WHEN 'CACE-24-010844' THEN 215160
    WHEN 'CACE-24-014862' THEN 456190
    WHEN 'CACE-24-016110' THEN 110480
    WHEN 'CACE-24-018041' THEN 337200
    WHEN 'CACE-25-002663' THEN 497690
    WHEN 'CACE-25-007824' THEN 180400
    WHEN 'CACE-25-010076' THEN 207140
    WHEN 'CACE-25-010119' THEN 1241860
    WHEN 'CACE-25-011675' THEN 287700
    WHEN 'CACE-25-012902' THEN 206020
    WHEN 'CACE-25-012938' THEN 170550
    WHEN 'CACE-25-013181' THEN 361460
    WHEN 'CACE-25-014553' THEN 437290
    WHEN 'CACE-25-014566' THEN 219130
    WHEN 'CACE-25-014626' THEN 827580
    WHEN 'CACE-25-015235' THEN 169350
    WHEN 'CACE-25-015544' THEN 242180
    WHEN 'CACE-25-015545' THEN 238170
    WHEN 'CACE-25-015855' THEN 238170
    WHEN 'CACE-25-016509' THEN 237070
    WHEN 'CACE-25-016671' THEN 374360
    WHEN 'CACE-25-016776' THEN 308280
    WHEN 'CACE-25-017735' THEN 450140
    WHEN 'CACE-25-017751' THEN 43970
    WHEN 'CACE-25-017780' THEN 369820
    WHEN 'CACE-25-019053' THEN 336830
    WHEN 'CACE-26-000191' THEN 466730
    WHEN 'CACE-26-000247' THEN 484570
    WHEN 'CACE-26-001078' THEN 109360
    WHEN 'CACE-26-002022' THEN 327100
    WHEN 'CACE-26-002686' THEN 310820
    WHEN 'CACE-26-004371' THEN 65940
    WHEN 'CACE-26-004611' THEN 348590
    WHEN 'COCE-25-034167' THEN 670170
    WHEN 'COCE-25-050854' THEN 238030
    WHEN 'COCE-25-084753' THEN 337470
    WHEN 'COCE-26-007332' THEN 133500
    WHEN 'COCE-26-012190' THEN 442350
    WHEN 'COCE-26-012931' THEN 276980
    WHEN 'CONO-21-003572' THEN 499060
    ELSE assessed_value
    END,
    market_value = CASE case_number
    WHEN 'CACE-09-033060' THEN 842500
    WHEN 'CACE-17-015398' THEN 1372250
    WHEN 'CACE-22-016620' THEN 481280
    WHEN 'CACE-23-014484' THEN 339800
    WHEN 'CACE-23-019709' THEN 456180
    WHEN 'CACE-24-006635' THEN 303630
    WHEN 'CACE-24-010844' THEN 215160
    WHEN 'CACE-24-014862' THEN 456190
    WHEN 'CACE-24-016110' THEN 166090
    WHEN 'CACE-24-018041' THEN 348570
    WHEN 'CACE-25-002663' THEN 497690
    WHEN 'CACE-25-007824' THEN 410640
    WHEN 'CACE-25-010076' THEN 207140
    WHEN 'CACE-25-010119' THEN 1710000
    WHEN 'CACE-25-011675' THEN 287700
    WHEN 'CACE-25-012902' THEN 206020
    WHEN 'CACE-25-012938' THEN 466610
    WHEN 'CACE-25-013181' THEN 361460
    WHEN 'CACE-25-014553' THEN 483770
    WHEN 'CACE-25-014566' THEN 493750
    WHEN 'CACE-25-014626' THEN 827580
    WHEN 'CACE-25-015235' THEN 470060
    WHEN 'CACE-25-015544' THEN 242180
    WHEN 'CACE-25-015545' THEN 238170
    WHEN 'CACE-25-015855' THEN 238170
    WHEN 'CACE-25-016509' THEN 266660
    WHEN 'CACE-25-016671' THEN 437420
    WHEN 'CACE-25-016776' THEN 308280
    WHEN 'CACE-25-017735' THEN 450140
    WHEN 'CACE-25-017751' THEN 109230
    WHEN 'CACE-25-017780' THEN 369820
    WHEN 'CACE-25-019053' THEN 336830
    WHEN 'CACE-26-000191' THEN 530530
    WHEN 'CACE-26-000247' THEN 484570
    WHEN 'CACE-26-001078' THEN 154070
    WHEN 'CACE-26-002022' THEN 569580
    WHEN 'CACE-26-002686' THEN 310820
    WHEN 'CACE-26-004371' THEN 190800
    WHEN 'CACE-26-004611' THEN 727020
    WHEN 'COCE-25-034167' THEN 670170
    WHEN 'COCE-25-050854' THEN 238030
    WHEN 'COCE-25-084753' THEN 337470
    WHEN 'COCE-26-007332' THEN 133500
    WHEN 'COCE-26-012190' THEN 442350
    WHEN 'COCE-26-012931' THEN 396490
    WHEN 'CONO-21-003572' THEN 842740
    ELSE market_value
    END,
    updated_at = now()
WHERE county='broward' AND case_number IN (
    'CACE-09-033060','CACE-17-015398','CACE-22-016620','CACE-23-014484','CACE-23-019709',
    'CACE-24-006635','CACE-24-010844','CACE-24-014862','CACE-24-016110','CACE-24-018041',
    'CACE-25-002663','CACE-25-007824','CACE-25-010076','CACE-25-010119','CACE-25-011675',
    'CACE-25-012902','CACE-25-012938','CACE-25-013181','CACE-25-014553','CACE-25-014566',
    'CACE-25-014626','CACE-25-015235','CACE-25-015544','CACE-25-015545','CACE-25-015855',
    'CACE-25-016509','CACE-25-016671','CACE-25-016776','CACE-25-017735','CACE-25-017751',
    'CACE-25-017780','CACE-25-019053','CACE-26-000191','CACE-26-000247','CACE-26-001078',
    'CACE-26-002022','CACE-26-002686','CACE-26-004371','CACE-26-004611','COCE-25-034167',
    'COCE-25-050854','COCE-25-084753','COCE-26-007332','COCE-26-012190','COCE-26-012931',
    'CONO-21-003572'
);

-- I fix: real BCPA parcel-polygon centroid geo (gisweb-adapters.bcpa.net ArcGIS "Parcels"
-- layer, FOLIO=484226091290, live queried 2026-08-23) for the one row where the numeric
-- BCPA folio format matched that layer's join key.
UPDATE multi_county_auctions
SET latitude = 26.258405090335167, longitude = -80.1195319132232, updated_at = now()
WHERE county='broward' AND case_number = 'CACE-23-014484';

-- J fix: 45 bid_decisions rows for the 45 broward case numbers with zero existing
-- bid_decisions row, generated via scripts/gold_standard_shard2_broward_j_dispatch_f6a6977d.py
-- (Shapira-v14 formula, real BCPA-value-grounded ARV for all 45 thanks to the I fix above).
-- The actual INSERT was executed by that script against the REST API (bulk POST to
-- /rest/v1/bid_decisions), not as raw SQL -- this migration documents the fix; the script is
-- the source of truth for the exact row shape and is committed alongside this file.
