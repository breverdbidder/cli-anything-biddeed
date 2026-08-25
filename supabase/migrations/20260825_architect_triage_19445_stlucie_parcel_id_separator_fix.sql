-- ARCHITECT TRIAGE issue #19445 (dispatch df9092e1): st_lucie letter I false-negative.
--
-- ROOT CAUSE (confirmed live against map.paslc.gov/arcgis/.../SLCPA_PublicParcels,
-- 13/13 sampled addresses matched exactly): the canonical St. Lucie County Property
-- Appraiser PARCELNO format uses a DASH as every separator, including the trailing
-- sub-parcel segment (e.g. "3420-695-1461-000-1"). Four zoning-ingestion runs
-- (port_st_lucie_arcgis_zoning, fort_pierce_arcgis_cityzoning,
-- st_lucie_county_arcgis_landuse_zoning -- both the 20260815 and 20260824 firings)
-- wrote parcel_zones.parcel_id with a SLASH in that final segment instead
-- ("3420-695-1461-000/1"). Separately, 93 multi_county_auctions.parcel_id rows for
-- st_lucie carried the same slash-instead-of-dash defect. Because both sides
-- happened to use the SAME wrong separator for the same real parcels, most rows
-- still joined "successfully" -- but any row where only one side had been touched
-- by a slash-writing ingestion (and not the other) silently failed the
-- v_zoning_gold_standard_card join that letter I depends on, undercounting
-- card_complete by more than the two tables' visible symptoms alone.
--
-- FIX (data-only, zero schema change, applied live via PostgREST before this file
-- was committed -- SUPABASE_DB_PASSWORD/psql pooler auth is unavailable in this
-- runner, same known constraint as decision_log ids 169/205/287):
--   1. multi_county_auctions: 93 st_lucie rows, parcel_id trailing "/N" -> "-N"
--   2. parcel_zones: 99 rows (63 from the 20260815 sources + 36 from the
--      20260815/20260824 remainder), parcel_id trailing "/N" -> "-N"
-- Verified zero remaining slash-format parcel_id rows in parcel_zones fleet-wide
-- after the fix (i.e. this defect was 100% isolated to the four st_lucie sources
-- above -- no cross-county blast radius).
--
-- RESULT: pencil_dod_evaluate_county('st_lucie') letter I: card_complete
-- 227 of 239 (94.98%%, FAIL) -> 229 of 239 (95.8%%, PASS). No regression on any
-- other letter (A/B/D/E/F/G/H/J unchanged; G still 97.0). Audit logged as
-- gold_standard_ultraloop_audit id 18179, survived=true.
--
-- st_lucie is now 9/10. Letter C (matched_clean=188/239=78.7%%) remains FAIL --
-- this is a SEPARATE, already-escalated-5x (2026-08-15, 08-16, 08-24 x2, 08-25)
-- structural ceiling: CLERK_SSOT_CANCELLED auctions count toward auctions_total
-- (the C denominator) but can never satisfy matched_clean by
-- pencil_dod_evaluate_county's own design (see
-- 20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql:21-27). Fixing
-- it requires a fleet-wide (all 67 counties) evaluator-formula policy change, which
-- is out of architect-triage autonomous-fix scope -- see the BLOCKED comment on
-- issue #19445 for the ready-to-apply migration and the human decision it needs.
--
-- Idempotent: re-running this UPDATE after the live fix is a no-op (no remaining
-- rows match the WHERE clause).

UPDATE public.multi_county_auctions
SET parcel_id = regexp_replace(parcel_id, '/(\d+)$', '-\1')
WHERE lower(county) = 'st_lucie'
  AND parcel_id ~ '/(\d+)$';

UPDATE public.parcel_zones
SET parcel_id = regexp_replace(parcel_id, '/(\d+)$', '-\1')
WHERE source IN (
    'port_st_lucie_arcgis_zoning_20260815',
    'port_st_lucie_arcgis_zoning_20260824',
    'fort_pierce_arcgis_cityzoning_20260815',
    'fort_pierce_arcgis_cityzoning_20260824',
    'st_lucie_county_arcgis_landuse_zoning_20260815',
    'st_lucie_county_arcgis_landuse_zoning_20260824'
  )
  AND parcel_id ~ '/(\d+)$';
