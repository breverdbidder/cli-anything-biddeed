-- Gold Standard shard-5 (dispatch 66eb9c40-b05f-49b1-a8fa-33c8138bdd7f, loop run 9764):
-- bradford / manatee / baker. Ultraloop-verified (fallback mode: manual Task
-- fan-out + independent adversarial re-fetch per claim, no /effort ultracode
-- menu available in this session).
--
-- BEFORE (VERIFIED live via pencil_dod_evaluate_county, session start):
--   bradford: A=PASS(1) B=FAIL(null) C=PASS(100) D=PASS(100) E=PASS(100)
--     F=FAIL(null) G=PASS(100) H=PASS(1.4h) I=PASS(100) J=PASS(100). 8/10.
--   manatee:  A=PASS(8) B=PASS(100) C=FAIL(86.9,93/107) D=FAIL(86.9,93/107)
--     E=PASS(97.2,104/107) F=PASS(100) G=PASS(96.4) H=PASS(0.1h)
--     I=FAIL(84.1,90/107) J=PASS(100). 7/10.
--   baker:    A=PASS(8) B=PASS(100) C=FAIL(64.7,11/17) D=FAIL(64.7,11/17)
--     E=FAIL(64.7,11/17) F=PASS(100) G=PASS(100) H=PASS(0.1h)
--     I=FAIL(64.7,11/17) J=FAIL(88.2,15/17). 5/10.
--
-- BRADFORD (no action): all 5 rows auction_status='upcoming', zero
-- closed_sold -- B/F are structurally unmeasurable, not broken. Matches 7
-- prior reconfirm sessions (2026-07-25 through 2026-08-02). Nothing to fix
-- without a real courthouse/clerk sale closing.
--
-- BAKER (no action): live re-eval unchanged from yesterday's
-- 20260807h_gold_standard_shard5_5d40a513_baker_cdei_g_backfill.sql, which
-- confirmed the remaining 6 rows (4 case numbers: 022025CA000002CAAXMX,
-- 022025CA000117CAAXMX, 022025CA000124CAAXMX, 022025CC000132CCAXMX) are
-- source-exhausted -- RealAuction's own parcel-ID field renders a ghost
-- anchor ("Property Appraiser" link text, no href) with no address/owner
-- data at all for 3 of them, and 022025CA000117CAAXMX has been confirmed
-- off the docket entirely across 5 sessions since 2026-07-05. Re-scraping
-- would duplicate exhausted work; not attempted.
--
-- MANATEE (real fixes, all independently adversarially verified before
-- writing -- see gold_standard_ultraloop_audit rows for this dispatch):
--
--   1. GHOST-SUCCESS PURGE (E): case 412025CA001735CAAXMA carried
--      parcel_id = the literal string 'Property Appraiser' (a scraper
--      anchor-text artifact, not a real parcel) with parity_status=
--      'matched_clean' riding on it -- a false positive. Corrected both to
--      NULL. E dropped 97.2%->96.3% (104/107->103/107) -- still PASS, now
--      honest.
--
--   2. I (geo/value backfill, 13 rows): the 13 rows added to manatee's
--      scope since the 2026-08-01 session (auction_date 2026-08-05
--      through 2026-08-12) all had a real parcel_id but NULL lat/long.
--      Queried Manatee County's own ArcGIS FeatureServer
--      (mymanatee.org/gisits/rest/services/commonoperational/parcellines/
--      FeatureServer/0) by PARCEL_ID -- independent source, same one used
--      by the 2026-08-01 manatee I fix. All 13 returned an exact address
--      match against the address already on file (corroborating the
--      parcel match) plus native LAT/LON and ASSESVAL fields. Every one of
--      the 13 was independently re-fetched by a second agent (adversarial
--      verify) before writing -- 13/13 survived, 0 refuted.
--
--   3. I (zone linkage, 9 of 13 rows): parcel_zones INSERT restricted to
--      zone codes with an EXISTING zoning_districts row that is either
--      fully non-applicable to G (PD-R, PD-MU: far/pk1000/density all
--      false per v_zoning_district_applicability) or already carries a
--      real zone_standards density value (RMF-6=6.0, RSF-4.5=4.5,
--      RSF-6=6.0, RSMH-6=6.0 du/acre). Deliberately skipped BR_T4-R (2
--      rows -- density_applicable=true but zone_standards NULL, the exact
--      G-regression trap the 2026-08-01 manatee migration documented and
--      reverted) and BR_R-1/HB_R-3 (2 rows -- no zoning_districts row at
--      all; would require fabricating standards). G re-verified
--      96.4%->96.5% (improved, zero regression) after the write.
--
--   4. C/D (1 verified outcome): case 412025CA002881CAAXMA (auction_date
--      2026-08-05, already past) confirmed "Canceled per County" on
--      manatee.realforeclose.com's own DAYLIST calendar via Playwright
--      navigation (plain curl only returns the login splash page for this
--      platform) -- independently re-navigated and confirmed by a second
--      agent. auction_status corrected to 'canceled', parity_status=
--      'matched_clean'.
--
--   5. C/D (8 claims REFUTED, correctly NOT written): the same research
--      pass attempted to resolve the other 8 past-dated cases (2026-08-05/
--      08-06) via manatee.realforeclose.com's results report / DAYLIST,
--      but every one of those 8 specific status/dollar-amount claims could
--      NOT be independently reproduced by the adversarial verifier --
--      RealAuction requires an authenticated session for the results
--      report and the DAYLIST daily grid, and plain curl (even with
--      cookies/UA/referer) only returns the generic login splash page.
--      Zero rows written for these 8; they remain unresolved, flagged as a
--      residual for a session with REALFORECLOSE_EMAIL/PASSWORD-based
--      authenticated access (that pattern already exists in this repo, see
--      pinellas_cd_21row_parity_backfill.py, but requires Playwright +
--      those specific env vars, neither confirmed available in this
--      session's sandbox).
--
-- AFTER (VERIFIED live, same session, immediately after writing):
--   manatee: C=FAIL(87.9,94/107) D=FAIL(87.9,94/107) E=PASS(96.3,103/107,
--     honest correction) G=PASS(96.5, improved not regressed)
--     I=FAIL(92.5,99/107, up from 84.1%) all else unchanged.
--   bradford, baker: unchanged (see NO ACTION sections above).
--
-- Net: manatee 7/10 -> 7/10 (no letter crossed its threshold this session,
-- but I closed 9 of its 17-row gap and C/D closed 1 of 14 -- material
-- progress, not yet PASS). bradford 8/10, baker 5/10 unchanged (both
-- correctly reconfirmed source-exhausted / structurally blocked, not
-- idled past without checking).
--
-- ADVERSARIAL AUDIT TRAIL: 6 rows inserted live into
-- gold_standard_ultraloop_audit (dispatch_id=66eb9c40-b05f-49b1-a8fa-
-- 33c8138bdd7f) covering manatee I/C/E, bradford B, baker C.
--
-- SQL VERIFICATION (run 2026-08-08, this session, live REST RPC):
--   SELECT public.pencil_dod_evaluate_county('manatee');
--   SELECT public.pencil_dod_evaluate_county('bradford');
--   SELECT public.pencil_dod_evaluate_county('baker');
--   -- see BEFORE/AFTER blocks above, both captured live via the RPC.

-- Idempotent mirror of the live writes (safe to re-run; every write is a
-- targeted case_number UPDATE guarded by IS NULL, or an INSERT ... WHERE
-- NOT EXISTS). All writes were already executed live via the Supabase
-- Management API SQL endpoint during this session.

-- 1. Ghost-success purge.
UPDATE public.multi_county_auctions
SET parcel_id = NULL, parity_status = NULL, parity_source = NULL, parity_confidence = NULL, updated_at = now()
WHERE county = 'manatee' AND case_number = '412025CA001735CAAXMA' AND parcel_id = 'Property Appraiser';

-- 2. Geo/value backfill (13 rows, Manatee County ArcGIS parcellines FeatureServer).
UPDATE public.multi_county_auctions SET latitude=27.47954306, longitude=-82.63091456, assessed_value=COALESCE(assessed_value,136267), updated_at=now() WHERE county='manatee' AND case_number='412025CA002881CAAXMA' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude=27.49072403, longitude=-82.56789731, assessed_value=COALESCE(assessed_value,48769), updated_at=now() WHERE county='manatee' AND case_number='412025CA002295CAAXMA' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude=27.40413758, longitude=-82.37054951, assessed_value=COALESCE(assessed_value,1385608), updated_at=now() WHERE county='manatee' AND case_number='412025CA000932CAAXMA' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude=27.52417991, longitude=-82.52072848, assessed_value=COALESCE(assessed_value,105385), updated_at=now() WHERE county='manatee' AND case_number='412025CA001253CAAXMA' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude=27.42967454, longitude=-82.37750854, assessed_value=COALESCE(assessed_value,525776), updated_at=now() WHERE county='manatee' AND case_number='412025CA002910CAAXMA' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude=27.43056216, longitude=-82.61045736, assessed_value=COALESCE(assessed_value,445344), updated_at=now() WHERE county='manatee' AND case_number='412024CA000165CAAXMA' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude=27.4869211, longitude=-82.57757662, assessed_value=COALESCE(assessed_value,76109), updated_at=now() WHERE county='manatee' AND case_number='412025CA000662CAAXMA' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude=27.51244329, longitude=-82.711532, assessed_value=COALESCE(assessed_value,760967), updated_at=now() WHERE county='manatee' AND case_number='412024CA001563CAAXMA' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude=27.46228699, longitude=-82.66288558, assessed_value=COALESCE(assessed_value,150334), updated_at=now() WHERE county='manatee' AND case_number='412025CA002616CAAXMA' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude=27.42050269, longitude=-82.39849422, assessed_value=COALESCE(assessed_value,349854), updated_at=now() WHERE county='manatee' AND case_number='412025CC004086CCAXMA' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude=27.52862883, longitude=-82.54598681, assessed_value=COALESCE(assessed_value,95879), updated_at=now() WHERE county='manatee' AND case_number='412026CA001304CAAXMA' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude=27.44652759, longitude=-82.3610222, assessed_value=COALESCE(assessed_value,492300), updated_at=now() WHERE county='manatee' AND case_number='412025CA001812CAAXMA' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude=27.60881497, longitude=-82.49901359, assessed_value=COALESCE(assessed_value,222319), updated_at=now() WHERE county='manatee' AND case_number='412026CA000001CAAXMA' AND latitude IS NULL;

-- 3. Zone linkage (9 of 13 -- G-safe codes only, see narrative above).
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT v.parcel_id, v.jurisdiction_id, v.zone_code, v.zone_code, 'manatee_county_gis_arcgis_parcellines_live_20260808'
FROM (VALUES
  ('586320459', 1257, 'PD-MU'),
  ('897200002', 1257, 'RSMH-6'),
  ('581717009', 1257, 'PD-MU'),
  ('6147303454', 1257, 'RMF-6'),
  ('7503500352', 1257, 'RSF-4.5'),
  ('584363009', 1257, 'PD-MU'),
  ('785800004', 1257, 'RSF-6'),
  ('581117559', 1257, 'PD-R'),
  ('612134609', 1257, 'PD-MU')
) AS v(parcel_id, jurisdiction_id, zone_code)
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones pz WHERE pz.parcel_id = v.parcel_id);

-- 4. Verified outcome (1 row -- 8 other candidate claims refuted, not written).
UPDATE public.multi_county_auctions
SET auction_status='canceled',
    parity_status='matched_clean',
    parity_source='tier1_realforeclose_daylist:manatee:20260808_shard5_new_rows_verify',
    parity_confidence=0.95,
    parity_checked_at=now(), last_parity_check=now(), updated_at=now()
WHERE county='manatee' AND case_number='412025CA002881CAAXMA';
