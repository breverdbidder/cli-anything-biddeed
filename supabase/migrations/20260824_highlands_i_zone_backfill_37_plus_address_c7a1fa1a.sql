-- Gold Standard shard-11 2nd firing (dispatch c7a1fa1a): highlands letter I
-- (card_complete) live-litmus re-check and fix.
--
-- Baseline (fetched live, pencil_dod_evaluate_county p_county='highlands'):
--   I: card_complete=343 of 401 = 85.5% FAIL (threshold >=95.0%, need >=381)
--
-- Diagnosis (live-joined multi_county_auctions against v_zoning_gold_standard_card
-- for county='highlands', re-derived fresh this session):
--   37 rows had complete address/geo/assessed_value already, but no
--   public.parcel_zones row (zone_code linkage missing). All 37 share the
--   Highlands County PIN format "C-NN-NN-NN-NNN-NNNN-NNNN" and were created
--   2026-08-22 as part of a fresh ingestion batch that had not yet had a
--   zone-assignment pass run over it. This is the same gap class documented
--   in the prior highlands I backfill, commit b0fcc3a3
--   (20260812b_highlands_i_zone_backfill_lake_placid_b1_guard.sql).
--
--   1 additional row (case_number 25000871) had a parcel_id and zone gap
--   AND a NULL property_address (its lat/long and assessed_value were
--   already populated). Fixing the 37 zone-only rows alone reaches
--   380/401 = 94.76%, one row short of the 381-row (95.0%) pass threshold
--   (401 * 0.95 = 380.95, rounds up to 381). This row was additionally
--   resolved to cross the threshold.
--
-- Fix (all writes verified against LIVE sources this session, applied via
-- PostgREST against the live Supabase project -- reproduced here as a
-- migration file per repo convention; the live writes already happened,
-- this file documents/replays them idempotently):
--
--   1. 38 parcel_zones rows inserted, one per parcel, using the proven
--      live Highlands County zoning ArcGIS MapServer lookup
--      (https://gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0/query,
--      STRAP_NUM = parcel_id with dashes removed). All 5 distinct
--      (jurisdiction_id, zone_code) pairs produced --
--      (840,'R1') x30, (918,'R1') x4, (918,'R1A') x2, (840,'B1') x1,
--      (1654,'R1') x1 -- already existed in zoning_districts /
--      zone_standards from prior sessions, so no new zoning_districts rows
--      were required and letter G (density/FAR/parking coverage) could not
--      regress from a missing-code crash. Verified live: G unchanged at
--      99.7% PASS before and after.
--
--   2. multi_county_auctions.property_address for case_number='25000871'
--      (parcel_id C-22-37-30-050-0500-0150) set to the real situs address
--      on file with the Highlands County Property Appraiser,
--      "352 PARADISE AVE, LAKE PLACID, FL 33852", fetched live from
--      https://www.hcpao.org/Search/Parcel/30372205005000150C (STRAP
--      C223730-05005000150, confirmed matching parcel via the site's own
--      unified search for the exact PIN). No fabricated geo/value: this
--      row's latitude/longitude/assessed_value were already populated
--      pre-existing in the row and were left untouched.
--
-- Result (fetched live, same evaluator, same session):
--   I: card_complete=381 of 401 = 95.0% PASS
--
-- NOTE: this migration is intentionally idempotent (ON CONFLICT DO NOTHING
-- for parcel_zones matches the live PostgREST call's
-- resolution=merge-duplicates Prefer header behavior; the UPDATE is a no-op
-- if already applied).

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT v.parcel_id, v.jurisdiction_id, v.zone_code, v.source
FROM (VALUES
  ('C-22-37-30-050-0500-0110', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-030-0300-0050', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-100-1020-0010', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-190-2280-0970', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-060-0610-0040', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-160-1670-0160', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-090-0570-0100', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-24-35-28-040-0040-0020', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-060-0540-0060', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-04-34-28-080-1100-0080', 1654, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-090-0570-0070', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-080-0930-0170', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-24-35-28-180-0940-0170', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-170-1730-0040', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-050-0500-0020', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-060-0590-0040', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-090-0820-0200', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-110-1090-0160', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-060-0540-0160', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-050-0510-0190', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-090-0630-0160', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-060-0620-0080', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-24-35-28-030-0040-0080', 918, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-160-1680-0040', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-050-0540-0050', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-050-0540-0200', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-070-0890-0220', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-060-0600-0140', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-191-1840-0110', 840, 'B1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-170-1760-0060', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-090-0770-0200', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-24-35-28-040-0040-0060', 918, 'R1A', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-090-0800-0080', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-090-0820-0130', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-24-35-28-180-0940-0140', 918, 'R1A', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-020-0440-0010', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-050-0500-0230', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a'),
  ('C-22-37-30-050-0500-0150', 840, 'R1', 'hcpao_zoning_arcgis:gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0:c7a1fa1a')
) AS v(parcel_id, jurisdiction_id, zone_code, source)
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones pz WHERE pz.parcel_id = v.parcel_id
);

UPDATE public.multi_county_auctions
SET property_address = '352 PARADISE AVE, LAKE PLACID, FL 33852'
WHERE case_number = '25000871'
  AND lower(county) = 'highlands'
  AND parcel_id = 'C-22-37-30-050-0500-0150'
  AND property_address IS NULL;
