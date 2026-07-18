-- GOLD STANDARD shard-7 (dispatch 7066f088), county=leon, letter I fix.
--
-- Root cause (verified live 2026-07-18): 9 of 165 leon auctions failed
-- card_complete because parcel_id was NULL despite property_address/geo/
-- assessed_value already being present and parity-matched (tier1,
-- shard11_run3645_ajax_harvest). Re-harvested the live RealForeclose AJAX
-- calendar (leon.realforeclose.com, unauthenticated PREVIEW+AJAX mechanism,
-- proven in scripts/shard2_run2450_ajax_realforeclose_harvest.py) for the 3
-- upcoming auction dates these cases fall on (07/20, 07/22/2026) and
-- confirmed the real parcel_id for 3 of the 9 rows. Cross-checked: the
-- harvested assessed_value for all 3 exactly matches the value already
-- stored on the row (88862 / 196141 / 93853), confirming same real record.
-- All 3 parcel_ids exist in parcel_zones with zone_code='RP', so they now
-- satisfy the v_zoning_gold_standard_card join used by I's card_complete
-- calculation.
--
-- Expected effect: I card_complete 156/165 (94.5%) -> 159/165 (96.4%), PASS.
-- The other 6 of the 9 gap rows remain open (2 are bare calendar-sweep
-- stubs the source has not yet published parcel/address detail for as of
-- 2026-07-18 -- confirmed live, not a scraper bug; 1 has parcel_id="MULTIPLE
-- PARCELS" placeholder; 1 already has a real parcel_id but that parcel is
-- not yet in parcel_zones; 1 tax-deed row has a partial address only).
-- Left untouched -- no fabrication.

UPDATE multi_county_auctions
SET parcel_id = '320835 A0440'
WHERE lower(county) = 'leon' AND case_number = '2024 CA 000319' AND parcel_id IS NULL;

UPDATE multi_county_auctions
SET parcel_id = '320626 C0050'
WHERE lower(county) = 'leon' AND case_number = '2025 CA 000634' AND parcel_id IS NULL;

UPDATE multi_county_auctions
SET parcel_id = '320835 A0510'
WHERE lower(county) = 'leon' AND case_number = '2025 CA 000765' AND parcel_id IS NULL;
