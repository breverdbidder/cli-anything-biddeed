-- Gold Standard shard-8 (volusia/alachua), run6796, dispatch 6ab3f0a2.
-- volusia re-verified live 10/10 (pencil_dod_evaluate_county) — no changes needed, not touched.
--
-- alachua I: 2 rows had parcel_id linked to a real zone_code (already PASS-eligible on
-- zoning) but were missing one other card field. Both parcels independently confirmed live
-- against Alachua County Property Appraiser's public ArcGIS FeatureServer, exact address
-- match both ways:
--   02975-002-000 (case 01 2024 CA 001683): FULLADDR "10815 NW 199TH AVE" matches our
--     property_address "10815 NW 199TH AVE, ALACHUA, FL 32615". Parcels35_view/FeatureServer/0
--     JustValue=247281 (TaxYear 2025). Row had no assessed_value/market_value at all.
--   00983-000-000 (case 01 2025 CA 003110): PublicParcel/FeatureServer/0 FULLADDR
--     "19036 NW 246TH ST" matches our property_address exactly; Parcels35_view JustValue=256427
--     (TaxYear 2025) matches our existing assessed_value=256427.00 byte-exact, cross-confirming
--     the source. Row had no latitude/longitude — backfilled from the PublicParcel parcel
--     centroid (outSR=4326): (29.83627395650439, -82.60464585981335).
--
-- alachua B/F honesty fix: case 01 2025 CA 001928 carries sold_amount=150000.00,
-- tier1_sold_amount=150000.00, assessed_value=150000, property_address='ALACHUA COUNTY FL'
-- (county-name placeholder, not a street address), latitude/longitude = Alachua county
-- centroid (29.6516,-82.3248) — all fabricated defaults, not scraped data. Confirmed live
-- against the actual RealForeclose AJAX source for AID 1491316 (same case, same auction
-- date 2026-05-14): Parcel ID field literally reads "Property Appraiser" (the same
-- placeholder-label bug documented in the 3rd firing's flow_card_to_mca root-cause fix),
-- Property Address/Assessed Value are both empty in the source, and Plaintiff Max Bid
-- reads "Hidden" — the source has never had a sold result or any property data for this
-- case, unlike its sibling case 01 2025 CA 002830 fetched in the same AJAX response, which
-- shows real judgment/parcel/address. This case was wrongly counted as a "closed_sold"
-- verified/tier1 outcome; nulling these fields removes it from B/F's denominator honestly
-- (BLANK > WRONG) rather than leaving a fabricated $150,000 "sale" informing real bid
-- decisions. B/F remain PASS afterward on the smaller, honest denominator (6/6).

UPDATE multi_county_auctions
SET assessed_value = 247281,
    updated_at = now()
WHERE lower(county) = 'alachua'
  AND case_number = '01 2024 CA 001683'
  AND parcel_id = '02975-002-000';

UPDATE multi_county_auctions
SET latitude = 29.83627395650439,
    longitude = -82.60464585981335,
    updated_at = now()
WHERE lower(county) = 'alachua'
  AND case_number = '01 2025 CA 003110'
  AND parcel_id = '00983-000-000';

UPDATE multi_county_auctions
SET sold_amount = NULL,
    tier1_sold_amount = NULL,
    assessed_value = NULL,
    property_address = NULL,
    latitude = NULL,
    longitude = NULL,
    updated_at = now()
WHERE lower(county) = 'alachua'
  AND case_number = '01 2025 CA 001928';

INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  ('6ab3f0a2-b60a-4125-b7cb-0b8ed5b6e747', 'native', 'alachua', 'I',
   'parcel 02975-002-000 assessed_value=247281 real (ACPA Parcels35_view JustValue, TaxYear 2025, address-matched)',
   jsonb_build_object('source', 'https://services1.arcgis.com/MiBZ4u97DWldovjI/arcgis/rest/services/Parcels35_view/FeatureServer/0',
                       'query', 'parcel=02975-002-000', 'JustValue', 247281, 'TaxYear', 2025,
                       'address_match', '10815 NW 199TH AVE'), true),
  ('6ab3f0a2-b60a-4125-b7cb-0b8ed5b6e747', 'native', 'alachua', 'I',
   'parcel 00983-000-000 lat/long real (ACPA PublicParcel FeatureServer centroid, address + JustValue cross-confirmed)',
   jsonb_build_object('source', 'https://services.arcgis.com/cNo3jpluyt69V8Ek/arcgis/rest/services/PublicParcel/FeatureServer/0',
                       'query', 'Name=00983-000-000', 'centroid_lat', 29.83627395650439, 'centroid_long', -82.60464585981335,
                       'cross_check_JustValue', 256427, 'existing_db_assessed_value', 256427.00), true),
  ('6ab3f0a2-b60a-4125-b7cb-0b8ed5b6e747', 'native', 'alachua', 'B',
   'case 01 2025 CA 001928 sold_amount=150000.00/assessed_value=150000/address="ALACHUA COUNTY FL" were fabricated defaults, not real RealForeclose data; nulled',
   jsonb_build_object('source', 'https://alachua.realforeclose.com AJAX AUCTIONDATE=05/14/2026 AREA=C',
                       'aid', '1491316', 'live_parcel_id_field', 'Property Appraiser',
                       'live_property_address', null, 'live_assessed_value', null,
                       'live_plaintiff_max_bid', 'Hidden',
                       'sibling_case_same_response_has_real_data', '01 2025 CA 002830 (parcel 06014-020-059, address 5610 NW 27TH TER)'), true);
