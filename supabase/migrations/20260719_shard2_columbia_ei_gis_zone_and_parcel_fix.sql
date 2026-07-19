-- Columbia County letters E (parcel linkage) and I (property card completeness) fix.
-- This file documents live writes already applied via mgmt_sql.py during the session (idempotent).
--
-- BASELINE (live pencil_dod_evaluate_county('columbia') before this session):
--   E: {"pass":false,"detail":"parcel_linked=14","metric":93.3}   (14 of 15)
--   I: {"pass":false,"detail":"card_complete=8 of 15","metric":53.3}
--
-- GROUND TRUTH (confirmed via pg_get_functiondef of public.pencil_dod_evaluate_county):
--   E's has_parcel counts ANY non-NULL parcel_id (no format validation).
--   I's card_complete requires property_address + COALESCE(lat,po_lat) + COALESCE(lon,po_lon)
--   + COALESCE(assessed_value,market_value) ALL non-null, AND a2.parcel_id must EXACT-MATCH
--   either v_zoning_gold_standard_card.parcel_id or .tax_account for a columbia jurisdiction,
--   WHERE that row's zone_code IS NOT NULL (a parcel_zones row alone is not enough).
--
-- METHOD (real GIS research, no fabrication):
--   Source: https://gis.columbiacountyfla.com/hosting/rest/services/Zoning_Atlas/MapServer/1
--   (ArcGIS REST, no auth/bot-protection; this is the SAME layer that produced the existing
--   8 columbia parcel_zones rows tagged source='gis.columbiacountyfla.com_zoning_atlas_spatial_intersect_verified').
--   For each parcel, pulled its authoritative polygon from
--   https://gis.columbiacountyfla.com/hosting/rest/services/Parcels/FeatureServer/1 (field ParcelNo,
--   e.g. '28-1S-17-04576-002') and ran a polygon-intersect query against the Zoning Atlas layer
--   (more robust than a single lat/long point query, since stored auction lat/long is a geocoded
--   street-address point that can sit outside the parcel's own polygon near boundaries).
--   Address-to-parcel lookups (case 2025-249-CA) used
--   https://gis.columbiacountyfla.com/hosting/rest/services/Addresses/FeatureServer/1 (fields
--   Address, RoadName, ParcelNo) -- exact address-number + street-name match, not a guess.
--
-- CASE 2025-249-CA (294 NE OMAR TERRACE) -- was parcel_id=NULL (the sole E failure):
--   Addresses layer exact match: Address='294  NE OMAR TER', RoadName='NE OMAR TER',
--   ParcelNo='28-1S-17-04576-002', City='LAKE CITY' (postal city; Parcels layer Municipality
--   field confirms 'Columbia County' i.e. unincorporated, not inside Lake City town limits).
--   Zoning Atlas polygon-intersect on this parcel's real geometry -> FinalZng='A-1'.
--   zoning_districts row for A-1 already exists (id=11788, jurisdiction_id=1405 Unincorporated
--   Columbia County) from a prior session -- no new district needed.
--   FIX: initially planned to set parcel_id='04576-002' (short form, matching the other 8
--   verified rows) and insert a new parcel_zones row -- but live-checking during apply found a
--   parcel_zones row for this exact parcel ALREADY EXISTED from a prior session (id=833992,
--   created 2026-07-11), with zone_code='A-1' already correct, but using the FULL tax_account
--   string '28-1S-17-04576-002' in its own parcel_id column (not the short '04576-002' form the
--   other 8 rows use -- an inconsistency from that earlier session, not touched/reconciled here,
--   out of this task's scope). To exact-match the evaluator's IN-clause against the row that
--   already exists, multi_county_auctions.parcel_id was set to '28-1S-17-04576-002' (matching
--   the existing parcel_zones.parcel_id verbatim) instead of inserting a duplicate/conflicting
--   row. No new parcel_zones row was needed for this case after all.
--
-- CASE 2025-63-CA (283 NW COLE TERRACE) -- parcel_id was malformed:
--   '00130-000 AND 00130-001' (two parcel numbers concatenated with ' AND ', not a valid
--   single parcel_id -- cannot exact-match any single parcel_zones.parcel_id/tax_account).
--   Parcels layer (current tax-roll parcels, live-queried):
--     ParcelNo='01-3S-15-00130-000' EXISTS (Owner='ROGERS WALTER B', Municipality='Columbia County').
--     ParcelNo='01-3S-15-00130-001' DOES NOT EXIST in the current live Parcels FeatureServer
--     (exact-match query returns zero features; broader STR-prefix wildcard query for the same
--     section/township/range also returns only the -000 parcel). This is a live, current,
--     official tax-roll layer -- a definitive absence, not a fabricated conclusion. Most likely
--     explanation: '00130-001' is a retired/merged parcel number no longer on the active roll
--     (parcel splits/combinations are common and leave stale numbers in older case filings).
--   Zoning Atlas polygon-intersect on '01-3S-15-00130-000' -> FinalZng='A-3' (zoning_districts
--   id=11789, jurisdiction_id=1405, already exists).
--   FIX (non-destructive, queryable): parcel_id set to the one REAL, current, GIS-verified
--   parcel ('00130-000') so it exact-matches a real parcel_zones row. The original combined
--   value and the non-existent second parcel number are preserved verbatim in
--   legal_description (previously NULL, unused) rather than deleted, per BLANK > WRONG --
--   information is not destroyed, just moved to a field the evaluator does not string-match on.
--
-- CASES CONFIRMED VIA POLYGON-INTERSECT (zone_code was simply missing, no other gap):
--   2023-79-CA   parcel_id=02123-027 (tax_account 14-3S-16-02123-027) -> A-3
--   2025-354-CA  parcel_id=04236-236 (tax_account 18-7S-16-04236-236) -> A-3
--   2025-501-CA  parcel_id=00312-008 (tax_account 01-4S-15-00312-008) -> A-3
--   2026-54-CA   parcel_id=04232-001 (tax_account 17-7S-16-04232-001) -> A-3
--   All four already had property_address/lat/long/assessed_value populated -- these 4 rows
--   flip straight to card_complete once zone_code exists. All map to zoning_districts A-3
--   (id=11789, jurisdiction_id=1405), which already existed -- no new district rows needed.
--
-- CASE 2025-2196-CC (357 SW AMIEL CT) -- NOT fixed, left alone, reported honestly:
--   parcel_id on file (04023-000 / tax_account 33-6S-16-04023-000) IS CORRECT and matches the
--   real current Parcels layer (Addresses layer confirms Address='357  SW AMIEL CT' ->
--   ParcelNo='33-6S-16-04023-000' exactly). The gap is that this parcel is GENUINELY
--   UNRESOLVABLE for zone_code: its polygon does not intersect the county Zoning_Atlas layer at
--   all (0 features on exact polygon-intersect), and a separate query against
--   https://gis.columbiacountyfla.com/hosting/rest/services/Ft_White_Limits/MapServer/1 confirms
--   this parcel's polygon IS inside Fort White town limits (Town of Fort White is its own
--   incorporated zoning authority per library.municode.com/fl/fort_white and
--   fortwhitefl.com/media/1956 "Town of Fort White Official Zoning Map" / .../media/2006 Land
--   Development Code, adopted 2013). No queryable Fort White GIS/ArcGIS REST zoning endpoint was
--   found this session (county's own service catalog only has Ft_White_Limits/Ft_White_Utility_
--   Plant/Ft_White_Water_Lines -- no zoning layer for the town). This is the SAME structural
--   pattern already documented and fixed for Hendry/Clewiston in
--   20260711n_hendry_g_pk1000_clewiston_placeholder_district_fix.sql (county zoning atlas defers
--   to an incorporated town's own zoning authority with no live GIS endpoint for that town).
--   Per that precedent AND per this task's explicit instruction ("only if genuinely unresolvable
--   after real research, register a structural placeholder district row... never guessing a zone
--   code itself"), NO placeholder is registered here in this session: unlike Clewiston (where the
--   county layer returns a literal placeholder value 'CLEWISTON' for every in-town parcel, giving
--   a real string to register), Fort White's county layer returns NOTHING (zero features) for
--   in-town parcels -- there is no GIS-supplied placeholder string to anchor a district row to,
--   only silence. Fabricating one here would cross from "structural placeholder for a real GIS
--   sentinel value" into "inventing a code with no GIS evidence at all." Left BLANK, not guessed.
--   This is the one case in the 7-parcel list this session could not resolve.

-- 1) Fix case 2025-249-CA: real parcel_id (was NULL). Set to the full tax_account string to
--    exact-match the parcel_zones row that already existed for this parcel (id=833992,
--    parcel_id='28-1S-17-04576-002', zone_code='A-1', jurisdiction_id=1405) -- see note above.
UPDATE multi_county_auctions
SET parcel_id = '28-1S-17-04576-002'
WHERE county = 'columbia' AND case_number = '2025-249-CA' AND parcel_id IS NULL;

-- 2) Fix case 2025-63-CA: malformed combined parcel_id -> real, single, GIS-verified parcel_id.
--    Second (non-existent) parcel number preserved verbatim in legal_description, not deleted.
UPDATE multi_county_auctions
SET parcel_id = '00130-000',
    legal_description = 'Original parcel_id on file was the combined/malformed value ''00130-000 AND 00130-001''. Live query of Columbia County GIS Parcels FeatureServer (gis.columbiacountyfla.com/hosting/rest/services/Parcels/FeatureServer/1) on 2026-07-19 confirms ParcelNo=01-3S-15-00130-000 EXISTS on the current tax roll (Owner: ROGERS WALTER B, Municipality: Columbia County / unincorporated), while ParcelNo=01-3S-15-00130-001 returns ZERO features (exact match and STR-prefix wildcard both empty) -- not a currently active parcel, most likely a retired/merged parcel number. parcel_id set to the one real, current, GIS-verified parcel (00130-000) so it exact-matches a real parcel_zones row; the original combined string is preserved here for reference, not lost.'
WHERE county = 'columbia' AND case_number = '2025-63-CA'
  AND parcel_id = '00130-000 AND 00130-001';

-- 3) Insert parcel_zones rows for the 5 parcels that needed a NEW row this session (all under
--    jurisdiction_id=1405, Unincorporated Columbia County, same source pattern as the existing
--    8 verified columbia rows). '28-1S-17-04576-002' (2025-249-CA) is NOT in this list -- its
--    parcel_zones row already existed (id=833992) from a prior session, see note above.
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('02123-027', '14-3S-16-02123-027', 1405, 'A-3', NULL, 'gis.columbiacountyfla.com_zoning_atlas_spatial_intersect_verified'),
  ('04236-236', '18-7S-16-04236-236', 1405, 'A-3', NULL, 'gis.columbiacountyfla.com_zoning_atlas_spatial_intersect_verified'),
  ('00312-008', '01-4S-15-00312-008', 1405, 'A-3', NULL, 'gis.columbiacountyfla.com_zoning_atlas_spatial_intersect_verified'),
  ('04232-001', '17-7S-16-04232-001', 1405, 'A-3', NULL, 'gis.columbiacountyfla.com_zoning_atlas_spatial_intersect_verified'),
  ('00130-000', '01-3S-15-00130-000', 1405, 'A-3', NULL, 'gis.columbiacountyfla.com_zoning_atlas_spatial_intersect_verified')
ON CONFLICT DO NOTHING;

-- NOTE: zoning_districts rows for A-3 (id=11789) and A-1 (id=11788) under jurisdiction_id=1405
-- already existed prior to this session -- no new zoning_districts INSERT required.

-- NET RESULT (pencil_dod_evaluate_county('columbia'), live re-verify post-fix):
--   E: parcel_linked 14 -> 15 of 15 (100%, PASS) -- 2025-249-CA was the sole gap.
--   I: card_complete 8 -> 12 of 15 (80.0%, still FAIL, threshold is >=95%) -- 4 of the 6
--      zone-code fixes (2023-79-CA, 2025-354-CA, 2025-501-CA, 2026-54-CA) flip straight to
--      complete since they already had address/lat/long/assessed_value. 2025-249-CA gets its
--      zone_code but remains card_complete=false because assessed_value/market_value are BOTH
--      still NULL for that row (a separate data gap, out of this task's explicit parcel_id/
--      zone_code scope -- not touched, reported honestly below). 2025-63-CA also remains
--      card_complete=false for the same reason (assessed_value/market_value both NULL) even
--      though its parcel_id/zone_code are now fixed. 2025-2196-CC remains card_complete=false
--      because no zone_code is resolvable for its Fort White parcel (see above).
--   Residual gaps, NOT fixed this session, reported honestly (BLANK > WRONG):
--     - 2025-249-CA and 2025-63-CA: assessed_value AND market_value both NULL. No Columbia
--       County GIS layer in this session's catalog carries assessed/market value (checked all
--       ~150 service names in the root catalog; none matched). columbia.floridapa.com (the
--       Property Appraiser's own site) is reachable but is a JS-driven interactive search form,
--       not a queryable REST endpoint -- resolving this would require browser automation not
--       attempted in this session. Left NULL, not fabricated.
--     - 2025-2196-CC: zone_code genuinely unresolvable (Fort White town zoning authority, no
--       GIS endpoint, no placeholder sentinel value to anchor to -- see case notes above).
