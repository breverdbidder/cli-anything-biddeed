-- Gold Standard shard-12 (dispatch 9edcfdc8-6e46-4f6a-b676-a8e9d6ecfe87):
-- broward, martin, osceola, taylor.
--
-- Applied LIVE against Supabase during the session via the Management API SQL
-- endpoint (direct psql/pooler auth was unavailable in this session's
-- environment -- SUPABASE_DB_PASSWORD did not authenticate against either
-- pooler host). This file is the historical record of what was already
-- executed; statements are idempotent (guarded by id/source/WHERE predicates)
-- so re-running this file is safe.
--
-- ============================================================================
-- FINDING 1 (VERIFIED live): taylor G was a ghost-success. zoning_districts
-- id=10723 name='Single Family Residential (Shard3 Synthetic)' + a single
-- parcel_zones row (parcel_id='SYN-TAY-R1001', source=
-- 'Shard3-gold-standard-2026-06-24') were the ENTIRE basis for taylor's
-- G=100.0 PASS. Not real Perry/Taylor County ordinance data -- fabricated by
-- a prior "Shard3" session. Purged. G now correctly reads FAIL/null (no real
-- zoning data exists for taylor yet).
-- ============================================================================
DELETE FROM parcel_zones WHERE parcel_id='SYN-TAY-R1001' AND jurisdiction_id=908;
DELETE FROM zoning_districts WHERE id=10723 AND jurisdiction_id=908 AND code='R-1' AND name ILIKE '%Synthetic%';

-- ============================================================================
-- FINDING 2 (VERIFIED live): taylor E fix. 4 of 5 taylor auctions had a real,
-- scrapable street address but no parcel_id/geo/value. Exact house-number +
-- street-name match against fl_parcels (co_no=72, confirmed empirically via
-- phy_city='Perry' -- fl_parcels.co_no does NOT match public.fl_counties.co_no
-- for this row set; see session report) returned a single unambiguous
-- candidate for each. The 5th taylor row has no address at all
-- (property_address='TAYLOR COUNTY, FL' placeholder) and was left untouched.
-- ============================================================================
UPDATE multi_county_auctions SET parcel_id='05151-000', latitude=30.1051425, longitude=-83.602693, assessed_value=64040
  WHERE id='601edece-d316-462d-95eb-58398d4d37fe' AND lower(county)='taylor' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='07993-000', latitude=30.0930975, longitude=-83.5423498, assessed_value=71600
  WHERE id='1c86dc75-a3ac-4011-9336-86327460face' AND lower(county)='taylor' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='06562-216', latitude=29.901757, longitude=-83.6247518, assessed_value=109500
  WHERE id='feb4f082-1710-4222-ba32-403832ef7a8c' AND lower(county)='taylor' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='02959-200', latitude=30.1252232, longitude=-83.5876357, assessed_value=107350
  WHERE id='1d87f97b-7354-44a1-a26b-76f7b9748136' AND lower(county)='taylor' AND parcel_id IS NULL;

-- ============================================================================
-- FINDING 3 (VERIFIED live, CRITICAL): martin G/I were BOTH resting on
-- fabricated/unverified zoning data from a PRIOR shard12 session (run1113).
-- Of 31 martin parcel_zones rows, only 3 were real (source=
-- geoweb.martin.fl.us live ArcGIS point-in-polygon lookups dated 2026-07-10).
-- The other 28 were:
--   - 3 rows with source 'shard12_run1113/martin_e_synthetic' and parcel_id
--     literally 'MARTIN-SYNTHETIC-*' (fabricated).
--   - 25 rows with source 'shard12_run1113/martin_stuart_r1a:HYPOTHESIS'
--     (explicitly labeled HYPOTHESIS, i.e. an unverified guessed zone
--     assignment -- one row's parcel_id is literally 'MARTIN-UNKNOWN-195').
-- This inflated martin's reported state materially: G showed FAIL 90.3 (true
-- value is 0.0) and I showed FAIL 93.8 / 30 of 32 (true value is 9.4 / 3 of
-- 32). Purged; martin now correctly reports its true, much-earlier-stage
-- zoning coverage.
-- ============================================================================
DELETE FROM parcel_zones WHERE id IN (
  821169,821170,821171,821172,821173,821174,821175,821176,821177,821178,
  821179,821180,821181,821182,821183,821184,821185,821186,821187,821188,
  821189,821190,821191,821192,821193,821194,821195,821196
) AND jurisdiction_id IN (SELECT id FROM jurisdictions WHERE lower(county)='martin');

-- ============================================================================
-- FINDING 4 (VERIFIED live): broward G was contaminated by 7 parcel_zones
-- rows misfiled under the Broward jurisdiction with synthetic Collier County
-- (COLLIER-FC-0001..0003, COLLIER-TD-0001..0003) and Hillsborough
-- (HILLS-PO-988_skip-000) placeholder parcel_ids (source shard5_collier_fill
-- / shard5_collier_td0001_fix). These do not belong to Broward. Removing them
-- moved broward's G from 98.9 (contaminated) to a clean 100.0.
-- ============================================================================
DELETE FROM parcel_zones
  WHERE parcel_id IN ('COLLIER-FC-0002','COLLIER-TD-0003','COLLIER-TD-0002','COLLIER-FC-0001',
                       'HILLS-PO-988_skip-000','COLLIER-FC-0003','COLLIER-TD-0001')
    AND jurisdiction_id IN (SELECT id FROM jurisdictions WHERE lower(county)='broward');

-- ============================================================================
-- FINDING 5 (VERIFIED live, partial): broward I -- 10 of 36 address-bearing
-- I-fail rows backfilled with real parcel_id/lat/lng/assessed_value via exact
-- house-number+street match against fl_parcels (co_no=16; folio-format
-- parcel_id confirmed compatible with the existing v_zoning_gold_standard_card
-- join key). Metric did not move (card_complete unchanged at 580/635) because
-- these specific parcels are not yet present in the zoning card view with a
-- non-null zone_code -- broward's per-parcel zoning coverage is not 100%
-- despite G's district-standard-completeness metric reading 100%. Real,
-- verified property data; reported honestly as a non-move on the I score.
-- Excluded from the batch: 1 candidate where street-type (ST vs CT) disagreed
-- with the appraiser record (address ambiguity, not applied), and 2 that hit
-- the uq_mca_county_sale_date_parcel unique constraint against pre-existing
-- rows (left untouched rather than overwritten).
-- ============================================================================
UPDATE multi_county_auctions SET parcel_id='494108AK0380', assessed_value=267310, latitude=26.2025941, longitude=-80.2735162
  WHERE id='5193e9a3-d75a-4235-bed9-cd5998f4fa27' AND lower(county)='broward' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='494116AA0120', assessed_value=315460, latitude=26.1858602, longitude=-80.2591874
  WHERE id='5ba513a3-02fb-47d0-a8e0-85ae33e1c6b7' AND lower(county)='broward' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='474131020740', assessed_value=968760, latitude=26.3250486, longitude=-80.2931135
  WHERE id='daf40a7c-ea78-458a-b15d-f8fdcb4f1f08' AND lower(county)='broward' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='484203B10100', assessed_value=101340, latitude=26.3051427, longitude=-80.1461325
  WHERE id='85b10b09-0d3a-4d9e-b409-f20c1760d9d1' AND lower(county)='broward' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='514033051390', assessed_value=690300, latitude=25.9578824, longitude=-80.3495715
  WHERE id='0d9d6b2e-3832-4901-8e35-102a82dc66da' AND lower(county)='broward' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='504231241520', assessed_value=719650, latitude=26.0595664, longitude=-80.1965284
  WHERE id='14e33b93-dec4-4b0d-975d-9d47de671766' AND lower(county)='broward' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='494104AA0370', assessed_value=384170, latitude=26.2136481, longitude=-80.2615954
  WHERE id='1d884267-f635-4668-945d-e8b2f5dd9b27' AND lower(county)='broward' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='484203KM0030', assessed_value=99910, latitude=26.3065193, longitude=-80.1415619
  WHERE id='4effa5f5-458c-4d61-a7bd-63a2268d85c5' AND lower(county)='broward' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='504005100850', assessed_value=396340, latitude=26.1255038, longitude=-80.3721686
  WHERE id='44d5875e-f5c9-4939-a9a3-89b32c9fb907' AND lower(county)='broward' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='514206083950', assessed_value=1003770, latitude=26.0390213, longitude=-80.1910469
  WHERE id='1d69abcc-5ee8-4ad6-91f8-cf32c0c785e9' AND lower(county)='broward' AND parcel_id IS NULL;
-- (ab66b8da-fcd9-403a-9d3a-945c53262054 and dda19efc-f855-4115-a279-1fcbf2585d1c matched
--  cleanly on address but hit uq_mca_county_sale_date_parcel against a pre-existing row
--  sharing the same parcel_id/date/sale_type -- left untouched, not forced.)

-- ============================================================================
-- FINDING 6 (VERIFIED live, partial): osceola I -- 13 of 106 address-bearing
-- I-fail rows backfilled with real assessed_value (2 also got lat/lng where
-- fl_parcels centroid was populated) via exact address match against
-- fl_parcels (co_no=59). Metric did not move (23/134 unchanged): fl_parcels
-- osceola rows mostly lack centroid_lat/lng, and osceola's real DOR parcel_id
-- is 18 digits while the existing zone_code join (source
-- 'shard5-loop472-seed') keys on a 12-digit format. Truncating to 12 digits
-- was considered and REJECTED: condo/multi-unit buildings share the same
-- 12-digit base parcel with distinct 6-digit unit suffixes, so truncation
-- would have misassigned different physical units to one parcel_id -- a
-- correctness regression, not a fix. Applied as accurate 18-digit data
-- instead; does not yet flip the I score.
-- ============================================================================
UPDATE multi_county_auctions SET parcel_id='262630061300011440', assessed_value=38000
  WHERE id='b726e7d6-7d1b-4205-923b-bd5950b17441' AND lower(county)='osceola' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='072530267700790060', assessed_value=262200
  WHERE id='cb482065-24e8-4f5d-acfb-fd93918b4c57' AND lower(county)='osceola' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='112528370000030050', assessed_value=126100
  WHERE id='afaa720f-1644-4294-8ed0-bed911ffdcef' AND lower(county)='osceola' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='072530267700780180', assessed_value=322500
  WHERE id='d193c6c9-bf95-4657-b7bf-469e8178411b' AND lower(county)='osceola' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='122528540500011310', assessed_value=126200
  WHERE id='af0d133f-9e3b-49a8-a2dd-8833538545db' AND lower(county)='osceola' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='112528370000150100', assessed_value=98900
  WHERE id='adeb84c4-e1c7-4919-a758-ba9ef9e11f7b' AND lower(county)='osceola' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='302527570400099030', assessed_value=330800, latitude=28.2762936, longitude=-81.6495791
  WHERE id='d282d1a5-fd4e-4465-8af4-9e74d4544a72' AND lower(county)='osceola' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='2225291050000J0015', assessed_value=306100
  WHERE id='ac449a80-50fb-4ebc-84e0-a484da7ae2dc' AND lower(county)='osceola' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='132528000002620000', assessed_value=986900
  WHERE id='fed66f82-cba5-4abe-97bb-796ae6b352c3' AND lower(county)='osceola' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='122528540500011360', assessed_value=125000
  WHERE id='d42bb4e4-f7c4-4b20-8aff-f38e22437d4a' AND lower(county)='osceola' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='062527469400010380', assessed_value=441700, latitude=28.3380438, longitude=-81.6445354
  WHERE id='cbe499c6-448d-41f4-aa20-b3479a7f30e8' AND lower(county)='osceola' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='192529124700010570', assessed_value=315700
  WHERE id='c2242770-06c9-40bc-8e6b-964d15649f00' AND lower(county)='osceola' AND parcel_id IS NULL;
UPDATE multi_county_auctions SET parcel_id='242528375600010910', assessed_value=350300
  WHERE id='e695b84b-d60f-466c-8403-9d49a2d34168' AND lower(county)='osceola' AND parcel_id IS NULL;

-- ============================================================================
-- ULTRALOOP audit rows already inserted live into gold_standard_ultraloop_audit
-- for all 6 findings above (dispatch_id 9edcfdc8-6e46-4f6a-b676-a8e9d6ecfe87,
-- ultraloop_mode='fallback' -- native ultracode fan-out was not used for the
-- DB verify layer this session; verification was direct live-query evidence
-- captured before/after each change, see session report).
-- ============================================================================
