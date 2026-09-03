-- Gold Standard indian_river letter G fix (architect triage #19817, blocked issue
-- #19805, DoD county indian_river).
--
-- ROOT CAUSE (confirmed live via v_zoning_gold_standard_kpi_v3 + parcel_zones +
-- zoning_districts direct query): indian_river G was FAIL 0.0% (density=96.2
-- far=0.0 pk1000=0.0) with only 1 far_applicable_parcel and 1 pk1000_applicable_parcel
-- out of 104 total. That single parcel is 31391900001598000026.0 (Sebastian, FL),
-- zone_code=RS-10, linked into parcel_zones TODAY (2026-09-03T16:28Z,
-- source=sebastian_arcgis_zoning_20260903) by the immediately-prior shard-3 session
-- as part of a letter-I card-completeness fix. That session correctly flagged this
-- as "G is newly visible as FAIL (0.0%, zone_standards gap) — pre-existing,
-- unrelated to this write" but did not fix it (out of scope for the I fix).
--
-- The gap: no public.zoning_districts row exists for (jurisdiction_id=936,
-- code='RS-10') at all. v_zoning_district_applicability's LEFT JOIN from
-- parcel_zones to zoning_districts misses entirely for this code, and
-- v_zoning_gold_standard_kpi_v3's pj CTE does COALESCE(applicable, true) on a
-- LEFT JOIN miss (documented precedent: 20260827i pinellas migration, same
-- mechanism) — forcing this single residential parcel to count as
-- far_applicable=true / pk1000_applicable=true with no possible zone_standards
-- value, guaranteeing 0.0% on both sub-metrics. G = LEAST(density, far, pk1000),
-- so one bad parcel zeroes the whole letter for the entire county.
--
-- REAL EVIDENCE (WebSearch + WebFetch of zoneomics.com/code/sebastian-FL/chapter_3,
-- 2026-09-03): RS-10 = "Single-Family Residential District", City of Sebastian LDC
-- Sec. 54-2-5.2.3, low-density residential on 10,000 sq ft lots. Confirmed: (1) no
-- Floor Area Ratio (FAR) requirement in the district's dimensional regulations
-- (Sec. 54-2-5.2.3(d)); (2) no per-1,000-sq-ft parking ratio — RS-10's dimensional
-- section contains no district-specific parking mandate (general city standard,
-- article XV, referenced only by other districts) — the same "residential =
-- per-dwelling-unit not per-1000sf" convention already used fleet-wide (see
-- 20260827i pinellas 1097/RM). category='Residential' is itself sufficient for the
-- view's fallback formula to exclude this parcel from far/pk1000 applicability, but
-- far_regulated/pk1000_regulated are set explicitly false here since we have a real
-- section citation, not left to the category fallback.
--
-- Does NOT touch density: this parcel already lacks a max_density_du_acre value and
-- will continue to (no verified figure sourced this session, not fabricated per
-- BLANK > WRONG) — density_applicable_parcels/pct_density_of_applicable for
-- indian_river are unaffected (96.2%, already >=95% threshold, not the blocker).
--
-- LIVE BEFORE (rpc/pencil_dod_evaluate_county('indian_river'), session start):
--   G: {"pass":false,"metric":0.0,"detail":"density=96.2 far=0.0 pk1000=0.0"}
--   (v_zoning_gold_standard_kpi_v3: far_applicable_parcels=1, pk1000_applicable_parcels=1)
--   All other letters (A-F,H,I,J) already PASS for indian_river this session.
--
-- EXPECTED AFTER: far_applicable_parcels/pk1000_applicable_parcels -> 0, so
-- pct_far_of_applicable/pct_pk1000_of_applicable -> NULL. Postgres LEAST() ignores
-- NULL arguments (returns NULL only if ALL args are NULL, per PG docs — confirmed
-- against the live wakulla row, which already has far_applicable_parcels=0 and
-- shows G detail "far= pk1000=" with metric=100.0, i.e. LEAST(density) alone).
-- indian_river G should therefore become PASS at density=96.2%, taking the county
-- to a RAW 10/10. This does NOT auto-certify indian_river: gold_standard_certify()
-- separately requires consecutive_gold>=2 with fresh (<7d) adversarial-survival
-- evidence for all 10 letters (per CANON, confirmed via 20260719g migration) — this
-- migration only fixes the letter-level data gap, not the certification hysteresis.
--
-- This migration was run via the Supabase REST API (POST to zoning_districts),
-- not psql (SUPABASE_DB_PASSWORD is a known-broken credential path, decision_log
-- ids 169/205/287) — this .sql file is the audit-trail record of that write per
-- CLAUDE.md M6/migration_workflow, not literally executed via `supabase db push`.

BEGIN;

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, far_regulated, pk1000_regulated, ordinance_section)
SELECT 936, 'RS-10', 'Residential Single-Family 1du/10,000ft2', 'Residential',
  'City of Sebastian, FL Land Development Code Sec. 54-2-5.2.3: Single-Family Residential District, low-density residential on 10,000 sq ft lots. Confirmed via WebFetch of zoneomics.com/code/sebastian-FL/chapter_3 (2026-09-03): no FAR requirement in the district dimensional regulations; no per-1,000sf parking ratio (general city standard applies, not district-specific). far_regulated=false, pk1000_regulated=false accordingly. GS-INDIANRIVER-G-19817-ARCHITECT.',
  false, false,
  'Sec. 54-2-5.2.3'
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 936 AND code = 'RS-10');

COMMIT;

-- VERIFICATION (run after apply):
-- SELECT rpc/pencil_dod_evaluate_county('indian_river');
-- Expected G: pass=true, metric~96.2, detail 'density=96.2 far= pk1000='
