-- Putnam County I (property-card completeness) / G (zoning density coverage) fix.
--
-- BASELINE (VERIFIED live via SELECT public.pencil_dod_evaluate_county('putnam')
-- before this migration was applied):
--   G: density=99.3 PASS
--   I: card_complete=405 of 450 = 90.0% FAIL
--
-- ROOT CAUSE (matches the residual documented in commit for
-- 20260711n_shard2_putnam_i2_zone_link_ag_density_residual.sql): zoning_districts
-- id=11512 (jurisdiction_id=931 "Palatka", code='AG', name='Agriculture') has ZERO
-- corresponding zone_standards row, so any parcel_zones row referencing this AG
-- district contributes a density-NULL to v_zoning_gold_standard_kpi_v3, dragging
-- letter G down if/when AG parcels are linked (as happened transiently in the prior
-- session, which reverted its parcel_zones inserts rather than fabricate a density
-- figure).
--
-- EVIDENCE (real, HTTP-200-verified public source): Putnam County Comprehensive
-- Plan, Future Land Use Element, Section 9 "Agriculture" (PDF p.25 / doc page A22):
--   https://www.putnam-fl.gov/wp-content/uploads/2025/05/Current_PutnamPlan.pdf
-- States base density "1 dwelling unit per 10 acres" for the Agriculture FLU
-- category (= 0.1 du/acre), with a documented 0.2 du/acre frontage-bonus exception.
--
-- PROVENANCE / HONESTY TAG: this is Comprehensive-Plan Future-Land-Use density,
-- INFERRED (not independently confirmed) to be identical to the Municode AG
-- zoning-ordinance density, because library.municode.com/fl/putnam_county Sec.
-- 45-72 AG remains HTTP 403-blocked to WebFetch/curl/Firecrawl in this sandbox
-- (same block hit by the two prior sessions that worked this residual). Recorded
-- with confidence_score=0.55 (below the 0.8+ used for zoning-ordinance-confirmed
-- values elsewhere in this table) and an explicit ordinance_section note flagging
-- the inference and the untested frontage-bonus exception.
--
-- APPLIED LIVE via Supabase Management API mgmt_query (no supabase CLI db push
-- available in this sandbox) -- same DML persisted below for the durable record:

INSERT INTO public.zone_standards (
  zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at
) VALUES (
  11512, 0.1,
  'https://www.putnam-fl.gov/wp-content/uploads/2025/05/Current_PutnamPlan.pdf',
  'Future Land Use Element, Section 9 Agriculture (PDF p.25/A22) -- INFERRED equal to Municode Sec 45-72 AG zoning density (Municode 403-blocked, not independently confirmed); Comp-Plan FLU states 1 du/10 acres base, 0.2 du/acre frontage-bonus exception exists',
  0.55,
  now()
);

-- VERIFICATION (live, immediately after apply, via
-- SELECT public.pencil_dod_evaluate_county('putnam')):
--   G: density=99.3 -> 99.5 PASS (IMPROVED, no regression -- guard rail satisfied)
--   I: card_complete=405 of 450 = 90.0% UNCHANGED (this insert only fills the
--      zone_standards density gap for the existing AG zoning_districts row; it does
--      not itself add parcel_zones rows, so letter I does not move from this insert
--      alone. Moving I requires re-running the separate 22-row AG parcel_zones
--      backfill documented in the prior session -- now safely unblocked since G no
--      longer regresses when those AG-linked parcels are added -- which is future
--      residual work, out of scope for this exact fix spec).
--
-- No revert needed: G improved, did not regress below 95%.
