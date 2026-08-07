-- Gold Standard shard-4 (dispatch 1338ab5d, county=pasco, letter=I) — batch 6
-- Purpose: pasco I is FAILING at 82.9% (card_complete=271 of 327, needs >=95%).
--
-- ROOT CAUSE (CONFIRMED via live query against pencil_dod_evaluate_county's exact
-- I-criterion SQL, replicated directly, 2026-08-07):
-- Of the 56 currently-incomplete pasco rows, the overwhelming majority (49 of 56)
-- already have a real (non-placeholder) parcel_id but have ZERO row in
-- parcel_zones for that parcel_id -- i.e. they fail the
-- `a2.parcel_id IN (SELECT parcel_id FROM zc)` branch of the I-criterion join
-- purely because no zoning has ever been looked up for them, not because of
-- missing address/geo/value.
--
-- FIX METHOD (real GIS point-in-polygon, not a blanket default):
-- Pasco County Property Appraiser BOCC Zoning ArcGIS REST layer
-- (mapping.pascopa.com/arcgis/rest/services/Land_Use/MapServer/1, field ZN_TYPE)
-- was queried live, per-parcel, using each row's own lat/lon (esriGeometryPoint,
-- esriSpatialRelIntersects, inSR=4326). This is the SAME live service used by
-- 20260731d_gold_standard_shard9_pasco_taylor_i_card_fix.sql, extended here to
-- batch-cover the remaining unlinked parcels instead of one-off manual lookups.
-- 43 of the 56 gap rows already carried real (non county-centroid-placeholder)
-- lat/lon and were queried directly. 7 more had a real parcel_id but NULL
-- lat/lon/assessed_value; for those, Pasco Parcels ArcGIS layer
-- (.../Parcels/MapServer/4, fields ParcelID/VAL_APPR/PHYS_STREET/geometry) was
-- queried by ParcelID to source assessed_value + a real polygon-centroid lat/lon
-- (ring-vertex average of the parcel's own returned geometry), then that
-- centroid was fed into the same Land_Use/MapServer/1 zoning lookup. 6 of those
-- 7 resolved to a real, non-municipal zone code; their multi_county_auctions
-- geo/value gap is backfilled in this migration alongside their zoning.
--
-- 100% hit rate: every parcel queried against Land_Use/MapServer/1 (50 total:
-- 43 + 6 successfully-geocoded of 7) returned a real ZN_TYPE value. Of those 49,
-- 45 resolved to a genuine county zoning code (not a municipal-boundary
-- placeholder) and are inserted below. zone_name text is taken verbatim from the
-- ArcGIS layer's own legend (uniqueValueInfos labels, HTML-stripped), sourced
-- live from the same service, e.g. "R-4 High Density Residential" for ZN_TYPE=R4.
-- Where an existing hyphenated code convention already has a matching
-- zoning_districts row for jurisdiction_id=1258 (R-2, R-4), the GIS's unhyphenated
-- form (R2, R4) is normalized to match so G-criterion district joins stay
-- consistent; all other codes (MPUD, PUD, MF1, MF2, RMH, R1MH, AR, C2, R1) are
-- inserted as returned by the source, none previously present for this
-- jurisdiction except MPUD/R1 (already used once each by prior sessions).
--
-- NOT fixed (left untouched, reported per BLANK > WRONG):
-- 4 of 56 rows land inside a municipal boundary where the county's own zoning
-- layer legend returns a city-name placeholder instead of a real zone code
-- (ZN_TYPE in {NPR, DC, SA, ZH} = New Port Richey / Dade City / San Antonio /
-- Zephyrhills -- actual zoning authority is the city, not the county, for these
-- parcels): ids 2268f430-5142-4655-9f5d-43ab15d06514 (DC),
-- 6997425f-6206-4fcc-baa3-63bdce5fc65e (SA), 0eab13ad-3dc9-41a1-84ca-97a439805cf6
-- (ZH), and 14-26-21-0160-00000-0530 / id 26a1ccdb-4150-4c1c-9de1-1f8a657fa97d
-- (ZH, one of the 7 geocoded rows). No live ArcGIS REST service was reachable
-- this session for Dade City, Port Richey, San Antonio, or Zephyrhills
-- (gis.cityofzephyrhills.org, www.zephyrhillsfl.org, cityofsanantoniofl.us all
-- returned connection failures; www.dadecityfl.com returned HTTP 404 for any
-- ArcGIS path). Fabricating a numeric zone code for these 4 would violate the
-- BANNED "ghost-success" guardrail -- left as a genuine data gap.
-- 1 of 56 (id ee7405d1-a0cc-4538-846b-bbc3ba8d5993) has NO parcel_id AND NO
-- property_address at all (both NULL) -- the card-completeness check fails on
-- the address field regardless of zoning; no source available to originate an
-- address for this row this session.
-- 6 of 56 (2 with junk parcel_id='IPLTMULE' and no other fields at all; 4 with a
-- real address but NULL parcel_id and NULL geo/value, one of which shares the
-- earlier-flagged 28.308/-82.4396 county-centroid placeholder pattern) could not
-- be matched to any Pasco Property Appraiser roll record by address this
-- session (zero-row ArcGIS query result) -- left untouched.
-- Total untouched: 56 - 45 = 11 rows (4 municipal-placeholder-zone + 1 no-address
-- + 6 unmatchable).
--
-- EXPECTED RESULT: card_complete rises from 271/327 (82.9%) to 271+45=316/327
-- (96.6%), crossing the >=95 threshold. (45 rows gain a real parcel_zones row;
-- 6 of those 45 also needed and receive a geo/value UPDATE to
-- multi_county_auctions in this same migration -- both parts required for those
-- 6 rows to flip to card_complete=true.)
--
-- Idempotent: INSERT guarded by NOT EXISTS (no parcel_id below currently exists
-- in parcel_zones, confirmed live pre-apply); UPDATEs are plain id-keyed SETs,
-- safe to re-run.

BEGIN;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT v.parcel_id, 1258, v.zone_code, v.zone_name,
       'pasco_bocc_gis:mapping.pascopa.com/Land_Use/MapServer/1 point-in-polygon (ZN_TYPE), GS-PASCO-4-I-BATCH6-V1'
FROM (VALUES
  ('01-25-16-0100-00000-2680', 'R1MH', 'R-1MH Single Family/Mobile Home 1'),
  ('01-25-16-0110-00000-3470', 'R1MH', 'R-1MH Single Family/Mobile Home 1'),
  ('01-26-19-0010-00000-0121', 'R1',   'R-1 Rural Density Residential'),
  ('02-26-19-0030-00000-9710', 'AR',   'A-R Agricultural-Residential'),
  ('03-25-16-051E-00000-1850', 'PUD',  'PUD Planned Unit Development'),
  ('03-25-17-0070-00000-0690', 'MPUD', 'MPUD Planned Unit Development'),
  ('04-26-20-0060-00M00-0040', 'MPUD', 'MPUD Planned Unit Development'),
  ('07-26-16-029A-00000-3020', 'MF2',  'MF-2 Multiple Family High Density 2'),
  ('09-24-17-0010-09500-0000', 'AR',   'A-R Agricultural-Residential'),
  ('09-26-21-0070-00000-1760', 'RMH',  'R-MH Mobile Home'),
  ('09-26-21-0770-00000-2840', 'RMH',  'R-MH Mobile Home'),
  ('10-25-16-0570-00000-2770', 'R-4',  'R-4 High Density Residential'),
  ('10-25-16-0600-00000-5760', 'R-4',  'R-4 High Density Residential'),
  ('11-25-16-017A-00800-00C0', 'PUD',  'PUD Planned Unit Development'),
  ('11-26-19-0010-00000-053A', 'AR',   'A-R Agricultural-Residential'),
  ('13-26-20-0110-00000-5690', 'AR',   'A-R Agricultural-Residential'),
  ('14-25-20-0130-00000-1900', 'MPUD', 'MPUD Planned Unit Development'),
  ('14-26-16-0100-00000-0470', 'R-4',  'R-4 High Density Residential'),
  ('15-25-16-075A-00000-8480', 'R-4',  'R-4 High Density Residential'),
  ('15-25-20-0080-02300-1100', 'MPUD', 'MPUD Planned Unit Development'),
  ('17-26-16-0550-00000-0260', 'RMH',  'R-MH Mobile Home'),
  ('19-24-17-0010-00000-0010', 'AR',   'A-R Agricultural-Residential'),
  ('19-24-17-0010-00000-0054', 'AR',   'A-R Agricultural-Residential'),
  ('19-26-18-0050-02500-0210', 'MPUD', 'MPUD Planned Unit Development'),
  ('21-25-16-011A-00400-00C0', 'MF1',  'MF-1 Multiple Family Medium Density'),
  ('21-26-17-0100-00800-0110', 'MPUD', 'MPUD Planned Unit Development'),
  ('22-25-16-0960-00000-6260', 'R-4',  'R-4 High Density Residential'),
  ('22-25-18-0010-00000-0651', 'C2',   'C-2 General Commercial'),
  ('24-26-15-0540-00002-3690', 'R-4',  'R-4 High Density Residential'),
  ('24-26-15-0820-00001-4890', 'R-4',  'R-4 High Density Residential'),
  ('24-26-20-0010-00000-6000', 'R1MH', 'R-1MH Single Family/Mobile Home 1'),
  ('26-24-16-0020-00000-0410', 'MPUD', 'MPUD Planned Unit Development'),
  ('27-24-16-0120-00D00-0100', 'R1MH', 'R-1MH Single Family/Mobile Home 1'),
  ('27-26-16-001A-00000-1930', 'PUD',  'PUD Planned Unit Development'),
  ('28-24-16-0200-00000-0020', 'R1MH', 'R-1MH Single Family/Mobile Home 1'),
  ('28-25-16-0140-00000-1900', 'R-4',  'R-4 High Density Residential'),
  ('28-25-16-014J-00400-00N0', 'MF2',  'MF-2 Multiple Family High Density 2'),
  ('29-25-19-0010-00000-0150', 'AR',   'A-R Agricultural-Residential'),
  ('31-26-20-0030-00100-0030', 'MPUD', 'MPUD Planned Unit Development'),
  ('33-24-16-0210-00C00-0050', 'RMH',  'R-MH Mobile Home'),
  ('33-24-21-0040-00D00-0100', 'R1MH', 'R-1MH Single Family/Mobile Home 1'),
  ('34-24-17-0080-00000-0460', 'MPUD', 'MPUD Planned Unit Development'),
  ('34-25-20-0040-00500-0020', 'MPUD', 'MPUD Planned Unit Development'),
  ('34-25-21-0020-00000-1500', 'R-2',  'R-2 Low Density Residential'),
  ('35-24-21-0020-00100-0020', 'R1MH', 'R-1MH Single Family/Mobile Home 1')
) AS v(parcel_id, zone_code, zone_name)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = v.parcel_id
);

-- 6 of the above 45 parcels had NULL latitude/longitude/assessed_value in
-- multi_county_auctions (real parcel_id + real address, but never geocoded).
-- Backfilled from the same Pasco Parcels ArcGIS layer used to source the zoning
-- centroid lookup above (VAL_APPR = county Assessed Value; lat/lon = average of
-- the parcel's own returned polygon ring vertices).

UPDATE multi_county_auctions SET latitude = 28.264366379822395, longitude = -82.2015155645405, assessed_value = 235751
WHERE id = '92aa2760-d18d-41ce-93a6-fd60d76986f4'; -- 34-25-21-0020-00000-1500

UPDATE multi_county_auctions SET latitude = 28.22726350140175, longitude = -82.67079852685971, assessed_value = 300277
WHERE id = 'd0731541-faa5-490a-8248-d5bc94f31543'; -- 14-26-16-0100-00000-0470

UPDATE multi_county_auctions SET latitude = 28.37105665016123, longitude = -82.69379405009131, assessed_value = 119373
WHERE id = 'bb03c23f-21b5-488e-b35e-4e10637190d3'; -- 27-24-16-0120-00D00-0100

UPDATE multi_county_auctions SET latitude = 28.304995059631864, longitude = -82.68410041304438, assessed_value = 178549
WHERE id = '9c3e26d0-78d7-4262-af81-11425fba0955'; -- 15-25-16-075A-00000-8480

UPDATE multi_county_auctions SET latitude = 28.321027431463342, longitude = -82.67592562484226, assessed_value = 114556
WHERE id = '8de5fdac-dc9a-4e42-964e-750b7703b1f3'; -- 11-25-16-017A-00800-00C0

UPDATE multi_county_auctions SET latitude = 28.307490115445752, longitude = -82.28383290173545, assessed_value = 231579
WHERE id = '489c442a-5d1d-498b-87dd-657b9039af3a'; -- 14-25-20-0130-00000-1900

COMMIT;

-- VERIFICATION QUERY (run after apply):
-- SELECT public.pencil_dod_evaluate_county('pasco');
-- Expected: I metric rises from 82.9 (271/327) to 96.6 (316/327), pass=true.
