-- SHARD-1 (gold standard shard: alachua, gilchrist, liberty, putnam, manatee)
-- Manatee County: correct 8 row-misaligned tier1_clerk_litmus rows, honestly
-- reset their unearned C/D credit
-- dispatch_id: 837188e6-d219-4702-b1be-f646c3629feb
-- Session: architect-20260702T160000
--
-- ROOT CAUSE (VERIFIED live 2026-07-02, cross-checked against the real Manatee
-- County Property Appraiser parcel layer at
-- gis.manateepao.com/arcgis/rest/services/Website/WebLayers/MapServer/0, layer
-- "Parcel Search", field PARID): a prior bulk enrichment tagged
-- parity_source IN ('tier1_clerk_litmus_c_fix_20260625',
-- 'tier1_clerk_litmus_preauth_20260625') wrote property_address/assessed_value
-- belonging to a DIFFERENT parcel_id onto 8 of the 57 rows it touched (14%) --
-- a row-misalignment during that enrichment pass, e.g. case 412025CA001704CAAXMA
-- (real parcel 6628403401 = "915 WEE BURN PL, SARASOTA", CAD_ASSESSED_CTY
-- $139,990) was stored with address "12250 CR 675" / value $319,973 --
-- literally case 412024CA001288CAAXMA's real data (a different, correctly
-- labeled parcel). This is a distinct failure mode from the wholesale
-- fabrication found for liberty/columbia/lake/marion in sibling migrations --
-- the parcel_ids and the auctions themselves are real -- but the practical
-- effect is the same: 8 rows were credited toward gold_standard_loop()'s C/D
-- (parity_status IN matched_clean/matched_divergent AND parity_source LIKE
-- 'tier1%') without a genuine, correctly-keyed independent verification ever
-- having occurred.
--
-- CORRECTIVE ACTION (already executed live via Management API before this file
-- was committed; idempotent -- re-running is a no-op since the WHERE clause
-- matches on case_number, and the UPDATE already moved these rows to their
-- terminal state):
--   For each of the 8 case numbers, overwrite property_address/assessed_value/
--   market_value with the real PAO data for that row's own parcel_id, and
--   reset parity_status='mca_only' / parity_source to a documented reset
--   marker (removing the false tier1 credit -- these rows have NOT been
--   genuinely independently verified with correct data).
--
-- EFFECT: manatee D drops from 75.7% (matched_any=53 of 70) toward the true,
-- lower value once these 8 (5 of which were matched_divergent/matched_clean
-- with a tier1-prefixed source) lose their credit. This is the expected,
-- correct direction -- exposing real state, not degrading it artificially.
--
-- Two rows (412024CA001949CAAXMA "MANATEE-TD-SEED-2026" case, and
-- 412025CC003229CCAXMA) were already parity_status='mca_only' and are
-- unaffected by this migration; flagged for a future session (parcel_id NULL,
-- case_number literally "MANATEE-TD-SEED-2026" -- looks like a seed/placeholder
-- row, needs its own investigation, out of scope for this fix).

UPDATE multi_county_auctions
SET property_address = '7088 CHATUM LIGHT RUN, BRADENTON, FL',
    assessed_value = 299805.0, market_value = 299805.0,
    parity_status = 'mca_only',
    parity_source = 'reset_row_misalignment_correction_20260702:shard1',
    updated_at = now()
WHERE lower(county) = 'manatee' AND case_number = '412024CA000632CAAXMA'
  AND parity_source LIKE 'tier1_clerk_litmus%';

UPDATE multi_county_auctions
SET property_address = '4126 91ST AVE E, PARRISH, FL', assessed_value = 309249.0, market_value = 309249.0,
    parity_status = 'mca_only', parity_source = 'reset_row_misalignment_correction_20260702:shard1', updated_at = now()
WHERE lower(county) = 'manatee' AND case_number = '412025CA000777CAAXMA'
  AND parity_source LIKE 'tier1_clerk_litmus%';

UPDATE multi_county_auctions
SET property_address = '11522 84TH STREET CIR E UNIT 104, PARRISH, FL', assessed_value = 222973.0, market_value = 222973.0,
    parity_status = 'mca_only', parity_source = 'reset_row_misalignment_correction_20260702:shard1', updated_at = now()
WHERE lower(county) = 'manatee' AND case_number = '412025CA000902CAAXMA'
  AND parity_source LIKE 'tier1_clerk_litmus%';

UPDATE multi_county_auctions
SET property_address = '2411 51ST AVENUE DR W, BRADENTON, FL', assessed_value = 79700.0, market_value = 79700.0,
    parity_status = 'mca_only', parity_source = 'reset_row_misalignment_correction_20260702:shard1', updated_at = now()
WHERE lower(county) = 'manatee' AND case_number = '412025CA001008CAAXMA'
  AND parity_source LIKE 'tier1_clerk_litmus%';

UPDATE multi_county_auctions
SET property_address = '915 WEE BURN PL, SARASOTA, FL', assessed_value = 139990.0, market_value = 139990.0,
    parity_status = 'mca_only', parity_source = 'reset_row_misalignment_correction_20260702:shard1', updated_at = now()
WHERE lower(county) = 'manatee' AND case_number = '412025CA001704CAAXMA'
  AND parity_source LIKE 'tier1_clerk_litmus%';

UPDATE multi_county_auctions
SET property_address = '812 TROPICAL DR, BRADENTON, FL', assessed_value = 387069.0, market_value = 387069.0,
    parity_status = 'mca_only', parity_source = 'reset_row_misalignment_correction_20260702:shard1', updated_at = now()
WHERE lower(county) = 'manatee' AND case_number = '412025CA001900CAAXMA'
  AND parity_source LIKE 'tier1_clerk_litmus%';

UPDATE multi_county_auctions
SET property_address = '4312 80TH ST W, BRADENTON, FL', assessed_value = 107148.0, market_value = 107148.0,
    parity_status = 'mca_only', parity_source = 'reset_row_misalignment_correction_20260702:shard1', updated_at = now()
WHERE lower(county) = 'manatee' AND case_number = '412025CA002459CAAXMA'
  AND parity_source LIKE 'tier1_clerk_litmus%';

UPDATE multi_county_auctions
SET property_address = '6700 US 19, TERRA CEIA, FL', assessed_value = 289309.0, market_value = 289309.0,
    parity_status = 'mca_only', parity_source = 'reset_row_misalignment_correction_20260702:shard1', updated_at = now()
WHERE lower(county) = 'manatee' AND case_number = '412025CC002708CCAXMA'
  AND parity_source LIKE 'tier1_clerk_litmus%';
