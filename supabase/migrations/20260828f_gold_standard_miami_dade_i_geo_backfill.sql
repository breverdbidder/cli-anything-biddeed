-- Gold Standard letter I for miami_dade: card_complete geo backfill
-- Date: 2026-08-28
--
-- Diagnosis (live query, pre-fix, over the pencil_dod_evaluate_county row
-- filter: lower(county)='miami_dade' AND (data_source IS DISTINCT FROM
-- 'propertyonion' OR tier1_authoritative=true)):
--   total=617, card_complete=569 (92.2%, FAIL, needs >=95% i.e. >=587/617)
--   48 failing rows, breakdown (a row can fail more than one field):
--     missing_address=17, missing_geo=14, missing_value=9,
--     missing_parcelid=15, missing_zonelink=26
--
-- Root causes investigated per bucket:
--   1. missing_zonelink (26 rows): all 26 have a real, valid parcel_id and
--      already pass address/geo/value. v_zoning_gold_standard_card for
--      miami_dade currently has only 511 spot-checked parcels across 23
--      jurisdictions (confirmed live: SELECT count(*) FROM parcel_zones pz
--      JOIN jurisdictions j ON j.id=pz.jurisdiction_id WHERE
--      norm_county_key(COALESCE(j.county_name,j.county))='miami dade' ->
--      511), vs. Miami-Dade's actual ~900K parcel county. None of the 26
--      target folios exist in parcel_zones. This is a genuine structural
--      zoning-substrate coverage gap (matches this campaign's documented
--      pattern for non-Brevard counties), NOT something fixable with real
--      data in one session without a full county zoning-layer ingestion
--      project (would need zoning_districts + zone_standards rows backing
--      each folio's PRIMARY_ZONE code from Miami-Dade's own GIS, which is
--      out of scope here). Left unresolved, documented as BLOCKED.
--   2. missing_address / missing_parcelid rows with NO address and NO
--      parcel_id on file (2021-002908-CA-01, 2023-025492-CA-01,
--      2024-002728-CA-01 x2 dup, 2024-010779-CA-01, 2024-016425-CA-01,
--      2025-001356-CA-01, 2025-001562-CA-01, 2025-004900-CA-01,
--      2025-009489-CA-01, 2025-015794-CA-01, 2025-095290-CC-05,
--      2025-099724-CC-05): no lever without a working RealForeclose/
--      RealTaxDeed scrape session (blocked, 403 on direct fetch) or the
--      original court docket. Left unresolved.
--   3. Rows with an address on file but NO parcel_id (2024-000006-CA-01:
--      "29490 SW 193RD AVE, HOMESTEAD"; 2025-023031-CA-01: "14255 SW
--      125TH AVE"; 2025-099724-CC-05: "3317 WEST 98TH PLACE"): queried
--      live against Miami-Dade County's official ArcGIS REST parcel index
--      (gisweb.miamidade.gov/arcgis/rest/services/MD_LandInformation/
--      MapServer/26, layer 'Parcels @ PaParcel', field TRUE_SITE_ADDR) with
--      exact and prefix LIKE matches, plus broadened house-number-only
--      scans. None of these three addresses resolve to ANY parcel in
--      Miami-Dade's own address index -- the source-scraped address string
--      does not correspond to a real Miami-Dade parcel. Per NEVER-LIE /
--      no-fabrication guardrail, NOT resolved -- left unresolved rather
--      than guessing a nearby folio.
--   4. Rows with junk placeholder parcel_id text ("Property Appraiser",
--      "MULTIPLE PARCELS" -- 2024-003527-CA-01, 2024-016268-CA-01,
--      2025-012237-CA-01, 2024-000401-CA-01): attempted resolution via
--      the case's own auction_url/source_url (RealForeclose/RealTaxDeed
--      detail pages) -- WebFetch returned HTTP 403 (bot-blocked), matching
--      this campaign's documented RealForeclose/RealTaxDeed access
--      pattern. For 2024-016268-CA-01 (address on file: "1000 ISLAND BLVD
--      3209, AVENTURA"), cross-referenced the building's full 355-unit
--      folio list from the same ArcGIS parcel index -- no unit "3209"
--      exists in the building's real folio set. Not resolved, no
--      fabricated folio applied.
--   5. missing_geo (5 rows resolved below): each has a REAL, DB-confirmed
--      parcel_id (Miami-Dade folio format) already matching the on-file
--      property_address exactly. Queried live against the same official
--      ArcGIS parcel/property index (layer 24 'Property @ PaGis' for
--      condo units flagged CONDO_FLAG='Y', layer 26 'Parcels @ PaParcel'
--      for non-condo), requesting outSR=4326 so the ArcGIS server itself
--      returns WGS84 lat/lng (no client-side reprojection risk). All 5
--      returned exactly one feature, address matched our on-file
--      property_address verbatim, CANCEL_FLAG='N' (active parcel):
--        2017-001966-CA-01 | 30-3206-051-0340 | 742 NE 90 ST 404, Miami
--          -> 25.8570691673693, -80.18257912256306
--        2025-009857-CA-01 | 02-3210-049-0110 | 6881 BAY DR 20, Miami Beach
--          -> 25.85444609665431, -80.12645856186093
--        2025-018900-CA-01 | 02-3234-118-0090 | 1500 OCEAN DR 1201, Miami Beach
--          -> 25.787992127082077, -80.12891075461191
--        2026-003141-CA-01 | 10-7928-017-0510 | 2661 SE 24 CT, Homestead
--          -> 25.449971302571075, -80.43736075963339
--          (cross-checked: a sibling duplicate row for the same
--          case_number+parcel_id already carries lat=25.4499057493208,
--          lon=-80.4374285431258 from an independent source -- matches
--          our GIS lookup to 3 decimal places, corroborating both)
--        2026-005645-CA-01 | 25-4006-072-1920 | 100 NW 114 AVE 29-104, Sweetwater
--          -> 25.771515351892475, -80.38291421944675
--
-- Fix: UPDATE only latitude/longitude + geo_source for these 5 rows, using
-- the ArcGIS-returned WGS84 coordinates verbatim. No address, value, or
-- parcel_id fields touched (already correct/present).
--
-- Verification (public.pencil_dod_evaluate_county, live, post-fix):
--   card_complete moved from 569/617 (92.2%, FAIL) to 570/617 (92.4%,
--   FAIL) -- net +1 row. Confirmed live per-row: of the 5 rows updated,
--   4 (2017-001966-CA-01, 2025-009857-CA-01, 2025-018900-CA-01,
--   2026-005645-CA-01) were ALSO blocked by the missing_zonelink
--   structural gap described above and remain card_complete=false even
--   with real geo now populated. Only 2026-003141-CA-01's genuinely-
--   unresolved duplicate row (id f66810e0-...) flipped to
--   card_complete=true (its sibling row bf336ce7-... already had geo
--   and was already passing pre-fix, so no double count). Still well
--   short of the 95% (>=587/617) threshold -- the 26-row zonelink
--   structural gap and the ~17 unresolved address/parcel_id rows
--   dominate the remaining deficit. Letter I remains FAIL after this
--   fix -- partial, honest progress only, not oversold.

SET statement_timeout = 0;

UPDATE multi_county_auctions
SET latitude = 25.8570691673693,
    longitude = -80.18257912256306,
    geo_source = 'miamidade_arcgis_parcel_centroid',
    updated_at = now()
WHERE lower(county) = 'miami_dade'
  AND case_number = '2017-001966-CA-01'
  AND parcel_id = '30-3206-051-0340'
  AND latitude IS NULL
RETURNING id, case_number, parcel_id, latitude, longitude;

UPDATE multi_county_auctions
SET latitude = 25.85444609665431,
    longitude = -80.12645856186093,
    geo_source = 'miamidade_arcgis_parcel_centroid',
    updated_at = now()
WHERE lower(county) = 'miami_dade'
  AND case_number = '2025-009857-CA-01'
  AND parcel_id = '02-3210-049-0110'
  AND latitude IS NULL
RETURNING id, case_number, parcel_id, latitude, longitude;

UPDATE multi_county_auctions
SET latitude = 25.787992127082077,
    longitude = -80.12891075461191,
    geo_source = 'miamidade_arcgis_parcel_centroid',
    updated_at = now()
WHERE lower(county) = 'miami_dade'
  AND case_number = '2025-018900-CA-01'
  AND parcel_id = '02-3234-118-0090'
  AND latitude IS NULL
RETURNING id, case_number, parcel_id, latitude, longitude;

UPDATE multi_county_auctions
SET latitude = 25.449971302571075,
    longitude = -80.43736075963339,
    geo_source = 'miamidade_arcgis_parcel_centroid',
    updated_at = now()
WHERE lower(county) = 'miami_dade'
  AND case_number = '2026-003141-CA-01'
  AND parcel_id = '10-7928-017-0510'
  AND latitude IS NULL
RETURNING id, case_number, parcel_id, latitude, longitude;

UPDATE multi_county_auctions
SET latitude = 25.771515351892475,
    longitude = -80.38291421944675,
    geo_source = 'miamidade_arcgis_parcel_centroid',
    updated_at = now()
WHERE lower(county) = 'miami_dade'
  AND case_number = '2026-005645-CA-01'
  AND parcel_id = '25-4006-072-1920'
  AND latitude IS NULL
RETURNING id, case_number, parcel_id, latitude, longitude;
