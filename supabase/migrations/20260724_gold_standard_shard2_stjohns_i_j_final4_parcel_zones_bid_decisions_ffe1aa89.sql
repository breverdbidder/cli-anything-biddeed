-- Gold Standard shard-2 (dispatch ffe1aa89-758e-42a2-8ac2-73ceeee9d290, loop
-- run 6080): st_johns C/D/E/I/J final-4-row closeout. Documents the actual
-- SQL applied live via the Management API SQL endpoint / REST during this
-- session (this file mirrors those calls for the repo record; the live
-- effect already happened during this session).
--
-- BASELINE AT SESSION START (live pencil_dod_evaluate_county('st_johns')):
--   A/B/F/G/H already PASS. C/D/E were ALSO already PASS at 100.0 (50/50) --
--   the brief's 92.0 numbers for C/D/E had already drifted since it was
--   written: a prior/concurrent process had enriched the 4 named stub rows
--   (CA22-1233, CA25-1470, CC25-0048, CC25-2919) with real, DISTINCT
--   parcel_id/property_address/lat/long/assessed_value and run
--   refresh_parity_tier1_outcomes('st_johns') producing
--   parity_status=matched_clean/parity_source=tier1_realforeclose_aids_st_johns
--   for all 4, before this session began. Verified live via direct SELECT --
--   no C/D/E fix needed, logged as re-verified-PASS in
--   gold_standard_ultraloop_audit.
--   Only I (92.0, 46/50) and J (92.0, 46/50) were still genuinely failing,
--   both blocked by the exact same 4 case_numbers.
--
-- ROOT CAUSE I: those 4 parcels (0288211410, 2881031960, 1821410080,
-- 0615191110) had ZERO rows in parcel_zones -- a real zoning-coverage gap
-- (parcel never ingested into that table for st_johns), not a join-key
-- mismatch. v_zoning_gold_standard_card.zone_code was therefore NULL for
-- all 4, failing I's card-completeness check.
--
-- FIX I: queried St Johns County's official ArcGIS Zoning MapServer
-- (https://www.gis.sjcfl.us/portal_sjcgis/rest/services/Zoning/MapServer/0
-- -- note: gis.sjcfl.us without "www." does not resolve from this
-- environment, "www.gis.sjcfl.us" does; discovered via
-- https://www.sjcfl.us/GIS/ page links) with a point-in-polygon query on
-- each parcel's own real lat/long already stored in multi_county_auctions:
--   CA22-1233 / 0288211410 (1201 MACLAREN ST)    -> ZONING=PUD  (OBJECTID 1366)
--   CA25-1470 / 2881031960 (1848 ENTERPRISE AVE) -> ZONING=PUD  (OBJECTID 1366, same large PUD polygon)
--   CC25-0048 / 1821410080 (129 KING ARTHUR CT)  -> ZONING=PUD  (OBJECTID 1262)
--   CC25-2919 / 0615191110 (129 OAK VIEW CIR)    -> ZONING=RG-1 (OBJECTID 1543)
-- Independently cross-verified against the same GIS host's Parcel/MapServer/0
-- layer by STRAP: querying STRAP='<parcel_id>' returned an EXACT PRP_ADDR
-- match for all 4 parcels (e.g. STRAP=0288211410 -> PRP_ADDR="1201 MACLAREN
-- ST"), confirming the lat/long used for the zoning point-in-polygon query
-- genuinely correspond to the correct parcels (adversarial refuter check).
-- Jurisdiction: 1364 ("Unincorporated St. Johns County") -- same jurisdiction
-- used by the prior 2-parcel PUD fix earlier in this same dispatch
-- (20260724_gold_standard_shard2_stjohns_i_parcel_zones_backfill.sql).
--
-- SIDE EFFECT ON G (discovered, then fixed in the same pass): inserting the
-- new RG-1 parcel_zones row initially regressed G from PASS(density=100.0
-- far=100.0 pk1000=blank) to FAIL(density=97.1 far=96.8 pk1000=0.0), because
-- RG-1 had no zoning_districts row for jurisdiction 1364, so
-- v_zoning_district_applicability defaulted far_applicable/pk1000_applicable/
-- density_applicable all to TRUE (no override) with no zone_standards to
-- satisfy them. Fixed by inserting a REAL zoning_districts + zone_standards
-- row for RG-1 sourced from the St. Johns County Land Development Code,
-- Table 6.01 "Schedule of Area, Height, Bulk and Placement Standards"
-- (Article VI, https://www.sjcfl.us/wp-content/uploads/2024/01/article-vi.pdf,
-- effective 2026-01-12): RG-1 SF Dwellings row states min lot width 75ft,
-- min lot area 7,500 sqft, max lot coverage 25%, Floor Area Ratio = "N/A"
-- (explicitly, matching every other residential row in the same table),
-- impervious surface ratio 70%, front/side/rear setback 25/8/10ft, max
-- height 35ft. max_density_du_acre and parking_per_1000sf are NOT published
-- in this table for ANY residential district (same true gap already present
-- for RS-3/OR in the DB) -- left NULL rather than inferred/computed, per the
-- fail-loud invariant. Once inserted, the view's rule-based applicability
-- (v_zoning_district_applicability, keyed off category='residential') auto-
-- derived far_applicable=false and pk1000_applicable=false for RG-1 (FAR
-- explicitly N/A in the ordinance; matches every existing residential
-- district in jurisdiction 1364), restoring G to PASS at 97.1 (density is
-- the one disclosed, still-real gap: RG-1's max_density_du_acre remains
-- unpublished in the source found this session).
--
-- ROOT CAUSE J: same 4 case_numbers had ZERO rows in bid_decisions -- the
-- J-generator had simply never run for them (their parcel/parity enrichment
-- landed after the last st_johns J-backfill pass, which explicitly excluded
-- them as "CAPTCHA/403-gated, zero indexed data" -- true at the time, no
-- longer true once this session's independent GIS-based enrichment closed
-- the underlying data gap; see script header for the specific stale
-- assumption being corrected).
--
-- FIX J: inserted bid_decisions rows using the existing house formula/
-- contract (arv_source=shapira_formula_stjohns_j_backfill_broker1_county_
-- median, pipeline_version=stjohns_j_backfill_v1 -- same contract as the
-- 2026-07-10, 2026-07-18, and earlier-in-this-dispatch st_johns J backfills,
-- scripts/stjohns_j_backfill_run6080_shard2_ffe1aa89.py), this time
-- correctly using each row's REAL, DISTINCT, verified assessed_value
-- (137006.00 / 365713.00 / 260374.00 / 629231.00 -- confirmed live NOT the
-- 200000 flat placeholder default that other st_johns rows carry) as the ARV
-- base, since prior runs had to null out assessed_value specifically because
-- it WAS that placeholder for the rows they processed. All 5 required
-- factor keys present (distress_location, distress_property, distress_owner,
-- cma_distressed, cma_resale) plus arv+max_bid+ml_score, satisfying J's
-- deal_complete check exactly.
--
-- HONESTY FLAG (flagged per task instruction, NOT fixed -- out of this
-- session's C/D/E/I/J scope): 15 of 50 st_johns rows (30%) carry
-- assessed_value=200000 identically, assessed_value_source IS NULL for all
-- of them. This spans rows with real, distinct property_address/parcel_id
-- (not bare stubs) -- e.g. CA25-0475 (6445 PINE CIR), CA26-0218 (742 PULLMAN
-- CIR) -- meaning some backfill/enrichment path stamped a flat 200000
-- default onto assessed_value independent of case-completeness. This is a
-- materially larger footprint than the 4 case numbers this session was
-- dispatched to fix (none of which turned out to still have this placeholder
-- by session start). INFERRED (not directly confirmed this session, since
-- the 4 named rows no longer exhibited the pattern by the time this session
-- queried them) that calendar_sweep_mca_v3 or a related backfill writes a
-- hardcoded 200000/29.8943 default on initial insert, based on the brief's
-- description of the original 4-row pattern and this session's confirmation
-- that the identical-200000 pattern recurs elsewhere in st_johns. Did not
-- verify scraper source code this session -- out of scope, flagged only.
--
-- RESULT (live pencil_dod_evaluate_county('st_johns') before/after):
--   BEFORE: C=100.0 PASS | D=100.0 PASS | E=100.0 PASS (already passing,
--           drifted since brief) | I=92.0 (46/50) FAIL | J=92.0 (46/50) FAIL
--   AFTER:  C=100.0 PASS | D=100.0 PASS | E=100.0 PASS (unchanged) |
--           I=100.0 (50/50) PASS | J=100.0 (50/50) PASS
--   G: transiently regressed to FAIL as a side effect of the I fix, then
--      restored to PASS (97.1) in the same session pass -- see above.
--   st_johns is now 10/10 ALL PASS.
--
-- This file is a documentation-only record of SQL already applied live via
-- the Management API SQL endpoint. Re-running it is safe/idempotent (all
-- statements are the same idempotent WHERE NOT EXISTS patterns used
-- elsewhere in this campaign) but not required.
-- ============================================================================

SET statement_timeout = 0;

-- (1) real zone_code for the 4 final I-gap parcels
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT v.parcel_id, 1364, v.zone_code, v.zone_name, 'gis.sjcfl.us_arcgis:shard2_run6080_ffe1aa89'
FROM (VALUES
  ('0288211410', 'PUD', 'Planned Unit Development'),
  ('2881031960', 'PUD', 'Planned Unit Development'),
  ('1821410080', 'PUD', 'Planned Unit Development'),
  ('0615191110', 'RG-1', 'Residential, General')
) AS v(parcel_id, zone_code, zone_name)
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones pz WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = 1364
);

-- (2) real RG-1 district + standards (St Johns LDC Table 6.01, Article VI,
-- effective 2026-01-12) -- fixes the G side effect from (1)
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, ordinance_section, effective_date)
SELECT 1364, 'RG-1', 'Residential, General', 'residential', 'Table 6.01 (Article VI)', '2026-01-12'
WHERE NOT EXISTS (SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id=1364 AND code='RG-1');

INSERT INTO public.zone_standards (zoning_district_id, min_lot_sqft, min_lot_width_ft, max_lot_coverage_pct, max_impervious_pct, front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft, source_url, ordinance_section, effective_date)
SELECT d.id, 7500, 75, 25, 70, 25, 8, 10, 35,
       'https://www.sjcfl.us/wp-content/uploads/2024/01/article-vi.pdf', 'Table 6.01', '2026-01-12'
FROM public.zoning_districts d
WHERE d.jurisdiction_id=1364 AND d.code='RG-1'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards s WHERE s.zoning_district_id = d.id);

-- (3) real bid_decisions rows for the 4 final J-gap cases (see
-- scripts/stjohns_j_backfill_run6080_shard2_ffe1aa89.py for the formula
-- source; values below are that script's actual computed output)
INSERT INTO public.bid_decisions
  (case_number, county_slug, parcel_id, address, auction_date, arv, repairs, max_bid,
   bid_judgment_ratio, ml_score, factors, recommendation, confidence, arv_source, pipeline_version)
SELECT v.case_number, v.county_slug, v.parcel_id, v.address, v.auction_date::date, v.arv, v.repairs, v.max_bid,
       v.bid_judgment_ratio, v.ml_score, v.factors, v.recommendation, v.confidence, v.arv_source, v.pipeline_version
FROM (VALUES
  ('CA22-1233', 'st_johns', '0288211410', '1201 MACLAREN ST', '2026-09-17', 138980.00, 25000.00, 41439.00, 0.5963, 0.7500,
   '{"model": "shapira_v14", "cma_resale": {"note": "retail resale arm — real county-appraiser assessed_value as ARV base (verified live, distinct per parcel), not per-parcel comp", "value": 138980.0, "honesty_marker": "VERIFIED_INPUT_INFERRED_ARV"}, "distress_owner": {"note": "judicial action filed", "score": 7.0, "honesty_marker": "INFERRED"}, "cma_distressed": {"note": "distressed comp arm", "value": 118133.0, "honesty_marker": "INFERRED"}, "distress_location": {"note": "st_johns county FL — coastal, St Augustine/Ponte Vedra area", "score": 7.5, "honesty_marker": "INFERRED"}, "distress_property": {"note": "foreclosure distress", "score": 5.0, "honesty_marker": "INFERRED"}}'::jsonb,
   'BID', 0.5, 'shapira_formula_stjohns_j_backfill_broker1_county_median', 'stjohns_j_backfill_v1'),
  ('CA25-1470', 'st_johns', '2881031960', '1848 ENTERPRISE AVE', '2026-09-24', 365713.00, 20000.00, 200999.10, 1.0992, 0.7500,
   '{"model": "shapira_v14", "cma_resale": {"note": "retail resale arm — real county-appraiser assessed_value as ARV base (verified live, distinct per parcel), not per-parcel comp", "value": 365713.0, "honesty_marker": "VERIFIED_INPUT_INFERRED_ARV"}, "distress_owner": {"note": "judicial action filed", "score": 7.0, "honesty_marker": "INFERRED"}, "cma_distressed": {"note": "distressed comp arm", "value": 310856.05, "honesty_marker": "INFERRED"}, "distress_location": {"note": "st_johns county FL — coastal, St Augustine/Ponte Vedra area", "score": 7.5, "honesty_marker": "INFERRED"}, "distress_property": {"note": "foreclosure distress", "score": 5.0, "honesty_marker": "INFERRED"}}'::jsonb,
   'BID', 0.5, 'shapira_formula_stjohns_j_backfill_broker1_county_median', 'stjohns_j_backfill_v1'),
  ('CC25-0048', 'st_johns', '1821410080', '129 KING ARTHUR CT', '2026-08-20', 260374.00, 20000.00, 127261.80, 0.9775, 0.7500,
   '{"model": "shapira_v14", "cma_resale": {"note": "retail resale arm — real county-appraiser assessed_value as ARV base (verified live, distinct per parcel), not per-parcel comp", "value": 260374.0, "honesty_marker": "VERIFIED_INPUT_INFERRED_ARV"}, "distress_owner": {"note": "judicial action filed", "score": 7.0, "honesty_marker": "INFERRED"}, "cma_distressed": {"note": "distressed comp arm", "value": 221317.9, "honesty_marker": "INFERRED"}, "distress_location": {"note": "st_johns county FL — coastal, St Augustine/Ponte Vedra area", "score": 7.5, "honesty_marker": "INFERRED"}, "distress_property": {"note": "foreclosure distress", "score": 5.0, "honesty_marker": "INFERRED"}}'::jsonb,
   'BID', 0.5, 'shapira_formula_stjohns_j_backfill_broker1_county_median', 'stjohns_j_backfill_v1'),
  ('CC25-2919', 'st_johns', '0615191110', '129 OAK VIEW CIR', '2026-08-20', 629231.00, 15000.00, 390461.70, 1.2411, 0.7500,
   '{"model": "shapira_v14", "cma_resale": {"note": "retail resale arm — real county-appraiser assessed_value as ARV base (verified live, distinct per parcel), not per-parcel comp", "value": 629231.0, "honesty_marker": "VERIFIED_INPUT_INFERRED_ARV"}, "distress_owner": {"note": "judicial action filed", "score": 7.0, "honesty_marker": "INFERRED"}, "cma_distressed": {"note": "distressed comp arm", "value": 534846.35, "honesty_marker": "INFERRED"}, "distress_location": {"note": "st_johns county FL — coastal, St Augustine/Ponte Vedra area", "score": 7.5, "honesty_marker": "INFERRED"}, "distress_property": {"note": "foreclosure distress", "score": 5.0, "honesty_marker": "INFERRED"}}'::jsonb,
   'BID', 0.5, 'shapira_formula_stjohns_j_backfill_broker1_county_median', 'stjohns_j_backfill_v1')
) AS v(case_number, county_slug, parcel_id, address, auction_date, arv, repairs, max_bid,
       bid_judgment_ratio, ml_score, factors, recommendation, confidence, arv_source, pipeline_version)
WHERE NOT EXISTS (SELECT 1 FROM public.bid_decisions bd WHERE bd.case_number = v.case_number);

-- Verification: SELECT public.pencil_dod_evaluate_county('st_johns');
-- Expected: 10/10 ALL PASS, I=100.0 (50/50), J=100.0 (50/50), G=97.1 PASS
-- (density metric carries one disclosed real gap: RG-1's max_density_du_acre
-- is not published in the Table 6.01 source found this session).
