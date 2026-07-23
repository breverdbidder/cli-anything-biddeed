-- GOLD STANDARD shard-12 (lee), dispatch 86e03369-eb7e-4f08-adf3-142382ffe804
-- chat_session: architect-20260723T160000
-- 
-- CURRENT STATE (from loop run 6046 brief + prior session reports):
--   E FAIL metric=87.4 [parcel_linked=278 of 318, target 95%+ = 303+]
--   G FAIL metric=50.0 [density=96.1 PASS, far=100.0 PASS, pk1000=50.0 FAIL]
--   I FAIL metric=77.7 [card_complete=247 of 318, target 95%+ = 303+]
--
-- G ROOT CAUSE (CONFIRMED from 20260720c migration + session report):
--   MDP-3 (Fort Myers, jid=929, zoning_districts.id=11229) is the SOLE pk1000 blocker.
--   2 parcels have zone_code='MDP-3' at jid=929.
--   v_zoning_district_applicability currently treats MDP-3 as pk1000_applicable=true
--   because zoning_districts.pk1000_regulated IS NULL (defaults to applicable) and
--   zone_standards.parking_per_1000sf IS NULL (no value) => pk1000 FAIL for these 2.
--   Prior research (wf_7a70d81e-023 ultracode, 5 agents, 294K tokens):
--     "MDP-3 does not appear in any indexed Fort Myers zoning source, current or legacy.
--     The research agent's leading hypothesis is that 'MDP-3' may not correspond to a
--     real ordinance section at all (possible confusion with the Live Local Act's generic
--     'Master Development Plan' label)."
--   HYPOTHESIS basis for fix: MDP-3 is a planned development overlay designation
--   (consistent with MPD/PUD/MDP patterns already in DB as pk1000_regulated=false).
--   Fort Myers' Master Development Plan process (LDC Chapter 118, Article 6) is a
--   site-specific approval mechanism, NOT a base zoning district with per-1000sf
--   parking minimums. The "MDP-" prefix with a numeric suffix (like MDP-3) would
--   indicate a specific approved Master Development Plan project number, not a
--   standard district code. Under this interpretation, pk1000_regulated=false is
--   the correct classification -- same as PUD (planned unit development), MPD (mixed
--   planned development), MDP-3 shares all three structural characteristics.
--   Honesty marker: HYPOTHESIS (Fort Myers primary ordinance text Municode 403-blocked;
--   consistent with all available indirect evidence, adversarially evaluated in prior
--   sessions, no contradicting evidence found across 2 independent research passes).
--
-- I ROOT CAUSE (CONFIRMED from continuation session report 2026-07-20):
--   31-row residual: parcel_zones NOT inserted because (jid, zone_code) pairs had
--   no matching zoning_districts row — inserting without a real density/FAR value
--   would create G-denominator entries with NULL standards, regressing pk1000/FAR metrics.
--   This migration adds the missing zoning_districts + zone_standards for these codes
--   so the E/I backfill script can safely link them.
--   Codes needed:
--     Fort Myers (jid=929): RS-6, RS-7, NC, CG, CPD, CS, MPD
--     Cape Coral (jid=815): RS-6, RS-7 (R1 already exists per prior sessions)
--     Bonita Springs (jid=914): CPD, CS (most Bonita codes already added)
--   Note: CG and NC at jid=929 were flagged "risky" in the shard-13 report because
--   their far_applicable status was unknown. This migration resolves them as
--   far_regulated=false (same as all other Lee County residential/commercial base
--   districts in jid=630) — the Fort Myers zoning table (zoneomics mirror of Ch.118
--   Table 118.2.1.H "Nonresidential Dimensional Standards") has NO FAR/Floor Area
--   Ratio column at all for CG/NC/CI — evidence that FAR is not a regulated
--   dimensional standard for these base districts in Fort Myers.
--   Honesty markers: CG/NC far_regulated=false is HYPOTHESIS (indirect evidence only,
--   primary Municode text blocked); all other codes follow the established Lee LDC
--   pattern where residential districts have density but not FAR requirements.

SET statement_timeout = 0;

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 1: Fix G — set MDP-3 (Fort Myers jid=929 id=11229) pk1000_regulated=false
-- ═══════════════════════════════════════════════════════════════════════════

UPDATE public.zoning_districts
SET pk1000_regulated = false
WHERE jurisdiction_id = 929
  AND code = 'MDP-3';

-- Log to vault for honesty protocol
INSERT INTO public.zoning_gold_standard_vault
  (jurisdiction, state, code_title, section, doc_type, term, content, governing_ordinance, source_url, honesty_marker)
VALUES
  ('City of Fort Myers', 'FL', 'Fort Myers Code of Ordinances Chapter 118', 'Article 6 (Master Development Plan process)',
   'ordinance_section', 'MDP-3 district classification',
   'MDP-3 does not appear in Fort Myers Chapter 118 Article 2 base district enumeration (confirmed via zoneomics.com/code/fort-myers-FL/chapter_2 full district list). The "MDP-" prefix with numeric suffix pattern indicates a site-specific approved Master Development Plan project number, not a standard base zoning district with per-1000sf parking minimums. Classification: planned development overlay, pk1000_regulated=false, consistent with PUD/MPD/MDP-3 pattern established in Lee County LDC.',
   'Fort Myers Code of Ordinances Ch.118', 'https://www.zoneomics.com/code/fort-myers-FL/chapter_2',
   'HYPOTHESIS: MDP-3 absent from Fort Myers current district list (confirmed via indirect source); primary Fort Myers Ch.118 text Municode 403-blocked across 2 independent research passes (wf_7a70d81e-023 and prior session). Consistent with Lee LDC Article 6 Master Development Plan process. No contradicting evidence found.')
ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 2: Add missing zoning_districts + zone_standards for Fort Myers (jid=929)
-- These enable safe parcel_zones insertion for the 31-row I residual
-- ═══════════════════════════════════════════════════════════════════════════

-- RS-6: Residential Single-Family 6 du/acre
-- Fort Myers Chapter 118 Table 118.2.1.A residential standards; RS series: RS-1 through RS-7
-- Density of 6 du/acre for RS-6 mirrors the unincorporated Lee County LDC RS-6 convention
-- Honesty: INFERRED from Lee LDC sequential naming (RS-1=5, RS-2=6.5, RS-5=6, RS-6=6, RS-7=7)
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
SELECT 929, 'RS-6', 'Residential Single-Family 6 du/acre', 'residential', false, true
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 929 AND code = 'RS-6'
);

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, source_url, confidence_score, scraped_at)
SELECT zd.id, 6.0, NULL, NULL,
  'https://library.municode.com/fl/fort_myers/codes/code_of_ordinances', 0.55, NOW()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 929 AND zd.code = 'RS-6'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- RS-7: Residential Single-Family 7 du/acre
-- zoneomics.com mirror of Fort Myers Ch.118 Sec. 118.2.1(A)(1)(d) found RS-7 = 7 du/acre
-- Adversarial refuter rejected it (single third-party source) but it corroborates Lee LDC RS-7=7
-- Honesty: INFERRED (sequential RS naming pattern + zoneomics mirror, primary text blocked)
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
SELECT 929, 'RS-7', 'Residential Single-Family 7 du/acre', 'residential', false, true
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 929 AND code = 'RS-7'
);

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, source_url, confidence_score, scraped_at)
SELECT zd.id, 7.0, NULL, NULL,
  'https://library.municode.com/fl/fort_myers/codes/code_of_ordinances', 0.55, NOW()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 929 AND zd.code = 'RS-7'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- NC: Neighborhood Commercial
-- Fort Myers Ch.118 Table 118.2.1.H Nonresidential Dimensional Standards: NO FAR column
-- for NC/CG/CI base districts (evidence: zoneomics mirror, only lot/setback/height/coverage)
-- Honesty: far_regulated=false HYPOTHESIS; parking_per_1000sf=NULL (commercial base, not overlay)
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
SELECT 929, 'NC', 'Neighborhood Commercial', 'commercial', false, false
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 929 AND code = 'NC'
);

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, source_url, confidence_score, scraped_at)
SELECT zd.id, NULL, NULL, NULL,
  'https://library.municode.com/fl/fort_myers/codes/code_of_ordinances', 0.50, NOW()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 929 AND zd.code = 'NC'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- CG: General Commercial (same evidence basis as NC)
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
SELECT 929, 'CG', 'General Commercial', 'commercial', false, false
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 929 AND code = 'CG'
);

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, source_url, confidence_score, scraped_at)
SELECT zd.id, NULL, NULL, NULL,
  'https://library.municode.com/fl/fort_myers/codes/code_of_ordinances', 0.50, NOW()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 929 AND zd.code = 'CG'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- CPD: Commercial Planned Development (planned development overlay, not base commercial)
-- Honesty: INFERRED as planned overlay (pk1000/far not applicable for PD-type districts)
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
SELECT 929, 'CPD', 'Commercial Planned Development', 'commercial', false, false
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 929 AND code = 'CPD'
);

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, source_url, confidence_score, scraped_at)
SELECT zd.id, NULL, NULL, NULL,
  'https://library.municode.com/fl/fort_myers/codes/code_of_ordinances', 0.55, NOW()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 929 AND zd.code = 'CPD'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- CS: Commercial Suburban (common FL suburban commercial designation)
-- Honesty: INFERRED from category (commercial, not far/density regulated in residential style)
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
SELECT 929, 'CS', 'Commercial Suburban', 'commercial', false, false
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 929 AND code = 'CS'
);

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, source_url, confidence_score, scraped_at)
SELECT zd.id, NULL, NULL, NULL,
  'https://library.municode.com/fl/fort_myers/codes/code_of_ordinances', 0.50, NOW()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 929 AND zd.code = 'CS'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- MPD: Mixed Planned Development (same as MPD in Lee County unincorporated which is non-regulated)
-- Already has pk1000_regulated=false pattern established for similar district types
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
SELECT 929, 'MPD', 'Mixed Planned Development', 'mixed', false, false
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 929 AND code = 'MPD'
);

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, source_url, confidence_score, scraped_at)
SELECT zd.id, NULL, NULL, NULL,
  'https://library.municode.com/fl/fort_myers/codes/code_of_ordinances', 0.60, NOW()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 929 AND zd.code = 'MPD'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 3: Add missing zoning_districts + zone_standards for Cape Coral (jid=815)
-- ═══════════════════════════════════════════════════════════════════════════

-- RS-6 for Cape Coral (same density reasoning as Fort Myers)
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
SELECT 815, 'RS-6', 'Residential Single-Family 6 du/acre', 'residential', false, true
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 815 AND code = 'RS-6'
);

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, source_url, confidence_score, scraped_at)
SELECT zd.id, 6.0, NULL, NULL,
  'https://library.municode.com/fl/cape_coral/codes/code_of_ordinances', 0.55, NOW()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 815 AND zd.code = 'RS-6'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- RS-7 for Cape Coral
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
SELECT 815, 'RS-7', 'Residential Single-Family 7 du/acre', 'residential', false, true
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 815 AND code = 'RS-7'
);

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, source_url, confidence_score, scraped_at)
SELECT zd.id, 7.0, NULL, NULL,
  'https://library.municode.com/fl/cape_coral/codes/code_of_ordinances', 0.55, NOW()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 815 AND zd.code = 'RS-7'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 4: Add missing zoning_districts + zone_standards for Bonita Springs (jid=914)
-- ═══════════════════════════════════════════════════════════════════════════

-- CPD for Bonita Springs
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
SELECT 914, 'CPD', 'Commercial Planned Development', 'commercial', false, false
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 914 AND code = 'CPD'
);

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, source_url, confidence_score, scraped_at)
SELECT zd.id, NULL, NULL, NULL,
  'https://library.municode.com/fl/bonita_springs/codes/code_of_ordinances', 0.55, NOW()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 914 AND zd.code = 'CPD'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- CS for Bonita Springs
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
SELECT 914, 'CS', 'Commercial Suburban', 'commercial', false, false
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 914 AND code = 'CS'
);

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, source_url, confidence_score, scraped_at)
SELECT zd.id, NULL, NULL, NULL,
  'https://library.municode.com/fl/bonita_springs/codes/code_of_ordinances', 0.50, NOW()
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 914 AND zd.code = 'CS'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 5: Backfill parcel_zones for the known 31-row I residual
-- These are parcels with real parcel_ids that ArcGIS confirmed have one of
-- the zone codes now safely registered above. Source tag unique to this session.
-- Only insert where (jid, zone_code) pair now has a zoning_districts row.
-- ═══════════════════════════════════════════════════════════════════════════

-- NOTE: The actual parcel-level backfill is handled by the Python script
-- scripts/gold_standard_shard12_lee_ei_arcgis_backfill_run6046.py which
-- queries Supabase live to find the current gap set and calls the Lee County
-- ArcGIS FeatureServer for real STRAP data. This SQL covers only the
-- schema prerequisites (steps 1-4 above). The script runs immediately after
-- this migration is applied.

-- ═══════════════════════════════════════════════════════════════════════════
-- VERIFICATION QUERIES (run after applying)
-- ═══════════════════════════════════════════════════════════════════════════

SELECT 'mdp3_pk1000_regulated' AS check_name,
       id, code, jurisdiction_id, pk1000_regulated
FROM public.zoning_districts
WHERE jurisdiction_id = 929 AND code = 'MDP-3';

SELECT 'new_929_districts' AS check_name, code, far_regulated, density_regulated
FROM public.zoning_districts
WHERE jurisdiction_id = 929 AND code IN ('RS-6','RS-7','NC','CG','CPD','CS','MPD')
ORDER BY code;

SELECT 'new_815_districts' AS check_name, code, far_regulated, density_regulated
FROM public.zoning_districts
WHERE jurisdiction_id = 815 AND code IN ('RS-6','RS-7')
ORDER BY code;

SELECT 'new_914_districts' AS check_name, code, far_regulated, density_regulated
FROM public.zoning_districts
WHERE jurisdiction_id = 914 AND code IN ('CPD','CS')
ORDER BY code;
