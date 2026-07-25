-- Gold Standard shard-4 (polk/jefferson/okaloosa) -- dispatch 3e3a8dd9-2ca8-4611-b6b9-fec7ac92d413
-- loop run 6354. Documents changes already applied LIVE via the Supabase Management API
-- (direct psql/pooler auth fails with the same stale-password issue every prior session
-- this month has hit -- Management API SQL + PostgREST both confirmed live and used
-- instead, per the documented fleet-wide workaround).
--
-- ============================================================
-- OKALOOSA: C/D/E FAIL (93.2%, 55/59) -> PASS (96.6%, 57/59)
-- ============================================================
-- Root cause: 4 rows carried parcel_id IS NULL. 2 of the 4 (2024-CA-000470,
-- 2024-TDD-000089) are the pre-migration dead legacy stub rows already exhaustively
-- documented as unfixable across 3+ prior sessions (2026-07-10 shard10 run3534,
-- 2026-07-11 shard8, 2026-07-19 SHARD-3) -- confirmed absent from the live Bid4Assets
-- platform via real browser search; left untouched again this session, not re-investigated.
--
-- The other 2 were genuinely fixable and are resolved here, both cross-verified against
-- two independent live sources (Okaloosa County GIS ArcGIS FeatureServer +
-- the Bid4Assets auction listing JSON) and then independently re-derived by a separate
-- adversarial-refuter Workflow run (ULTRALOOP PROTOCOL) before being counted as survived.
--
-- Parity: parity_status/parity_source stamped following the EXACT precedent set by the
-- 2026-07-24 shard9 run6080 session for this same county (tier1:okaloosa_gis_arcgis_
-- pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121[:label]) -- not a new pattern.

-- 2025-CA-002243-F: property_address on file was already a real, well-formed address
-- (3191 E Scenic Hwy 98 #212, Destin FL) but had no parcel_id -- the Bid4Assets FC grid
-- carries no APN/parcel column (documented structural limitation, 2026-07-19 SHARD-3
-- session). Resolved via a direct address+unit query against Okaloosa County's own
-- parcel/addressing GIS layer: exactly one PIN matches "3191 SCENIC HIGHWAY 98 UNIT 212".
UPDATE multi_county_auctions
SET parcel_id = '00-2S-22-0520-0000-2120',
    property_address = '3191 SCENIC HIGHWAY 98 UNIT 212 DESTIN FL 32541',
    assessed_value = 360000.0,
    market_value = 360000.0,
    assessed_value_source = 'okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:shard4_run6354',
    latitude = 30.382356095392748,
    longitude = -86.41881498459489,
    parity_status = 'matched_clean',
    parity_source = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:shard4_run6354',
    parity_checked_at = now(),
    updated_at = now()
WHERE county = 'okaloosa' AND case_number = '2025-CA-002243-F' AND parcel_id IS NULL;

-- 2025-CA-002234-F: property_address on file was a broken scraper artifact, literally the
-- string "Movable:" with nothing else (the Bid4Assets FC grid's address field was empty
-- for this row and a template label leaked through). Root cause found by fetching the raw
-- Bid4Assets listing JSON directly: Asset_Title reveals the real property ("Condominium
-- Unit No. 601-8, Fair Oaks Village") and Defendant is "Guevara, Sean Lazaro". Cross-
-- referenced against Okaloosa GIS by owner surname: exactly one match, OWNER "GUEVARA SEAN
-- L", legal description "FAIR OAKS VILLAGE CONDO" / "BLDG E UNIT 8" -- an exact match on
-- both owner name and condo development name, not a coincidental address collision.
UPDATE multi_county_auctions
SET parcel_id = '02-2S-24-0750-000E-0080',
    property_address = '609 COLONIAL DR UNIT 8 FORT WALTON BEACH FL 32547',
    assessed_value = 102850.0,
    market_value = 106000.0,
    assessed_value_source = 'okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:shard4_run6354',
    latitude = 30.4392683959039,
    longitude = -86.62230009310485,
    parity_status = 'matched_clean',
    parity_source = 'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:shard4_run6354',
    parity_checked_at = now(),
    updated_at = now()
WHERE county = 'okaloosa' AND case_number = '2025-CA-002234-F' AND parcel_id IS NULL;

-- NOT included: letter I (property card completeness) is NOT fixed by this migration and
-- cannot cross the 95% bar this session even in the best case. card_complete requires the
-- parcel to ALSO be zoned (linked via v_zoning_gold_standard_card). Neither of the 2 parcels
-- fixed above is in parcel_zones -- no county-wide Okaloosa zoning ArcGIS layer is currently
-- live (Planning-Development/Zoning MapServer, previously present per parcel_zones.source
-- values from 2026-07-19, now returns only Flood/Flood2 -- the zoning service has been
-- removed or renumbered since). Even a hypothetical successful zoning of both new parcels
-- only reaches 56/59=94.9% (still FAIL), because the ceiling is capped by 3 permanently
-- unresolvable rows: the 2 dead legacy stubs above (no address/parcel_id at all, confirmed
-- absent from the live platform) and B4A-1299799 / 37 Mary Esther Dr (parcel
-- 172S24236000060030, confirmed no live zoning GIS source for Mary Esther, static PDF map
-- only, per 2026-07-24 shard8 session). I remains FAIL at 91.5% (54/59), unchanged by this
-- migration; residual for a future session, contingent on a new Okaloosa zoning source
-- appearing or the 2 dead-stub rows being resolved/archived by a future decision.
--
-- NOT included: jefferson B/F (verified=0 closed_sold=0). Only 1 of jefferson's 3 rows
-- (25-CA-164, foreclosure, sale date 2026-06-25, auction_status='sold') has actually closed
-- in the real world, but sold_amount is NULL for it and no independent outcome exists in
-- foreclosure_outcomes. jeffersonclerk.com's Foreclosures page has no case-level results
-- table (its "Upcoming Foreclosure Sales" section renders empty, confirmed via a real
-- headless-Chromium render, not just a static-HTML miss). The only per-case lookup channel,
-- Jefferson's Civitek OCRS portal (civitekflorida.com/ocrs/county/33), is gated by a live
-- Cloudflare Turnstile challenge on its case-search form -- confirmed directly this session
-- via a real headed Chromium session under Xvfb (challenges.cloudflare.com/cdn-cgi/
-- challenge-platform/.../turnstile/... iframe present), the same class of hard anti-bot
-- gate already root-caused for hamilton's myfloridacounty.com block on 2026-07-25 (see
-- 20260725_shard5_hamilton_bf_turnstile_and_taxcollector_dead_end_reverify.sql). Not
-- solvable by curl/WebFetch/headless-Chromium; would require a real browser + human or a
-- paid CAPTCHA-solving service, out of scope. No writes made for jefferson this session.
