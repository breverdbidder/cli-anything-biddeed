-- ARCHITECT TRIAGE #19760 for blocked issue #19743.
-- DoD: EXISTS(SELECT 1 FROM gold_standard_certifications WHERE county_slug =
-- ANY('{alachua,levy,santa_rosa,baker,martin}') AND certified). DoD was FALSE
-- at session start (all 5 certified=false; issue #19743's own CC GHA-only run
-- failed twice on Claude Code session/usage-limit exhaustion before doing any
-- diagnostic work -- last_error: none logged because no work ever ran).
--
-- LIVE DIAGNOSIS (loop_run_id 16429, pre-fix):
--   alachua 9/10 (I FAIL 93.5%, card_complete=87/93) -- all other letters PASS,
--     all 10 letters had fresh (<7d) survived=true rows in
--     gold_standard_ultraloop_audit, and both precert guards
--     (calendar_parity, denominator_integrity) already passing.
--   levy 9/10 (I FAIL 88.9%) but consecutive_non_gold=83 with additional
--     stale calendar_parity/denominator_integrity guard failures -- deeper
--     residual, out of scope for this session.
--   santa_rosa 9/10 (I FAIL 92.2%) -- investigated: ALL 129 rows have
--     zoning_code NULL end-to-end in v_auction_property_card; the real gap
--     behind the I metric is v_zoning_gold_standard_card parcel_id coverage,
--     not a handful of rows -- large genuine data gap, out of scope.
--   baker 8/10 (B/F FAIL, metric=null: verified=0 closed_sold=0) -- zero
--     closed sales exist yet, structurally unfixable until a real sale closes.
--   martin 8/10 (E/I FAIL) -- untouched, alachua was the clear highest-leverage
--     target (single letter, 2-of-93 gap, both already scraped).
--
-- ROOT CAUSE for alachua I (VERIFIED via pencil_dod_evaluate_county source,
-- migration 20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql):
-- card_complete requires address+geo+value present on multi_county_auctions
-- AND parcel_id present in v_zoning_gold_standard_card (i.e. a row in
-- public.parcel_zones with non-null zone_code for that parcel/jurisdiction).
-- It does NOT read multi_county_auctions.zoning_code or the
-- v_auction_property_card zoning columns directly (those are a separate,
-- looser-joined display path) -- this is a real definitional gap between
-- pencil_dod_criteria.measures' plain-English description ("v_auction_property_card
-- ... zoning_code") and the actual SQL, which explains why prior sessions'
-- zoning fixes had to write into parcel_zones (see the flagler/lake/hernando
-- precedent migrations), not zoning_code columns.
--
-- Of alachua's 6 incomplete active rows, 3 had real address+geo+value+parcel_id
-- but NULL zone_code; of those 3, exactly 2 already had a real, high-confidence,
-- previously-scraped zoning value sitting unused in public.zoning_assignments
-- (source=county_gis_alachua_arcgis, zone_confidence=high, scraped 2026-08-15)
-- that had simply never been bridged into parcel_zones:
--   06650-108-015 -> unincorporated_alachua_county -> jurisdiction_id 1404,
--     zone_code R-3 (zoning_districts id 13419 "Residential Multi-Family (R-3)"
--     already exists for this jurisdiction -- no new district row needed)
--   06125-018-000 -> unincorporated_alachua_county -> jurisdiction_id 1404,
--     zone_code PD (zoning_districts id 13416 "Planned Development (PD)"
--     already exists -- no new district row needed)
-- (A 3rd row, 17251-014-006/Waldo, also has real zoning_assignments data but
-- Waldo has zero zoning_districts rows and the source value is a plain-English
-- name ("Residential Medium Density") rather than a code -- left untouched
-- since the other 2 rows alone are sufficient to clear the 95% bar; not a
-- fabrication risk either way, just unnecessary for this DoD.)
--
-- These 2 rows lift alachua I from 87/93 (93.5%, FAIL) to 89/93 (95.7%, PASS)
-- -- VERIFIED live via pencil_dod_evaluate_county('alachua') immediately
-- after the insert, pasted below. All other 9 letters unchanged (still PASS).
--
-- Zero data mutation to any other row. Zero schema DDL. No cron jobs
-- (109/111/115/gold-standard-loop-*) modified.

SET statement_timeout = 0;

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '06650-108-015', 1404, 'R-3', 'Residential Multi-Family (R-3)',
       'zoning_assignments backfill (county_gis_alachua_arcgis, high confidence, scraped 2026-08-15) -- architect triage issue 19760/19743'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones WHERE parcel_id = '06650-108-015' AND jurisdiction_id = 1404
);

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '06125-018-000', 1404, 'PD', 'Planned Development (PD)',
       'zoning_assignments backfill (county_gis_alachua_arcgis, high confidence, scraped 2026-08-15) -- architect triage issue 19760/19743'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones WHERE parcel_id = '06125-018-000' AND jurisdiction_id = 1404
);

-- AFTER (VERIFIED live via pencil_dod_evaluate_county('alachua') post-fix):
--   I: card_complete 87/93 (93.5%) -> 89/93 (95.7%), FAIL -> PASS.
--   A-J all PASS at loop_run_id 16496 and again at 16497 (2 independent
--   fleet-wide gold_standard_loop() runs, both re-confirming alachua 10/10).
--
-- gold_standard_certify() requires, beyond 10/10: >=1 survived=true row per
-- letter in gold_standard_ultraloop_audit within 7 days (alachua already had
-- all 10, last dated 2026-08-27 through 2026-08-31 -- untouched this session),
-- both precert guards fresh within 7 days (alachua already passing both,
-- last dated 2026-09-01 -- untouched this session), AND 2 CONSECUTIVE
-- gold-run calls to flip consecutive_gold 0->2. Ran gold_standard_loop() +
-- gold_standard_certify() twice this session (loop_run_id 16496 then 16497)
-- to accrue that hysteresis, re-confirming alachua still 10/10 between calls.
-- Both certify() calls returned revoked_now=0 -- the pre-existing "blocked"
-- counties (collier, dixie, franklin, gilchrist, hardee, leon, pinellas) were
-- already revoked before this session (revoked_at timestamps predate both
-- calls) and this session caused zero collateral revocations, unlike the
-- 20260902r st_johns triage precedent.
--
-- DoD SQL re-executed live post-fix and read back TRUE:
--   gold_standard_certifications: alachua certified=true, consecutive_gold=2,
--   revoked_at=NULL, last_verified_run=16497.
--
-- OUT-OF-SCOPE FINDING (flagged, not fixed -- different table, not named in
-- this issue, M5/M2 scope discipline): public.rls_gate_check() reports ONE
-- new (non-baseline) RLS violation, public.fl_parcel_appraiser_accounts
-- anon_policy, present both before and after this session's changes (this
-- session touched only public.parcel_zones, which already had RLS enabled
-- pre-session). This will fail the ship-to-main rls_gate step for the NEXT
-- unrelated GHA session on this repo until someone adds an RLS policy /
-- removes the anon grant on that table. Logged to decision_log; not touched
-- here per M5 (schema/policy change to a table not named in this issue).
