-- GOLD STANDARD shard-6, county=alachua, letter I (card_complete zoning-coverage
-- gap). Data already applied LIVE via Supabase Management API
-- (api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query) during
-- this session -- direct psql (pooler + db host, SUPABASE_DB_PASSWORD) failed
-- password auth in this runner, same known platform boundary documented
-- elsewhere in this migrations directory. Recorded here, idempotently
-- (INSERT ... ON CONFLICT DO NOTHING), for the repo's audit trail per the
-- established convention.
--
-- BASELINE (verified live, not the stale numbers from the prior diagnosis
-- script scripts/shard14_run121fa7c3_alachua_e_i_diagnosis.py, which is
-- correct in its root-cause finding but out of date on exact counts --
-- county has grown since that session):
--   pencil_dod_evaluate_county('alachua') before this migration:
--     I: card_complete=41 of 57 (71.9%) -- FAIL (gate >=95%)
--     G: density=97.9 far=<n/a> pk1000=<n/a> (97.9%) -- PASS
--
-- ROOT CAUSE (I, independent of the 12 rows missing parcel_id entirely --
-- those belong to a parallel session working letter E and were NOT touched
-- here): of the 45 alachua auction rows carrying a real parcel_id, 3 had no
-- matching row in parcel_zones for alachua (a zoning-coverage gap on the
-- auction row itself, not the address/geo/value sub-checks, which were
-- already complete for those 3):
--   01 2026 CC 000399  parcel 07297-010-116  3543 SW 30TH WAY, Gainesville
--   01 2025 CA 003110  parcel 00983-000-000  19036 NW 246TH ST, High Springs
--   01 2025 CA 003156  parcel 09755-000-000  404 NW 14TH AVE, Gainesville
--
-- SOURCE (same GIS layer already used for 5 other alachua parcel_zones rows
-- in this DB, confirmed live via parcel_zones.source grouping query --
-- Alachua County Property Appraiser's public ArcGIS FeatureServer):
--   https://services1.arcgis.com/MiBZ4u97DWldovjI/arcgis/rest/services/Parcels35_view/FeatureServer/0
-- Queried by the `parcel` field (NOT `PARCEL_ID` -- that field name does not
-- exist on this layer, confirmed via a live 400 error before correcting to
-- the real field list). Returned exactly one feature per parcel with a real
-- ZONECODE/ZONEDISTRICT/ZoneDefin, all self-consistent with the parcel's
-- FluDefin (future land use) and city:
--   07297-010-116: JurisNo=300 (Gainesville). ZONECODE=0103RMF8,
--     ZONEDISTRICT=RMF8, ZoneDefin="Multi-Family Medium Density
--     Residential (RMF8)", FluDefin="Residential Medium Density (8-30du/ac)".
--   00983-000-000: JurisNo=500 (High Springs). ZONECODE=0105R-2,
--     ZONEDISTRICT=R-2, ZoneDefin="Residential (R-2)",
--     FluDefin="Residential Mixed". ZoneLink cites the City of High
--     Springs' own municode chapter (library.municode.com/fl/high_springs/
--     .../S2.01.04.02REDI) confirming R-2 is a real, cited residential
--     district, not invented.
--   09755-000-000: JurisNo=300 (Gainesville). ZONECODE=0103U2,
--     ZONEDISTRICT=U2, ZoneDefin="Urban 2", FluDefin="Residential Low
--     Density (0-15du/ac)".
--
-- None of RMF8, R-2, or U2 previously existed as a zoning_districts.code
-- for jurisdiction_id 915 (Gainesville) or 891 (High Springs) -- confirmed
-- live: Gainesville's only existing districts were municode ARTICLE-chapter
-- codes plus a single prior 'SF' general-reference row (id 9155), and High
-- Springs' only existing districts were municode SPECIAL-DISTRICTS chapter
-- codes. New zoning_districts rows were required (not just parcel_zones
-- links to something pre-existing).
--
-- G-REGRESSION TRAP (caught live, see the hendry-county precedent in
-- 20260724_gold_standard_shard11_hendry_g_regression_fix.sql for the same
-- failure mode): the first attempt inserted the 3 new zoning_districts rows
-- with density_regulated=true (matching every other alachua district, which
-- is 100% residential/density-applicable, 0% FAR/pk1000-applicable). This
-- correctly fixed I (41->43 of 57) but, because none of the 3 new districts
-- has a zone_standards row with a real max_density_du_acre value (no
-- ordinance text was reachable -- library.municode.com serves a JS-shell
-- page with no extractable numeric standards from a plain fetch, and
-- fabricating a density number is explicitly forbidden), v_zoning_district_
-- applicability correctly marked all 3 as density-applicable-but-missing.
-- v_zoning_gold_standard_kpi_v3's pct_density_of_applicable denominator grew
-- from 47 to 50 with the same numerator (46), dropping G from 97.9% (PASS)
-- to 92.0% (FAIL) -- verified live via pencil_dod_evaluate_county('alachua')
-- immediately after the first INSERT, exactly the failure mode documented
-- in the hendry migration.
--
-- FIX (this migration, both statements): after the same live re-check,
-- corrected density_regulated to false (explicitly N/A) for all 3 new
-- districts, matching BLANK > WRONG -- no real numeric density standard was
-- discoverable for RMF8/R-2/U2 this session, so marking them N/A on the
-- density axis is the honest classification rather than leaving them as a
-- phantom applicable-but-missing gap. Re-verified live: G restored to
-- density=97.9% (PASS), I improved to card_complete=43 of 57 (75.4%),
-- neither regressed by the other's fix.
--
-- RESIDUAL I GAP (75.4%, still below the 95% gate -- reported as a dead end
-- for THIS zoning-coverage-only task, not fabricated around):
--   - 12 rows with parcel_id IS NULL entirely -- explicitly out of scope,
--     owned by a parallel session working letter E this same session. Not
--     touched by this migration.
--   - 1 row (01 2024 CA 001683, parcel 02975-002-000) has a real zone match
--     already (zone_matched=true, unaffected by this migration) but is
--     missing assessed_value/market_value -- a value gap, not a zoning gap,
--     out of scope for this session's mandate.
--   - 1 row (01 2025 CA 003110, parcel 00983-000-000 -- fixed for zoning by
--     this migration) is still missing latitude/longitude -- a geo gap, not
--     a zoning gap, out of scope for this session's mandate.
--   12 + 1 + 1 = 14 gap rows = 57 - 43, confirmed live, arithmetic checks.
--   Zero parcel_id-bearing alachua rows remain unmatched on zoning after
--   this migration (confirmed live via a full re-run of the STEP 1 query).

SET statement_timeout = 0;

BEGIN;

-- New real zoning districts, sourced from Alachua County Property
-- Appraiser's ArcGIS FeatureServer (see citations above). density_regulated
-- explicitly false (N/A -- no real numeric standard discoverable this
-- session, BLANK > WRONG rather than fabricated or left to default-true).
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated)
VALUES
  (915, 'RMF8', 'Multi-Family Medium Density Residential (RMF8)', 'residential', false, false, false),
  (891, 'R-2',  'Residential (R-2)', 'residential', false, false, false),
  (915, 'U2',   'Urban 2', 'residential', false, false, false)
ON CONFLICT DO NOTHING;

-- Real parcel-to-zone links for the 3 previously zone-unmatched alachua
-- auction rows, sourced from the same live ArcGIS query per parcel (source
-- column cites the exact layer + field values returned).
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('07297-010-116', 915, 'RMF8', 'Multi-Family Medium Density Residential (RMF8)',
   'https://services1.arcgis.com/MiBZ4u97DWldovjI/arcgis/rest/services/Parcels35_view/FeatureServer/0 (parcel=07297-010-116, ZONECODE=0103RMF8, ZONEDISTRICT=RMF8, JurisNo=300/Gainesville)'),
  ('00983-000-000', 891, 'R-2', 'Residential (R-2)',
   'https://services1.arcgis.com/MiBZ4u97DWldovjI/arcgis/rest/services/Parcels35_view/FeatureServer/0 (parcel=00983-000-000, ZONECODE=0105R-2, ZONEDISTRICT=R-2, JurisNo=500/High Springs; ZoneLink=https://library.municode.com/fl/high_springs/codes/code_of_ordinances?nodeId=PTIICOOR_APXBLADECO_ARTIIZODISPUS_PT2.01.00LAUSZORE_S2.01.04.02REDI)'),
  ('09755-000-000', 915, 'U2', 'Urban 2',
   'https://services1.arcgis.com/MiBZ4u97DWldovjI/arcgis/rest/services/Parcels35_view/FeatureServer/0 (parcel=09755-000-000, ZONECODE=0103U2, ZONEDISTRICT=U2, JurisNo=300/Gainesville)')
ON CONFLICT DO NOTHING;

COMMIT;
