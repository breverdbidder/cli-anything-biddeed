-- Gold Standard shard-1 (dispatch ecb6f64b), columbia county, 4th firing.
-- Re-applies the E/I parcel_id writes that the 2026-07-19 16:42 migration
-- (20260719_shard2_columbia_ei_gis_zone_and_parcel_fix.sql, commit fa896ef1)
-- CLAIMED had landed but which live re-query (2026-07-24) proved had NOT
-- persisted: 2025-249-CA.parcel_id was still NULL, and 2025-63-CA.parcel_id
-- was still the malformed dual string '00130-000 AND 00130-001'. The
-- separately-run assessed_value/market_value backfill (commit 05dec1ff, same
-- day) DID persist correctly and is untouched here.
--
-- This is a PERSISTENCE REPAIR, not new research -- the underlying GIS facts
-- were independently re-verified live via gis.columbiacountyfla.com REST
-- (ArcGIS FeatureServer, no auth) on 2026-07-24 before re-applying:
--   * Addresses/FeatureServer/1 query Address LIKE '294%OMAR%' ->
--     exactly one feature: Address='294  NE OMAR TER', ParcelNo=
--     '28-1S-17-04576-002'. Confirms the 2025-249-CA target parcel.
--   * Parcels/FeatureServer/1 query ParcelNo='01-3S-15-00130-000' ->
--     1 feature (Owner ROGERS WALTER B, Municipality Columbia County).
--   * Parcels/FeatureServer/1 query ParcelNo='01-3S-15-00130-001' ->
--     0 features (re-confirmed still absent from the current tax roll).
--   * parcel_zones id=833992 (parcel_id='28-1S-17-04576-002', zone_code=
--     'A-1') and id=839442 (parcel_id='00130-000', zone_code='A-3') both
--     confirmed still present in parcel_zones, jurisdiction_id=1405.
--
-- WRITES (applied live via REST PATCH to multi_county_auctions on
-- 2026-07-24, NOT just via this file -- this file documents the same SQL
-- for the historical record):

UPDATE multi_county_auctions
SET parcel_id = '28-1S-17-04576-002'
WHERE county = 'columbia' AND case_number = '2025-249-CA' AND parcel_id IS NULL;

UPDATE multi_county_auctions
SET parcel_id = '00130-000',
    legal_description = 'Original parcel_id on file was the combined/malformed value ''00130-000 AND 00130-001''. Live GIS re-verification (2026-07-24) via gis.columbiacountyfla.com Parcels FeatureServer confirms ParcelNo=01-3S-15-00130-000 EXISTS (Owner ROGERS WALTER B, Municipality Columbia County / unincorporated) while ParcelNo=01-3S-15-00130-001 returns ZERO features (re-confirmed both exact match). parcel_id set to the one real GIS-verified parcel (00130-000) to exact-match parcel_zones id=839442 (zone_code A-3). Original combined string preserved here for reference.'
WHERE county = 'columbia' AND case_number = '2025-63-CA'
  AND parcel_id = '00130-000 AND 00130-001';

-- POST-WRITE VERIFICATION (fresh SELECT via Management API, immediately
-- after the REST PATCH calls, in the same session -- not trusting the PATCH
-- response alone, per this shard's explicit instruction to close the exact
-- honesty gap that caused the original regression):
--   2025-249-CA: parcel_id='28-1S-17-04576-002' (CONFIRMED persisted)
--   2025-63-CA:  parcel_id='00130-000'          (CONFIRMED persisted)
--
-- RESULT (pencil_dod_evaluate_county('columbia'), live re-verify post-fix,
-- 2026-07-24):
--   BEFORE: E metric=93.3 (parcel_linked=14 of 15); I metric=80.0 (card_complete=12 of 15)
--   AFTER:  E metric=100.0 (parcel_linked=15 of 15, PASS); I metric=93.3 (card_complete=14 of 15, still FAIL, threshold >=95%)
--
-- RESIDUAL (not touched, correctly unresolved, matches prior session's
-- finding verbatim): 2025-2196-CC (357 SW AMIEL CT, Fort White) remains the
-- sole I gap. parcel_id=04023-000 is correct and GIS-verified; zone_code is
-- genuinely unresolvable (0 features across Zoning_Atlas + 2 other layers,
-- parcel sits inside Town of Fort White's own incorporated zoning authority
-- with no queryable GIS endpoint). market_value is also NULL for this row
-- with no available source. Left BLANK, not guessed.
--
-- A/B/F (Cloudflare Turnstile block): re-checked live 2026-07-24, one cheap
-- request each, not a full re-investigation per this session's scope:
--   * columbiaclerk.com/ -> HTTP 403, response body contains Cloudflare
--     "challenge" markers (cf-mitigated:challenge family). Still blocked.
--   * civitekflorida.com/ocrs/app/search/case -> HTTP 302 to
--     index.xhtml;jsessionid=... (JSF/PrimeFaces session redirect); a
--     direct ?county=12 GET also 302s rather than reaching the case-search
--     form. This matches the previously screenshot-confirmed flow: the app
--     requires a stateful ViewState form POST before the actual query UI
--     (and its live Turnstile challenge) is reachable -- not solvable via
--     plain HTTP requests, tooling-independent, consistent with the 3rd
--     firing's finding. No CAPTCHA-solving service was purchased or wired
--     (not pre-authorized). Still blocked -- residual, not re-litigated
--     further this pass.
