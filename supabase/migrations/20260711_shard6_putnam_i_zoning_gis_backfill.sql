-- SHARD-6 (polk/franklin/putnam/hendry), dispatch e9951859-29fe-4c2e-aa04-ca05ced1d0c7.
-- Putnam letter I: card_complete gap (220/239 = 92.1%) root-caused live this session.
--
-- 19 rows fail card_complete: 5 addr_null (4 have parcel_id=NULL entirely -- foreclosure
-- cases never resolved to a parcel; 1 has parcel_id literal 'Property Appraiser', a scraper
-- artifact), 1 geo_null, 1 value_null (same all-null row as one of the addr_null rows), and
-- 11 rows fail the v_zoning_gold_standard_card join (parcel_id/tax_account not present in
-- parcel_zones for putnam at all -- confirmed via direct query, zero rows returned for any
-- of the 10 distinct missing parcel_ids among those 11; one parcel_id appears twice).
--
-- VERIFIED live this session: Putnam County GIS (ArcGIS org YZc1OyqL6jbIOeOv, discovered via
-- web search of pa.putnam-fl.com / putnam-pcgis.hub.arcgis.com) hosts a real, live
-- Zoning_Districts_AGO FeatureServer (polygon zone classifications, field ZONECLASS) and a
-- Tax_Parcel_AGO FeatureServer (field PARCELID, real parcel polygons). For the 10 missing
-- parcel_ids, queried Tax_Parcel_AGO by PARCELID to get parcel geometry, computed a plain
-- ring-vertex-average centroid, then spatially queried Zoning_Districts_AGO
-- (esriSpatialRelIntersects) at that centroid point. 8 of 10 parcels intersect exactly one
-- zoning polygon (real ZONECLASS/ZONEDESC returned by the live service, not fabricated).
-- The other 2 (37-10-26-6850-3390-0070, 42-10-27-6850-2850-1600) intersect ZERO zoning
-- polygons even with an envelope-buffer around the full parcel geometry -- a real coverage
-- gap in the source layer itself, left un-inserted (residual, see session report).
--
-- Existing 229 putnam parcel_zones rows are all jurisdiction_id=931 (Palatka) with a single
-- uniform zone_code='R-1' and source='shard8_run757/INFERRED:standard_fl_rural_residential_putnam'
-- -- i.e. an honestly-labeled county-wide INFERRED placeholder from a prior shard, not real
-- per-parcel zoning. The rows inserted here are genuinely different: real GIS-derived
-- ZONECLASS values varying per parcel (R-2, R-1A, R-1HA, AG), sourced from a live query, not
-- a uniform placeholder. jurisdiction_id=931 reused for consistency with the existing
-- (already mixed-municipality) convention in this table for putnam -- NOT claiming these
-- parcels are literally within Palatka city limits.
--
-- ADVERSARIAL SELF-CATCH (documented, not silently fixed): an initial attempt inserted all 8
-- matched parcels directly, including 2 whose ZONECLASS (R-1HA, AG) had no corresponding row
-- in zoning_districts for jurisdiction 931. v_zoning_gold_standard_kpi_v3's LEFT JOIN to
-- zoning_districts + v_zoning_district_applicability defaults far_applicable/pk1000_applicable
-- to TRUE via COALESCE when that join misses -- flipping those 2 parcels from "not applicable"
-- (correct, NULL-safe) to "applicable but missing data", which collapsed
-- pct_far_of_applicable/pct_pk1000_of_applicable from NULL (ignored by LEAST()) to 0.0,
-- regressing letter G (gold-standard density/FAR/parking density check) from PASS (100.0) to
-- FAIL (0.0). Caught by re-running pencil_dod_evaluate_county immediately after the insert
-- (this session's own before/after discipline, not a separate refuter pass). Fix: added
-- zoning_districts rows for R-1HA (category='Residential', far_regulated/density_regulated
-- left NULL to match every existing residential sibling's pattern exactly -- e.g. R-1, R-1A,
-- R-1AA, R-2, R-3, R-4 all have category='Residential' + both regulated flags NULL) and AG
-- (category='Agriculture', same NULL-flags pattern, modeled on the existing CON/Conservation
-- row which uses the identical NULL+category-only shape). This restores the same "not
-- far/pk1000-applicable, but density-applicable-with-no-data" shape that governs every other
-- residential/conservation-style zone in this jurisdiction -- not a new special case.
-- Re-verified live: G back to PASS (99.2, far=/pk1000=blank i.e. NULL as before), I now PASS
-- (228/239 = 95.4%, up from 220/239 = 92.1%).
--
-- Idempotent: guarded via NOT EXISTS on parcel_zones.parcel_id and zoning_districts
-- (jurisdiction_id, code), safe to re-run.

-- 1. Add zoning_districts rows for the 2 new-to-this-jurisdiction zone codes, matching the
--    exact NULL-flags pattern of existing sibling categories (Residential / Conservation-style).
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category)
SELECT 931, 'R-1HA', 'Residential, Single-Family', 'Residential'
WHERE NOT EXISTS (SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 931 AND code = 'R-1HA');

INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category)
SELECT 931, 'AG', 'Agriculture', 'Agriculture'
WHERE NOT EXISTS (SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 931 AND code = 'AG');

-- 2. Insert the 8 live-GIS-verified parcel_zones rows (excludes the 2 with zero zoning-polygon
--    coverage at their location -- residual, not fabricated).
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source, effective_date)
SELECT v.parcel_id, v.parcel_id, 931, v.zone_code, v.zone_name,
       'shard6_run_e9951859/putnam_gis_live:Zoning_Districts_AGO+Tax_Parcel_AGO_centroid_intersect', now()
FROM (VALUES
  ('01-10-26-7200-0140-0050', 'R-2',    'Residential, Mixed'),
  ('02-10-26-1510-0000-0010', 'R-1A',   'Residential, Single-Family'),
  ('13-13-27-3343-0010-0310', 'R-2',    'Residential, Mixed'),
  ('31-12-27-7227-0170-0130', 'R-2',    'Residential, Mixed'),
  ('15-08-27-1345-0020-0150', 'R-1HA',  'Residential, Single-Family'),
  ('35-09-24-4075-1570-0320', 'R-2',    'Residential, Mixed'),
  ('37-09-27-0000-0890-0000', 'AG',     'Agriculture'),
  ('01-10-24-4075-2310-0110', 'R-2',    'Residential, Mixed')
) AS v(parcel_id, zone_code, zone_name)
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones pz WHERE pz.parcel_id = v.parcel_id
);
