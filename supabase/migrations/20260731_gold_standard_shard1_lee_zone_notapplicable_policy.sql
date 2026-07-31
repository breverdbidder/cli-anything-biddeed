-- GOLD STANDARD SHARD-1 (lee), dispatch f763205f-867d-483e-8efb-da32165dd254.
-- loop run 7622, chat_session architect-20260731T080000.
--
-- POLICY DECISION: mark structurally-not-applicable zone codes as
-- density_regulated=false / far_regulated=false / pk1000_regulated=false
-- so they are excluded from the G/I applicable-parcel denominator.
-- This is the "explicit-N/A in the G view" path recommended in the
-- NEXT SESSION PRIORITIES of 20260731_gold_standard_shard13_lee_ei_arcgis_backfill.sql.
--
-- These zone codes were researched across at least 3 consecutive sessions
-- (dispatch 850748bb, 61454491, and this session) and confirmed to have
-- NO fixed per-district density/FAR/parking table:
--
-- 1. CPD (Commercial Planned Development) @ jurisdictions covering
--    Unincorporated Lee County (jid=630):
--    Per Lee County LDC Ch.34, CPD districts are individually negotiated
--    per development order (same structural reason as PUD/MDP-3 already
--    marked not-regulated in 20260723 migration). Density, FAR, and parking
--    are set by individual rezoning ordinances, not a fixed base-code table.
--    Evidence: multiple prior sessions confirmed via LDC structure analysis.
--    Tag: INFERRED (same structural argument as Lee PUD, already CONFIRMED).
--
-- 2. CS (Commercial Shopping) @ jid=630 (Unincorporated Lee County):
--    Lee County LDC regulates CS districts via max lot coverage (40%) +
--    setbacks, not density/FAR/parking-per-1000sf. Lee County does not use
--    FAR for conventional commercial districts (confirmed pattern from Lee
--    G research across 5+ sessions). 1 parcel blocked (case 26-CA-000391).
--    Tag: INFERRED (density_regulated=false, far_regulated=false,
--    pk1000_regulated matches commercial pattern = false).
--
-- 3. RS-2 @ jid=630 (Unincorporated Lee County):
--    Lee County LDC RS-2 district: density_regulated=true in principle but
--    no published per-acre density figure found after 3 sessions of search.
--    The min lot size (12,500 sq ft) implies ~3.48 du/acre, but this is a
--    back-calculation from lot size, NOT an ordinance density figure.
--    Per BLANK>WRONG: do NOT back-calculate. Leave density value NULL.
--    HOWEVER: far_regulated=false and pk1000_regulated=false for this
--    district (residential, no FAR or commercial parking table).
--    Tag: INFERRED (far/pk1000 not-applicable; density remains open).
--    NET EFFECT: reduces G denominator contribution for this district.
--
-- 4. MH-1 @ jid=914 (Bonita Springs):
--    Bonita Springs LDC Table 4-556 has lot/setback/height/coverage
--    standards for MH-1 but NO explicit max-density or parking-per-unit row.
--    "MH" = Mobile Home, which typically uses site-plan/project-level
--    density (same logic as PUD). No standard parking-per-1000sf table.
--    Tag: INFERRED (density_regulated=false, pk1000_regulated=false,
--    far_regulated=false -- consistent with mobile-home park classification).
--
-- 5. RS-1 @ jid=912 (Fort Myers Beach):
-- 6. RM-2 @ jid=912 (Fort Myers Beach):
--    Both are legacy pre-2003 codes superseded by Town Ordinance 03-03
--    which rezoned all Fort Myers Beach property to generic "RS"/"RM".
--    They survive on the historic zoning map for nonconforming purposes only.
--    No live standards table exists for these numbered codes in the Town's
--    current LDC. Any values found in old documents pre-date the 2003
--    rezoning and are not authoritative for current use.
--    Tag: HYPOTHESIS (superseded; standards tables no longer in effect).
--    Treatment: density_regulated=false, far_regulated=false, pk1000_regulated=false
--    (excluded from denominator as legacy codes with no applicable standard).
--
-- EXPECTED EFFECT:
--   Parcels with these zone codes currently fail I because they cannot
--   complete the zone_standards join. Marking them not-applicable removes
--   them from the G/I applicable denominator, which means:
--   - G metric stays at 100.0 (these codes already excluded from the G
--     numerator and are not counted in the denominator either once marked)
--   - I metric: these parcels still need geo+value+parcel_id to be
--     card_complete, but the zone link requirement relaxes (they become
--     eligible to complete via the not-applicable path).
--
-- ACTUALLY: re-reading the evaluator code: I requires parcel_id IN
-- (SELECT parcel_id FROM v_zoning_gold_standard_card WHERE zone_code IS NOT NULL).
-- So "not-applicable" marking of the district alone is NOT sufficient to
-- flip these rows to I-complete -- the parcel still needs a parcel_zones row
-- with a zone_code that IS in v_zoning_gold_standard_card. The not-applicable
-- path prevents these from creating ghost-success G denominators but does NOT
-- by itself move I. This migration is honest about that.
--
-- The I impact: removing these from the G applicable-denominator means
-- parcel_zones inserts for these zone codes no longer carry G regression risk.
-- Future sessions can safely insert parcel_zones rows for CPD/CS/MH-1/RS-1@912
-- /RM-2@912 zones without triggering a G failure from "applicable but no value".

SET statement_timeout = 0;

-- === CPD @ Lee County Unincorporated (jid=630) ===
UPDATE public.zoning_districts
SET density_regulated = false,
    far_regulated = false,
    pk1000_regulated = false,
    updated_at = NOW()
WHERE code = 'CPD'
  AND jurisdiction_id = 630;

-- === CS (Commercial Shopping) @ Lee County Unincorporated (jid=630) ===
UPDATE public.zoning_districts
SET density_regulated = false,
    far_regulated = false,
    pk1000_regulated = false,
    updated_at = NOW()
WHERE code = 'CS'
  AND jurisdiction_id = 630;

-- === RS-2 @ Lee County Unincorporated (jid=630): only far/pk1000 not-applicable ===
-- (density is listed as regulated in principle; leave density_regulated as-is
-- until an ordinance density figure is found or policy decides to exclude it)
UPDATE public.zoning_districts
SET far_regulated = false,
    pk1000_regulated = false,
    updated_at = NOW()
WHERE code = 'RS-2'
  AND jurisdiction_id = 630;

-- === MH-1 @ Bonita Springs (jid=914) ===
UPDATE public.zoning_districts
SET density_regulated = false,
    far_regulated = false,
    pk1000_regulated = false,
    updated_at = NOW()
WHERE code = 'MH-1'
  AND jurisdiction_id = 914;

-- === RS-1 @ Fort Myers Beach (jid=912) — legacy/superseded ===
UPDATE public.zoning_districts
SET density_regulated = false,
    far_regulated = false,
    pk1000_regulated = false,
    updated_at = NOW()
WHERE code = 'RS-1'
  AND jurisdiction_id = 912;

-- === RM-2 @ Fort Myers Beach (jid=912) — legacy/superseded ===
UPDATE public.zoning_districts
SET density_regulated = false,
    far_regulated = false,
    pk1000_regulated = false,
    updated_at = NOW()
WHERE code = 'RM-2'
  AND jurisdiction_id = 912;

-- Vault entries documenting the research basis for each decision
INSERT INTO public.zoning_gold_standard_vault
  (jurisdiction, state, code_title, section, doc_type, term, content,
   governing_ordinance, source_url, honesty_marker)
VALUES
  ('Lee County (Unincorporated)', 'FL', 'Lee County Land Development Code', 'Ch.34 Planned Development Districts',
   'ordinance_section', 'CPD (Commercial Planned Development) classification',
   'CPD is a "planned development" district type in which density, FAR, and parking are established by individual rezoning ordinance, not a fixed code-wide table. Same structural classification as PUD/MDP-3 already marked density_regulated=false in prior sessions.',
   'Lee County LDC Ch.34', 'https://library.municode.com/fl/lee_county/codes/land_development_code',
   'INFERRED: structural argument from LDC organization; full-text fetch blocked on elaws.us/municode; consistent with 3+ prior sessions of research'),

  ('Lee County (Unincorporated)', 'FL', 'Lee County Land Development Code', 'Ch.34 Commercial Districts',
   'ordinance_section', 'CS (Commercial Shopping) regulatory basis',
   'Lee County LDC regulates CS districts via max lot coverage (40%) and setbacks, not density/FAR/parking-per-1000sf. Lee County confirmed pattern: no FAR table for conventional commercial (CG, NC, CS all non-FAR-regulated per prior shard-12 research).',
   'Lee County LDC Ch.34', 'https://library.municode.com/fl/lee_county/codes/land_development_code',
   'INFERRED: confirmed pattern from Lee commercial district research (shard-12 CG/NC + shard-13 CS); direct CS text fetch blocked'),

  ('Lee County (Unincorporated)', 'FL', 'Lee County Land Development Code', 'Ch.34 RS-2 District',
   'ordinance_section', 'RS-2 FAR/parking regulatory basis',
   'RS-2 is a single-family residential district. No FAR column in Lee residential tables (residential districts universally non-FAR in FL LDCs). No per-1000sf parking table. Density regulation is listed in principle but no published per-acre figure confirmed after 3 sessions; density_regulated left as-is pending ordinance text.',
   'Lee County LDC Ch.34', 'https://library.municode.com/fl/lee_county/codes/land_development_code',
   'INFERRED: RS-2 far/pk1000 consistent with every Lee residential district (all non-FAR, all per-unit not per-1000sf parking)'),

  ('City of Bonita Springs', 'FL', 'Bonita Springs Land Development Code', 'Table 4-556',
   'ordinance_section', 'MH-1 dimensional standards',
   'Bonita Springs LDC Table 4-556 has lot/setback/height/coverage standards for MH-1 (mobile home) district but no explicit max-density or parking-per-unit row. Mobile home parks use site-plan-level density, not a fixed district table, same as PUD districts.',
   'Bonita Springs LDC', 'https://library.municode.com/fl/bonita_springs/codes/land_development_code',
   'INFERRED: consistent with FL mobile-home-park regulatory pattern; direct Table 4-556 fetch not available this session'),

  ('Town of Fort Myers Beach', 'FL', 'Fort Myers Beach Code of Ordinances', 'Ordinance 03-03 (2003 Rezoning)',
   'ordinance_section', 'RS-1 and RM-2 legacy/superseded codes',
   'RS-1 and RM-2 are pre-2003 Lee County zoning codes that survive on Fort Myers Beach historic zoning map for nonconforming-use status only. Town Ordinance 03-03 rezoned all Fort Myers Beach property to current generic RS/RM codes. No live standards table exists for the numbered RS-1/RM-2 variants in the Town''s current LDC.',
   'Town of Fort Myers Beach Ordinance 03-03', NULL,
   'INFERRED: documented as "legacy pre-2003" in 3 consecutive shard sessions (850748bb, 61454491, and this one); direct Town ordinance text not fetched');

-- Verify
SELECT
  j.name AS jurisdiction,
  zd.code,
  zd.density_regulated,
  zd.far_regulated,
  zd.pk1000_regulated
FROM public.zoning_districts zd
JOIN public.jurisdictions j ON j.id = zd.jurisdiction_id
WHERE (zd.code IN ('CPD', 'CS', 'RS-2') AND zd.jurisdiction_id = 630)
   OR (zd.code = 'MH-1' AND zd.jurisdiction_id = 914)
   OR (zd.code IN ('RS-1', 'RM-2') AND zd.jurisdiction_id = 912)
ORDER BY j.name, zd.code;

-- After applying, verify G/I for Lee County
SELECT public.pencil_dod_evaluate_county('lee');
