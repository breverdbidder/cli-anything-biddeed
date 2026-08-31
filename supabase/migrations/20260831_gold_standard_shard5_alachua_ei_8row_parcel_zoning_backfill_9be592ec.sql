-- Gold Standard shard-5 alachua, dispatch 9be592ec-e1bd-47b8-8a88-ca1e8217d800, 2026-08-31.
--
-- Idempotent reflection of live PostgREST writes made this session (direct
-- psql/pooler auth is a known-dead constraint per repo decision_log ids
-- 169/205/287 -- all writes executed via REST, this file documents them for
-- replay/audit).
--
-- BEFORE (VERIFIED live, pencil_dod_evaluate_county('alachua'), 2026-08-31 08:00Z):
--   E FAIL metric=91.2 (parcel_linked=83 of 91)
--   I FAIL metric=91.2 (card_complete=83 of 91)
--   (A/B/C/D/F/G/H/J already PASS; G=96.7)
--
-- This is the 5th+ consecutive session on this exact 8-row gap. Prior sessions
-- (most recently dispatch cf625237, 2026-08-30) exhaustively confirmed this
-- was structurally blocked via every conventional avenue: RealForeclose AJAX
-- (parcel field literal placeholder "Property Appraiser"/"MULTIPLE PARCEL"),
-- qpublic.schneidercorp.com (HTTP 403 Cloudflare), isol.alachuaclerk.org (JS
-- redirect wall), myfloridacounty.com/Trellis (login/403-gated), Firecrawl
-- (credits repeatedly exhausted).
--
-- BREAKTHROUGH THIS SESSION: two MCP tools connected for the first time this
-- session -- mcp__brightdata__scrape_as_markdown/search_engine (claims to
-- unlock bot-protected pages) and mcp__tracerfy (skip-trace/parcel lookup,
-- ultimately not usable here -- 0 credits, and these bare-stub rows have no
-- address/parcel to seed it with anyway). BrightData was explicitly denied
-- qpublic.schneidercorp.com by BrightData's own KYC/robots.txt policy gate
-- (not a technical failure -- respected, not routed around). BUT
-- search_engine + scrape_as_markdown surfaced case-number citations on
-- PropertyOnion.com free-preview pages, noticeregistry.com (official Chapter
-- 45 Notice-of-Sale full text), and alachuacountytoday.com legal notices --
-- none of which were reachable/known avenues in any prior alachua session.
--
-- ULTRALOOP native Workflow fan-out (per user's ultracode opt-in this turn):
-- 8 cases -> research agent (find address/owner via BrightData, resolve
-- parcel via the Alachua Property Appraiser's public ArcGIS PublicParcel
-- FeatureServer) -> independent adversarial-verify agent (no shared context
-- with the research agent) per case with a claim. 4 of 8 SURVIVED
-- independent verification with multi-source corroboration (official court
-- notice text + commercial aggregator + county ArcGIS parcel record all
-- agreeing on the same case_number/address/parcel/owner, zero ambiguity). The
-- other 4 were honestly reported as genuine research dead ends -- including
-- one (01 2025 CA 003287) reconfirmed as a genuine multi-parcel foreclosure
-- (Goodwin Lumber Co. site, 4 real STRAP sub-parcels, correctly left
-- unwritable rather than guessing which one) and two (01 2025 CA 003919, 01
-- 2025 CA 002760) that remain fully UNKNOWN. No fabrication attempted on any
-- of the 4 non-survivors.
--
-- THE 4 CONFIRMED CASES (case_number -> parcel_id, address, DOR assessed
-- value from the FL Dept. of Revenue Statewide Cadastral public ArcGIS
-- FeatureServer -- https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/
-- services/Florida_Statewide_Cadastral/FeatureServer/0, CO_NO=11/Alachua, JV
-- field, cross-checked against PHY_ADDR1 matching exactly):
--
--   01 2025 CA 002643  07651-002-000  1123 NW 192ND AVE, GAINESVILLE 32609   JV=218086
--     (Rocket Mortgage LLC v. Karla Mariott/Favored Home Buyers LLC et al.,
--      sale canceled 07/23/2026, final judgment $200,168 -- PropertyOnion +
--      ArcGIS PublicParcel Prop_ID 71376 agree exactly, single unambiguous
--      FULLADDR match countywide.)
--   01 2026 CA 000658  15701-055-000  205 SE 16TH AVE, GAINESVILLE 32601     JV=21851200
--     (Sweetwater on 16th Apartments, ~18.77ac multifamily; Fannie Mae v.
--      Sweetwater 16 L.P.; official Notice of Sale UCC Exhibit 1 debtor
--      mailing address, 13 First Ave, Waterbury CT, matches the ArcGIS
--      parcel's Owner_Mail_Addr2/City/State/Zip EXACTLY -- two independent
--      fields, not just a name match.)
--   01 2026 CA 001045  17814-001-000  11653 SE 3RD PL, GAINESVILLE 32641     JV=114648
--     (Windsor subdivision mobile home, ~7.15ac; owner Christie Milton,
--      matches across PropertyOnion + ArcGIS Owner_Mail_Name exactly.)
--   01 2025 CA 003080  09169-000-000  1808 NW 10TH AVE, GAINESVILLE 32605    JV=324737
--     (U.S. Bank Trust Natl Assoc as Trustee of Chalet Series IV Trust v.
--      Stephanie A. Ivey / Richard C. Griffin; official Chapter 45 Notice of
--      Sale full text names both defendants at this exact address with a
--      metes-and-bounds legal description; matches ArcGIS Owner_Mail_Name
--      "IVEY STEPHANIE A" exactly.)
--
-- Lat/lon are ArcGIS PublicParcel polygon centroids fetched with
-- outSR=4326&returnCentroid=true (real per-parcel WGS84 coordinates, not the
-- county-centroid placeholder 29.6516/-82.3248 seen elsewhere in this table).
--
-- AFTER E (VERIFIED live): parcel_linked=87 of 91 = 95.6% PASS (>=95%).
--
-- I (card_complete) ALSO required geo+value+a zoned-parcel link
-- (v_zoning_gold_standard_card, zone_code IS NOT NULL) for these same 4 rows.
-- Two are unincorporated county (jurisdiction_id=1404) and matched the
-- county's own authoritative zoning layer
-- (services2.arcgis.com/Zzhtlau4ccHkQgTu/.../Alachua_County_Zoning/
-- FeatureServer/0, point-in-polygon at the parcel centroid) to zonecode
-- "0100A" / zonedefin "Agricultural (A)" -- this EXACT code+jurisdiction
-- already existed in zoning_districts (id 13147, far/density/pk1000
-- regulated all already false, zero G-regression risk, same
-- already-established agricultural-exemption precedent used fleet-wide) --
-- only a parcel_zones LINK row was needed for these two, no new district.
--
-- The other two sit inside Gainesville city limits, which the countywide
-- layer excludes. Found the City of Gainesville's own authoritative zoning
-- layer (services2.arcgis.com/Zzhtlau4ccHkQgTu/.../Land_Planning_Layers/
-- FeatureServer/17, "ExistingZoning") and matched by EXACT PARCELID
-- attribute query (not just point-in-polygon): 15701-055-000 -> RMF-7
-- (Multiple-Family Residential), 09169-000-000 -> RSF-1 (Residential
-- Single-Family). Neither code existed yet for Gainesville (jurisdiction_id
-- 915) in zoning_districts, so two new district rows were created, sourced
-- from real City of Gainesville government legislative records (not
-- guessed):
--   RSF-1: max_density_du_acre=3.5, City of Gainesville Legistar File
--     #190089 (2019), which states verbatim "Single-Family Residential
--     (RSF-1): Maximum 3.5 Dwelling Units per Acre".
--   RMF-7: Legistar File #100682 (2010) states the category range as
--     "8-21 units/acre multiple-family residential district" -- a RANGE,
--     not a single figure. Per the no-guessing rule, max_density_du_acre was
--     left NULL rather than picking an arbitrary point in that range; only
--     the district's existence/code/category is recorded. (Multiple
--     independent commercial real-estate/MLS sources cite "14 du/acre" as a
--     commonly-quoted by-right figure for RMF-7, but that is not a primary
--     ordinance citation, so it was NOT used for the numeric field --
--     flagged here for a future session to source more precisely if the
--     full LDC density table can be parsed cleanly.)
-- Both new districts: far_regulated=false, pk1000_regulated=false,
-- density_regulated=true (standard Florida practice -- FAR/commercial-GFA
-- parking ratios do not apply to pure single/multi-family residential
-- zoning; consistent with the existing fleet-wide override precedent for
-- non-GFA residential districts).
--
-- AFTER I (VERIFIED live): card_complete=87 of 91 = 95.6% PASS (>=95%).
--
-- REGRESSION CHECK (VERIFIED live via fresh pencil_dod_evaluate_county
-- immediately after all writes, same session): A PASS (fc=72 td=19) | B PASS
-- 100.0 | C PASS 100.0 | D PASS 100.0 | E PASS 95.6 | F PASS 100.0 | G PASS
-- 95.2 (down slightly from 96.7 -- expected and harmless: adding 2 new
-- agricultural parcels grows the zoning-applicable universe without adding
-- to the FAR/pk1000/density-applicable numerator, since agricultural is
-- correctly non-applicable to all three -- same shape as every prior
-- agricultural-exemption addition fleet-wide) | H PASS 0.0 | I PASS 95.6 | J
-- PASS 100.0.
--
-- ALACHUA IS NOW 10/10 LIVE. Independently re-verified by a second ULTRALOOP
-- adversarial-verify pass (workflow run wf_a49d4f58-968, 3 claims: value
-- backfill, zoning link, final scoreboard) with no shared context with the
-- agents that made these writes, per the "verifier of a fix is never the
-- agent that wrote it" rule. That pass caught one real discrepancy: the two
-- new zoning_districts rows (14372/14373) were briefly readable as
-- far_regulated=NULL instead of the inserted false (a transient
-- read-after-write/replica-lag artifact, not a logic bug -- an immediate
-- PATCH held stable on re-select and again 5s later, and
-- pencil_dod_evaluate_county reproduced the identical 10/10 scoreboard
-- before and after). The INSERT below reflects the corrected, now-stable
-- far_regulated=false. See gold_standard_ultraloop_audit rows logged this
-- session (ids 19904/19905) for the full survival-vote record; per the
-- EVALUATOR V6 SQL CERTIFY GATE, full fleet certification additionally
-- requires survived=true audit rows for ALL 10 letters within 7 days, not
-- just E/I -- this session only logged E/I (the two letters actually
-- touched); other letters' most recent audit rows should be checked for
-- freshness before certify fires.
--
-- No PropertyOnion-derived data_source was ever written (data_source column
-- was left untouched on all 4 rows -- pre-existing values of null/
-- 'calendar_sweep_mca_v3' preserved, avoiding any risk of the
-- propertyonion-exclusion clause changing the card_rows denominator).
-- PropertyOnion pages were used only as a research LEAD, cross-verified
-- against an official court notice and/or the county's own ArcGIS parcel
-- record before being trusted -- never as the data_source of record.

-- === multi_county_auctions: parcel_id/address/geo/value backfill ===
UPDATE public.multi_county_auctions
SET parcel_id = '07651-002-000',
    property_address = '1123 NW 192ND AVE, GAINESVILLE, FL 32609',
    latitude = 29.827809, longitude = -82.336340,
    assessed_value = 218086
WHERE case_number = '01 2025 CA 002643' AND lower(county) = 'alachua';

UPDATE public.multi_county_auctions
SET parcel_id = '09169-000-000',
    property_address = '1808 NW 10TH AVE, GAINESVILLE, FL 32605',
    latitude = 29.661813, longitude = -82.345978,
    assessed_value = 324737
WHERE case_number = '01 2025 CA 003080' AND lower(county) = 'alachua';

UPDATE public.multi_county_auctions
SET parcel_id = '15701-055-000',
    property_address = '205 SE 16TH AVE, GAINESVILLE, FL 32601',
    latitude = 29.629374, longitude = -82.325088,
    assessed_value = 21851200
WHERE case_number = '01 2026 CA 000658' AND lower(county) = 'alachua';

UPDATE public.multi_county_auctions
SET parcel_id = '17814-001-000',
    property_address = '11653 SE 3RD PL, GAINESVILLE, FL 32641',
    latitude = 29.647680, longitude = -82.195917,
    assessed_value = 114648
WHERE case_number = '01 2026 CA 001045' AND lower(county) = 'alachua';

-- === zoning_districts: 2 new Gainesville districts (idempotent) ===
INSERT INTO public.zoning_districts
  (jurisdiction_id, code, name, category, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 915, 'RSF-1', 'Residential Single-Family (RSF-1)', 'residential',
       'City of Gainesville Legistar File #190089 (2019): Single-Family Residential (RSF-1) Maximum 3.5 Dwelling Units per Acre',
       false, true, false
WHERE NOT EXISTS (SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 915 AND code = 'RSF-1');

INSERT INTO public.zoning_districts
  (jurisdiction_id, code, name, category, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 915, 'RMF-7', 'Multiple-Family Residential (RMF-7)', 'residential',
       'City of Gainesville Zoning Map Atlas category definition, Legistar File #100682 (2010): RMF-7 = 8-21 units/acre multiple-family residential district (documented range, not reduced to a single figure)',
       false, true, false
WHERE NOT EXISTS (SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 915 AND code = 'RMF-7');

-- === zone_standards: density figures (idempotent via district lookup) ===
INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 3.5,
       'https://gainesville.legistar.com/LegislationDetail.aspx?ID=3988725&GUID=DD7F7923-FA90-46C5-81EC-B43615D603C1',
       'File #190089: Single-Family Residential (RSF-1) Maximum 3.5 Dwelling Units per Acre', 0.85
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 915 AND zd.code = 'RSF-1'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, NULL,
       'https://gainesville.legistar.com/LegislationDetail.aspx?ID=1211739&GUID=78722276-BAC1-4040-98BC-408F68705A32',
       'File #100682: RMF-7 = 8-21 units/acre multiple-family residential district (range only, no single max figure sourced this session)', 0.5
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 915 AND zd.code = 'RMF-7'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);

-- === parcel_zones: link the 4 parcels (idempotent) ===
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT v.parcel_id, v.jurisdiction_id, v.zone_code, v.zone_name, v.source
FROM (VALUES
  ('07651-002-000', 1404, 'A', 'Agricultural (A)', 'alachua_county_zoning_arcgis_ZoningCountyWide_2026-08-31'),
  ('17814-001-000', 1404, 'A', 'Agricultural (A)', 'alachua_county_zoning_arcgis_ZoningCountyWide_2026-08-31'),
  ('15701-055-000', 915, 'RMF-7', 'Multiple-Family Residential (RMF-7)', 'gainesville_land_planning_layers_existingzoning_arcgis_2026-08-31'),
  ('09169-000-000', 915, 'RSF-1', 'Residential Single-Family (RSF-1)', 'gainesville_land_planning_layers_existingzoning_arcgis_2026-08-31')
) AS v(parcel_id, jurisdiction_id, zone_code, zone_name, source)
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones pz WHERE pz.parcel_id = v.parcel_id AND pz.zone_code = v.zone_code
);
