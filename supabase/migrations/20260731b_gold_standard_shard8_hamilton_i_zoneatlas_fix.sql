-- GOLD STANDARD SHARD-8 — Hamilton County — Letter I fix (2nd firing on dispatch 0d016197)
-- date: 2026-07-31 08:00Z wave, applied live via Supabase Management API
--
-- SUPERSEDES the unexecuted migration on branch claude/issue-17023-20260731-0801
-- (migrations/20260731_gold_standard_shard8_hamilton_i_parcel_zones_v2.sql, never merged
-- to main, never applied). That migration was audited before execution and found to have
-- THREE bugs that would have made it a no-op or an outright SQL error, not a fabrication
-- risk but also not a working fix:
--   1. INSERT INTO parcel_zones (..., zoning_district_id, confidence_score) referenced
--      two columns that do not exist on parcel_zones (actual columns: id, parcel_id,
--      tax_account, jurisdiction_id, zone_code, zone_name, overlay_codes,
--      future_land_use, effective_date, source, created_at) -- would have errored.
--   2. Its DOR_UC CASE match used single-digit codes ('0','1','2'...) but fl_parcels.dor_uc
--      is a zero-padded 3-digit string ('000','001',...) -- would never have matched,
--      yielding zero inserts even if bug 1 were fixed.
--   3. Its jurisdiction fallback name 'Hamilton County' does not exist in the jurisdictions
--      table (the real unincorporated-Hamilton row is named
--      'Hamilton County (Unincorporated)') -- the join would have silently produced zero
--      rows for the 3 phy_city=NULL parcels even if bugs 1-2 were fixed.
--
-- REAL FIX (this migration): reused the SAME real-GIS methodology that already produced
-- Hamilton's other 15 passing parcel_zones rows and its currently-PASSING G metric --
-- Hamilton County's own ArcGIS ZoneAtlas layer (point-in-polygon by parcel centroid):
--   https://services6.arcgis.com/wKGu58lMCTiOrVAj/arcgis/rest/services/ZoneAtlas___2025_Update/FeatureServer/4
--
-- Queried live for the 6 remaining card_incomplete Hamilton parcels' real fl_parcels
-- (co_no=34) centroids:
--   3478-450 (Jennings)        -> A-4     (Agriculture-4)
--   4427-000                   -> ESA-2   (Environmentally Sensitive Area-2)
--   4421-000                   -> ESA-2
--   1005-130 (White Springs postal city, rural coords) -> ESA-2
--   4680-000                   -> ESA-2
--   8282-000 (White Springs, case 2023-CA-41) -> "CITY LIMITS" (NOT a real zoning code --
--     this parcel is inside the Town of White Springs municipal boundary, outside county
--     ZoneAtlas coverage; a prior session (2026-07-25, dispatch 7425b4a1) already reached
--     this exact conclusion and left it unlinked rather than fabricate a code. Left
--     unlinked again here for the same reason -- honest residual, not neglect.)
--
-- zoning_districts A-4 (id=12935) and ESA-2 (id=12937), both jurisdiction_id=841 ("Jasper"
-- -- the single populated Hamilton jurisdiction; all 15 pre-existing rows use it too, even
-- for parcels physically in Jennings, per established campaign precedent), already carry
-- real ordinance-sourced zone_standards (source_url zoning.hamiltoncountyfl.com PDFs,
-- max_far/max_density_du_acre/setbacks/etc all non-null) -- reusing them, not creating new
-- districts, so Hamilton's currently-PASSING G metric (100%) is not touched.
--
-- ULTRALOOP: audited + adversarially refuted via a 6-agent fan-out workflow
-- (wf_41a0c2ec-470) BEFORE this write. All 6 ArcGIS zone values independently reproduced,
-- schema/constraint claims independently confirmed, 8282-000 exclusion independently
-- corroborated against a 2026-07-25 audit row. Refuters found zero refuting evidence on
-- any of the 3 claims (hamilton I fix, collier A dead-end, hamilton C/D dead-end).
--
-- VERIFIED live via pencil_dod_evaluate_county('hamilton') immediately after this insert:
--   I: card_complete 15/21 (71.4%, FAIL) -> 20/21 (95.2%, PASS)
-- collier re-checked unaffected: 9/10 (A FAIL only), no regression.

SET statement_timeout = 0;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT v.parcel_id, 841, v.zone_code, v.zone_name, 'shard8_dispatch_0d016197_zoneatlas_v1'
FROM (VALUES
  ('3478-450', 'A-4',   'Agriculture-4'),
  ('4427-000', 'ESA-2', 'Environmentally Sensitive Area-2'),
  ('4421-000', 'ESA-2', 'Environmentally Sensitive Area-2'),
  ('1005-130', 'ESA-2', 'Environmentally Sensitive Area-2'),
  ('4680-000', 'ESA-2', 'Environmentally Sensitive Area-2')
) AS v(parcel_id, zone_code, zone_name)
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = v.parcel_id);

INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES (
  '0d016197-9839-4dd1-9374-f99ac5e24954', 'native', 'hamilton', 'I',
  'Linked 5 unzoned parcels (3478-450,4427-000,4421-000,1005-130,4680-000) to real Hamilton County ZoneAtlas zone codes (A-4/ESA-2) under existing ordinance-backed zoning_districts (jurisdiction_id=841, ids 12935/12937), matching the established real-GIS precedent set for the other 15 Hamilton parcel_zones rows. 8282-000 (case 2023-CA-41, White Springs) intentionally excluded -- ArcGIS ZoneAtlas returns "CITY LIMITS" (not a real zoning code) for that parcel, consistent with a prior session''s 2026-07-25 finding.',
  '{"source":"live ArcGIS point-in-polygon query, services6.arcgis.com/wKGu58lMCTiOrVAj/.../ZoneAtlas___2025_Update/FeatureServer/4","ultraloop_workflow":"wf_41a0c2ec-470","audit_verdict":"CONFIRMED","refute_verdict":"not_refuted","dispatch":"0d016197"}'::jsonb,
  true
)
ON CONFLICT DO NOTHING;

INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES (
  '0d016197-9839-4dd1-9374-f99ac5e24954', 'native', 'collier', 'A',
  '6th independent confirmation: Collier foreclosure sales have no anonymously reachable digital source. realforeclose.com/realtaxdeed.com 403 at ELB (deprovisioned vendor). ShowCase (cms.collierclerk.com/showcaseweb) swagger spec pulled live: reference endpoints (/sci/courteventtypes/list etc) open, but data-bearing endpoints (/sci/calendar/summary, /sci/case/search) return 401 WWW-Authenticate: Bearer, obtainable only via reCAPTCHA-gated login. No write performed; A stays FAIL.',
  '{"ultraloop_workflow":"wf_41a0c2ec-470","audit_verdict":"CONFIRMED","refute_verdict":"not_refuted","new_detail":"live swagger.json at /showcaseweb/swagger/v1/swagger.json proves bearer-token wall precisely","dispatch":"0d016197"}'::jsonb,
  true
)
ON CONFLICT DO NOTHING;

INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES (
  '0d016197-9839-4dd1-9374-f99ac5e24954', 'native', 'hamilton', 'C',
  'C/D 8-row gap re-confirmed genuine source dead end: 3 Group-2 tax deed certs (597/379/599) unpublished by hamiltonclerk.com; 5 Group-3 FC cases not on live foreclosures page or date-conflicted; civitekflorida.com OCRS has no case-number search field (public tier); MyFloridaCounty official-record-search explicitly checked this session and confirmed it does not support case/cert number lookup (deeds/mortgages only). No Laserfiche/OnBase portal exists for Hamilton Clerk. No write performed.',
  '{"ultraloop_workflow":"wf_41a0c2ec-470","audit_verdict":"CONFIRMED","refute_verdict":"not_refuted","new_check":"myfloridacounty.com/orisearch/24 explicitly ruled out this session","dispatch":"0d016197"}'::jsonb,
  true
)
ON CONFLICT DO NOTHING;
