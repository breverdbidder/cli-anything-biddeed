-- Gold Standard: highlands letter I (card_complete) 46-parcel zone-linkage
-- backfill, dispatch 8d4cd6c7 continuation. County: highlands. Letter: I.
--
-- scripts/highlands_i_zone_backfill.py --apply resolved all 46 remaining
-- highlands auction parcels that had a real parcel_id but no public.parcel_zones
-- row (zone-linkage gap flagged live 2026-08-12), via the same live Highlands
-- County zoning ArcGIS MapServer already used and documented in
-- supabase/migrations/20260723170500_shard8_gadsden_highlands_e_i_g_close_740368a6.sql
-- and supabase/migrations/20260811_highlands_e_i_g_hl_eij_8d4cd6c7.sql:
--   https://gis.highlandsfl.gov/server/rest/services/Layers/Zoning/MapServer/0
--   STRAP_NUM = parcel_id with dashes stripped; ZON = real zone code.
-- Live result (46/46 resolved, 0 skipped): 44 R1/R1A/R3/M1... rows already
-- covered by existing zoning_districts rows for jurisdictions 840 (Lake
-- Placid), 918 (Sebring), 1654 (unincorporated Highlands County) -- and 1
-- new (jurisdiction_id=840, code='B1') for parcel C-22-37-30-191-1840-0090
-- (953 CR 29, Lake Placid) that has NO existing zoning_districts row for
-- 840/B1, unlike the already-covered 918/B1 and 1654/B1 rows.
--
-- Per the documented regression class in 20260723170500 ("adding B1/R3/M1S
-- parcel_zones above without matching zoning_districts/zone_standards rows
-- crashed v_zoning_gold_standard_kpi_v3 far/pk1000 to 0%"), this migration
-- adds the missing 840/B1 zoning_districts row using the SAME real Highlands
-- County Land Development Regulations ordinance section already cited for
-- the identical B-1 Neighborhood Business District code at jurisdictions
-- 918 and 1654 (12.05.240(I) -- county-wide LDR chapter, not
-- jurisdiction-specific, so the same section applies to Lake Placid parcels
-- zoned under the county's B-1 designation):
--   https://cms2.revize.com/revize/highlandscountyfl/highlandscounty/departments/engineering/uploads/Chapter_12_Land_Development_Regulations.pdf
--
-- Result verified live via pencil_dod_evaluate_county('highlands') after
-- the parcel_zones INSERT: I moved from card_complete=297 of 354 (83.9%,
-- FAIL) to card_complete=341 of 354 (96.3%, PASS, threshold >=95%).
-- Residual 13-row gap = 11 rows with NULL parcel_id (hard ceiling, no
-- parcel to link) + 2 rows with real parcel_id/zone but missing
-- property_address (cases 25000831, 25000865) -- left alone per
-- BLANK>WRONG (their existing lat/lon values look like a placeholder pair
-- shared across both rows and were not touched or trusted by this session).

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 840, 'B1', 'B-1 Neighborhood Business District', 'commercial', '12.05.240(I)', true, false, false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 840 AND code = 'B1');

INSERT INTO zone_standards (zoning_district_id, max_far, max_height_ft, source_url, ordinance_section)
SELECT id, 0.8, 50,
  'https://cms2.revize.com/revize/highlandscountyfl/highlandscounty/departments/engineering/uploads/Chapter_12_Land_Development_Regulations.pdf',
  '12.05.240(I)'
FROM zoning_districts d
WHERE d.jurisdiction_id = 840 AND d.code = 'B1'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);
