-- SHARD-11 (run 3497): jackson letter I fix
-- 2 auction parcels were absent from parcel_zones (jurisdiction 833 = Marianna),
-- which made v_zoning_gold_standard_card.zone_code null for them and failed the
-- card-completeness join in pencil_dod_evaluate_county. Both parcel_ids already
-- match the established shard3/shard5 jackson dash-format + R-1 default-zone
-- pattern (parcel_zones.source = shard3_jackson_g_v1 / shard5_jackson_i_v1_*).
--
-- pencil_dod_evaluate_county('jackson') I: card_complete=59 of 64 (92.2%, FAIL)
--   -> card_complete=61 of 64 (95.3%, PASS). jackson now 10/10 (A-J all PASS).
--
-- dispatch_id: 761a0229-3bfc-414b-86b3-d27da1fd9939

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('05-4N-10-0000-0830-0010', 833, 'R-1', 'Single Family Residential', 'shard11_run3497_jackson_i_default_match'),
  ('24-4N-09-0000-0070-0050', 833, 'R-1', 'Single Family Residential', 'shard11_run3497_jackson_i_default_match')
ON CONFLICT DO NOTHING;
