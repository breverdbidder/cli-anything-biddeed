-- Gold Standard shard-5 martin (dispatch 1f420b07, 08:00Z session).
-- Letter I (property card completeness). Two rows had property_address + parcel_id +
-- assessed_value already populated but were missing latitude/longitude, the only
-- remaining gap in the "address+geo+value+zoned parcel" card_complete definition.
--
-- Both addresses geocoded via Martin County's own official GeocodeServer
-- (geoweb.martin.fl.us/arcgis/rest/services/geocoding/mc_address_points_ll) and
-- independently cross-checked against the US Census Bureau geocoder
-- (geocoding.geo.census.gov) before writing:
--   25000102CAAXMX  828 SE 14TH ST, STUART FL 34996        delta vs Census ~13m
--   25000496CAAXMX  2600 S KANNER HWY H10, STUART FL 34994  delta vs Census ~90m (lat), ~280m (lon; condo subaddress point vs building centroid)
--
-- Applied live via PostgREST during the session (direct psql unavailable per the
-- documented pooler tenant-identifier constraint); this file is the audit record.
--
-- UPDATE (same session, after a Workflow fan-out + adversarial verify pass):
-- 09-38-41-003-009-00010-1 (25000102CAAXMX) IS inside Stuart city limits, where
-- the county's Future_Landuse_Zoning layer only returns a "STUART" placeholder.
-- Found and adversarially verified the City of Stuart's OWN official zoning
-- source: services.arcgis.com/RyoFD3Lw9KSERnvQ/arcgis/rest/services/COS_Zoning/
-- FeatureServer/0 (City of Stuart GIS Dept). Two independent queries against it
-- (PCN attribute match + point-in-polygon at the geocoded coords) both return
-- OBJECTID 1563, ZONING='R-1', ZONING_SUB='ELDORADO HEIGHTS' -- a refuter agent
-- independently reproduced both queries before this was counted as verified.
-- Reused existing zoning_districts id 7520 (R-1/jurisdiction 812=Stuart), already
-- populated from a prior session (20260718n / 20260719 shard-14 Stuart R-1 fixes)
-- and already in use by 2 other Stuart parcels -- no new unstandardized zone code
-- introduced, so no G-regression risk (confirmed live: G held at 100.0% after).
-- card_complete moved 38/43 (88.4%) -> 39/43 (90.7%). Applied live via PostgREST
-- INSERT into parcel_zones (id 863149); see gold_standard_ultraloop_audit rows
-- 15991/15992 for the full adversarial-verify evidence trail.
--
-- 25000496CAAXMX's parcel (16-38-41-005-008-00100-7) resolves to a real zoning
-- code too -- R-3A, unincorporated Martin, confirmed live via geoweb.martin.fl.us
-- Administrative_Areas/Future_Landuse_Zoning/MapServer/1 point-in-polygon query --
-- but was deliberately NOT inserted this session: R-3A does not yet exist in our
-- zoning_districts/zone_standards tables, and inserting it without real
-- max_density_du_acre/max_far/parking_per_1000sf values would regress letter G
-- (documented failure mode, see
-- 20260814_gold_standard_shard2_5f3a88a5_okaloosa_g_destin_roitd_zoning_fix.sql).
-- Martin LDR Article 3, Division 2, Section 3.12 (Table 3.12 Development
-- Standards) is the correct source for R-3A's real standards
-- (https://library.municode.com/fl/martin_county/codes/land_development_regulations_?nodeId=LADERE_ART3ZODI_DIV2STZODI_S3.11PEUS)
-- but WebFetch (403/timeout) and Firecrawl (out of credits) were both unavailable
-- this session -- left for a future session rather than fabricate values.
--
-- E remains at its documented structural ceiling (40/43, 93.0%): the 3
-- NON_REAL_PROPERTY rows (23001555CCAXMX personal-property lien, 25001634CCAXMX +
-- 25001632CCAXMX timeshare-interest, Plantation Beach Club Condominium
-- Association) got two fresh, genuinely new research angles this session
-- (Fla Stat 721 timeshare-estate parcel theory; Tropical Acres co-op-share
-- structure confirmation) -- both surfaced real, useful context but neither
-- produced a case-specific, citable parcel_id, so nothing was written. See the
-- session report for the full evidence trail and next-session leads.

UPDATE public.multi_county_auctions
SET latitude = 27.186488, longitude = -80.239480
WHERE county = 'martin' AND case_number = '25000102CAAXMX';

UPDATE public.multi_county_auctions
SET latitude = 27.172924, longitude = -80.255404
WHERE county = 'martin' AND case_number = '25000496CAAXMX';

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES (
  '09-38-41-003-009-00010-1',
  812,
  'R-1',
  'Residential - Single Family General',
  'services.arcgis.com/RyoFD3Lw9KSERnvQ/arcgis/rest/services/COS_Zoning/FeatureServer/0 (City of Stuart) attribute+point-in-polygon dual-query exact match OBJECTID 1563, PCN 093841003009000101 VERIFIED live 2026-08-16, gold-standard-shard5-martin-1f420b07'
)
ON CONFLICT DO NOTHING;
