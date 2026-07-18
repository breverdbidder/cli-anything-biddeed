-- GOLD STANDARD shard-7 (dispatch 7066f088), county=alachua, letter E/C/D/I/J fix.
--
-- Root cause (verified live 2026-07-18): case 01 2024 CA 001683 was one of
-- 10 alachua rows missing parcel_id, blocking E (parcel_linked), and
-- cascading into C/D/I/J since the row was not card_complete. A prior
-- session (scripts/shard10_run3645_alachua_e_parcel_backfill.py, run3645,
-- 2026-07-10) already identified and evidenced the correct parcel via
-- isol.alachuaclerk.org docid=3696062 (JUDGMENT, grantee "PAUL JEREMY" /
-- "PAUL VIRGINIA") cross-referenced against Alachua County Property
-- Appraiser's public ArcGIS FeatureServer (PublicParcel/FeatureServer/0):
-- Owner_Mail_Name LIKE '%PAUL%JEREMY%' returns exactly 2 rows; only
-- "PAUL JEREMY & VIRGINIA" (parcel 02975-002-000, 10815 NW 199TH AVE,
-- Alachua FL 32615) matches both first names on the judgment -- the other
-- match ("PAUL JEREMY C & SOHEILA C") is a different household. Re-verified
-- live this session against the same live FeatureServer -- identical result,
-- still unclaimed by any other multi_county_auctions row.
--
-- The script that discovered this evidence was committed but never executed
-- against this specific row (its sibling case 01 2025 CA 001356 WAS applied
-- and is confirmed present in the live DB). This migration completes that
-- deferred write.
--
-- Expected effect: E parcel_linked 41/51 (80.4%) -> 42/51 (82.4%); C/D
-- matched_clean/matched_any 47/51 -> 48/51 if this row also parity-matches;
-- I/J follow if the parcel resolves in v_zoning_gold_standard_card.

UPDATE multi_county_auctions
SET parcel_id = '02975-002-000',
    property_address = '10815 NW 199TH AVE, ALACHUA, FL 32615'
WHERE lower(county) = 'alachua' AND case_number = '01 2024 CA 001683' AND parcel_id IS NULL;
