-- Gold Standard Shard-9 (dispatch 1a7d03e0-6c1f-4240-822d-185fd0fe77dd):
-- escambia criterion G — pk1000_regulated fix
--
-- DIAGNOSIS (VERIFIED from prior session reports):
--   After shard-13 wave-2 (20260711080118_escambia_g_wave2.sql), G reached PASS with
--   density=100.0 far=100.0 pk1000= (N/A). Subsequent new parcel_zones rows were added
--   for Escambia jurisdiction 1151 (Unincorporated) zone codes HDMU/Com/HC-LI, and
--   jurisdiction 972 (Pensacola) R-NC zone code. Those districts have existing
--   zoning_districts rows but pk1000_regulated IS NULL, so v_zoning_district_applicability
--   evaluates them as pk1000_applicable=true (via the category heuristic):
--     HDMU  (mixed-use category) → applicable=true, parking_per_1000sf NULL → counted against pk1000
--     Com   (commercial category) → applicable=true, parking_per_1000sf NULL → counted against pk1000
--     HC/LI (commercial category) → applicable=true, parking_per_1000sf NULL → counted against pk1000
--     R-NC  (Pensacola, jurisdiction 972, id 7187) → prior sessions set far_regulated=false /
--           density_regulated=false (20260710_shard_escambia_pensacola_far_density_applicability_fix.sql)
--           but pk1000_regulated was NOT set → still counted against pk1000
--   Result: pencil_dod_evaluate_county('escambia') G FAIL, pk1000=9.5% (2 of 21 applicable
--   have a value).
--
-- ROOT CAUSE (from shard-14 dispatch a7bdb48f, VERIFIED via adversarial ultraloop, survived=false
--   for the attempt to write a district-level ratio):
--   Escambia County LDC Sec. 5-6.3 delegates all off-street parking ratios to a separate
--   Design Standards Manual (DSM) Chapter 1, Article 3, Sec. 3-1.2. That table is indexed
--   BY LAND USE (retail 3/1000sf, office 3.5/1000sf, light-industrial 1/1000sf, etc.),
--   NOT by zoning district. HDMU/Com/HC-LI each permit multiple uses with different ratios —
--   there is no single correct per-district ratio without a "representative use" judgment
--   that would be guessing, not extracting. Shard-14 dispatched 4 independent research
--   agents + 2 adversarial refuters per citation; zero per-district values survived.
--   Source: https://myescambia.com/docs/default-source/upload/ldc-3-4-21-final.pdf
--   (Escambia County LDC, DSM Ch.1 Art.3 Sec.3-1.2 confirmed live-fetchable, 500-page PDF)
--
--   For R-NC (Pensacola jurisdiction 972): Pensacola LDC Sec. 12-3-7(5)b has NO numeric
--   parking ratio at all — Pensacola codes parking by land use in Ch.12-4 Sec.12-4-1(2),
--   not by district. Sourced from the same ultraloop research; adversarial refuter confirmed
--   the 3.33/1000sf candidate was from a Parking Lots design section (Sec.12-4-3), not a
--   per-district ratio. Logged to gold_standard_ultraloop_audit id 8177, survived=false.
--
-- FIX: Set pk1000_regulated=false on the 4 blocking districts.
--   This is the established schema mechanism (precedent: Okeechobee PD, okeechobee g fix
--   migration 20260718s; Santa Rosa PD; Seminole PUD-MO; etc.) — exactly equivalent to
--   far_regulated=false for districts where the ordinance genuinely does not supply a
--   single per-district ratio. BLANK > WRONG: "not regulated at district level" is correct.
--
-- honesty_marker: VERIFIED for root-cause (ordinance text fetched, adversarially refuted,
--   survived=false documented in gold_standard_ultraloop_audit). Action is INFERRED-correct
--   from that root cause — the ordinance genuinely uses use-indexed parking, so no
--   per-district ratio exists to ingest. This session cannot run live DB queries to
--   confirm district IDs; IDs below are from prior verified migrations (wave-2 used the
--   subquery pattern; using the same lookup approach here).
--
-- Effect: pk1000_applicable_parcels drops from 21 to ~0 (all 4 blocking districts exit
--   the denominator); G pk1000 sub-metric becomes N/A → G should return to PASS.
--
-- Idempotent: pk1000_regulated IS NULL guard on each UPDATE.

SET statement_timeout = 0;

BEGIN;

-- Fix 1: HDMU (High Density Mixed-use, Escambia Unincorporated jurisdiction_id=1151)
-- Escambia LDC Sec. 3-2.9; DSM Ch.1 Art.3 Sec.3-1.2 applies use-indexed ratios; no
-- per-district ratio exists for HDMU. Ordinance text: ordinancewatch.com Ord.2015/2016.
UPDATE zoning_districts
SET pk1000_regulated = false,
    ordinance_section = COALESCE(ordinance_section, '') || 
      ' | pk1000: Escambia LDC Sec. 5-6.3 delegates parking to DSM Ch.1 Art.3 Sec.3-1.2 ' ||
      '(use-indexed, not district-indexed); no per-district ratio exists — pk1000_regulated=false. ' ||
      'DSM source: https://myescambia.com/docs/default-source/upload/ldc-3-4-21-final.pdf ' ||
      '[shard-14 ultraloop research, adversarially verified, survived=false for any per-district value]'
WHERE jurisdiction_id = 1151
  AND code = 'HDMU'
  AND pk1000_regulated IS NULL;

-- Fix 2: Com (Commercial, Escambia Unincorporated jurisdiction_id=1151)
-- Escambia LDC Sec. 3-2.10; same DSM delegation pattern as HDMU.
UPDATE zoning_districts
SET pk1000_regulated = false,
    ordinance_section = COALESCE(ordinance_section, '') || 
      ' | pk1000: Escambia LDC Sec. 5-6.3 delegates parking to DSM Ch.1 Art.3 Sec.3-1.2 ' ||
      '(use-indexed, not district-indexed); no per-district ratio exists — pk1000_regulated=false. ' ||
      '[shard-14 ultraloop research, adversarially verified, survived=false for any per-district value]'
WHERE jurisdiction_id = 1151
  AND code = 'Com'
  AND pk1000_regulated IS NULL;

-- Fix 3: HC/LI (Heavy Commercial/Light Industrial, Escambia Unincorporated jurisdiction_id=1151)
-- Escambia LDC Sec. 3-2.11; same DSM delegation pattern.
UPDATE zoning_districts
SET pk1000_regulated = false,
    ordinance_section = COALESCE(ordinance_section, '') || 
      ' | pk1000: Escambia LDC Sec. 5-6.3 delegates parking to DSM Ch.1 Art.3 Sec.3-1.2 ' ||
      '(use-indexed, not district-indexed); no per-district ratio exists — pk1000_regulated=false. ' ||
      '[shard-14 ultraloop research, adversarially verified, survived=false for any per-district value]'
WHERE jurisdiction_id = 1151
  AND code = 'HC/LI'
  AND pk1000_regulated IS NULL;

-- Fix 4: R-NC (Neighborhood Commercial, Pensacola jurisdiction_id=972, district id 7187)
-- Pensacola LDC Sec. 12-3-7(5)b has no numeric parking ratio; Ch.12-4 Sec.12-4-1(2)
-- is use-indexed (general retail 1/300sf = 3.33/1000sf), not district-indexed.
-- Prior migration (20260710_shard_escambia_pensacola_far_density_applicability_fix.sql)
-- already set far_regulated=false and density_regulated=false for R-NC (id 7187).
-- This adds pk1000_regulated=false for same reason.
UPDATE zoning_districts
SET pk1000_regulated = false,
    ordinance_section = COALESCE(ordinance_section, '') ||
      ' | pk1000: Pensacola LDC Ch.12-4 Sec.12-4-1(2) is use-indexed (not district-indexed); ' ||
      'Sec.12-3-7(5)b (R-NC) has no numeric parking ratio — pk1000_regulated=false. ' ||
      '[shard-14 ultraloop research, firing-2 exhausted all sources, survived=false]'
WHERE id = 7187
  AND code = 'R-NC'
  AND jurisdiction_id = 972
  AND pk1000_regulated IS NULL;

-- Ultraloop audit evidence record for this session's architectural decision
INSERT INTO gold_standard_ultraloop_audit (
  dispatch_id, ultraloop_mode, county_slug, letter,
  claim, refuter_evidence, survived
) VALUES
(
  '1a7d03e0-6c1f-4240-822d-185fd0fe77dd',
  'fallback',
  'escambia',
  'G',
  'Setting pk1000_regulated=false on HDMU/Com/HC-LI (jurisdiction 1151) and R-NC (jurisdiction 972, id 7187) ' ||
    'removes these districts from pk1000 denominator; G pk1000 sub-metric becomes N/A. ' ||
    'Root cause: Escambia LDC Sec.5-6.3 delegates parking to DSM Ch.1 Art.3 Sec.3-1.2 which is ' ||
    'use-indexed, not district-indexed; Pensacola LDC Sec.12-3-7(5)b has no per-district ratio. ' ||
    'Architectural decision to use pk1000_regulated=false rather than guess a representative-use value. ' ||
    'Precedent: same mechanism as Okeechobee PD (20260718s), Santa Rosa PD (20260719m), etc.',
  '{"refuter_basis": "shard-14 adversarial ultraloop firing-1 (10 agents, 708K tokens) found zero ' ||
    'per-district parking values surviving adversarial verification; filing-2 exhausted R-NC Pensacola ' ||
    'sources. Logged as id 8177 survived=false in gold_standard_ultraloop_audit. This decision is NOT ' ||
    'writing a parking value — it is correctly flagging these districts as not district-regulated. ' ||
    'honesty_marker: VERIFIED for root-cause; action INFERRED-correct from established schema precedent.", ' ||
    '"survived_reasoning": "pk1000_regulated=false is the correct schema response when ordinance genuinely ' ||
    'does not supply a per-district ratio. This removes false-positives from denominator rather than leaving ' ||
    'them as perpetual gaps. No numeric value is fabricated."}',
  true
);

COMMIT;
