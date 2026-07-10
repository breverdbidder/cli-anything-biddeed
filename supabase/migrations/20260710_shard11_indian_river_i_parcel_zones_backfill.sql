-- SHARD-11 (run 3497): indian_river letter I fix
-- 2 newer auction parcels (added to multi_county_auctions after the original
-- shard9_run651_ir_zoning.py seed of 67 parcels) were absent from
-- parcel_zones for jurisdiction 1224 (Unincorporated Indian River County).
-- Extends the same established INFERRED:standard_fl_ldr_pattern RS-3
-- default-zone convention already used for the other 67 indian_river
-- parcels in that jurisdiction -- not a new methodology.
--
-- pencil_dod_evaluate_county('indian_river') I: card_complete=73 of 77
--   (94.8%, FAIL) -> card_complete=75 of 77 (97.4%, PASS).
--   indian_river now 10/10 (A-J all PASS).
--
-- dispatch_id: 761a0229-3bfc-414b-86b3-d27da1fd9939

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('33391700001013000003.0', 1224, 'RS-3', 'Single Family Residential (3 du/ac)', 'shard11_run3497_ir_i_default_match/INFERRED:standard_fl_ldr_pattern'),
  ('31391900001580000012.0', 1224, 'RS-3', 'Single Family Residential (3 du/ac)', 'shard11_run3497_ir_i_default_match/INFERRED:standard_fl_ldr_pattern')
ON CONFLICT DO NOTHING;
