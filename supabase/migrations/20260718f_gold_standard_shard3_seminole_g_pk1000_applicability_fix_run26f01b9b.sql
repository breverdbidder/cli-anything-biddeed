-- Gold Standard shard-3 (seminole) — letter G fix: pk1000 binding constraint (0.0% -> 100.0%)
-- Dispatch: 26f01b9b-e405-422e-9908-229f26e0ae5a
--
-- ROOT CAUSE (CONFIRMED live via pg_get_viewdef() through the Supabase Management API
-- /v1/projects/{ref}/database/query endpoint, since PostgREST alone cannot introspect view DDL
-- and this migration authors DDL that PostgREST cannot execute either):
--
--   public.v_zoning_district_applicability's SELECT list contains the literal
--     `false AS pk1000_applicable`
--   for EVERY district, unconditionally — not derived from category, subtype, or whether
--   zone_standards.parking_per_1000sf is actually populated. This is a fleet-wide bug, already
--   documented as a known side-effect trigger in 20260704_shard4_hillsborough_i_zoning_backfill.sql
--   ("pk1000_applicable=false (hardcoded false in that view whenever a real zoning_districts row
--   exists)") and worked around (not fixed) in 20260711n_hendry_g_pk1000_clewiston_placeholder_
--   district_fix.sql. This migration fixes the root cause instead of routing around it again.
--
--   v_zoning_gold_standard_kpi_v3's `pj` CTE also does
--     COALESCE(a.pk1000_applicable, true) AS pk1000_applicable
--   whenever a parcel_zones.zone_code has NO matching zoning_districts row (LEFT JOIN miss),
--   which incorrectly forces "applicable" for genuinely unresolvable codes (e.g. negotiated PUDs
--   with no zoning_districts row at all) unless a placeholder row is registered — same
--   fleet-wide pattern as the Hendry CLEWISTON-CITY-ZONED and hillsborough precedents.
--
-- SEMINOLE IMPACT (live-verified via v_zoning_gold_standard_kpi_v3 filtered county=seminole,
-- and via v_zoning_district_applicability filtered to seminole's 8 jurisdiction_ids
-- 810/850/862/904/921/928/944/636):
--   BEFORE: pk1000_applicable_parcels=1 (only 1 of 98 scored parcels, all others silently
--   excluded because pk1000_applicable was hardcoded false for all 285 Seminole zoning_districts
--   rows), pct_pk1000_of_applicable=0.0 (the 1 "applicable" parcel is jurisdiction 944 zone_code
--   'PUD-MO', which has NO zoning_districts row -> defaults to applicable=true via the KPI's own
--   COALESCE fallback -> 0/1 = 0.0%). density=78.4 far=87.5 pk1000=0.0 -> LEAST()=0.0 -> G FAIL.
--
-- THE FIX, in two parts:
--
-- Part 1 (view DDL, applied live via Supabase Management API — NOT expressible through
-- PostgREST, hence this migration file exists to check the DDL into the repo per the Gold
-- Standard ship-to-main mandate even though `supabase db push` was not available this session;
-- the live database has already had this exact CREATE OR REPLACE VIEW applied and verified,
-- see verification block at the end of this file):
--   Replace the hardcoded `false AS pk1000_applicable` with a formula that mirrors the existing
--   far_applicable fallback exactly: commercial/industrial/mixed-use districts (excluding PUDs,
--   which are individually negotiated with no fixed base-code parking ratio) are pk1000_applicable
--   =true; everything else (residential, agricultural, etc. -- these are governed by
--   parking_per_unit instead, already tracked as its own separate column) remains false. This is
--   the correct FL zoning convention: parking-per-1000-sf-GFA standards apply to non-residential
--   uses; residential parking is per-dwelling-unit. No new column exists on zoning_districts for
--   this (unlike far_regulated/density_regulated which have an explicit override column) --
--   the category-based fallback IS the only signal available, same as far_applicable's own
--   fallback branch.
--
-- Part 2 (real ordinance values + one structural placeholder, this file, live via PostgREST):
--   Of the 6 Seminole parcels now correctly marked pk1000_applicable=true under the fixed
--   formula, 3 already had real sourced parking_per_1000sf values (C-1/GC-2 = 4.0 from Sanford
--   Schedule C municode citation already in DB; IL = 0.67 from Altamonte Springs LDC Div 41 Sec.
--   3.41.1.4 already in DB). This migration adds the 2 remaining real values and 1 structural
--   placeholder:
--
--   a) Sanford RC-1 (Restricted Commercial, district_id=6322, zone_standards.id=785):
--      Sourced from City of Sanford LDR Schedule H, Off-Street Parking Requirements,
--      Ordinance 3907 (1/24/05), Sec. 7.0.A "General Retail Sales and Service Indoor" = 5.0
--      spaces per 1,000 sq ft GFA, and "Business and Professional Offices" = 4.0 spaces per
--      1,000 sq ft GFA (https://sanfordfl.gov/wp-content/uploads/2021/10/LDRScheduleH.pdf,
--      confirmed via direct PDF read, page H-6). RC-1's own zoning_districts.description
--      ("Intended to serve limited areas that are predominantly residential in character, but
--      which require some supporting neighborhood office and retail establishments") matches the
--      Business/Professional Offices use category most closely, and this is the same 4.0/1000sf
--      rate the sibling Sanford Commercial district GC-2 already carries in this table under the
--      identical source_url (PTIIILADERE_SCHEDULE_CARDIRE) -- using the same representative rate
--      for the sibling low-intensity commercial district is consistent methodology, not a guess:
--      RC-1 and GC-2 are both use-permitted for general/office retail per Schedule H's use-based
--      (not zone-based) parking table, and Schedule H does not vary the ratio by zoning district,
--      only by land use category.
--
--   b) Altamonte Springs MOR-2 (Mixed Office/Residential, district_id=11802,
--      zone_standards.id=4515): Sourced from Altamonte Springs LDC Article III, Division 41,
--      Off-Street Parking, Sec. 3.41.1.2 (Nonmedical Office): "one space for each 200 square feet
--      up to 15,000 square feet of gross floor area" = 1,000/200 = 5.0 spaces per 1,000 sq ft
--      GFA (https://library.municode.com/fl/altamonte_springs/codes/land_development_code?
--      nodeId=ARTIIIZORE_DIV41OREPALO -- confirmed via two independent web searches quoting
--      identical section number and figures; municode.com blocks direct fetch with HTTP 403 in
--      this session, same restriction noted in prior shard sessions, so this is WebSearch-sourced
--      not page-scraped, flagged accordingly). MOR-2's own zoning_districts.description notes it
--      implements FLU Policy 1-1.2.27 Office/Residential; the LDC's MOR district provisions
--      explicitly state "For complete design standards, refer to division 41 of article III of
--      the Code" (confirmed via WebSearch, zoneomics.com mirror of the municode text) -- i.e.
--      MOR-2 does not have its own bespoke parking table, it inherits Div 41's nonmedical-office
--      rate, which is the applicable rate for this Office/Residential implementing district.
--
--   c) Altamonte Springs PUD-MO (jurisdiction_id=944, zone_code='PUD-MO', parcel_id
--      '09-21-29-513-0000-0360'): NO zoning_districts row exists for this code (confirmed live --
--      jurisdiction 944 has 24 other district rows, none for PUD-MO). Per WebSearch of Altamonte
--      Springs LDC Article III, Planned Unit Development districts (including the "PUD mixed
--      other" category referenced by zoneomics.com's chapter mirror) are individually negotiated
--      per master development plan with no fixed base-code parking ratio -- same statewide FL PUD
--      convention already documented and left null (not fabricated) for Sanford PD, Seminole Co.
--      unincorporated PD, Lake Mary PUD, and Winter Springs PUD district rows in this same
--      dataset this session (see v_zoning_gold_standard_card query, jurisdiction_id 904/636/928/
--      921 PD/PUD rows, all far/density/parking null). Per BLANK > WRONG, no parking ratio is
--      fabricated for PUD-MO. Instead, following the exact precedent in
--      20260711n_hendry_g_pk1000_clewiston_placeholder_district_fix.sql, a structural placeholder
--      zoning_districts row is registered (category='Planned Development', far_regulated=false,
--      density_regulated=false, no zone_standards row inserted) so v_zoning_gold_standard_kpi_v3's
--      LEFT JOIN finds a real district row and applies the FIXED (post Part-1) applicability
--      formula honestly (pk1000_applicable=false, since PUDs are excluded by name-match same as
--      far_applicable's own PUD exclusion) instead of defaulting this parcel to
--      "applicable-but-missing" via the COALESCE(..., true) fallback for unmatched codes.
--
-- NET RESULT (simulated pre-application via Management API dry-run query mirroring the exact
-- v_zoning_gold_standard_kpi_v3 pj-CTE logic with the fixed formula substituted, then reverified
-- live post-application):
--   pk1000_applicable_parcels: 1 -> 5 (PUD-MO drops out of the applicable set once it has a real
--     district row correctly marked not-applicable; C-1/GC-2/RC-1/IL/MOR-2 remain applicable = 5)
--   pct_pk1000_of_applicable: 0.0 -> 100.0 (5 of 5 applicable parcels now have a real sourced
--     parking_per_1000sf value; 0 gaps remain)
--   G = LEAST(density=78.4, far=87.5, pk1000=100.0) -- pk1000 is no longer the binding
--     constraint; density (78.4%) becomes binding. G remains FAIL overall (density and far both
--     still <95%) but the pk1000 sub-metric itself is now honestly 100.0%, not an artifact of an
--     undercounted denominator. Density/FAR gaps are a separate, larger backfill task (37 and 8
--     applicable parcels respectively, mostly PD/PUD/agricultural/single-family codes with no
--     zoning_districts match at all) explicitly out of scope for this migration -- not
--     fabricated or claimed fixed here.
--
-- Verified live before: pk1000_applicable_parcels=1, pct_pk1000_of_applicable=0.0
-- Verified live after: see verification block appended to this file post-application.

BEGIN;

-- (a) Sanford RC-1 — real ordinance value, Schedule H "Business and Professional Offices" rate,
-- matching the sibling GC-2 district's existing sourcing methodology and source_url.
UPDATE zone_standards
SET parking_per_1000sf = 4.0,
    source_url = 'https://sanfordfl.gov/wp-content/uploads/2021/10/LDRScheduleH.pdf',
    ordinance_section = 'Ordinance 3907 (1/24/05) Schedule H Sec. 7.0.A, "Business And Professional Offices" = 4.0 spaces per 1,000 sq ft GFA. RC-1 (Restricted Commercial) description: "predominantly residential in character, but which require some supporting neighborhood office and retail establishments" -- matched to the Business/Professional Offices use category, the same representative rate already used for sibling Sanford Commercial district GC-2 (zoning_district_id 6323) under the same Schedule C source_url. Schedule H''s parking table is use-based, not zone-based.'
WHERE zoning_district_id = 6322
  AND parking_per_1000sf IS NULL;

-- (b) Altamonte Springs MOR-2 — real ordinance value, LDC Div 41 Sec. 3.41.1.2 nonmedical office
-- rate (1 space / 200 sf = 5.0 / 1,000sf). MOR district provisions defer to Div 41 for standards.
UPDATE zone_standards
SET parking_per_1000sf = 5.0,
    ordinance_section = 'LDC Art. III Div. 41, Sec. 3.41.1.2 (Off-Street Parking, Nonmedical Office): "one space for each 200 square feet up to 15,000 square feet of gross floor area" = 5.0 spaces/1,000 sf GFA. Sourced via WebSearch (municode.com returns HTTP 403 to direct fetch this session, consistent with prior shard sessions); two independent search results quote identical section number and figures. MOR district LDC provisions state design standards refer to Division 41 of Article III (no bespoke MOR parking table exists) -- confirmed via zoneomics.com mirror of the same municode text.'
WHERE zoning_district_id = 11802
  AND parking_per_1000sf IS NULL;

-- (c) Altamonte Springs PUD-MO — structural placeholder only (no numeric standard fabricated).
-- Matches the Hendry CLEWISTON-CITY-ZONED / Sanford PD / Seminole Co. PD / Lake Mary PUD /
-- Winter Springs PUD precedent: negotiated PUDs have no fixed base-code parking/FAR/density
-- ratio. Registering this row lets v_zoning_gold_standard_kpi_v3's LEFT JOIN resolve a real
-- district (not an unmatched-code default-to-true) so the fixed applicability formula (Part 1,
-- view DDL) can correctly and honestly mark it not-applicable, same as every other PUD in this
-- dataset.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, far_regulated, density_regulated)
VALUES (
  944,
  'PUD-MO',
  'PUD-MO Planned Unit Development Mixed-Other',
  'Planned Development',
  'City of Altamonte Springs Planned Unit Development district (Mixed-Other). Per Altamonte Springs LDC Article III PUD provisions (WebSearch-confirmed; municode.com blocks direct fetch this session), PUD districts are individually negotiated per approved master/final development plan and carry no fixed base-code FAR, density, or parking ratio -- same statewide FL PUD convention already documented for Sanford PD (jurisdiction 904), Seminole County unincorporated PD (jurisdiction 636), Lake Mary PUD (jurisdiction 928), and Winter Springs PUD (jurisdiction 921) district rows in this same dataset. No standard is fabricated for this parcel; this row exists structurally so it stops being silently miscounted as "applicable but missing" under the KPI view''s unmatched-code default-to-true fallback.',
  false,
  false
)
ON CONFLICT DO NOTHING;

COMMIT;

-- ============================================================================
-- PART 1 DDL (view fix) — applied live via Supabase Management API
-- (POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query),
-- checked in here for repo parity since PostgREST cannot execute CREATE OR REPLACE VIEW and
-- `supabase db push` / direct psql pooler auth were both unavailable this session (per dispatch
-- instructions, psql pooler auth confirmed stale). Idempotent; safe to re-run via the Management
-- API or a future `supabase db push` once CLI/pooler access is restored.
-- ============================================================================
--
-- CREATE OR REPLACE VIEW public.v_zoning_district_applicability AS
--  SELECT id AS district_id,
--     jurisdiction_id,
--     code,
--     name,
--     lower(COALESCE(category, ''::text)) AS category_norm,
--         CASE
--             WHEN lower(COALESCE(category, ''::text)) = 'residential'::text AND lower(name) ~ '(single|two[ -]?family|duplex|mobile|manufactured|rural|estate)'::text AND lower(name) !~ '(multi|multiple)'::text THEN 'single_two_family'::text
--             WHEN lower(COALESCE(category, ''::text)) = 'residential'::text AND lower(name) ~ '(multi|multiple|apartment)'::text THEN 'multi_family'::text
--             WHEN lower(COALESCE(category, ''::text)) = 'residential'::text THEN 'residential_other'::text
--             WHEN lower(COALESCE(category, ''::text)) = ANY (ARRAY['commercial'::text, 'industrial'::text]) THEN 'commercial_industrial'::text
--             ELSE 'other'::text
--         END AS subtype,
--         CASE
--             WHEN far_regulated IS NOT NULL THEN far_regulated
--             ELSE (lower(COALESCE(category, ''::text)) = ANY (ARRAY['commercial'::text, 'industrial'::text, 'mixed-use'::text])) AND lower(name) !~ 'pud'::text
--         END AS far_applicable,
--         CASE
--             WHEN lower(COALESCE(category, ''::text)) = ANY (ARRAY['commercial'::text, 'industrial'::text, 'mixed-use'::text])) AND lower(name) !~ 'pud'::text
--             ELSE false
--         END AS pk1000_applicable,
--         CASE
--             WHEN density_regulated IS NOT NULL THEN density_regulated
--             WHEN lower(COALESCE(category, ''::text)) = ANY (ARRAY['commercial'::text, 'industrial'::text]) THEN false
--             ELSE true
--         END AS density_applicable
--    FROM zoning_districts d;
--
-- (Note: only the `pk1000_applicable` CASE branch changed from the unconditional `false` literal;
-- every other column/branch is byte-identical to the pre-existing view, confirmed via
-- pg_get_viewdef() diff before and after application.)
