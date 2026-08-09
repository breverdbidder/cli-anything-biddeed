-- Gilchrist County letter I (card_complete) follow-up after E-fix attempt in same session.
-- NO WRITES EXECUTED. This file documents the diagnostic evidence only.
--
-- Evaluator: pencil_dod_evaluate_county('gilchrist') run fresh this session:
--   I: {"pass": false, "detail": "card_complete=8 of 14", "metric": 57.1}  (unchanged from baseline)
--   E: {"pass": false, "detail": "parcel_linked=8", "metric": 57.1}       (unchanged, E-fix verified as no-op this session)
--
-- Row-level diagnosis (query run live):
--   The 8 rows WITH parcel_id ALL have property_address, latitude/longitude,
--   assessed_value/market_value, AND a zone_code match in v_zoning_gold_standard_card
--   (all zone_code='R-1', Single Family Residential, county='gilchrist').
--   => These 8 rows are already 100% card-complete. I cannot exceed E's ceiling.
--
--   The 6 rows WITHOUT parcel_id (212025CA000033/036/043/064/070CAAXMX, 212026CA000004CAAXMX)
--   have NULL for property_address, latitude, longitude, assessed_value, AND market_value.
--   There is zero backfillable data on these rows independent of resolving parcel identity first.
--
-- Diagnostic query used:
SELECT m.case_number, m.parcel_id, m.property_address, m.latitude, m.longitude,
       m.assessed_value, m.market_value, z.zone_code
FROM multi_county_auctions m
LEFT JOIN v_zoning_gold_standard_card z ON z.parcel_id = m.parcel_id
WHERE lower(m.county)='gilchrist'
  AND (COALESCE(m.data_source,'') <> 'propertyonion' OR COALESCE(m.tier1_authoritative,false)=true)
ORDER BY m.parcel_id IS NULL, m.case_number;
--
-- New source attempt this follow-up session (beyond the 7 already exhausted by the E-fix agent):
--   FL GIO ArcGIS Florida_Statewide_Cadastral FeatureServer root discovery
--   (https://services9.arcgis.com/Gh9awoU677aKNXcj/.../FeatureServer?f=json) returned
--   HTTP 200 body {"error":{"code":400,"message":"Invalid URL"}} even for the bare
--   service-root discovery call with zero query predicates -- confirming this is not
--   a CO_NO=21-specific query issue (as the E-fix agent characterized it) but an
--   environment-level block/stale-endpoint on this exact ArcGIS path from this sandbox.
--   No alternate reachable source was found. No parcel_id, address, geo, or value was
--   fabricated for the 6 unlinked rows.
--
-- CONCLUSION: I is structurally gated by E. Blocked, same root cause, needs more research
-- (a working, non-blocked source for Gilchrist parcel/owner-name lookup) before either
-- letter can move. 0 rows changed.
