-- SHARD-6 hendry, letter I fix (real, scoped zoning substrate).
--
-- Context: only 3 of hendry's 20 multi_county_auctions rows (17 tax_deed +
-- 3 newly-ingested foreclosure, see 20260711_shard6_hendry_a_foreclosure_docket_ingest.sql)
-- had a parcel_zones row (the Montura Ranches "1-28-43-A0-XXXXX-0000.00" format,
-- already present in the DB from a prior session, 21 rows total for hendry).
-- The other 14 tax_deed parcels use a different real Hendry parcel numbering
-- scheme ("SECTION TOWNSHIP RANGE ... " raw PARCELNO format, e.g.
-- "1 29 43 17 100 0000-027.0") that was simply never sourced -- NOT a
-- normalization mismatch, a genuine coverage gap.
--
-- Source found + verified this session: Hendry County's own public ArcGIS
-- Online organization (owner smccormick@hendryfla.net, hosted via
-- gis.hendryfla.net / services7.arcgis.com) publishes a live, queryable
-- "Zoning" FeatureServer with a PARCELNO field that exact-matches our raw
-- MCA parcel_id format:
--   https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1
-- Queried by exact PARCELNO for the 14 previously-unlinked parcels: 14 of 14
-- matched, each returning Current_Zo (current zoning code). This is the
-- county's own authoritative zoning layer -- not PropertyOnion, not an
-- estimate.
--
-- One parcel (3 34 43 01 010 0356-001.0, "W ALVERDEZ AVE, CLEWISTON") returned
-- Current_Zo='CLEWISTON', meaning the county's own zoning layer treats it as
-- inside the City of Clewiston's zoning jurisdiction rather than the
-- unincorporated-county zoning code set -- it is linked to the existing
-- Clewiston jurisdiction (id 866) with zone_code='CLEWISTON-CITY-ZONED'
-- (literal placeholder for "zoned by City of Clewiston, exact municipal code
-- not resolved this session" -- see residual_gaps in session report; this is
-- NOT a fabricated zone code, it is an honest label for "we know the
-- authority, not yet the specific municipal zone designation").
--
-- The remaining 13 parcels are unincorporated Hendry County parcels (Wheeler,
-- Montura Ranches annex, Port LaBelle) -- no existing jurisdiction row covers
-- unincorporated Hendry, so one is created here following the
-- "<County> County (Unincorporated)" naming pattern already used by Polk,
-- Escambia, Hamilton (see jurisdictions table).

INSERT INTO public.jurisdictions (name, county, state, county_name, co_no, data_source, active, data_completeness, last_updated, created_at)
VALUES ('Hendry County (Unincorporated)', 'Hendry', 'FL', 'Hendry', 26,
        'shard6_run3679_hendry_i_zoning_substrate:gis.hendryfla.net_Zoning_FeatureServer',
        true, 5.00, now(), now())
ON CONFLICT DO NOTHING;

-- Insert parcel_zones rows for the 14 previously-unlinked parcels, using the
-- real Current_Zo value from the county Zoning FeatureServer query (verified
-- 2026-07-11, see session report for full query + raw response).
DO $$
DECLARE
  v_unincorp_id bigint;
  v_clewiston_id bigint := 866;
BEGIN
  SELECT id INTO v_unincorp_id FROM public.jurisdictions
   WHERE name = 'Hendry County (Unincorporated)' AND county_name = 'Hendry';

  INSERT INTO public.parcel_zones (jurisdiction_id, parcel_id, zone_code, zone_name, source)
  VALUES
    (v_unincorp_id, '1 28 44 07 A00 0203.0000', 'RR-WE', 'Rural Residential - Water/Estate', 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 29 43 18 050 0002-009.1', 'A-2', 'Agricultural', 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 29 43 18 030 0000-103.0', 'A-2', 'Agricultural', 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 29 43 18 030 0000-055.0', 'A-2', 'Agricultural', 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 29 43 17 100 0000-027.0', 'RG-3M', 'Residential General - Manufactured', 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 29 43 18 050 0004-003.1', 'A-2', 'Agricultural', 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 29 43 18 030 0000-143.0', 'A-2', 'Agricultural', 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 32 44 13 A00 0007.0000', 'RR-F', 'Rural Residential - Farm', 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 34 43 14 A00 0054.0100', 'RG-3M', 'Residential General - Manufactured', 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '1 34 43 14 A00 0054.0200', 'RG-3M', 'Residential General - Manufactured', 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '4 29 43 10 030 2095-008.0', 'RG-3', 'Residential General', 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '4 29 43 10 060 2193-046.0', 'RG-3', 'Residential General', 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_unincorp_id, '4 29 43 10 030 2117-015.0', 'RG-3', 'Residential General', 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1'),
    (v_clewiston_id, '3 34 43 01 010 0356-001.0', 'CLEWISTON-CITY-ZONED', 'City of Clewiston jurisdiction (exact municipal zone code not resolved this session)', 'https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/Zoning/FeatureServer/1')
  ON CONFLICT DO NOTHING;
END $$;
