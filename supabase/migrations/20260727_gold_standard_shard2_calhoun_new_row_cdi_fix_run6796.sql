-- GOLD STANDARD shard-2 (hernando/walton/jefferson/calhoun), loop run 6796,
-- dispatch 12f1aab8-908e-4fed-97ab-190250f06921.
--
-- DIAGNOSIS (live-verified 2026-07-27 via pencil_dod_evaluate_county('calhoun')):
-- calhoun regressed from the 2026-07-21/24 shipped state of C/D/I=100% (7 of 7)
-- to C/D/I=87.5% (7 of 8) because a NEW auction row was scraped in the interim:
-- case_number='383 OF 2024', parcel_id='33-2N-09-0000-0016-0500', tax deed,
-- auction_date=2026-09-10, created_at=2026-07-25 via the existing calhoun_clerk_scrape
-- cron -- carrying only the bare case/parcel/date, with parity_status, property_address,
-- lat/lng, assessed_value, and zoning all NULL/missing (not yet enriched). This is the
-- SAME "8th row" gap the calhoun sprint history has hit before on prior new-row arrivals
-- (see 20260724_shard10_calhoun_i_address_backfill.sql for the analogous I-only fix on
-- 5 earlier rows) -- not a new root cause, just a fresh unenriched row.
--
-- FIX (three independent live-sourced enrichments, each cross-checked against an
-- existing precedent for the same county so nothing here is a guess):
--
-- 1) C/D (parity): live-fetched calhounclerk.com/court-services/property-sales/tax-deed-sales/
--    (same JSON-blob-in-Vue-prop technique the 2026-07-21 4th-firing report demonstrated
--    working for this exact page) and found an exact match: case "383 OF 2024",
--    parcel "33-2N-09-0000-0016-0500", cert_holder "FIG 20 LLC", sale_date
--    "Sep 10, 2026 10:00 am", status "scheduled" -- byte-identical to our DB row's
--    case_number/parcel_id/auction_date/auction_status. Written as parity_status=
--    'matched_clean', parity_source='tier1:calhoun_clerk_live_20260727' -- exactly the
--    same source-naming convention as the other 7 calhoun rows (all
--    'tier1:calhoun_clerk_live_20260710').
--
-- 2) I (address/geo/value): queried FL GIO Florida_Statewide_Cadastral FeatureServer/0
--    live (https://services9.arcgis.com/Gh9awoU677aKree0/.../FeatureServer/0/query) for
--    PARCEL_ID='332N09000000160500' (our stored parcel_id with dashes stripped -- FL GIO's
--    own field has no dashes, confirmed empirically: a dash-included query returns zero
--    rows even for parcels already matched in our DB) AND CO_NO=17 (Calhoun). Got a single
--    exact match: PHY_ADDR1='23311 NW BLACK BOTTOM RD', PHY_CITY='ALTHA', PHY_ZIPCD=32421,
--    JV=79985, DOR_UC='001'. Centroid computed by FL GIO itself (returnCentroid=true,
--    outSR=4326): lat=30.52288255781302, lng=-85.1414146852005.
--
-- 3) I (zoning -- required because pencil_dod_evaluate_county's card_complete join
--    requires parcel_id to already be zoned in v_zoning_gold_standard_card): the parcel's
--    DOR_UC='001' matches the existing dor_use_code:floridaparcels.com crosswalk already
--    used for the other 6 rural calhoun parcels -- confirmed by directly querying FL GIO
--    for two of those existing precedent parcels (26-1S-10-0000-0004-0100 and
--    33-1N-08-0780-0001-0203), both also DOR_UC='001' and both already zoned SFR under
--    jurisdiction_id=922 (existing zoning_districts.id=11554, "Single Family Residential
--    (DOR use-code crosswalk -> Calhoun R Residential district)", with zone_standards
--    already carrying max_far=0.8 and max_density_du_acre=2.0 sourced from the Calhoun
--    County LDC -- no new zone_standards row needed, this parcel inherits the existing
--    SFR standard exactly like the other 2 DOR_UC=001 precedents). Inserted one
--    parcel_zones row with the same (jurisdiction_id=922, zone_code='SFR',
--    source='dor_use_code:floridaparcels.com') shape as the precedents.
--
-- All three writes were applied live via the PostgREST REST API with the service-role
-- key during this session (psql direct/pooler connection failed on password auth for
-- every host/user combination tried, consistent with every prior shard session's
-- documented finding -- SUPABASE_DB_PASSWORD is stale in this sandbox). This file
-- documents the equivalent SQL for the repo record; it is NOT re-applied by migration
-- tooling in this session (no psql/exec-RPC path available) -- the live writes already
-- landed via REST, reproduced in equivalent SQL form below for anyone applying via psql.
--
-- pencil_dod_evaluate_county('calhoun') before -> after (adversarially verified live,
-- see gold_standard_ultraloop_audit rows written this session and the session report):
--   C: matched_clean=7 of 8 (87.5%, FAIL) -> matched_clean=8 of 8 (100.0%, PASS)
--   D: matched_any=7 of 8   (87.5%, FAIL) -> matched_any=8 of 8   (100.0%, PASS)
--   I: card_complete=7 of 8 (87.5%, FAIL) -> card_complete=8 of 8 (100.0%, PASS)
--   A/E/G/H/J: unchanged (already PASS)
--   B/F: unchanged, still FAIL (verified=0/closed_sold=0, tier1_sold=0/closed_sold=0) --
--     genuinely blocked on real-world sale accrual + a documented MyFloridaCounty ORI
--     Turnstile form-automation gap (4+ prior firings, see
--     GOLD_STANDARD_SHARD7_HILLSBOROUGH_CALHOUN_DISPATCH_74E8C56B_4TH_FIRING_SESSION_REPORT.md).
--     Not re-attempted this session -- no new tooling (Firecrawl credits, browser
--     automation) available to close the documented gap; re-litigating with the same
--     curl/WebFetch toolset already exhausted across 4 firings would not move the metric.
--     calhoun's 3 non-tax-deed cases past their sale date were spot-checked this session
--     for a status change -- none found; no new lever, no writes.

BEGIN;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
VALUES ('33-2N-09-0000-0016-0500', 922, 'SFR', 'dor_use_code:floridaparcels.com')
ON CONFLICT DO NOTHING;

UPDATE multi_county_auctions
SET property_address = '23311 NW Black Bottom Rd Altha FL 32421',
    city = 'Altha',
    zip = '32421',
    latitude = 30.52288255781302,
    longitude = -85.1414146852005,
    assessed_value = 79985,
    assessed_value_source = 'fl_gio_cadastral_jv'
WHERE lower(county) = 'calhoun' AND case_number = '383 OF 2024';

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:calhoun_clerk_live_20260727',
    parity_checked_at = '2026-07-27T11:27:00+00:00'
WHERE lower(county) = 'calhoun' AND case_number = '383 OF 2024';

COMMIT;
