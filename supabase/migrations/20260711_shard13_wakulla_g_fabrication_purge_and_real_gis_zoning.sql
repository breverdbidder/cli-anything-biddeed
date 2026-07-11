-- Wakulla County G fix: FABRICATION PURGE + real ArcGIS zoning backfill. Shard-13, run3713.
--
-- FABRICATION FOUND (flagged directly in the SUMMIT task brief this session, confirmed
-- live before touching anything): parcel_zones had 3 rows for jurisdiction_id=1145
-- (Crawfordville) with parcel_id='WAKULLA-PARCEL-0001'/'0002'/'0003', zone_code='R-1',
-- source='shard5_bootstrap_run338', created_at='2026-06-24'. These parcel_ids do NOT
-- match ANY real row in multi_county_auctions for county=wakulla (verified: a fresh
-- query for county=wakulla parcel_ids returns only tax-deed-format IDs like
-- '00-00-035-008-06854-000' and '07-5S-02W-000-02638-000' -- never 'WAKULLA-PARCEL-000N').
-- These 3 synthetic rows were the ENTIRE basis for wakulla's G showing PASS
-- (density=100.0) before this fix -- a ghost-success matching the exact honesty-
-- violation pattern already caught elsewhere in this repo (see git log: "marion J
-- false-VERIFIED honesty bug"). The zoning_districts row backing them (id=10722,
-- code='R-1', description="...shard5 bootstrap run338") was equally fabricated and is
-- purged too.
--
-- PURGE: delete exactly parcel_zones ids 818428/818429/818430 and zoning_districts id
-- 10722 (matched by id, re-verified live immediately before deletion to confirm they
-- were still the same fake rows -- no other session had touched them).
--
-- JURISDICTION GAP: wakulla's jurisdictions table had only 3 tiny municipal rows
-- (St. Marks id=1144, Sopchoppy id=919, Crawfordville id=1145). None of wakulla's real
-- tax-deed-format parcel_ids (00-00-0XX-0XX-XXXXX-000 pattern) belong to those
-- municipalities -- confirmed via the real GIS zoning layer below, whose AGENCY field
-- is blank for every matched parcel and whose zone codes (R1/RMH1/RR1) are the
-- countywide unincorporated codes, not municipal codes. Inserted a new
-- "Unincorporated Wakulla" jurisdiction row (id=1402, county='Wakulla', co_no=65,
-- data_source='shard13_run3713_ZoningWakulla_ArcGIS').
--
-- REAL SOURCE FOUND AND QUERIED LIVE: Wakulla County publishes a public, unauthenticated
-- ArcGIS FeatureServer zoning layer --
--   https://services1.arcgis.com/lDFzr3JyGEn5Eymu/arcgis/rest/services/ZoningWakulla/FeatureServer/0
--   (14,785 features, fields include PIN_DSP [parcel id, format matches our
--   multi_county_auctions parcel_id exactly], CUR_ZONING, ORI_ZONING, LAND_USE).
-- Queried this layer live by PIN_DSP for all 23 real wakulla tax-deed-format parcel_ids
-- currently in multi_county_auctions (non-propertyonion scope). 20 of 23 matched with
-- real CUR_ZONING values: R1 (14 parcels), RMH1 (5 parcels), RR1 (1 parcel). The
-- remaining 3 (26-4S-02W-022-02220-000, 26-4S-02W-022-02204-000,
-- 07-5S-02W-000-02638-000 -- Section-Township-Range format, not the 00-00- tax-deed
-- format) fell outside this layer's apparent coverage (service description says
-- "selection...intersecting the Wakulla Springs springshed project area", i.e. not a
-- full-county layer) and returned zero features. These 3 were left UNLINKED rather
-- than guessed -- a documented residual, not a fabrication.
--
-- Inserted 3 new zoning_districts rows (R1, RMH1, RR1) under jurisdiction_id=1402, each
-- description citing the live ArcGIS query as the source of the zone_code itself.
-- Inserted 20 parcel_zones rows (source='ZoningWakulla_ArcGIS_run3713') linking each
-- real parcel_id to its real zone_code via jurisdiction_id=1402.
--
-- DIMENSIONAL STANDARDS -- NOT SOURCED, NOT FABRICATED: attempted to source Wakulla
-- County's real zoning ordinance dimensional standards (density, FAR, setbacks) this
-- session via 4 independent paths, all failed:
--   1. library.municode.com/fl/wakulla_county?nodeId=PTILADECO_CH5ZOREDI -- HTTP 200 but
--      reCAPTCHA-gated JS SPA shell, no extractable ordinance text (same failure mode
--      as the Calhoun County precedent, 20260711g migration).
--   2. wakullacounty.elaws.us (Article III mirror) -- HTTP 503 Service Unavailable on
--      3 separate attempts, ~4s apart. Not gated, just down this session.
--   3. qpublic.schneidercorp.com (WakullaCountyFL) -- HTTP 403 (bot-blocked).
--   4. No Firecrawl API key available in this sandbox session to escalate past #1.
-- A third-party aggregator (zoneomics.com) returned detailed R-1/RMH-1/RR-1 dimensional
-- figures, but a separate independent web-search snippet gave CONFLICTING density
-- numbers for the same districts (RR-2 and AG). Per HARD GUARDRAILS and the explicit
-- session instruction not to backfill placeholder/unverified values to keep a number
-- high, NO numeric standard was inserted into zone_standards. All 3 new
-- zoning_districts rows have far_regulated=null, density_regulated=null and zero
-- zone_standards rows -- explicitly flagged as a residual gap for a future session with
-- Firecrawl access or a working eLaws mirror.
--
-- pencil_dod_evaluate_county('wakulla') before -> after this migration (applied live via
-- PostgREST DELETE/POST during this session; this file documents the change for replay):
--   G: density=100.0 (PASS, but 100% FAKE -- entirely from 3 synthetic parcel_ids that
--      matched zero real auctions) -> density=0.0 (FAIL, 100% REAL -- 20/20 applicable
--      real parcels correctly zone-linked to real GIS zone codes, but zero have sourced
--      dimensional standards yet). v_zoning_gold_standard_kpi_v3 confirms:
--      parcels=20, density_applicable_parcels=20, pct_density_of_applicable=0.0.
--   A/C/D/E/H/J: unchanged (A,C,D,H,J already pass; E=76.7% still fails, out of scope
--      for this G-focused fix). B/F: unchanged, still fail (no closed sale yet).
-- wakulla letters unchanged except G, which flips from a FALSE PASS to an HONEST FAIL.
-- This is the correct outcome per the task brief -- a documented honest partial (real
-- zone_code coverage: 20/23 = 87% of candidate parcels, real GIS-sourced) is preferred
-- over a fabricated 100%.
--
-- Adversarially self-verified live this same session (re-query of parcel_zones/
-- zoning_districts row counts and content, ZoningWakulla ArcGIS endpoint reachability,
-- and pencil_dod_evaluate_county output) -- survived=true, logged to
-- gold_standard_ultraloop_audit id=5626.

BEGIN;

DELETE FROM parcel_zones
WHERE id IN (818428, 818429, 818430)
  AND parcel_id IN ('WAKULLA-PARCEL-0001', 'WAKULLA-PARCEL-0002', 'WAKULLA-PARCEL-0003')
  AND source = 'shard5_bootstrap_run338';

DELETE FROM zoning_districts
WHERE id = 10722
  AND jurisdiction_id = 1145
  AND code = 'R-1'
  AND description LIKE '%shard5 bootstrap run338%';

INSERT INTO jurisdictions (name, county, state, data_completeness, data_source, active, county_name, municode_url, co_no)
VALUES ('Unincorporated Wakulla', 'Wakulla', 'FL', 0.0, 'shard13_run3713_ZoningWakulla_ArcGIS', true, 'Wakulla', 'https://library.municode.com/fl/wakulla_county', 65);
-- live insert returned id=1402

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, far_regulated, density_regulated)
VALUES
  (1402, 'R1', 'Single Family Residential (Rural/Urban)',
   'residential',
   'zone_code sourced live from ArcGIS FeatureServer https://services1.arcgis.com/lDFzr3JyGEn5Eymu/arcgis/rest/services/ZoningWakulla/FeatureServer/0 (field CUR_ZONING=R1, PIN_DSP matched against real multi_county_auctions parcel_ids), run3713 2026-07-11. Dimensional standards NOT sourced this session -- Municode 403/reCAPTCHA-gated, eLaws mirror 503 x3, qPublic 403-blocked, no Firecrawl key available. No replacement value fabricated.',
   NULL, NULL),
  (1402, 'RMH1', 'Mobile Home Residential',
   'residential',
   'zone_code sourced live from ArcGIS FeatureServer https://services1.arcgis.com/lDFzr3JyGEn5Eymu/arcgis/rest/services/ZoningWakulla/FeatureServer/0 (field CUR_ZONING=RMH1), run3713 2026-07-11. Dimensional standards NOT sourced this session -- same primary-source access failures as R1.',
   NULL, NULL),
  (1402, 'RR1', 'Rural Residential',
   'residential',
   'zone_code sourced live from ArcGIS FeatureServer https://services1.arcgis.com/lDFzr3JyGEn5Eymu/arcgis/rest/services/ZoningWakulla/FeatureServer/0 (field CUR_ZONING=RR1), run3713 2026-07-11. Dimensional standards NOT sourced this session -- same primary-source access failures as R1.',
   NULL, NULL);
-- live insert returned ids=11647 (R1), 11648 (RMH1), 11649 (RR1)

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, future_land_use, source)
VALUES
  ('00-00-035-008-07276-000', 1402, 'R1',   'Single Family Residential (Rural/Urban)', 'RURAL 2', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-035-008-07526-000', 1402, 'R1',   'Single Family Residential (Rural/Urban)', 'RURAL 2', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-035-008-07878-000', 1402, 'R1',   'Single Family Residential (Rural/Urban)', 'RURAL 2', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-035-008-06854-000', 1402, 'R1',   'Single Family Residential (Rural/Urban)', 'RURAL 2', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-035-008-07474-000', 1402, 'R1',   'Single Family Residential (Rural/Urban)', 'RURAL 2', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-043-010-08943-000', 1402, 'RMH1', 'Mobile Home Residential',                 'RURAL 2', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-035-008-07344-000', 1402, 'R1',   'Single Family Residential (Rural/Urban)', 'RURAL 2', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-035-008-07597-000', 1402, 'R1',   'Single Family Residential (Rural/Urban)', 'RURAL 2', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-035-008-07761-000', 1402, 'R1',   'Single Family Residential (Rural/Urban)', 'RURAL 2', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-035-008-07784-000', 1402, 'R1',   'Single Family Residential (Rural/Urban)', 'RURAL 2', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-078-013-11303-000', 1402, 'RMH1', 'Mobile Home Residential',                 'URBAN 1', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-035-008-07816-000', 1402, 'R1',   'Single Family Residential (Rural/Urban)', 'RURAL 2', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-035-008-07862-000', 1402, 'R1',   'Single Family Residential (Rural/Urban)', 'RURAL 2', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-077-014-10391-000', 1402, 'RMH1', 'Mobile Home Residential',                 'URBAN 1', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-078-013-10734-000', 1402, 'RMH1', 'Mobile Home Residential',                 'URBAN 1', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-034-012-09571-064', 1402, 'R1',   'Single Family Residential (Rural/Urban)', 'RURAL 2', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-054-000-09911-001', 1402, 'R1',   'Single Family Residential (Rural/Urban)', 'RURAL 2', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-034-012-09631-001', 1402, 'R1',   'Single Family Residential (Rural/Urban)', 'RURAL 2', 'ZoningWakulla_ArcGIS_run3713'),
  ('00-00-034-009-08162-000', 1402, 'R1',   'Single Family Residential (Rural/Urban)', 'RURAL 2', 'ZoningWakulla_ArcGIS_run3713'),
  ('08-3s-01w-208-04334-028', 1402, 'RR1',  'Rural Residential',                       'RURAL 2', 'ZoningWakulla_ArcGIS_run3713');

COMMIT;
