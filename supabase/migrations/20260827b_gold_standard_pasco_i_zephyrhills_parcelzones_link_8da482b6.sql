-- Gold Standard dispatch 8da482b6-8cff-45ea-9950-4e8fed552f37 — pasco letter I
-- (follow-up to 20260827_gold_standard_pasco_i_parcelzones_link_geo_backfill_8da482b6.sql)
--
-- POST-APPLY RE-VERIFICATION found the prior migration's Pattern-1 list
-- incorrectly included 2 parcels (04-26-21-0150-00800-0080, 6964 RIPPLE POND
-- LOOP is a typo for its address -- correct address is 36523 SMITHFIELD
-- LANE; and 04-26-21-0140-00100-0470, 6964 RIPPLE POND LOOP) that were NOT
-- actually present in zoning_assignments (that SELECT correctly excluded
-- them, so no wrong data was written -- but they remained un-linked, still
-- failing letter I after the first migration applied).
--
-- Live re-check via Pasco GIS (services9.arcgis.com/.../Parcels_2023
-- FeatureServer) shows why: both parcels are JURISDICTION_NAME=
-- "CITY OF ZEPHYRHILLS" (an INCORPORATED municipality, jurisdiction_id=811
-- in the jurisdictions table), not unincorporated Pasco County
-- (jurisdiction_id=1258) like the other 12 parcels in the prior migration.
-- ZONING field='ZH-100' (base code 'ZH') for both. This is why they weren't
-- in zoning_assignments under the 'county_gis_pasco_pascopa_arcgis' sync
-- (that sync appears scoped to unincorporated parcels for pasco) and why
-- assuming jurisdiction 1258 for them would have been wrong.
--
-- Both parcels already have real address+geo+assessed_value from the prior
-- 2026-08-25 backfill session (confirmed via direct SELECT before writing
-- this migration) -- only the parcel_zones link is missing.
--
-- HONESTY MARKERS:
--   zone_code='ZH', jurisdiction_id=811: CONFIRMED -- live-fetched this
--   session from services9.arcgis.com/.../Parcels_2023/FeatureServer/0/query,
--   HPARCEL exact match, JURISDICTION_NAME field read directly from the
--   county's own GIS attribute (not inferred from postal city this time).
--
-- HARD GUARDRAILS FOLLOWED: county-scoped (pasco), no shared function
-- touched, no fabricated value, idempotent (NOT EXISTS guard).
-- ============================================================================

SET statement_timeout = 0;

INSERT INTO public.parcel_zones (jurisdiction_id, parcel_id, zone_code, source)
SELECT 811, v.parcel_id, 'ZH', 'gold_standard_pasco_i_8da482b6:zephyrhills_arcgis_direct'
FROM (VALUES
  ('04-26-21-0150-00800-0080'),
  ('04-26-21-0140-00100-0470')
) AS v(parcel_id)
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = 811
);

-- ============================================================================
-- VERIFICATION (run after applying)
-- ============================================================================
-- SELECT public.pencil_dod_evaluate_county('pasco');
-- Expect I metric to rise from 97.8 (360/368) to 98.4 (362/368).
