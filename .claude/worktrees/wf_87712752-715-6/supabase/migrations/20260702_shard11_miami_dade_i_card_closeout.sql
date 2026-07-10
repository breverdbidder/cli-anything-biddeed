-- SHARD-11 (miami_dade) closeout: apply ONLY the findings that survived the
-- ULTRALOOP adversarial verify pass (workflow wf_31fa8987-96f) from the
-- first-pass migration 20260702_shard11_miami_dade_i_card_backfill.sql.
-- dispatch_id: 7a6b2043-0106-46ec-8afa-c8362cb2b9bc
--
-- CONFIRMED and applied:
-- 1) 3 "orphan folio" parcels (real folios not in FL DOR NAL, but active in
--    Miami-Dade's own PA/GIS system) -- geo+value independently re-verified
--    live by the refuter against apps.miamidadepa.gov + gisweb.miamidade.gov
--    (folio existence, CANCEL_FLAG=N, address match, lat/lon reprojection to
--    <2m, exact dollar-figure re-pull). Zoning for these 3 queried live by
--    this session against Miami-Dade's zoning ArcGIS service; both resulting
--    districts (RU-4L unincorporated, RMF4 Aventura) ALREADY have complete
--    zone_standards rows (max_far/max_density_du_acre populated) -- safe,
--    matches the established no-regression pattern, no new district needed.
-- 2) NCUC and T3-R zoning_districts classification -- VERIFIED by the
--    refuter via pinpoint ordinance citations (Miami-Dade Naranja district
--    regs PDF Sec. 33-284.66-75; Miami 21 Code Art. 5 Illustration 5.3).
--    far_regulated=false and density_regulated set explicitly on the
--    district row this time (unlike the first pass), so
--    v_zoning_district_applicability no longer falls through to the
--    COALESCE(...,true) default that caused the earlier G regression.
--    T3-R's max_density_du_acre=9 is an exact ordinance figure (not a
--    guess) and is recorded in zone_standards. NCUC's ordinance gives a
--    12-52 units/acre RANGE varying by sub-district with no way to
--    determine this parcel's specific sub-district -- left NULL rather
--    than guessing a number (density_regulated stays true/applicable,
--    honestly incomplete rather than fabricated).
--
-- EXCLUDED (per refuter verdict, NOT applied):
-- - condo_folios bucket: every case in that bucket is still missing at
--   least one required field (value, in all cases) even after applying the
--   confirmed parts -- would not flip any case to complete, so nothing to
--   write.
-- - E-M (Palmetto Bay) zoning: refuter found the specific lot-coverage/
--   open-space/height figures unsourced and the primary ordinance text
--   (Municode) inaccessible (403/503). Parcel 33-5022-008-0170 remains
--   unresolved on the zoning criterion.
-- - Case 2026-007470-CA-01 (1401 NE 195th St #180, Doral): address is
--   internally inconsistent (NE-quadrant street name, wrong zip for
--   Doral's NW addressing) -- flagged as bad source data, not a lookup
--   gap. No fix applied; needs manual correction at the source.

-- 1) NCUC (Miami-Dade unincorporated, jurisdiction 626) + T3-R (Miami,
--    jurisdiction 855) district classification
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, ordinance_section)
SELECT 626, 'NCUC', 'Naranja Community Urban Center District', 'mixed-use', false, true,
       'Sec. 33-284.66-33-284.75, Article XXXIII(J), Code of Miami-Dade County'
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 626 AND code = 'NCUC')
UNION ALL
SELECT 855, 'T3-R', 'Sub-Urban Transect Zone, Restricted', 'residential', false, true,
       'Miami 21 Code, Article 5, Illustration 5.3 (As Adopted May 2010)'
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 855 AND code = 'T3-R');

-- T3-R has an exact ordinance density figure; record it. NCUC's ordinance
-- gives a 12-52 units/acre range with no way to resolve this parcel's
-- sub-district, so its zone_standards density is left NULL (honest gap).
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT d.id, 9.00, 'https://www.miami21.org/PDFs/FinalDocumentsMay2010/Article5-SpecifictoZones-AsAdopted-May2010.pdf',
       'Miami 21 Code, Article 5, Illustration 5.3'
FROM zoning_districts d
WHERE d.jurisdiction_id = 855 AND d.code = 'T3-R'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);

-- 2) Re-add parcel_zones for the 2 parcels whose district is now properly
--    classified (reverses part of the 20260702_shard11...backfill.sql revert)
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, effective_date)
SELECT '30-6927-032-0100', 626, 'NCUC', 'Naranja Community Urban Center District',
       'miamidade_gisweb_arcgis_live_query+ordinance_classification:shard11_miami_dade:2026-07-02', CURRENT_DATE
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '30-6927-032-0100')
UNION ALL
SELECT '01-4106-021-0300', 855, 'T3-R', 'Sub-Urban Transect Zone, Restricted',
       'miamidade_gisweb_arcgis_live_query+ordinance_classification:shard11_miami_dade:2026-07-02', CURRENT_DATE
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '01-4106-021-0300');

-- 3) 3 orphan-folio parcels: parcel_zones (existing, fully-populated
--    districts -- no new zoning_districts/zone_standards rows needed)
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, effective_date)
SELECT '30-4935-018-0250', 626, 'RU-4L', 'Limited Apartment House District, 23 units/net acre',
       'miamidade_gisweb_arcgis_live_query:shard11_miami_dade:2026-07-02', CURRENT_DATE
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '30-4935-018-0250')
UNION ALL
SELECT '30-2107-023-0020', 626, 'RU-4L', 'Limited Apartment House District, 23 units/net acre',
       'miamidade_gisweb_arcgis_live_query:shard11_miami_dade:2026-07-02', CURRENT_DATE
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '30-2107-023-0020')
UNION ALL
SELECT '28-2210-014-3240', 902, 'RMF4', NULL,
       'miamidade_gisweb_arcgis_live_query:shard11_miami_dade:2026-07-02', CURRENT_DATE
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '28-2210-014-3240');

-- 4) multi_county_auctions geo+value backfill for the 3 orphan folios --
--    VERIFIED live, re-confirmed independently by the refuter against
--    apps.miamidadepa.gov (2026 assessed/market values, exact re-pull match)
UPDATE multi_county_auctions a
SET latitude = v.lat, longitude = v.lng, assessed_value = v.av, market_value = v.mv
FROM (VALUES
  ('28-2210-014-3240', 25.942856::double precision, -80.145776::double precision, 222068::numeric, 222068::numeric),
  ('30-2107-023-0020', 25.926942, -80.291363, 68509, 242200),
  ('30-4935-018-0250', 25.687768, -80.413342, 206271, 206271)
) AS v(parcel_id, lat, lng, av, mv)
WHERE a.county = 'miami_dade' AND a.parcel_id = v.parcel_id;
