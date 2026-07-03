-- SHARD-13: escambia/polk/pinellas/bradford — 2026-07-03 session (loop run 2753)
-- dispatch_id: bdd45e66-a630-4279-95d9-6b60418710bc
-- Session: architect-20260703T160000
-- ultraloop_mode: native (Workflow tool — 2 parallel diagnose agents + 3 parallel adversarial
-- refuters; gold_standard_ultraloop_audit ids 3157-3161)
--
-- ENVIRONMENT CONSTRAINT (matches every other shard session today): direct psql/psycopg2 auth
-- fails in this sandbox. All reads/writes below via the Supabase Management API
-- (POST /v1/projects/mocerqjnksmhcjzxrewo/database/query, Bearer SUPABASE_ACCESS_TOKEN) and
-- PostgREST (SUPABASE_SERVICE_ROLE_KEY).
--
-- =====================================================================================
-- 1) POLK — C/D real gain via realforeclose_aids case-number matches
-- =====================================================================================
-- Found 19 exact-normalized-case_number matches between polk's currently-unmatched
-- multi_county_auctions rows and realforeclose_aids (82 polk rows available). An adversarial
-- refuter agent independently re-derived the join and additionally cross-checked each
-- candidate's EXISTING property_address on the mca row against realforeclose_aids' address for
-- the same case_number (a check the initial diagnosis did not perform). This caught 8 candidates
-- where the case_number matched but the mca row already carried a DIFFERENT, conflicting street
-- address than realforeclose_aids reports for that case (parcel_id only matched on the ambiguous
-- 12-digit county/plat prefix, not the full 18-digit parcel) -- these are NOT safe to classify as
-- matched_clean without manual resolution of which address is authoritative, and were rejected.
-- 11 of 19 survived: exact case_number match, consistent street address AND/OR exact full
-- 18-digit parcel_id match on both sides, genuine terminal auction_status (completed/cancelled),
-- no placeholder parcel_id ("Property Appraiser"/"MULTIPLE PARCELS" sentinel values excluded from
-- consideration up front).
--
-- REJECTED (not applied, flagged for a future session with a way to resolve the address
-- conflict -- e.g. re-scrape the mca row's own source to confirm which address is current):
--   2023CA005714000000, 2024CA000544000000, 2024CA001566000000, 2024CA001934000000,
--   2024CC006028000000, 2025CA000713000000, 2025CC007137A000BA, 2025CC007400A000BA
--
-- VERIFIED via pencil_dod_evaluate_county('polk') before/after -- see closing session summary.
--
-- =====================================================================================
-- 2) BRADFORD — I-criterion honesty fix: revert fabricated placeholder valuation
-- =====================================================================================
-- Bradford's 4 real multi_county_auctions rows (inserted 2026-07-03 11:32:51 by
-- 20260703_shard3_bradford_real_foreclosure_ingestion_and_taxdeed_zero_confirmed.sql with real
-- case_number/judgment_amount/plaintiff data from a verified clerk source) were found at
-- updated_at=2026-07-03 16:40:34 to carry assessed_value=145000 and market_value=152250.0
-- IDENTICAL across all 4 distinct properties -- the same "identical value across distinct rows"
-- signature already flagged twice today for bradford fabrication (see
-- 20260703_shard5_bradford_ghost_success_revert_columbia_orphan_cleanup.sql and the hamilton
-- revert in 20260703_shard3_hamilton_ghost_success_revert_pasco_i_fix_bradford_discovery.sql).
--
-- ROOT CAUSE (independently confirmed by an adversarial refuter, not just the diagnose agent):
-- scripts/shard4_run472_main_executor.py, phase_i_property_cards (Phase 4, ~lines 258-295),
-- contains a hardcoded county_median dict with 'bradford': 145000, documented in its own
-- docstring as "FL county median assessed values (INFERRED from 2023 FL DOR data)" -- a
-- statewide guess constant, NOT a per-parcel appraisal. The script bulk-PATCHes every row in a
-- county WHERE assessed_value IS NULL with this single constant and sets
-- market_value = round(145000 * 1.05, 2) = 152250.0, matching the observed value exactly and
-- mathematically confirming provenance. The script's own log line falsely tags this as
-- "[VERIFIED]" when it is actually an unlabeled INFERRED guess -- a Honesty Protocol violation
-- in the source script itself (flagged here, NOT fixed this session -- out of scope; the script
-- will re-corrupt these same rows if re-run against bradford before it is fixed or disabled).
--
-- assessed_value_source was NULL (not tagged per the campaign's established INFERRED-value
-- convention, e.g. pasco's judgment_amount*0.75 pattern), and no genuine per-parcel source
-- (BCPA/appraiser) was found for these 4 Bradford properties this session (realforeclose_aids
-- has zero Bradford rows; Bradford is not a RealAuction tenant per prior discovery). BLANK >
-- WRONG: reverted to NULL rather than keep or re-guess. Zero metric regression -- criterion I
-- was already FAIL (card_complete=0 of 4) due to missing parcel_id/address/geo regardless of
-- assessed_value, confirmed by evaluator re-run showing an unchanged scorecard.
--
-- VERIFIED via pencil_dod_evaluate_county('bradford') before/after -- see closing session
-- summary. Both actions logged to gold_standard_ultraloop_audit (ids 3157-3161, all
-- survived=true).
--
-- NOT DONE / left honestly open:
--   - pinellas C/D (91.0%, matched_clean=343/377): diagnose + independent verify both confirmed
--     zero additional safe matches exist in realforeclose_aids for the residual 24-row gap.
--     Genuine data ceiling -- closing it needs either a fresh realforeclose_aids harvest run
--     targeting missed auction dates, or a tax-deed-specific tier1 source (only 24 of 431
--     distinct realforeclose_aids pinellas cases are TAXDEED).
--   - pinellas B (37.9%, verified=50/132): confirmed no harvestable independent source exists in
--     this repo today. realforeclose_aids is a PRE-auction listing scrape (no outcome field,
--     structurally incapable of supplying B). scripts/shard2_verified_outcomes.py's
--     pinellasclerk.org scraper is an unimplemented stub that would fabricate data if run.
--     Needs a real authenticated RealForeclose/RealTaxDeed result-page harvester or true clerk
--     court-records scraping -- infrastructure build, out of scope for this session.
--   - escambia C/D (3.4%, matched_clean=9/266): confirmed structural block. 245 of 266 escambia
--     auctions are tax-deed (92%); no tax-deed tier1 litmus table exists fleet-wide (same gap
--     independently found for santa_rosa by the parallel SHARD-14 RUN2753 session today). The 6
--     unmatched foreclosure-lane rows do not case-match any of the 32 available realforeclose_aids
--     escambia rows. Needs a realtaxdeed_aids-equivalent harvester (does not exist yet) or a
--     realforeclose_aids re-harvest that covers escambia's specific missing auction dates.
--
-- Applied live via Supabase Management API before this file was committed -- this migration
-- documents and reproduces the changes for repo history / future audits.

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1_realforeclose_polk',
    parity_checked_at = now(),
    updated_at = now()
WHERE county = 'polk'
  AND case_number IN (
    '2018CA003775000000','2023CA006222000000','2024CA000954000000','2024CA001420000000',
    '2024CA003420000000','2024CA003515000000','2024CA003657000000','2024CA004488000000',
    '2024CA004773000000','2025CA000677000000','2025CA002154A000BA'
  );

UPDATE multi_county_auctions
SET assessed_value = NULL,
    market_value = NULL,
    updated_at = now()
WHERE county = 'bradford'
  AND id IN (
    '2fb112bd-a170-4a35-87a8-4ad003f853ed','64f76e07-85ba-4d68-880b-7207f89f9470',
    '7b7d7ff2-3f4e-4678-b4db-61585b463b3a','fa1d1ae8-7c64-4973-a158-9d7563426011'
  );

-- Verification
SELECT public.pencil_dod_evaluate_county('polk');
SELECT public.pencil_dod_evaluate_county('bradford');
SELECT public.pencil_dod_evaluate_county('pinellas');
SELECT public.pencil_dod_evaluate_county('escambia');
