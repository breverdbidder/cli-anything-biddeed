-- GOLD STANDARD shard-11, county=hendry (dispatch bebd50e5, loop run 6148).
--
-- CONTEXT: I=52.6% (card_complete=20 of 38) going into this session. The prior
-- hendry I session (20260711_shard6_hendry_i_zoning_substrate.sql +
-- 20260711_shard6_hendry_cd_live_calendar_match_and_i_geocode.sql) closed the
-- gap for 20 of 38 rows (3 Clewiston + 14 unincorporated parcels via the
-- county's own Zoning FeatureServer, plus a partial 4-row geocode). This
-- session verified live that the OTHER 18 rows fail card_complete for a
-- single root cause -- NOT independent geo/zone gaps: every one of the 18
-- has property_address and assessed/market value present, but NULL
-- latitude/longitude AND no parcel_zones row, and the two gaps are the exact
-- same 18 case numbers (verified: 0 rows have one gap without the other).
-- These 18 rows (Montura Ranches interior sections, Port LaBelle north
-- sections, and one Harlem parcel) were simply never enriched in either
-- pass -- a genuine coverage gap, not a normalization mismatch (fl_parcels
-- co_no=36 has all 18 with matching phy_addr1, confirming correct parcel_id,
-- but centroid_lat/lng is null for ALL of them there too -- FL GIO's own
-- centroid computation is incomplete for hendry, 1998 of 35721 parcels only).
--
-- SOURCE (same authoritative source as the prior session, re-verified live
-- this session, 2026-07-24): Hendry County's own public ArcGIS Zoning
-- FeatureServer (gis.hendryfla.net org, services7.arcgis.com), queried by
-- exact PARCELNO for all 18 remaining parcel_ids -- 18 of 18 matched
-- (3 required a single-space PARCELNO variant vs our stored parcel_id:
-- "10070"->"10 070", "10080"->"10 080", "21051"->"21 051"; verified byte-
-- identical PARCELNO on the matched feature otherwise). Query used
-- outSR=4326&returnCentroid=true to get the real per-parcel polygon centroid
-- directly in WGS84 in the same call as the zone code -- no separate geocoder
-- needed, no invented coordinates. All 18 zone codes are unincorporated
-- Hendry codes already present in this DB from real ordinance-backed rows
-- (RR-F, RR, RG-3, RG-3M) -- not a new zone family, not a placeholder.
--
-- Zone-name mapping reused verbatim from the existing 20260711 migration's
-- naming for the same codes (RR-F "Rural Residential - Farm", RG-3
-- "Residential General", RG-3M "Residential General - Manufactured"); RR
-- ("Rural Residential", no -F suffix) is a code not previously seen for
-- hendry in this DB, named consistently with the RR-F pattern.

SET statement_timeout = 0;

BEGIN;

DO $$
DECLARE
  v_unincorp_id bigint;
BEGIN
  SELECT id INTO v_unincorp_id FROM public.jurisdictions
   WHERE name = 'Hendry County (Unincorporated)' AND county_name = 'Hendry';

  IF v_unincorp_id IS NULL THEN
    RAISE EXCEPTION 'Hendry County (Unincorporated) jurisdiction not found -- prior migration 20260711_shard6_hendry_i_zoning_substrate.sql expected to have created it';
  END IF;

  INSERT INTO public.parcel_zones (jurisdiction_id, parcel_id, zone_code, zone_name, source)
  VALUES
    (v_unincorp_id, '1 34 43 21051 000C-024.0', 'RG-3',   'Residential General',                'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 32 44 36 A00 0210.0000', 'RR-F',   'Rural Residential - Farm',            'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 33 44 07 030 0008-005.0','RR',     'Rural Residential',                   'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 32 44 13 A00 0046.0000', 'RR-F',   'Rural Residential - Farm',            'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 32 44 15 A00 0273.0100', 'RR-F',   'Rural Residential - Farm',            'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 32 44 22 010 0040-008.0','RR-F',   'Rural Residential - Farm',            'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 32 44 22 010 0040-009.0','RR-F',   'Rural Residential - Farm',            'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 32 44 22 010 0040-010.0','RR-F',   'Rural Residential - Farm',            'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 32 44 22 010 0061-030.0','RR-F',   'Rural Residential - Farm',            'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 32 44 22 010 0063-013.0','RR-F',   'Rural Residential - Farm',            'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 32 44 22 010 0067-003.0','RR-F',   'Rural Residential - Farm',            'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 32 44 22 010 0079-015.0','RR-F',   'Rural Residential - Farm',            'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 34 43 23 030 0000-009.0','RG-3M',  'Residential General - Manufactured',  'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 32 44 24 A00 0054.0000', 'RR-F',   'Rural Residential - Farm',            'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 32 44 24 A00 0058.0000', 'RR-F',   'Rural Residential - Farm',            'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '4 29 43 10 070 000D-007.0','RG-3',   'Residential General',                 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '4 29 43 10070 2242-019.0', 'RG-3',   'Residential General',                 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '4 29 43 10080 000D-004.0', 'RG-3',   'Residential General',                 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1')
  ON CONFLICT DO NOTHING;
END $$;

-- Real per-parcel centroid (WGS84) from the same Hendry Zoning FeatureServer
-- query (outSR=4326&returnCentroid=true), one call returning both zone and
-- geometry -- coordinates vary per parcel (not a flat placeholder).
UPDATE public.multi_county_auctions SET latitude = 26.729128151015967, longitude = -80.95084577352911, updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-107' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.61184259973992,  longitude = -81.07915504531374, updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-110' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.66389127444826,  longitude = -81.07833205696458, updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-45'  AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.659844443934226, longitude = -81.08530681812805, updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-47'  AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.654471905308053, longitude = -81.11564242428373, updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-48'  AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.647695054806395, longitude = -81.11250058250653, updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-53'  AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.647683351170553, longitude = -81.1133832585006,  updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-54'  AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.648111022648262, longitude = -81.11342141978538, updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-55'  AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.638759014260437, longitude = -81.10121296116164, updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-56'  AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.645955991115194, longitude = -81.10118203986165, updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-57'  AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.642711337279273, longitude = -81.0981537105248,  updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-58'  AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.646912662450838, longitude = -81.0930804008991,  updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-59'  AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.739184364791512, longitude = -80.91404268435784, updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-60'  AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.647063853624445, longitude = -81.08193705806013, updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-61'  AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.645690654318972, longitude = -81.08190352190314, updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-62'  AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.738189667936638, longitude = -81.3865298473078,  updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-80'  AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.734802947716453, longitude = -81.38038347103809, updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-83'  AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.73855242558373,  longitude = -81.36463629209858, updated_at = now() WHERE lower(county)='hendry' AND case_number = '25-84'  AND latitude IS NULL;

COMMIT;
