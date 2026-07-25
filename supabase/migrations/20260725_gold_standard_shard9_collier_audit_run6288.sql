-- Gold Standard shard-9, dispatch 24d13132-b46a-4dd9-82e6-27972d9aa712, run 6288
-- collier — 6th session. No DB metric changes applied. Ultraloop audit rows only.
--
-- BEFORE (verified via issue brief run 6288 — no live query tool available in this
-- GHA execution context; the issue brief reflects the gold_standard_loop run at
-- 07:30Z which queries pencil_dod_evaluate_county directly):
--   A: pass=false, metric=0,   fc=0, td=212
--   G: pass=false, metric=0.0, density=100.0, far=0.0, pk1000=<null>
--   B/C/D/E/F/H/I/J: all pass
--
-- STATE SUMMARY (from 5 prior sessions, all VERIFIED in committed session reports):
--
-- LETTER A (fc=0):
--   The ONLY Collier tax-deed source (collierclerk.com Laserfiche WebLink) is already
--   wired and running daily (gold-standard-collier-taxdeed-laserfiche.yml). It has
--   produced td=212 rows that are the ENTIRETY of the county's online footprint.
--   Foreclosure sales are in-person at the courthouse (3315 Tamiami Trail East,
--   Naples FL 34112) — cor.collierclerk.com/coraccess/ requires Blazor Server SignalR
--   + reCAPTCHA, NO REST surface reachable without full browser JS execution.
--   Both collier.realforeclose.com and collier.realtaxdeed.com redirect unconditionally
--   to http://www.realauction.com (deprovisioned vendor account) — confirmed 2026-07-03,
--   2026-07-18, 2026-07-20, 2026-07-24. Prior sessions also tried:
--     - collierclerk.com ShowCase (cms.collierclerk.com/showcaseweb/) — AngularJS SPA
--       with Google reCAPTCHA v3, all probed API paths return the 27KB SPA shell only
--     - app.collierclerk.com/LFOfficialRecords/ — WebLink 11 Angular SPA; REST repo
--       GUID is resolved at client-side runtime, not guessable via plain httpx
--     - WordPress events iCal/RSS on collierclerk.com — generic clerk-office events,
--       not auction listings
--   ACTION: None. No online FC source exists. A is correctly FAIL with fc=0.
--   This is a sourcing gap (in-person-only county), not a data-quality gap.
--
-- LETTER G (far=0.0):
--   density=100.0: VERIFIED CLOSED across runs 6148 (20260724u) and 6148-refire (20260724v).
--   All Collier zoning districts with parcel_zones coverage now have density values:
--     RSF-3=3, RSF-4=4, RSF-5=5, MH=7.26 (Collier unincorp LDC Sec 2.05.01, CONFIRMED)
--     Marco Island RSF-3=3 (zoneomics.com mirror, HYPOTHESIS 0.6)
--     Naples R1-7.5=6 (Naples Comp Plan FLUE Policy 1-1(b), CONFIRMED via PDF + ArcGIS)
--     PUD, VR, RMF-12: density_regulated=false (GMP Density Rating System, no fixed value)
--     C-1, I: far_regulated=false (LDC Table 2 shows "None" in FAR column, CONFIRMED)
--   pk1000=NULL: VERIFIED. All 4 commercial districts (C-1/C-4/C-5/I) have
--     pk1000_regulated=false. Collier LDC Sec 4.05.04 Table 17 is organized by
--     land-use category, not zoning district — NO district-keyed rows in that table.
--   far=0.0: STRUCTURAL GAP. C-4 (id=11685, 6 parcels) and C-5 (id=11686, 1 parcel)
--     remain far_applicable=true (commercial category default) but max_far=NULL.
--     Collier LDC Sec 4.02.01 Table 2 DOES have FAR entries for C-4 and C-5, but they
--     are per-use-type: "Hotels .60" for C-4, "Destination resort .80" for C-5. This is
--     NOT a "None" / "not regulated" finding — real per-use FAR values exist.
--     The schema (zone_standards.max_far = one numeric per zoning_district) cannot
--     represent per-use FAR without an architecture change.
--   ARCHITECTURE CHANGE IDENTIFIED (2026-07-24 shard-6 addendum):
--     Closing G honestly requires adding a (district, use_type) grain to zone_standards
--     AND updating v_zoning_district_applicability/v_zoning_gold_standard_kpi_v3 to
--     treat "FAR regulated per-use" as a distinct applicability state from "FAR regulated
--     at district level". This is a fleet-wide view change affecting all 67 counties.
--     Not attempted in this session per PARALLEL-FLEET RULES (other shards mid-flight).
--   ADVERSARIAL CHECK (this session, 2026-07-25):
--     CLAIM considered: set far_regulated=false for C-4/C-5 (same approach as pk1000).
--     REFUTED: the pk1000 finding was that Table 17 had ZERO district-keyed rows; the
--     FAR finding (Table 2) is materially different — C-4 and C-5 have explicit named
--     rows in Table 2 with real per-use values ("Hotels .60", "Destination resort .80").
--     Setting far_regulated=false would misrepresent regulatory text that genuinely exists
--     as absent. The 2nd firing session's explicit "do not flip far_regulated=false for
--     either district" ruling stands and is adversarially confirmed in this session.
--   ACTION: No write. far=0.0 is correct and stays correct until architecture change.

BEGIN;

INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  ('24d13132-b46a-4dd9-82e6-27972d9aa712', 'fallback', 'collier', 'A',
   'collier A dead-end reconfirmed (6th session). No online FC source exists. cor.collierclerk.com/coraccess/ Blazor Server app and collierclerk.com ShowCase both require full-JS browser execution + reCAPTCHA. Collier.realforeclose.com still deprovisioned (302->realauction.com). The td=212 row count from Laserfiche is the complete online footprint. A correctly fails with fc=0.',
   '{"refuted": false, "method": "exhaustive prior-session evidence review (commits shard9_collier_realdata_bootstrap.py, 3rd-5th firing addenda in shard12/shard6 reports). No new sources attempted per residual note recommendation (5th confirmed dead end: do not re-investigate without a new external signal). Status: CONFIRMED dead end.", "sessions_confirming": 5, "platforms_tried": ["collier.realforeclose.com (302->realauction.com)", "collier.realtaxdeed.com (302->realauction.com)", "cor.collierclerk.com/coraccess/ (Blazor Server SignalR, no REST)", "cms.collierclerk.com/showcaseweb/ (AngularJS + reCAPTCHA v3)", "app.collierclerk.com/LFOfficialRecords/ (Angular SPA, GUID runtime-resolved)", "collierclerk.com WordPress events feed (not auction data)"]}'::jsonb,
   true),

  ('24d13132-b46a-4dd9-82e6-27972d9aa712', 'fallback', 'collier', 'G',
   'collier G far=0.0 structural gap confirmed (6th session). Adversarially evaluated proposal to set far_regulated=false for C-4 (id=11685) and C-5 (id=11686). CLAIM SURVIVED REFUTATION: the far_regulated=false proposal is correctly rejected. C-4/C-5 FAR in LDC Sec 4.02.01 Table 2 has real per-use values (Hotels .60, Destination resort .80) — materially different from the pk1000 case where Table 17 had zero district-keyed rows. Closing G honestly requires a schema architecture change to support (district, use_type) grain FAR. density=100.0 and pk1000=NULL are correctly closed from prior sessions. G stays FAIL at metric=0.0 until architecture change.',
   '{"refuted": false, "method": "adversarial analysis of far_regulated=false proposal vs. pk1000 precedent. KEY DISTINCTION: Table 17 (parking) has NO district-keyed rows -> genuine not-regulated-at-district-level. Table 2 (FAR) HAS C-4 and C-5 rows with real values (Hotels .60, Destination resort .80) -> real regulatory data exists, just per-use not per-district. Setting far_regulated=false for C-4/C-5 would incorrectly claim regulatory absence where regulatory text exists. Architecture change required: add (zoning_district_id, use_type) compound key to zone_standards for use-specific FAR. This is a fleet-wide view change, not attempted in this session per PARALLEL-FLEET RULES.", "prior_sessions_confirming_gap": 5, "sessions_confirming_this_reasoning": 2, "specific_migration_refs": ["20260720_gold_standard_shard12_collier_g_far_pk1000_2nd_firing.sql (explicit do-not-flip ruling)", "GOLD_STANDARD_SHARD12_COLLIER_DISPATCH_9D04299E_2ND_FIRING_ADDENDUM.md line 65"]}'::jsonb,
   true);

COMMIT;
