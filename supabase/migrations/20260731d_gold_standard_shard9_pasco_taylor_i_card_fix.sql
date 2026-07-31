-- Gold Standard shard-9 (dispatch 2a942b32): pasco + taylor criterion I property-card fixes
-- All values below are VERIFIED via live Pasco Property Appraiser ArcGIS
-- (mapping.pascopa.com/arcgis/rest/services/Parcels/MapServer/3), Pasco BOCC zoning GIS
-- (mapping.pascopa.com/arcgis/rest/services/Land_Use/MapServer/1), Taylor Clerk court filings
-- (taylorclerk.com), floridaparcels.com Taylor County mirror, and NCFRPC City of Perry
-- Official Zoning Atlas (ncfrpc.org PEZN14.pdf) -- each independently adversarially
-- re-verified this session (ULTRALOOP verify+refute workflow, run wf_cf7827f6-3ed).
-- Rows with no real source found (Pasco cases blocked by realforeclose.com 403 +
-- exhausted Firecrawl credits + gated OCRS) are intentionally left untouched --
-- see GOLD_STANDARD_SHARD9_PASCO_TAYLOR_DISPATCH_2A942B32_SESSION_REPORT.md.

-- ── Pasco: 7 "missing/junk parcel_id" rows -- 2 resolved, 5 remain UNKNOWN (untouched) ──

UPDATE multi_county_auctions
SET parcel_id = '28-25-16-014J-00400-00N0',
    property_address = '6609 RIDGE ROAD UNIT 2, PORT RICHEY, FL 34668',
    latitude = 28.280867, longitude = -82.705285,
    assessed_value = 142188
WHERE id = 'f08c65ea-c8e6-4695-9a28-ac6a136a58f7';

-- unit 302's own parcel centroid (refuter corrected the sibling-209 borrow)
UPDATE multi_county_auctions
SET parcel_id = '07-26-16-029A-00000-3020',
    latitude = 28.241974, longitude = -82.734589,
    assessed_value = 155824
WHERE id = '5ec38313-8ffb-4e08-9480-b391fa06a1d2';

-- corrected parcel_id (refuter caught section/range transposition in the original find)
UPDATE multi_county_auctions
SET parcel_id = '33-24-21-0040-00D00-0100',
    latitude = 28.354448, longitude = -82.207843,
    assessed_value = 267246
WHERE id = 'c2b08da3-7a21-41c9-a84e-9835f67f830f';

-- ── Pasco: 6 "brand-new, geo/value blank" rows -- all 6 resolved ──
-- (assessed_value = county Assessed Value where HAS_HX homestead cap applies;
--  market_value = Just Value populated separately where they diverge, per refuter)

UPDATE multi_county_auctions
SET latitude = 28.234613721854622, longitude = -82.218473781,
    assessed_value = 87223
WHERE id = 'b635d53f-66ce-4546-bc75-35ae2a9510be';

UPDATE multi_county_auctions
SET latitude = 28.249625806641127, longitude = -82.31455285212894,
    assessed_value = 98350, market_value = 231494
WHERE id = '8ff4280b-128b-442d-b91e-c56891d362f1';

UPDATE multi_county_auctions
SET latitude = 28.296650034591806, longitude = -82.69349338506935,
    assessed_value = 209151
WHERE id = 'f2b10982-b205-4e2d-8940-e45029ab5599';

UPDATE multi_county_auctions
SET latitude = 28.339545380221598, longitude = -82.58518552969196,
    assessed_value = 291898
WHERE id = 'd2675c0c-84e8-46a8-b3f5-2991a56c6832';

UPDATE multi_county_auctions
SET latitude = 28.214347424407215, longitude = -82.61415748470345,
    assessed_value = 456740, market_value = 468898
WHERE id = 'db300655-181a-4fef-9b9c-b1ff06639220';

UPDATE multi_county_auctions
SET latitude = 28.213890734018694, longitude = -82.75153395994474,
    assessed_value = 170390, market_value = 245955
WHERE id = 'ba076e9d-ad11-4164-a78c-0c0537980869';

-- ── Pasco: 2 rows with real parcel_id/geo/value but no zoning link ──
-- Real per-parcel zone codes from Pasco BOCC Zoning GIS (NOT the prior R-2 blanket
-- default from scripts/shard9_run651_pasco_zoning.py, which this session's research
-- proved wrong for both of these parcels). Also corrects duplicate/stale placeholder
-- lat/lng (both rows previously shared the identical wrong coordinate 28.308/-82.4396).

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('21-26-16-0160-00200-0330', 1258, 'MPUD', 'MPUD Planned Unit Development',
   'pasco_bocc_gis:mapping.pascopa.com/Land_Use/MapServer/1 point-in-polygon, LDC Ch.500 p.81, GS-PASCO-9-I-V1'),
  ('07-26-19-0010-00000-0160', 1258, 'R1', 'R-1 Rural Density Residential',
   'pasco_bocc_gis:mapping.pascopa.com/Land_Use/MapServer/1 point-in-polygon, LDC Ch.500 p.59, GS-PASCO-9-I-V1')
ON CONFLICT DO NOTHING;

UPDATE multi_county_auctions SET latitude = 28.215499, longitude = -82.703617
WHERE id = 'ae0a7b8b-6337-42ec-9ff4-c82248c194af';

UPDATE multi_county_auctions SET latitude = 28.240957, longitude = -82.450648
WHERE id = 'd034b065-141c-4eae-9b56-f7b35c46b81d';

-- ── Taylor: the 1 I-failing row (23-597 CA, parcel 05026-000) ──
-- Address/value from taylorclerk.com Summary Final Judgment PDF + floridaparcels.com
-- Taylor County mirror (cross-verified against DOR County Number Map for CO_NO=72).
-- lat/lng is an address-level Nominatim geocode (no parcel-centroid GIS layer exists
-- for Taylor in the FL GIO statewide cadastral service -- confirmed empty for CO_NO=72).
-- assessed_value intentionally left NULL (source site's "valued at" figure could not be
-- disambiguated between Just/Assessed/Taxable value); market_value populated instead.

UPDATE multi_county_auctions
SET property_address = '101 Buffalo Drive, Perry, FL 32348',
    latitude = 30.0983370, longitude = -83.6002790,
    market_value = 83750
WHERE id = '83a4e2b2-e1be-438c-94b1-1c4994f32b90';

-- Zone via NCFRPC City of Perry Official Zoning Atlas PEZN14.pdf, point-in-polygon
-- (adversarially re-verified: geometrically distinct from the RSF-2 district already
-- assigned to 2 other Perry parcels 05151-000/02959-200 -- not a copy-paste default).
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('05026-000', 908, 'RSF/MH-2', 'Residential (Mixed) Single Family/Mobile Home',
   'ncfrpc.org City of Perry Official Zoning Atlas PEZN14.pdf (2020-02-16), georeferenced point-in-polygon; TIGERweb jurisdiction cross-check; GS-TAYLOR-9-I-V1')
ON CONFLICT DO NOTHING;
