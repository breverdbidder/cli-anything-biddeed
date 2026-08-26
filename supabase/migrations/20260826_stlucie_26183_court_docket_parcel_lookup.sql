-- St Lucie County, case 26-183 (tax_deed) — court-docket parcel lookup.
--
-- IDEMPOTENT RECORD of live REST writes applied this session via the
-- Supabase REST API (direct psql unavailable in this environment).
--
-- ── CONTEXT ──
-- Row for case 26-183 (multi_county_auctions.id 3d75bc02-6c66-44cd-a914-
-- 74e5c99a2479) landed via the calendar_sweep_mca_v3 feed on 2026-08-25
-- with parcel_id=NULL, property_address=NULL, assessed_value=NULL. It was
-- one of 8 st_lucie rows flagged in the same-day 2026-08-26 shard-5
-- migration (babb4725) as "needing a court-docket parcel lookup, different
-- lever, not attempted in this migration". This migration performs that
-- lookup.
--
-- ── METHOD ──
-- 1. Live GET+POST round trip against acclaimweb.stlucieclerk.gov/TributeWeb/
--    #dgResults (the same tax-deed search table scripts/clerk_ssot/parsers/
--    st_lucie.py already scrapes), date range today-120d..today+180d,
--    ddStatus=0 (all statuses), txtPageSize=500. 133 rows returned. Row for
--    Case Number "26-183" found directly (not inferred, not name-matched):
--      Applicant:        TLOA OF FLORIDA LLC, TLOA SERVICING, LLC AS
--                         CUSTODIAN FOR SECURED PARTY
--      Certificate:       2024/5348 (Issue Year 2024)
--      Parcel ID (raw):   4427-600-0096-000/4
--      Sale Date:         Nov 09, 2026  (exact match to
--                         multi_county_auctions.auction_date on file)
--      Current Status:    SALE
--      Opening Bid:       $109,682.89
--      Property Owners:   VITO STRAMAGLIAICS DIVERSIFIED INC (concatenated
--                         cell text — two owners, see step 2)
-- 2. map.paslc.gov/arcgis/rest/services/PROD/SLCPA_PublicParcels/MapServer/0,
--    query PARCELNO='4427-600-0096-000-4' (raw clerk Parcel ID with "/"
--    normalized to "-" to match STRAP format) -> exact single-feature match:
--      Owner1:           Vito Stramaglia
--      Owner2:           ICS Diversified Inc
--      (confirms the clerk's concatenated "VITO STRAMAGLIAICS DIVERSIFIED
--      INC" cell is Owner1+Owner2 joined with no separator — same case,
--      not a coincidence)
--      SiteAddress:      108 SE SANTA LUCIA
--      DistrictGroup:    0011 - Port Saint Lucie (jurisdiction_id 953,
--                         per established babb4725 precedent)
--      JustMarketValue:  1,686,500 (confirms the 150000 value on file for
--                         other unrelated cases is a fabricated placeholder,
--                         not a real assessed value for this parcel)
-- 3. Zone lookup: services1.arcgis.com/YdUP5V6WwzeG8T8r/arcgis/rest/services/
--    Zoning/FeatureServer/1 ("PZ_ZONING", the full citywide layer, NOT
--    layer 0 which is a small non-citywide subset), point-intersect on the
--    parcel polygon centroid (-8943228.05, 3151682.53 in 102100) ->
--      ZOLEGEND: PUD   ZONING: PLANNED UNIT DEVELOPMENT   ZO_ID: Z853
--    Centroid reprojects to lat/lon (27.2256, -80.3384), geographically
--    consistent with Port St. Lucie / Santa Lucia area.
--
-- ── WRITES ──
-- multi_county_auctions (case_number='26-183', county='st_lucie'):
--   parcel_id             -> '4427-600-0096-000-4'
--   property_address      -> '108 SE SANTA LUCIA'
--   city                  -> 'Port St Lucie'
--   assessed_value        -> 1686500
--   assessed_value_source -> 'map.paslc.gov_SLCPA_PublicParcels_MapServer0'
--   owner_name            -> 'Vito Stramaglia / ICS Diversified Inc'
--   plaintiff             -> 'TLOA of Florida LLC, TLOA Servicing LLC as
--                              Custodian for Secured Party'
--   cert_number           -> '2024/5348'
--   opening_bid           -> 109682.89
-- parcel_zones (new row, parcel_id keyed to match multi_county_auctions.
--   parcel_id literally, per established STRAP-keyed precedent):
--   parcel_id='4427-600-0096-000-4', tax_account='4427-600-0096-000-4',
--   jurisdiction_id=953, zone_code='PUD',
--   zone_name='PLANNED UNIT DEVELOPMENT',
--   source='st_lucie_26183_psl_arcgis_zoning_layer1_20260826'
--
-- ── RESULT (verified live via direct PATCH/POST + re-GET, 2026-08-26) ──
-- multi_county_auctions row for 26-183: all 9 target fields persisted and
-- confirmed via echo-back response (fill-was-NULL, no pre-existing values
-- overwritten). parcel_zones row inserted (id 870901), confirmed via
-- echo-back response.

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
SELECT * FROM (VALUES
  ('4427-600-0096-000-4', '4427-600-0096-000-4', 953, 'PUD', 'PLANNED UNIT DEVELOPMENT',
   'st_lucie_26183_psl_arcgis_zoning_layer1_20260826')
) AS v(parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v.jurisdiction_id AND pz.source = v.source
);

-- Fill-NULL-only backfill on multi_county_auctions (never overwrites a
-- non-null value already on file).
UPDATE multi_county_auctions SET
  parcel_id = '4427-600-0096-000-4',
  property_address = '108 SE SANTA LUCIA',
  city = 'Port St Lucie',
  assessed_value = 1686500,
  assessed_value_source = 'map.paslc.gov_SLCPA_PublicParcels_MapServer0',
  owner_name = 'Vito Stramaglia / ICS Diversified Inc',
  plaintiff = 'TLOA of Florida LLC, TLOA Servicing LLC as Custodian for Secured Party',
  cert_number = '2024/5348',
  opening_bid = 109682.89
WHERE case_number = '26-183' AND county = 'st_lucie' AND parcel_id IS NULL;
