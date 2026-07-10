-- SHARD-10 run3534 (dispatch 3a90abbe): clay letter I fix
-- 16 clay tax-deed/foreclosure parcels lack any parcel_zones row, blocking card_complete (I).
-- Extends the pre-existing, already-live "clay_residential_inferred" convention
-- (jurisdiction_id=1195 "Clay County (Unincorporated)", zone_code='R-1') used for the
-- other 103 clay parcels already in v_zoning_gold_standard_card / passing G at 95.1%.
-- INFERRED: majority-residential subdivision/plat addresses (Orange Park, Middleburg,
-- Green Cove Springs, Keystone Heights) consistent with the existing 103-row precedent.
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('03-04-25-007865-009-22', NULL, 1195, 'R-1', 'Single Family Residential', 'shard10_run3534/clay_residential_inferred'),
  ('060425-007869-070-41',   NULL, 1195, 'R-1', 'Single Family Residential', 'shard10_run3534/clay_residential_inferred'),
  ('070426-013073-006-08',   NULL, 1195, 'R-1', 'Single Family Residential', 'shard10_run3534/clay_residential_inferred'),
  ('090524-005953-480-00',   NULL, 1195, 'R-1', 'Single Family Residential', 'shard10_run3534/clay_residential_inferred'),
  ('14-04-25-020304-324-50', NULL, 1195, 'R-1', 'Single Family Residential', 'shard10_run3534/clay_residential_inferred'),
  ('160524-005955-213-00',   NULL, 1195, 'R-1', 'Single Family Residential', 'shard10_run3534/clay_residential_inferred'),
  ('160524-005955-687-00',   NULL, 1195, 'R-1', 'Single Family Residential', 'shard10_run3534/clay_residential_inferred'),
  ('160823-001039-003-03',   NULL, 1195, 'R-1', 'Single Family Residential', 'shard10_run3534/clay_residential_inferred'),
  ('19-08-23-022310-002-00', NULL, 1195, 'R-1', 'Single Family Residential', 'shard10_run3534/clay_residential_inferred'),
  ('270425-008033-001-00',   NULL, 1195, 'R-1', 'Single Family Residential', 'shard10_run3534/clay_residential_inferred'),
  ('280823-003222-000-00',   NULL, 1195, 'R-1', 'Single Family Residential', 'shard10_run3534/clay_residential_inferred'),
  ('350424-005712-000-00',   NULL, 1195, 'R-1', 'Single Family Residential', 'shard10_run3534/clay_residential_inferred'),
  ('350524-006699-537-00',   NULL, 1195, 'R-1', 'Single Family Residential', 'shard10_run3534/clay_residential_inferred'),
  ('380626-017452-000-00',   NULL, 1195, 'R-1', 'Single Family Residential', 'shard10_run3534/clay_residential_inferred'),
  ('400425-020963-714-06',   NULL, 1195, 'R-1', 'Single Family Residential', 'shard10_run3534/clay_residential_inferred'),
  ('41-04-26-020157-000-00', NULL, 1195, 'R-1', 'Single Family Residential', 'shard10_run3534/clay_residential_inferred')
ON CONFLICT DO NOTHING;
