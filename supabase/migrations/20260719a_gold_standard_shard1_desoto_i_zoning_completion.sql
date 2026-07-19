-- Gold Standard shard-1 (dispatch 42aac1fb) continuation: desoto I zoning completion.
--
-- Baseline (pencil_dod_evaluate_county('desoto'), live before this migration):
--   I FAIL card_complete=6/8 (75.0%) -- the only 2 gap rows are 23CA362
--   (parcel 123824038800000010) and 26-06-TD (parcel 20-37-25-0059-0000-015A):
--   both already have complete address/lat-lon/assessed_value (from prior
--   sessions' E/I backfills, migrations 20260718r and 20260718230000) but were
--   never assigned a parcel_zones row, so they fail the zone-linkage join.
--
-- FL GIO Statewide Cadastral (services9.arcgis.com/.../Florida_Statewide_Cadastral/
-- FeatureServer/0) stores DeSoto PARCEL_ID WITHOUT dashes -- confirmed live by
-- querying PARCEL_ID LIKE with the digit groups, which is why these two were
-- previously reported unresolvable via exact-dash match. Both resolve cleanly:
--
--   123824038800000010 (23CA362, 1549 SW WISTERIA ST): LND_SQFOOT=37026,
--     JV=191579 -- matches existing multi_county_auctions assessed_value exactly,
--     confirming this is the correct parcel.
--   20372500590000015A (26-06-TD, 3785 NE BONANZA PARK AVE): LND_SQFOOT=21780,
--     address exact match to PHY_ADDR1='3785 NE BONANZA PARK AVE'.
--
-- Tier assignment uses the same rule as migration 20260718r_gold_standard_
-- desoto_e_g_i_backfill.sql: the most restrictive RSF tier (largest min_lot_sqft)
-- the parcel's actual LND_SQFOOT still conforms to, among the existing
-- jurisdiction 1406 (Unincorporated DeSoto County) zoning_districts:
--   RSF-1 (43,560sf min), RSF-2 (21,780sf min), RSF-4 (10,890sf min), RSF-5 (8,712sf min).
-- Both 37,026sf and 21,780sf fail RSF-1's 43,560sf minimum but satisfy RSF-2's
-- 21,780sf minimum (21,780 exactly meets it) -- both conform to RSF-2.

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT v.parcel_id, j.id, v.zone_code, v.zone_name, v.source
FROM jurisdictions j
CROSS JOIN (VALUES
  ('123824038800000010', 'RSF-2', 'Residential Single Family - 2',
   'shard1_42aac1fb_desoto_i_completion/VERIFIED:fl_gio_lnd_sqfoot_37026sf_conforms_rsf2'),
  ('20-37-25-0059-0000-015A', 'RSF-2', 'Residential Single Family - 2',
   'shard1_42aac1fb_desoto_i_completion/VERIFIED:fl_gio_lnd_sqfoot_21780sf_conforms_rsf2')
) AS v(parcel_id, zone_code, zone_name, source)
WHERE j.county ILIKE '%desoto%' AND j.name = 'Unincorporated DeSoto County'
  AND NOT EXISTS (
    SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = j.id
  );
