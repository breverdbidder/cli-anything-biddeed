-- Gold Standard: jackson I fix (card_complete zoning-substrate linkage)
-- Session: 2026-08-30, county=jackson, letter=I
-- Before: I FAIL, card_complete=126 of 145 (86.9%)
-- After:  I PASS, card_complete=142 of 145 (97.9%)
--
-- Diagnosis (re-verified live this session via Supabase REST):
--   141 of 145 multi_county_auctions rows for county=jackson are field-complete
--   (address, lat, lon, assessed/market value, parcel_id all NOT NULL). Of those,
--   15 had zero matching row in v_zoning_gold_standard_card / parcel_zones --
--   a real zoning-substrate coverage gap, not a join/key-format bug (confirmed
--   parcel_zones had zero rows for these parcel_ids before this migration).
--
--   14 of the 15 are in "Compass Lake Hills" subdivision (Marianna/Alford,
--   unincorporated Jackson County). Looked each parcel up live at
--   https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/Jackson_County_Parcel/FeatureServer/1
--   (real LATITUDE/LONGITUDE returned for all 14, ZONING field null -- consistent
--   with Jackson County's stated policy of FLU-category regulation, not
--   traditional zoning: https://www.jacksoncountyfl.gov/services/community-development/planning-division/).
--   Point-in-polygon queried each of the 14 coordinates against
--   https://services.arcgis.com/9Jk4Zl9KofTtvg3x/arcgis/rest/services/FLUM/FeatureServer/10
--   (Jackson_Residential layer) -- all 14 hit F_NAME='Compass Lake Home Owners Ass',
--   Max_Densit='Min 1 per Acre Max 4 per Acre'. This is the exact same district
--   already in the DB (zoning_districts.id=12794, code='FLU-RES',
--   jurisdiction_id=1515 'Unincorporated Jackson County', zone_standards.id=5261,
--   max_density_du_acre=4.0) created by the prior confirmed-successful
--   20260724zzz_gold_standard_shard3_jackson_i_flu_zoning_3rd_firing.sql migration.
--   No new zoning_districts/zone_standards row needed -- pure parcel_zones INSERT
--   reusing the existing district, so G (density=100%) cannot regress.
--
--   The 15th (31-5N-11-0093-00C0-0030, case 322025CA000221CAAXMX, LEVY ST,
--   Cottondale) sits inside the Town of Cottondale's corporate limits (confirmed
--   via Jackson FLUM Incorporated layer, FeatureServer/4, F_NAME='Cottondale',
--   MAP_ACRES=1203.23), not unincorporated county. Queried the per-town
--   Cottondale_FLUM FeatureServer
--   (https://services.arcgis.com/9Jk4Zl9KofTtvg3x/arcgis/rest/services/Cottondale_FLUM/FeatureServer/0)
--   at the parcel's own DB centroid (-85.369094,30.791977) -- FID=73,
--   LAND_USE='Residential-Suburban'. jurisdictions.id=1024 (Cottondale, county
--   Jackson) already existed with zero prior zoning_districts/parcel_zones rows.
--   New district FLU-COTTONDALE-RES-SUBURBAN created following the exact same
--   far_regulated/pk1000_regulated/density_regulated=false pattern already used
--   for FLU-SNEADS-AG / FLU-CAMPBELLTON-RES (Cottondale_FLUM schema has no
--   density/FAR/parking figure -- LAND_USE/NOTES/ACRES/Shape__Area/Shape__Length
--   only -- so all three flags stay false, not fabricated).
--
--   Opportunistic 16th fix: multi_county_auctions row "2803 OF 2019"
--   (parcel_id=12-2N-11-0000-0020-0014) was field-incomplete (missing lat/lon
--   only). Looked it up live at the same Jackson_County_Parcel FeatureServer --
--   real LATITUDE=30.603394, LONGITUDE=-85.283906 returned -- backfilled those
--   two columns from that real source, which then made this row field-complete
--   and eligible for the card join. Point-in-polygon at that coordinate hit
--   FLUM/FeatureServer/3 (Jackson_Conservation layer), F_NAME='1',
--   Max_Densit='1 per 40 Acres' -- the existing FLU-CONSERVATION district
--   (zoning_districts.id=12831, jurisdiction_id=1515, density_regulated=true,
--   already created by the 20260724zzz migration). Reused verbatim, no new
--   district/standard, so G cannot regress from this either.
--
-- Residual (genuinely unrecoverable this session, not attempted):
--   - "3505 OF 2019" (parcel_id=03-6N-13-0000-0210-0000, Graceville area):
--     field-complete except lat/lon. Queried the Jackson_County_Parcel
--     FeatureServer live for this exact APN -- zero features returned (empty
--     result set, not an error). No alternate lookup key available this
--     session. BLANK > WRONG -- left untouched.
--   - "322025CA000190CAAXMX" and "322026CA000029CAAXMX": zero parcel_id, zero
--     address, zero geo, zero value in multi_county_auctions -- no lookup key
--     exists to research against any GIS/appraiser source. Consistent with the
--     2026-07-23 session's finding that some jackson rows are structurally
--     blocked at the source-scrape level. Out of scope for a zoning-substrate
--     fix; would require re-scraping the underlying RealForeclose/Clerk source.
--
-- Verification (live pencil_dod_evaluate_county('jackson') RPC, re-run after
-- each write in this session):
--   before: I={"pass":false,"detail":"card_complete=126 of 145","metric":86.9}
--   after tier1+tier2 (15 parcel_zones rows): I={"pass":true,"detail":"card_complete=141 of 145","metric":97.2}
--   after opportunistic geo+card fix (16th row): I={"pass":true,"detail":"card_complete=142 of 145","metric":97.9}
--   All other letters (A/B/C/D/E/F/G/H/J) remained PASS throughout, including
--   G staying at density=100.0 (no new applicable district introduced).

BEGIN;

-- Tier 1: 14 unincorporated Compass Lake Hills parcels -> existing FLU-RES district (id=12794)
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, future_land_use, source)
SELECT v.parcel_id, 1515, 'FLU-RES', 'Residential (Compass Lake HOA)', 'Residential', 'jackson_flum_pointinpolygon:jackson_i_20260830'
FROM (VALUES
  ('02-2N-11-0086-0840-0060'),
  ('02-2N-11-0086-0800-0270'),
  ('02-2N-11-0086-0810-0100'),
  ('02-2N-11-0086-0820-0170'),
  ('02-2N-11-0083-00F0-0020'),
  ('02-2N-11-0083-00F0-0030'),
  ('02-2N-11-0083-10AG-0080'),
  ('02-2N-11-0084-0710-0070'),
  ('02-2N-11-0084-0740-0240'),
  ('02-2N-11-0084-0710-0010'),
  ('02-2N-11-0084-0760-0270'),
  ('02-2N-11-0083-10AF-0010'),
  ('02-2N-11-0083-10AF-0040'),
  ('02-2N-11-0084-0790-0090')
) AS v(parcel_id)
ON CONFLICT DO NOTHING;

-- Tier 2: Cottondale (incorporated) parcel -> new town-level FLU district
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated)
SELECT j.id, 'FLU-COTTONDALE-RES-SUBURBAN',
  'Future Land Use: Residential-Suburban -- Town of Cottondale FLUM FeatureServer (services.arcgis.com/9Jk4Zl9KofTtvg3x/.../Cottondale_FLUM/FeatureServer, LAND_USE=Residential-Suburban, FID=73). Town-maintained vector FLU layer, separate from the county FLUM -- schema carries only LAND_USE/NOTES/ACRES/Shape__Area/Shape__Length, no density/FAR/parking figures exist, hence far_regulated/pk1000_regulated/density_regulated all explicitly false.',
  'residential', false, false, false
FROM jurisdictions j WHERE j.id = 1024 AND j.name = 'Cottondale' AND j.county = 'Jackson'
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, source_url, ordinance_section)
SELECT zd.id, 'https://services.arcgis.com/9Jk4Zl9KofTtvg3x/arcgis/rest/services/Cottondale_FLUM/FeatureServer/0 (LAND_USE field, FID=73)', 'Town of Cottondale FLUM'
FROM zoning_districts zd JOIN jurisdictions j ON j.id = zd.jurisdiction_id
WHERE j.name = 'Cottondale' AND zd.code = 'FLU-COTTONDALE-RES-SUBURBAN'
ON CONFLICT DO NOTHING;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, future_land_use, source)
SELECT '31-5N-11-0093-00C0-0030', j.id, 'FLU-COTTONDALE-RES-SUBURBAN', 'Residential-Suburban (Town of Cottondale FLUM)', 'Residential-Suburban', 'cottondale_flum_pointinpolygon:jackson_i_20260830'
FROM jurisdictions j WHERE j.name = 'Cottondale' AND j.county = 'Jackson'
ON CONFLICT DO NOTHING;

-- Opportunistic: backfill lat/lon for "2803 OF 2019" from live Jackson_County_Parcel FeatureServer,
-- then link it to the existing FLU-CONSERVATION district (id=12831) confirmed via point-in-polygon.
UPDATE multi_county_auctions
SET latitude = 30.603394, longitude = -85.283906
WHERE county = 'jackson' AND case_number = '2803 OF 2019' AND parcel_id = '12-2N-11-0000-0020-0014';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, future_land_use, source)
SELECT '12-2N-11-0000-0020-0014', 1515, 'FLU-CONSERVATION', 'Conservation', 'Conservation', 'jackson_flum_pointinpolygon:jackson_i_20260830'
ON CONFLICT DO NOTHING;

COMMIT;
