-- GOLD STANDARD shard-6 (st_lucie), loop run 6288, dispatch 5fa42352-4a49-40b4-9548-8ed140b2d4bc
-- Applied LIVE via Management API during the 2026-07-25 session, adversarially
-- verified by an independent refuter agent (fresh Bash/curl context, no shared
-- context with the implementer). This migration is the idempotent record.
--
-- BEFORE this file's changes (st_lucie was already 9/10 after the C/D/F fixes
-- in 20260725_gold_standard_shard6_highlands_stlucie_run6288.sql):
--   I FAIL 86.5% (card_complete=96/111)
-- AFTER: I PASS 96.4% (card_complete=107/111), G held PASS at 97.9%
--   (density=97.9, far/pk1000 not applicable -- same pattern as before this
--   change, see note below on the regression this migration also repairs).

-- ── ST_LUCIE I ───────────────────────────────────────────────────────────────
-- 11 auction rows had complete property_address/lat/lon/assessed_value but no
-- zoning linkage: their parcel_ids simply don't appear in st_lucie's sparse
-- (237-row) parcel_zones sample. Each zone_code below was independently
-- researched via live county/city GIS (ArcGIS FeatureServer/MapServer, exact
-- parcel-ID or spatial-intersect match) and adversarially confirmed by a
-- second agent using a DIFFERENT source path than the original lookup before
-- being written here — see gold_standard_ultraloop_audit rows for
-- county_slug='st_lucie' AND letter='I' (loop run 6288) for full evidence.
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, effective_date)
VALUES
  ('342062015600003', 953,  'RS-2', 'Single-Family Residential',                  'shard6_run6288:port_st_lucie_arcgis_zoning_featureserver:PZ_ZONING:ZO_ID=Z958', CURRENT_DATE),
  ('341951502580009', 1400, 'RS-4', 'Residential Single-Family (RS-4)',           'shard6_run6288:slcgis.stlucieco.gov:LandUse/Zoning/MapServer:Parcel_num_exact_match', CURRENT_DATE),
  ('332382600660007', 953,  'PUD',  'Planned Unit Development',                   'shard6_run6288:port_st_lucie_arcgis_re_parcels_web:PARCELID_exact_match', CURRENT_DATE),
  ('342060506510004', 953,  'RS-2', 'Single-Family Residential',                  'shard6_run6288:port_st_lucie_arcgis_zoning_featureserver:PZ_ZONING_spatial_intersect', CURRENT_DATE),
  ('240951600420001', 971,  'R-4',  'Medium Density Residential Zone',            'shard6_run6288:fort_pierce_arcgis_cityzoning_featureserver:ParcelID_exact_match', CURRENT_DATE),
  ('242980200900002', 971,  'PD',   'Planned Development',                        'shard6_run6288:fort_pierce_arcgis_cityzoning_featureserver:ParcelID_exact_match', CURRENT_DATE),
  ('24989',           971,  'R-2',  'City of Fort Pierce Zoning',                 'shard6_run6288:slcgis.stlucieco.gov:LandUse/ForttPierceZoningFLU/MapServer:resolved_via_PA_crossref', CURRENT_DATE),
  ('137184',          953,  'PUD',  'Planned Unit Development',                   'shard6_run6288:port_st_lucie_arcgis_zoning_featureserver:PZ_ZONING', CURRENT_DATE),
  ('72947',           953,  'RS-2', 'Single-Family Residential',                  'shard6_run6288:port_st_lucie_arcgis_zoning_featureserver:resolved_via_PA_PropertyID_crossref', CURRENT_DATE),
  ('62261',           953,  'RS-2', 'Single-Family Residential',                  'shard6_run6288:port_st_lucie_arcgis_zoning_featureserver:resolved_via_PA_PropertyID_crossref', CURRENT_DATE),
  ('110113',          1400, 'RM-9', 'Residential Multi-Family (RM-9)',            'shard6_run6288:map.paslc.gov:StLucie_PAT_Layers_MapServer_29:spatial_intersect', CURRENT_DATE)
ON CONFLICT DO NOTHING;

-- 3 rows remain fully unresolved (2024CA000214 fully blank; 2023CA000465 and
-- 2025CA002738 carry a "Property Appraiser" garbage parcel_id from an
-- upstream scraper bug). The research workflow could not find live-verifiable
-- data for these and correctly returned found=false/confidence=UNTESTED
-- rather than guessing (BLANK > WRONG). Left unfixed; I=96.4% already clears
-- the >=95% threshold without them. Flagged for a future session/scraper-bug
-- fix (the garbage parcel_id is a separate root-cause worth its own pass).

-- ── ST_LUCIE G (regression introduced by the I fix above, repaired here) ────
-- 2 of the 11 zone_code links above (PUD@jurisdiction 953, PD@jurisdiction
-- 971) pointed at existing zoning_districts rows with no far_regulated/
-- density_regulated override, and a third (RM-9@jurisdiction 1400) had NO
-- zoning_districts row at all. v_zoning_gold_standard_kpi_v3's
-- COALESCE(a.far_applicable, true) silently defaulted the orphaned RM-9
-- parcel to "applicable, no standards on file" for ALL THREE metrics, and
-- category=NULL on the PUD/PD rows fell through the same "applicable"
-- default -- collapsing G from 95.4% (density-only, far/pk1000 previously
-- had zero applicable rows and were ignored) to 0.0% FAIL.
--
-- Repair: mark PUD/PD as NOT far/density-regulated (they are individually
-- negotiated per-development, not code-fixed dimensional standards -- some,
-- not a strict majority, of fleet-wide PUD districts already carry this same
-- explicit override; see ultraloop_audit for the corrected precedent count),
-- and create the missing RM-9 zoning_districts row with category='Residential'
-- so far/pk1000 correctly default to not-applicable while density correctly
-- stays applicable (honestly still missing a value -- no numeric density
-- fabricated for RM-9).
UPDATE zoning_districts
SET far_regulated = false, density_regulated = false
WHERE id IN (11559, 12073);  -- PUD@Port St Lucie(953), PD@Fort Pierce(971)

INSERT INTO zoning_districts (jurisdiction_id, code, name, category)
VALUES (1400, 'RM-9', 'Residential Multi-Family (RM-9)', 'Residential')
ON CONFLICT DO NOTHING;
