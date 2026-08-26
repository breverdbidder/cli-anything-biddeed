-- Gold Standard ULTRALOOP shard-2, dispatch 62855eaa-34ca-4dc6-88ee-b7cb1a2e98ed
-- counties=gadsden, okeechobee, alachua, calhoun, leon
-- Session 2026-08-26. IDEMPOTENT RECORD of live REST PATCH/POST writes already
-- applied to production Supabase by the parallel fix agents this session, and
-- independently confirmed by the paired adversarial-verify agents (survived=true
-- for every letter below). Direct psql unavailable (documented ENOIDENTIFIER
-- pooler constraint) -- all writes were made via PostgREST, reconstructed here
-- as equivalent SQL for the historical record.
--
-- NOT included (no real write occurred, or claim was structural-block only):
--   gadsden C            -- investigation-only, no PATCH applied (10 rows are
--                            genuinely CLERK_SSOT_CANCELLED, confirmed redeemed
--                            pre-sale on live gadsdenclerk.com sheet)
--   calhoun C            -- structural block, case '546 OF 2024' already
--                            CLERK_SSOT_CANCELLED from prior 2026-08-11/12
--                            migrations, re-confirmed absent from live docket,
--                            no new write this session
--   alachua residual 5   -- 01 2025 CA 001928 / 003287 (multi-parcel) /
--                            01 2026 CA 000169 / 01 2025 CA 003919 /
--                            01 2025 CA 002643 -- no free public source
--                            surfaced a name/address; left NULL, not fabricated
--   leon B residual 2    -- 2025 CA 001586 / 2026 CA 000145 -- no independent
--                            2nd-source confirmation available (Leon Clerk
--                            cvweb.leonclerk.com HTTP 403 Akamai block); left
--                            unresolved rather than replicate the 2026-07-10
--                            single-source fabrication-revert precedent

-- ============================================================
-- OKEECHOBEE — letter I: FAIL 94.1% (card_complete=80/85) -> PASS 95.3% (81/85)
-- Case 472025CA000189CAAXMX (id b1c0dd06-cd4d-4082-8615-bc9b29a5d287).
-- Sources: myokeeclerk.com foreclosure list + court-filed Summary Judgment PDF
-- (Case No. 2025000189CAAXMX) + okeechobeepa.com Grizzly-GIS quickSearch/detail
-- endpoints + live WMS point-in-polygon zoning sample (okeechobeegis.com).
-- ============================================================
UPDATE multi_county_auctions
SET parcel_id = '1-29-37-35-0010-00000-0890',
    property_address = '2085 SW 19TH LN, OKEECHOBEE, FL 34974',
    latitude = 27.22606539952889,
    longitude = -80.84967876575895,
    market_value = 299838,
    assessed_value = 161101,
    parity_status = 'CLERK_VERIFIED'
WHERE lower(county) = 'okeechobee' AND id = 'b1c0dd06-cd4d-4082-8615-bc9b29a5d287';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES (
  '1-29-37-35-0010-00000-0890', 943, 'RSF', 'Residential Single-Family',
  'okeechobeegis.com_wms_ol_themes_point_in_polygon;layer=zoning_ResidentialSingleFamily;xy_epsg2236=(705015.98,1051378.34);case=472025CA000189CAAXMX'
);

-- AFTER (pencil_dod_evaluate_county('okeechobee'), live): 10/10 all pass.

-- ============================================================
-- ALACHUA — letters E, I: both FAIL 92.9% (79/85) -> FAIL 94.1% (80/85)
-- (genuine improvement, did not reach the 95.3% pass threshold this session)
-- Case '01 2025 CA 002983' (id d79e713b-2957-46b9-a49f-2ae97d5321da).
-- Sources: WebSearch case identification (Lakeview Loan Servicing v. Shirley
-- Baker) + Alachua County public ArcGIS PublicParcel FeatureServer (owner-name
-- match) + Alachua Property Appraiser ArcGIS Parcels35_view layer.
-- ============================================================
UPDATE multi_county_auctions
SET parcel_id = '03209-010-022',
    property_address = '15022 NW 130TH DR, ALACHUA, FL 32615',
    city = 'ALACHUA',
    zip = '32615',
    latitude = 29.793247,
    longitude = -82.484567,
    market_value = 137754,
    assessed_value_source = 'acpa_arcgis_Parcels35_view'
WHERE lower(county) = 'alachua' AND id = 'd79e713b-2957-46b9-a49f-2ae97d5321da';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
VALUES ('03209-010-022', 973, 'RSF-6', 'acpa_arcgis_Parcels35_view');

-- AFTER (pencil_dod_evaluate_county('alachua'), live):
--   E: parcel_linked=80/85 (94.1%) FAIL (needs 81)
--   I: card_complete=80/85 (94.1%) FAIL (needs 81)
--   No other letter regressed.

-- ============================================================
-- CALHOUN — letter D: FAIL 88.9% (matched_any=8/9) -> PASS 100.0% (9/9)
-- Case '25-52CA' (id ceaaa9e7-555f-49f4-ada2-fb1e44808fc1).
-- Source: live Calhoun Clerk WP REST foreclosures feed
-- (calhounclerk.com/wp-json/wp/v2/foreclosures), slug=25-52ca, confirmed
-- genuinely newly-posted (posted 2026-08-20, after a prior session's
-- 2026-08-11 check that found only 2 unrelated cases).
-- ============================================================
UPDATE multi_county_auctions
SET parity_status = 'PARITY_OK',
    parity_source = 'calhoun_clerk_foreclosure'
WHERE lower(county) = 'calhoun' AND id = 'ceaaa9e7-555f-49f4-ada2-fb1e44808fc1';

-- ============================================================
-- CALHOUN — letter I: FAIL 88.9% (card_complete=8/9) -> PASS 100.0% (9/9)
-- Same row (case '25-52CA'). Source: FL DOH statewide parcels ArcGIS layer 6
-- (maps.floridahealth.gov/server/rest/services/EHWATER/Parcels/MapServer/6),
-- the repo's newly-adopted appraiser-data SSOT (commit a05a127d) used to route
-- around Beacon/Schneider's Cloudflare bot-wall for this county. DOR_UC='001'
-- zone crosswalk cross-validated against 2 other calhoun parcels already
-- tagged zone_code='SFR' with the same DOR_UC.
-- ============================================================
UPDATE multi_county_auctions
SET latitude = 30.4567147673963,
    longitude = -85.0538237464868,
    market_value = 58826,
    assessed_value = 43094,
    assessed_value_source = 'fl_doh_statewide_parcels_layer6_calhoun',
    geo_source = 'fl_doh_statewide_parcels_layer6_calhoun_centroid',
    owner_name = 'DEASON ROBERT W &'
WHERE lower(county) = 'calhoun' AND id = 'ceaaa9e7-555f-49f4-ada2-fb1e44808fc1';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
VALUES ('29-1N-08-0000-0030-0000', 922, 'SFR', 'dor_use_code:fl_doh_statewide_parcels_layer6_calhoun');

-- AFTER (pencil_dod_evaluate_county('calhoun'), live): 9/10 (only C remains
-- FAIL, structurally blocked by case '546 OF 2024' CLERK_SSOT_CANCELLED).

-- ============================================================
-- LEON — letters C, D: both FAIL 94.4% (matched_clean/matched_any=237/251)
-- -> PASS 97.2% (244/251).
-- 7 rows matched against a fresh live RealAuction/RealTaxDeed AJAX calendar
-- harvest (scripts/realforeclose_aids_paginated_harvest.py) for auction dates
-- 09/04/2026, 09/08/2026 (foreclosure) and 09/16/2026 (tax_deed), confirming
-- real parcel/address/judgment data on the live platform for each case.
-- ============================================================
UPDATE multi_county_auctions
SET parity_status = 'matched_clean', parity_source = 'tier1_realforeclose_leon'
WHERE lower(county) = 'leon' AND case_number IN (
  '2024 CA 000670',
  '2025 CC 003163',
  '2025 CA 000400',
  '26-0090',
  '26-0093',
  '26-0089',
  '2025 CA 000325'
);

-- AFTER (pencil_dod_evaluate_county('leon'), live):
--   C: matched_clean=244/251 (97.2%) PASS
--   D: matched_any=244/251 (97.2%) PASS
--   7 residual tax_deed rows (26-0097, 26-0099, 26-0098, 26-0106, 26-0096,
--   26-0102, 26-0103) confirmed absent from 2 independent fresh live
--   re-harvests this session -- left parity_status=NULL, not fabricated.

-- ============================================================
-- LEON — letter F: FAIL 94.1% (tier1_sold=16/17) -> PASS 100.0% (17/17)
-- Case '2026 CA 000145'. Full bid ladder confirmed real (Opening Bid $0.00 ->
-- winning bid $100.00, is_winner=true, tier1_buyer_type='plaintiff'). Fleet-
-- wide cross-check confirmed nominal ($100-$101) plaintiff credit-bids are a
-- routinely-promoted tier1_authoritative pattern already established in
-- miami_dade, marion, bay, pasco, hillsborough -- this was the one leon row
-- not yet promoted through that same step.
-- ============================================================
UPDATE multi_county_auctions
SET tier1_authoritative = true,
    tier1_sold_amount = 100.0,
    tier1_sale_status = 'SOLD',
    tier1_verified_at = '2026-08-26T16:40:00Z'
WHERE lower(county) = 'leon' AND case_number = '2026 CA 000145';

-- AFTER (pencil_dod_evaluate_county('leon'), live): 9/10 (only B remains FAIL
-- at 88.2%, 2 genuinely-unresolved rows -- see notes above, no write applied).

-- ============================================================
-- Adversarial verification (paired verify agents, this session): all 11
-- letter-verdicts above independently re-confirmed (survived=true) by
-- re-querying the live rows/tables/external sources directly rather than
-- reusing the fix agent's evidence. Zero refuted claims this session.
-- Logged to public.gold_standard_ultraloop_audit (ids 18493-18503).
-- ============================================================
