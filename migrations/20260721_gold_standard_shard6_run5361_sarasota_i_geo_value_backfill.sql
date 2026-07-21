-- Gold Standard shard-6 (sarasota, run 5361): letter I (property card completeness) --
-- geo/value backfill via a REAL, verified per-account crosswalk.
--
-- BASELINE (VERIFIED 2026-07-21 via pencil_dod_evaluate_county('sarasota') and fresh
-- live query, same predicate as the letter-I gate):
--   I: card_complete=143 of 341 (41.9%), FAIL (threshold 95%).
--   Root-cause query for the specific slice this migration targets (fresh, same session):
--     SELECT count(*) FROM public.multi_county_auctions a2
--     WHERE lower(a2.county)='sarasota'
--       AND (COALESCE(a2.data_source,'') <> 'propertyonion' OR COALESCE(a2.tier1_authoritative,false)=true)
--       AND a2.parcel_id IS NOT NULL
--       AND (COALESCE(a2.latitude, a2.po_latitude::double precision) IS NULL
--            OR COALESCE(a2.longitude, a2.po_longitude::double precision) IS NULL
--            OR COALESCE(a2.assessed_value, a2.market_value) IS NULL)
--     => 134 rows. parcel_id on these rows is the Sarasota Property Appraiser's own
--     10-digit tax-account number (e.g. '0086012004'), NOT the FL GIO 488K-row
--     fl_parcels 15-digit cadastral strap for co_no=58 -- CONFIRMED zero matches on a
--     direct parcel_id join against fl_parcels in an earlier session; not repeated here.
--
-- SOURCE DISCOVERED THIS SESSION (VERIFIED, live, public, no auth):
--   Sarasota County Property Appraiser (sc-pa.com) publishes its own hosted ArcGIS
--   FeatureServer at ags3.scgov.net (the same self-hosted ArcGIS Server that already
--   backs the county's zoning layers used in the prior sarasota-G migration). Reached
--   via the "PARCEL MAP" ArcGIS Online Experience Builder app linked from
--   https://www.sc-pa.com/search/map-property-search/
--   (item 86f63894cd9a45e2a6394df227d08e6e), whose embedded webmap JSON lists, among
--   others, a full-county-roll layer:
--     https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0
--   Row count VERIFIED live: 309,444 features (matches full county parcel-roll scale;
--   contrast with the decoy 953-row "Hosted/SarasotaCountyParcel" sample layer on the
--   same server, which was checked and rejected because it does not contain the
--   accounts needed -- see method notes below).
--   Fields used: account (10-digit tax-account number, VERIFIED same format/values as
--   multi_county_auctions.parcel_id for this county), fulladdress, assd (assessed
--   value), just (just/market value), plus polygon geometry (outSR=4326, i.e. WGS84
--   lon/lat) from which a shoelace-formula area-weighted centroid was computed for
--   latitude/longitude.
--
-- FIELD-MAPPING VERIFICATION (2-3+ known accounts, done BEFORE the batch, per task
-- instructions) -- 6 accounts spot-checked, all matched on house number + street:
--   0043030031 -> '2222 DR MARTIN LUTHER KING JR WAY SARASOTA FL, 34234' assd=200800 just=200800
--     (our DB: '2222 DR MARTIN LUTHER KING JR, SARASOTA, FL- 34234')
--   0091010009 -> '4825 VICTORIA AVE SARASOTA FL, 34233' assd=75200 just=75200
--     (our DB: '4825 VICTORIA AVE, SARASOTA, FL- 34233')
--   0488030012 -> '1711 BAYSHORE DR ENGLEWOOD FL, 34223' assd=585218 just=703700
--     (our DB: '1711 BAYSHORE DR, ENGLEWOOD, FL- 34223')
--   0436010038 -> '1250 CAMBRIDGE DR VENICE FL, 34293' assd=223900 just=223900
--   0449010115 -> '1065 DARWIN RD VENICE FL, 34293' assd=116700 just=116700
--   0042150004 -> '1906 ANDREA PL SARASOTA FL, 34235' assd=283000 just=283000
--
-- BATCH METHOD (all 134 targeted accounts, this session, live):
--   1. Queried Hosted/ParcelProperty/FeatureServer/0 in 25-account OR-chunks by
--      `account='<10-digit>'`, outFields=account,fulladdress,assd,just,txbl,
--      returnGeometry=true, outSR=4326.
--   2. 128 of 134 accounts matched. 6 did NOT match after individual re-query
--      confirmation (empty features[] on direct single-account query, not a chunking
--      artifact): 0020011231, 0104132007, 0012042111, 0175041024, 2027034007,
--      2022011063. Left completely untouched -- BLANK > WRONG, no fabricated/borrowed
--      values, no fl_parcels substitution.
--   3. For the 128 matches: computed polygon centroid (largest ring by |signed area|,
--      standard shoelace-formula area-weighted centroid) from the returned WGS84
--      polygon geometry -> latitude/longitude.
--   4. Automated house-number cross-check: normalized both multi_county_auctions
--      .property_address and the GIS fulladdress, compared leading numeric token.
--      0 mismatches out of 128 (100% pass) before any UPDATE was issued.
--   5. Sanity bbox check: all 128 centroids fall inside 26.8-27.5 lat / -82.7..-82.0
--      lon (Sarasota County FL bounding box). 0 rejected.
--   6. UPDATE ... SET column = COALESCE(column, <new value>) for latitude, longitude,
--      assessed_value (from assd), market_value (from just/market value), and
--      source_url (per-account ags3.scgov.net query URL) -- COALESCE ensures this
--      migration only ever fills genuinely-NULL cells and never overwrites any
--      pre-existing real value (e.g. rows that already had a source_url from a prior
--      pipeline retain it).
--
-- RESULT (VERIFIED live, same session): 128 of 134 rows updated. Re-running the exact
-- root-cause query above after the UPDATE batch returns count=6 (the untouched
-- no-match accounts).
--
-- WHY THE I METRIC ITSELF DID NOT MOVE (VERIFIED, not a silent failure -- root-caused
-- live this session, in scope disclosure per BLANK > WRONG):
--   pencil_dod_evaluate_county()'s letter-I `card_complete` predicate requires BOTH
--   (a) the geo/value completeness this migration targets, AND (b) that
--   a2.parcel_id join to v_zoning_gold_standard_card (zone_code IS NOT NULL) succeeds.
--   Live query this session:
--     geo_value_complete (address+lat+lng+assessed/market all present) = 329 of 341
--       (up from ~195 pre-migration -- this migration's real, verified effect)
--     card_complete (geo_value_complete AND zoning-crosswalk match)      = 143 of 341
--       (unchanged -- gate is the zoning join, not geo/value)
--     geo_ok_but_no_zoning_match = 176 rows
--   v_zoning_gold_standard_card for sarasota has only 142 distinct zone_code-populated
--   parcel/tax_account rows total (consistent with the already-known, separately
--   tracked letter-G FAIL: density=74.1 far=92.9 pk1000=0.0 in the same
--   pencil_dod_evaluate_county('sarasota') run). Closing that gap is a zoning-coverage
--   task (parcel_zones / zoning_districts / zone_standards expansion), not a geo/value
--   backfill task, and is out of scope for this migration. Flagged here for the next
--   sarasota session queue.
--
-- Dispatch: gold-standard-shard6-run5361, sarasota letter I 2nd attempt (geo/value
-- backfill only). No branches/PRs per ship-to-main mandate -- applied live via
-- mgmt_sql.py against project mocerqjnksmhcjzxrewo, then this file committed for
-- the record.

BEGIN;

-- All 128 UPDATE statements, one per matched Sarasota Property Appraiser
-- tax-account number, COALESCE-guarded so only genuinely-NULL cells are filled.
-- This is the exact batch applied live via mgmt_sql.py in this session.

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.07583),
  longitude = COALESCE(longitude, -82.428636),
  assessed_value = COALESCE(assessed_value, 237600),
  market_value = COALESCE(market_value, 237600),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270433060013%27&f=json')
WHERE id = 'e20c5339-06c7-43e3-b06b-91aec11aa1c3';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.072674),
  longitude = COALESCE(longitude, -82.184764),
  assessed_value = COALESCE(assessed_value, 205889),
  market_value = COALESCE(market_value, 255000),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270981040919%27&f=json')
WHERE id = '06bf09d9-e4bd-4fbb-bb5f-a8ff0440b7c6';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.103578),
  longitude = COALESCE(longitude, -82.227415),
  assessed_value = COALESCE(assessed_value, 247500),
  market_value = COALESCE(market_value, 247500),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270951145620%27&f=json')
WHERE id = 'bc48f6f0-06cb-4a49-918d-e1926a1b2772';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.322587),
  longitude = COALESCE(longitude, -82.522433),
  assessed_value = COALESCE(assessed_value, 292700),
  market_value = COALESCE(market_value, 292700),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%272035030040%27&f=json')
WHERE id = '027a11dd-74e5-4468-9a12-323833f0dea0';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.056173),
  longitude = COALESCE(longitude, -82.257343),
  assessed_value = COALESCE(assessed_value, 76606),
  market_value = COALESCE(market_value, 141200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270769160031%27&f=json')
WHERE id = '0b654d52-8952-4beb-ab61-c27b491bdaa8';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.054214),
  longitude = COALESCE(longitude, -82.206995),
  assessed_value = COALESCE(assessed_value, 222000),
  market_value = COALESCE(market_value, 222000),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270992186115%27&f=json')
WHERE id = '989efe61-35d7-44c5-80eb-199ddfc6172e';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.111387),
  longitude = COALESCE(longitude, -82.215947),
  assessed_value = COALESCE(assessed_value, 270910),
  market_value = COALESCE(market_value, 295800),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270944150414%27&f=json')
WHERE id = '8d7c40fa-903c-4152-b761-a368b197dbd9';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.064659),
  longitude = COALESCE(longitude, -82.341303),
  assessed_value = COALESCE(assessed_value, 409623),
  market_value = COALESCE(market_value, 460800),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270758150021%27&f=json')
WHERE id = 'd82ea2df-0e03-4166-a0aa-9cf50e48e564';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.296851),
  longitude = COALESCE(longitude, -82.425345),
  assessed_value = COALESCE(assessed_value, 333100),
  market_value = COALESCE(market_value, 333100),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270259030001%27&f=json')
WHERE id = 'f5adcbc5-66c9-4266-92f0-c2675f858e10';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.267504),
  longitude = COALESCE(longitude, -82.332939),
  assessed_value = COALESCE(assessed_value, 398666),
  market_value = COALESCE(market_value, 650200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270609020441%27&f=json')
WHERE id = '54a1de93-6e63-48ca-9ef1-a684dcf397bf';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.089277),
  longitude = COALESCE(longitude, -82.247358),
  assessed_value = COALESCE(assessed_value, 215300),
  market_value = COALESCE(market_value, 215300),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270971131602%27&f=json')
WHERE id = '23f4f9ec-1fe9-48db-a2ca-c2536aeaa086';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.269402),
  longitude = COALESCE(longitude, -82.436919),
  assessed_value = COALESCE(assessed_value, 625900),
  market_value = COALESCE(market_value, 625900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270285010011%27&f=json')
WHERE id = '4fac0cac-cdb0-47e0-838e-c119f4ef2990';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.270449),
  longitude = COALESCE(longitude, -82.493857),
  assessed_value = COALESCE(assessed_value, 241000),
  market_value = COALESCE(market_value, 241000),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270090130005%27&f=json')
WHERE id = 'acc301bf-662b-40cf-824c-ea44d708745b';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.087847),
  longitude = COALESCE(longitude, -82.201995),
  assessed_value = COALESCE(assessed_value, 11338),
  market_value = COALESCE(market_value, 16000),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270965054038%27&f=json')
WHERE id = 'fb422ae3-d456-474c-b71d-abdf9fb049ae';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.093014),
  longitude = COALESCE(longitude, -82.173014),
  assessed_value = COALESCE(assessed_value, 8283),
  market_value = COALESCE(market_value, 15500),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270958112505%27&f=json')
WHERE id = 'ab9e8521-76b1-4476-b0d3-8815b880f608';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.035912),
  longitude = COALESCE(longitude, -82.231018),
  assessed_value = COALESCE(assessed_value, 4800),
  market_value = COALESCE(market_value, 4800),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271000030026%27&f=json')
WHERE id = '662dd8cc-1c5c-40da-ad80-4429fad6a525';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.040688),
  longitude = COALESCE(longitude, -82.094596),
  assessed_value = COALESCE(assessed_value, 9000),
  market_value = COALESCE(market_value, 9000),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271147203424%27&f=json')
WHERE id = '948b0761-6cd0-4b6c-aadc-d95a9337d167';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.07213),
  longitude = COALESCE(longitude, -82.080064),
  assessed_value = COALESCE(assessed_value, 3630),
  market_value = COALESCE(market_value, 5900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271125229401%27&f=json')
WHERE id = '215f3919-ae72-4c91-9ff3-797bcbe87030';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.071851),
  longitude = COALESCE(longitude, -82.079513),
  assessed_value = COALESCE(assessed_value, 3630),
  market_value = COALESCE(market_value, 5900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271125229431%27&f=json')
WHERE id = '06159cd3-6e66-4a3c-ad7b-c52543edc910';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.033959),
  longitude = COALESCE(longitude, -82.077711),
  assessed_value = COALESCE(assessed_value, 5138),
  market_value = COALESCE(market_value, 9500),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271150234319%27&f=json')
WHERE id = 'af01cacc-eccc-47f5-9d89-0aec59cecfef';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.061948),
  longitude = COALESCE(longitude, -82.0685),
  assessed_value = COALESCE(assessed_value, 4093),
  market_value = COALESCE(market_value, 7700),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271128226912%27&f=json')
WHERE id = '8abddab0-b5f7-4b02-826c-6d055e012c2a';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.07),
  longitude = COALESCE(longitude, -82.090783),
  assessed_value = COALESCE(assessed_value, 5600),
  market_value = COALESCE(market_value, 5600),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271123232615%27&f=json')
WHERE id = '74a90d3a-8248-4f13-bb9b-4c162ba5c8e1';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.045687),
  longitude = COALESCE(longitude, -82.07729),
  assessed_value = COALESCE(assessed_value, 9500),
  market_value = COALESCE(market_value, 9500),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271149216511%27&f=json')
WHERE id = 'fc5200ff-6c32-4c48-ae7e-6279807d8240';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.359428),
  longitude = COALESCE(longitude, -82.525473),
  assessed_value = COALESCE(assessed_value, 200800),
  market_value = COALESCE(market_value, 200800),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270043030031%27&f=json')
WHERE id = 'f31e7e46-0bda-4089-8a6c-c35cf24554d5';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.047654),
  longitude = COALESCE(longitude, -82.098691),
  assessed_value = COALESCE(assessed_value, 3703),
  market_value = COALESCE(market_value, 7100),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271134201602%27&f=json')
WHERE id = '860b930d-3224-4e43-a1a9-09a06963ca31';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.04865),
  longitude = COALESCE(longitude, -82.092233),
  assessed_value = COALESCE(assessed_value, 9664),
  market_value = COALESCE(market_value, 15800),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271134201717%27&f=json')
WHERE id = '3e6853c8-a7b9-4601-ba4f-439ebe42271b';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.05188),
  longitude = COALESCE(longitude, -82.090726),
  assessed_value = COALESCE(assessed_value, 4430),
  market_value = COALESCE(market_value, 10600),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271134209603%27&f=json')
WHERE id = '3b9ba12f-4a0b-4d51-b15a-d1f281b70048';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.034321),
  longitude = COALESCE(longitude, -82.223845),
  assessed_value = COALESCE(assessed_value, 62500),
  market_value = COALESCE(market_value, 62500),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271000040509%27&f=json')
WHERE id = 'd61d93a2-f12e-4c0c-b98a-b7148acf3a00';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.040727),
  longitude = COALESCE(longitude, -82.099108),
  assessed_value = COALESCE(assessed_value, 7200),
  market_value = COALESCE(market_value, 7200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271147200405%27&f=json')
WHERE id = 'd407abd7-85cd-4d2d-9398-f1653af1df86';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.033315),
  longitude = COALESCE(longitude, -82.226341),
  assessed_value = COALESCE(assessed_value, 13000),
  market_value = COALESCE(market_value, 13000),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271000040323%27&f=json')
WHERE id = '56ba82a3-8a9a-4d81-b79b-ae7a3cbd4e41';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.042644),
  longitude = COALESCE(longitude, -82.059331),
  assessed_value = COALESCE(assessed_value, 3113),
  market_value = COALESCE(market_value, 4900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271151217712%27&f=json')
WHERE id = '64e7d7f1-6378-407f-b25a-d8cf58cbf673';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.040386),
  longitude = COALESCE(longitude, -82.060906),
  assessed_value = COALESCE(assessed_value, 4300),
  market_value = COALESCE(market_value, 4300),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271151226511%27&f=json')
WHERE id = 'd110bc09-ced8-43d4-ae67-1701e6febdb4';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.04057),
  longitude = COALESCE(longitude, -82.059842),
  assessed_value = COALESCE(assessed_value, 4400),
  market_value = COALESCE(market_value, 4400),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271151217302%27&f=json')
WHERE id = '6db65c6b-0956-4a7d-9472-c0c785da0524';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.04668),
  longitude = COALESCE(longitude, -82.08683),
  assessed_value = COALESCE(assessed_value, 7200),
  market_value = COALESCE(market_value, 7200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271149211812%27&f=json')
WHERE id = '32cfa9a2-a350-4f16-8c03-f83a1a20ccbc';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.283258),
  longitude = COALESCE(longitude, -82.466812),
  assessed_value = COALESCE(assessed_value, 75200),
  market_value = COALESCE(market_value, 75200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270091010009%27&f=json')
WHERE id = 'c2999463-27c5-4311-bd58-08efd0a4de1d';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 26.9975),
  longitude = COALESCE(longitude, -82.395112),
  assessed_value = COALESCE(assessed_value, 585218),
  market_value = COALESCE(market_value, 703700),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270488030012%27&f=json')
WHERE id = '105aac21-1d57-405d-97ba-14db584edccb';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.071571),
  longitude = COALESCE(longitude, -82.40474),
  assessed_value = COALESCE(assessed_value, 223900),
  market_value = COALESCE(market_value, 223900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270436010038%27&f=json')
WHERE id = '6bb028a7-3eb4-4291-a0eb-858b394bf02c';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.040631),
  longitude = COALESCE(longitude, -82.083069),
  assessed_value = COALESCE(assessed_value, 9500),
  market_value = COALESCE(market_value, 9500),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271149215110%27&f=json')
WHERE id = 'bfb1dc65-bca8-41d9-8e13-30176b60b6a3';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.033739),
  longitude = COALESCE(longitude, -82.222462),
  assessed_value = COALESCE(assessed_value, 4200),
  market_value = COALESCE(market_value, 4200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271000040038%27&f=json')
WHERE id = 'fe39925e-df30-40d1-91b4-211dc8854c4e';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.069365),
  longitude = COALESCE(longitude, -82.087165),
  assessed_value = COALESCE(assessed_value, 5900),
  market_value = COALESCE(market_value, 5900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271125232904%27&f=json')
WHERE id = 'c1f13374-c29d-4692-b7e4-b7d22fb78aca';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.065933),
  longitude = COALESCE(longitude, -82.088617),
  assessed_value = COALESCE(assessed_value, 2852),
  market_value = COALESCE(market_value, 4300),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271126233240%27&f=json')
WHERE id = '5db85746-1f1f-4902-b11d-887094732514';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.047644),
  longitude = COALESCE(longitude, -82.10084),
  assessed_value = COALESCE(assessed_value, 4675),
  market_value = COALESCE(market_value, 8300),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271134201420%27&f=json')
WHERE id = 'b569bd17-81f3-4f49-afb5-e1ece66bb02b';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.103391),
  longitude = COALESCE(longitude, -82.210859),
  assessed_value = COALESCE(assessed_value, 5845),
  market_value = COALESCE(market_value, 11100),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270953152304%27&f=json')
WHERE id = '669bec44-36b0-400c-a048-e42290e0c9bc';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.041083),
  longitude = COALESCE(longitude, -82.095196),
  assessed_value = COALESCE(assessed_value, 8600),
  market_value = COALESCE(market_value, 8600),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271147203405%27&f=json')
WHERE id = 'f634a34b-ddec-45cc-a6b5-507de9e02ed1';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.098604),
  longitude = COALESCE(longitude, -82.253668),
  assessed_value = COALESCE(assessed_value, 7086),
  market_value = COALESCE(market_value, 10700),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270950135901%27&f=json')
WHERE id = '3164c0c9-787d-4122-9cb0-d915ceaeb492';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.079344),
  longitude = COALESCE(longitude, -82.223756),
  assessed_value = COALESCE(assessed_value, 7200),
  market_value = COALESCE(market_value, 7200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270970061218%27&f=json')
WHERE id = '13f59999-1822-4e9c-ac04-8c5823b777b2';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.078954),
  longitude = COALESCE(longitude, -82.162659),
  assessed_value = COALESCE(assessed_value, 14000),
  market_value = COALESCE(market_value, 14000),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270962092423%27&f=json')
WHERE id = '09564243-2afc-4276-a2e7-7331549adb15';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.091724),
  longitude = COALESCE(longitude, -82.229707),
  assessed_value = COALESCE(assessed_value, 7086),
  market_value = COALESCE(market_value, 10700),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270969122728%27&f=json')
WHERE id = 'f408156c-791c-4238-bb34-5896d48c22a6';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.09896),
  longitude = COALESCE(longitude, -82.229482),
  assessed_value = COALESCE(assessed_value, 7086),
  market_value = COALESCE(market_value, 8000),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270952123324%27&f=json')
WHERE id = 'cf009602-96c3-4c9c-b9e4-ae75396298ff';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.06384),
  longitude = COALESCE(longitude, -82.401263),
  assessed_value = COALESCE(assessed_value, 116700),
  market_value = COALESCE(market_value, 116700),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270449010115%27&f=json')
WHERE id = '0058c171-51fd-45ef-8948-f46fee34616f';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.354014),
  longitude = COALESCE(longitude, -82.501643),
  assessed_value = COALESCE(assessed_value, 283000),
  market_value = COALESCE(market_value, 283000),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270042150004%27&f=json')
WHERE id = '13738ae1-29a2-48a6-bd5c-7b820e26e1ab';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.102235),
  longitude = COALESCE(longitude, -82.423796),
  assessed_value = COALESCE(assessed_value, 95000),
  market_value = COALESCE(market_value, 95000),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270409101101%27&f=json')
WHERE id = '19005c82-bc48-4e21-8b43-db21105c3e48';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.044344),
  longitude = COALESCE(longitude, -82.092411),
  assessed_value = COALESCE(assessed_value, 5314),
  market_value = COALESCE(market_value, 9600),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271147202712%27&f=json')
WHERE id = '646c6706-4764-468d-a48d-80db75ba15e0';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.091538),
  longitude = COALESCE(longitude, -82.229791),
  assessed_value = COALESCE(assessed_value, 7086),
  market_value = COALESCE(market_value, 10700),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270969122727%27&f=json')
WHERE id = '878f2489-4530-4322-98e7-7d58b4b21f14';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.050622),
  longitude = COALESCE(longitude, -82.079907),
  assessed_value = COALESCE(assessed_value, 7400),
  market_value = COALESCE(market_value, 7400),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271132212412%27&f=json')
WHERE id = '2dfbc4ba-898a-4848-8aab-cb9ced365dad';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.100401),
  longitude = COALESCE(longitude, -82.19923),
  assessed_value = COALESCE(assessed_value, 11100),
  market_value = COALESCE(market_value, 11100),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270955155001%27&f=json')
WHERE id = 'e0ebb0c7-53ff-4f0b-a43d-c54a116277c3';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.09373),
  longitude = COALESCE(longitude, -82.22383),
  assessed_value = COALESCE(assessed_value, 7086),
  market_value = COALESCE(market_value, 10700),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270952125008%27&f=json')
WHERE id = '7ee3ca8d-bbac-427a-b2f3-c4fe7c742c73';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.034308),
  longitude = COALESCE(longitude, -82.104705),
  assessed_value = COALESCE(assessed_value, 5138),
  market_value = COALESCE(market_value, 9500),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271148199006%27&f=json')
WHERE id = '09ca94e7-a2dd-4966-8116-5fc4631a30b0';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.035322),
  longitude = COALESCE(longitude, -82.101),
  assessed_value = COALESCE(assessed_value, 10100),
  market_value = COALESCE(market_value, 10100),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271148204314%27&f=json')
WHERE id = '26197f73-4503-48fa-82d7-2434852c4dc5';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.040188),
  longitude = COALESCE(longitude, -82.095272),
  assessed_value = COALESCE(assessed_value, 4993),
  market_value = COALESCE(market_value, 9000),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271147203507%27&f=json')
WHERE id = '3409eac7-1413-4ef8-9053-d77add530c55';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.103344),
  longitude = COALESCE(longitude, -82.210956),
  assessed_value = COALESCE(assessed_value, 5845),
  market_value = COALESCE(market_value, 11100),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270953152303%27&f=json')
WHERE id = 'b21004ac-f5b7-44b6-adc0-64320321c90e';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.048461),
  longitude = COALESCE(longitude, -82.076415),
  assessed_value = COALESCE(assessed_value, 7200),
  market_value = COALESCE(market_value, 7200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271132212903%27&f=json')
WHERE id = '546c8528-c1cb-44c2-914d-dc51e8557f19';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.092445),
  longitude = COALESCE(longitude, -82.141611),
  assessed_value = COALESCE(assessed_value, 23900),
  market_value = COALESCE(market_value, 23900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271094003500%27&f=json')
WHERE id = 'f726fd40-2fa3-4ef2-b1ab-1a6afbd02a17';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.034863),
  longitude = COALESCE(longitude, -82.185584),
  assessed_value = COALESCE(assessed_value, 10469),
  market_value = COALESCE(market_value, 13200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271006021116%27&f=json')
WHERE id = 'bc18d816-4602-46b5-a9df-87b19942afce';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.106191),
  longitude = COALESCE(longitude, -82.248263),
  assessed_value = COALESCE(assessed_value, 7409),
  market_value = COALESCE(market_value, 9900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270949136822%27&f=json')
WHERE id = '02bf8aff-1157-4faa-9063-034eb5e4dba4';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.036949),
  longitude = COALESCE(longitude, -82.106131),
  assessed_value = COALESCE(assessed_value, 5143),
  market_value = COALESCE(market_value, 9500),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271148199403%27&f=json')
WHERE id = '7f849839-41b5-41ba-8562-638b3970d806';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.358878),
  longitude = COALESCE(longitude, -82.535117),
  assessed_value = COALESCE(assessed_value, 39943),
  market_value = COALESCE(market_value, 46900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%272024020086%27&f=json')
WHERE id = 'f603eb98-3094-4c10-ac18-7882e0a83534';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.090785),
  longitude = COALESCE(longitude, -82.166565),
  assessed_value = COALESCE(assessed_value, 15900),
  market_value = COALESCE(market_value, 15900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270961111933%27&f=json')
WHERE id = '59b95998-7962-4d3d-a61a-c94add3d9ffa';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.086858),
  longitude = COALESCE(longitude, -82.218428),
  assessed_value = COALESCE(assessed_value, 9181),
  market_value = COALESCE(market_value, 14600),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270967060208%27&f=json')
WHERE id = '6ce3bc79-933c-44e7-9781-5ddbde1b0fc4';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.082952),
  longitude = COALESCE(longitude, -82.169392),
  assessed_value = COALESCE(assessed_value, 8283),
  market_value = COALESCE(market_value, 15500),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270962089939%27&f=json')
WHERE id = '98ea532c-896c-48ae-91e7-7f8dafaf992b';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.054841),
  longitude = COALESCE(longitude, -82.167625),
  assessed_value = COALESCE(assessed_value, 10452),
  market_value = COALESCE(market_value, 13400),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270985023413%27&f=json')
WHERE id = '8a1382f9-4c57-4b65-8ed9-c398398715da';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.079208),
  longitude = COALESCE(longitude, -82.25278),
  assessed_value = COALESCE(assessed_value, 17800),
  market_value = COALESCE(market_value, 17800),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270972169157%27&f=json')
WHERE id = 'ad1285bf-282f-455e-a2ea-659af9f2ac27';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.044856),
  longitude = COALESCE(longitude, -82.078383),
  assessed_value = COALESCE(assessed_value, 5360),
  market_value = COALESCE(market_value, 10000),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271149214707%27&f=json')
WHERE id = '3889cf5a-a74c-4863-acd9-a8ca0ca8e0de';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.038006),
  longitude = COALESCE(longitude, -82.07882),
  assessed_value = COALESCE(assessed_value, 3897),
  market_value = COALESCE(market_value, 12300),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271150216203%27&f=json')
WHERE id = '5a4b4f01-ae49-43f2-a1b6-71295af76897';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.042876),
  longitude = COALESCE(longitude, -82.083329),
  assessed_value = COALESCE(assessed_value, 3313),
  market_value = COALESCE(market_value, 6400),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271149214003%27&f=json')
WHERE id = '5850a670-c93c-49d2-90e8-6296a55591f3';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.047879),
  longitude = COALESCE(longitude, -82.06266),
  assessed_value = COALESCE(assessed_value, 6100),
  market_value = COALESCE(market_value, 6100),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271130218602%27&f=json')
WHERE id = 'a4d15689-7291-4d18-8d3f-24f73112d3e7';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.06529),
  longitude = COALESCE(longitude, -82.251231),
  assessed_value = COALESCE(assessed_value, 11128),
  market_value = COALESCE(market_value, 19100),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270974183042%27&f=json')
WHERE id = '5828abbe-d621-4d91-8009-62ba4b6e8cd5';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.066228),
  longitude = COALESCE(longitude, -82.252974),
  assessed_value = COALESCE(assessed_value, 11500),
  market_value = COALESCE(market_value, 11500),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270974182705%27&f=json')
WHERE id = 'eb201143-4c29-4431-9607-5a3c38ca21ce';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.331649),
  longitude = COALESCE(longitude, -82.496792),
  assessed_value = COALESCE(assessed_value, 229300),
  market_value = COALESCE(market_value, 229300),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%272033130048%27&f=json')
WHERE id = 'efa25d4f-991a-4588-ad70-d16933413992';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.103425),
  longitude = COALESCE(longitude, -82.213856),
  assessed_value = COALESCE(assessed_value, 7570),
  market_value = COALESCE(market_value, 9700),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270953151601%27&f=json')
WHERE id = '062713f6-face-40b0-bb87-3bc025b85060';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.121961),
  longitude = COALESCE(longitude, -82.439124),
  assessed_value = COALESCE(assessed_value, 78166),
  market_value = COALESCE(market_value, 86500),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270405020050%27&f=json')
WHERE id = 'b7d0152b-6401-45da-adda-c020555e5b43';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.041111),
  longitude = COALESCE(longitude, -82.276884),
  assessed_value = COALESCE(assessed_value, 8300),
  market_value = COALESCE(market_value, 8300),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270790013665%27&f=json')
WHERE id = 'e3177aa5-a319-4a45-bbc9-931794e31dce';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.081759),
  longitude = COALESCE(longitude, -82.238618),
  assessed_value = COALESCE(assessed_value, 7016),
  market_value = COALESCE(market_value, 12400),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270972064619%27&f=json')
WHERE id = '13bee813-d70b-46d2-9857-0b6eac963922';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.075231),
  longitude = COALESCE(longitude, -82.083532),
  assessed_value = COALESCE(assessed_value, 6100),
  market_value = COALESCE(market_value, 6100),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271125231002%27&f=json')
WHERE id = '7714ef99-cc0c-4351-bf09-190d42e901f7';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.07208),
  longitude = COALESCE(longitude, -82.064295),
  assessed_value = COALESCE(assessed_value, 4900),
  market_value = COALESCE(market_value, 4900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271127227908%27&f=json')
WHERE id = 'f857eaf2-bb4d-4149-81e8-27b0a7bfa43b';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.056937),
  longitude = COALESCE(longitude, -82.058529),
  assessed_value = COALESCE(assessed_value, 3113),
  market_value = COALESCE(market_value, 5100),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271129220904%27&f=json')
WHERE id = '5c770438-b75d-4a25-a3e7-abdc15d8457e';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.074384),
  longitude = COALESCE(longitude, -82.090407),
  assessed_value = COALESCE(assessed_value, 3864),
  market_value = COALESCE(market_value, 4900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271125231833%27&f=json')
WHERE id = 'd8da3546-7187-478d-8737-00c6c01214a6';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.060424),
  longitude = COALESCE(longitude, -82.093111),
  assessed_value = COALESCE(assessed_value, 9500),
  market_value = COALESCE(market_value, 9500),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271133207123%27&f=json')
WHERE id = '7359366d-0f6d-4ef3-8a77-c1d2b4475d1c';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.070917),
  longitude = COALESCE(longitude, -82.064517),
  assessed_value = COALESCE(assessed_value, 5900),
  market_value = COALESCE(market_value, 5900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271127227923%27&f=json')
WHERE id = '97ed4240-078b-41aa-83ae-092ec33bf2b1';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.10363),
  longitude = COALESCE(longitude, -82.161989),
  assessed_value = COALESCE(assessed_value, 15290),
  market_value = COALESCE(market_value, 15400),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270959116110%27&f=json')
WHERE id = '36758309-c7cb-4172-98f7-5626530dec1f';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.043488),
  longitude = COALESCE(longitude, -82.07491),
  assessed_value = COALESCE(assessed_value, 9100),
  market_value = COALESCE(market_value, 9100),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271149216703%27&f=json')
WHERE id = '480e3a3a-59c9-4483-a5bc-76a0b0f98958';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.092821),
  longitude = COALESCE(longitude, -82.186442),
  assessed_value = COALESCE(assessed_value, 16000),
  market_value = COALESCE(market_value, 16000),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270958066822%27&f=json')
WHERE id = '355533c4-b444-4bcc-afa5-e3d4f9ad5c54';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.068185),
  longitude = COALESCE(longitude, -82.170067),
  assessed_value = COALESCE(assessed_value, 10469),
  market_value = COALESCE(market_value, 14200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270984046914%27&f=json')
WHERE id = '014fc7a5-ec84-4aad-8ae5-bdba41111ea9';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.103504),
  longitude = COALESCE(longitude, -82.169189),
  assessed_value = COALESCE(assessed_value, 6764),
  market_value = COALESCE(market_value, 15400),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270959119320%27&f=json')
WHERE id = '8ee06b2b-4a3f-4b19-9af3-f9fbd60da1d0';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.079732),
  longitude = COALESCE(longitude, -82.221442),
  assessed_value = COALESCE(assessed_value, 4348),
  market_value = COALESCE(market_value, 6100),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270968061429%27&f=json')
WHERE id = '34331b6a-ac59-423d-ba57-d7320d12231c';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.053511),
  longitude = COALESCE(longitude, -82.420475),
  assessed_value = COALESCE(assessed_value, 40702),
  market_value = COALESCE(market_value, 53600),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270452090065%27&f=json')
WHERE id = '0b939e9f-b93c-4287-852a-dba536821196';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.042645),
  longitude = COALESCE(longitude, -82.076154),
  assessed_value = COALESCE(assessed_value, 9400),
  market_value = COALESCE(market_value, 9400),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271149216239%27&f=json')
WHERE id = '5a293e64-407c-4844-8da7-dc6592e450fd';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.04388),
  longitude = COALESCE(longitude, -82.08623),
  assessed_value = COALESCE(assessed_value, 7409),
  market_value = COALESCE(market_value, 13900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271149211738%27&f=json')
WHERE id = '96545aaf-75cc-49c2-b3db-df426cf326de';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.042484),
  longitude = COALESCE(longitude, -82.076366),
  assessed_value = COALESCE(assessed_value, 3721),
  market_value = COALESCE(market_value, 7200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271149216236%27&f=json')
WHERE id = '50212041-e064-4977-b9a1-85605232db75';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.059704),
  longitude = COALESCE(longitude, -82.059751),
  assessed_value = COALESCE(assessed_value, 5900),
  market_value = COALESCE(market_value, 5900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271129221202%27&f=json')
WHERE id = '1114ac3b-0d7a-4355-9a91-607971d42ec0';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.035558),
  longitude = COALESCE(longitude, -82.193),
  assessed_value = COALESCE(assessed_value, 10469),
  market_value = COALESCE(market_value, 13200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271004020213%27&f=json')
WHERE id = '7cb9e9d7-cf58-41b9-9ef9-893700df0c29';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.045167),
  longitude = COALESCE(longitude, -82.087638),
  assessed_value = COALESCE(assessed_value, 7300),
  market_value = COALESCE(market_value, 7300),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271149211750%27&f=json')
WHERE id = 'e249027a-4549-4c33-aad7-ffd64a87d02f';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.042649),
  longitude = COALESCE(longitude, -82.073286),
  assessed_value = COALESCE(assessed_value, 5800),
  market_value = COALESCE(market_value, 5800),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271151217009%27&f=json')
WHERE id = '26507e09-015a-461e-9275-a2c759ea091e';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.072998),
  longitude = COALESCE(longitude, -82.068648),
  assessed_value = COALESCE(assessed_value, 5700),
  market_value = COALESCE(market_value, 5700),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271127227701%27&f=json')
WHERE id = '4e8772ec-9b46-413e-a80b-c434b6fed11c';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.039887),
  longitude = COALESCE(longitude, -82.06028),
  assessed_value = COALESCE(assessed_value, 4300),
  market_value = COALESCE(market_value, 4300),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271151226508%27&f=json')
WHERE id = '33f1e644-986f-46c4-b659-af64be8c9c62';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.040375),
  longitude = COALESCE(longitude, -82.070847),
  assessed_value = COALESCE(assessed_value, 4671),
  market_value = COALESCE(market_value, 9700),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271151235515%27&f=json')
WHERE id = '0c15f93b-8266-405e-bf54-ec150138e439';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.040374),
  longitude = COALESCE(longitude, -82.071408),
  assessed_value = COALESCE(assessed_value, 4671),
  market_value = COALESCE(market_value, 9700),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271151235519%27&f=json')
WHERE id = 'c43174be-aaa4-41ed-856a-1c62fc9b15ed';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.074471),
  longitude = COALESCE(longitude, -82.076648),
  assessed_value = COALESCE(assessed_value, 3113),
  market_value = COALESCE(market_value, 4900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271125229520%27&f=json')
WHERE id = 'f3c52c2b-34ee-4b1a-b1c7-49bad9e569f9';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.032523),
  longitude = COALESCE(longitude, -82.08355),
  assessed_value = COALESCE(assessed_value, 9800),
  market_value = COALESCE(market_value, 9800),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271150247721%27&f=json')
WHERE id = '87c283d1-67d8-44da-b124-ad3ab3915946';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.066611),
  longitude = COALESCE(longitude, -82.058954),
  assessed_value = COALESCE(assessed_value, 3366),
  market_value = COALESCE(market_value, 5200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271128225508%27&f=json')
WHERE id = '21690b79-56b3-468f-9624-2e45c65ad621';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.099636),
  longitude = COALESCE(longitude, -82.173395),
  assessed_value = COALESCE(assessed_value, 11600),
  market_value = COALESCE(market_value, 11600),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270957117603%27&f=json')
WHERE id = '04aa8544-7525-4dcf-9636-ad77804545ed';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.046171),
  longitude = COALESCE(longitude, -82.085959),
  assessed_value = COALESCE(assessed_value, 6764),
  market_value = COALESCE(market_value, 12900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271149211729%27&f=json')
WHERE id = '763cbc8d-70c5-40b3-86fd-24eb54b45aba';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.356185),
  longitude = COALESCE(longitude, -82.534528),
  assessed_value = COALESCE(assessed_value, 83100),
  market_value = COALESCE(market_value, 83100),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%272024080009%27&f=json')
WHERE id = '3db4565f-8a66-4a2a-b8bc-76e312f006bb';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.064187),
  longitude = COALESCE(longitude, -82.094173),
  assessed_value = COALESCE(assessed_value, 200),
  market_value = COALESCE(market_value, 200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271124207136%27&f=json')
WHERE id = '6a14e543-7f54-4e76-b53a-5e6e948d36b4';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.118933),
  longitude = COALESCE(longitude, -82.436998),
  assessed_value = COALESCE(assessed_value, 1800),
  market_value = COALESCE(market_value, 1800),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270405090032%27&f=json')
WHERE id = '5df83041-7e78-45a4-9248-22ada40034ec';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.080441),
  longitude = COALESCE(longitude, -82.242676),
  assessed_value = COALESCE(assessed_value, 18709),
  market_value = COALESCE(market_value, 33200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270972171913%27&f=json')
WHERE id = '83b756a6-1bd4-4cd6-8e4d-889c03d9a5d6';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.074441),
  longitude = COALESCE(longitude, -82.077702),
  assessed_value = COALESCE(assessed_value, 5100),
  market_value = COALESCE(market_value, 5100),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271125229417%27&f=json')
WHERE id = '4ac09941-6baf-4ff9-b5d4-4230fdf1ef0a';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.037821),
  longitude = COALESCE(longitude, -82.191284),
  assessed_value = COALESCE(assessed_value, 13500),
  market_value = COALESCE(market_value, 13500),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271004019717%27&f=json')
WHERE id = '2adfd744-de19-4b00-afff-d14722acb50c';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.037977),
  longitude = COALESCE(longitude, -82.191079),
  assessed_value = COALESCE(assessed_value, 13200),
  market_value = COALESCE(market_value, 13200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271004019716%27&f=json')
WHERE id = 'eed347d5-e763-49b9-b343-77363f17d338';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.074389),
  longitude = COALESCE(longitude, -82.076928),
  assessed_value = COALESCE(assessed_value, 3113),
  market_value = COALESCE(market_value, 4900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271125229519%27&f=json')
WHERE id = '658be2ff-981d-4b9d-9456-d4e99a1817ed';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.373549),
  longitude = COALESCE(longitude, -82.552043),
  assessed_value = COALESCE(assessed_value, 300),
  market_value = COALESCE(market_value, 300),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%272004020016%27&f=json')
WHERE id = 'f4921e29-e6a6-4459-adcb-57ae6cfe8d2c';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.041467),
  longitude = COALESCE(longitude, -82.270147),
  assessed_value = COALESCE(assessed_value, 90000),
  market_value = COALESCE(market_value, 90000),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270789011099%27&f=json')
WHERE id = '2faa8441-445c-4359-89d4-5fbe0b8b42e4';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.06954),
  longitude = COALESCE(longitude, -82.059151),
  assessed_value = COALESCE(assessed_value, 3113),
  market_value = COALESCE(market_value, 5400),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271127225902%27&f=json')
WHERE id = '2b960297-330b-43eb-b822-377b5e2273be';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.064714),
  longitude = COALESCE(longitude, -82.071496),
  assessed_value = COALESCE(assessed_value, 7400),
  market_value = COALESCE(market_value, 7400),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271128227227%27&f=json')
WHERE id = 'b0f795be-a797-4326-915f-b54ec32f9d93';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.069835),
  longitude = COALESCE(longitude, -82.092506),
  assessed_value = COALESCE(assessed_value, 4500),
  market_value = COALESCE(market_value, 4500),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271123233334%27&f=json')
WHERE id = 'a1e8bcb5-5dfe-43e3-be9a-a16208350a40';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.04658),
  longitude = COALESCE(longitude, -82.085761),
  assessed_value = COALESCE(assessed_value, 6603),
  market_value = COALESCE(market_value, 12400),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271149211727%27&f=json')
WHERE id = '3f3e488c-859a-441d-93d5-0fbbfd288181';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.14095),
  longitude = COALESCE(longitude, -82.455027),
  assessed_value = COALESCE(assessed_value, 54113),
  market_value = COALESCE(market_value, 79900),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%270165100074%27&f=json')
WHERE id = 'b9935399-b149-4c73-aa2f-d72c70141d14';

UPDATE public.multi_county_auctions SET
  latitude = COALESCE(latitude, 27.034408),
  longitude = COALESCE(longitude, -82.062594),
  assessed_value = COALESCE(assessed_value, 11200),
  market_value = COALESCE(market_value, 11200),
  source_url = COALESCE(source_url, 'https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0/query?where=account=%271152236811%27&f=json')
WHERE id = '31f76ee8-396d-40e8-9131-1ef1cf4b4ae1';

COMMIT;
