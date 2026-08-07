-- Gold Standard shard-5 (dispatch 5d40a513-fb55-4c9c-ad49-be84afb8388f), county=osceola, letter=I.
--
-- BEFORE: pencil_dod_evaluate_county('osceola').I = {"pass": false, "detail":
-- "card_complete=127 of 137", "metric": 92.7}.
--
-- ROOT CAUSE (matches the documented osceola-specific trap from
-- .claude/workflows/gold-standard-shard4-bradford-osceola-nassau-41bd7ce3.js and
-- gold-standard-shard9-highlands-osceola-255f0be0-v2.js): 9 tax_deed rows had
-- multi_county_auctions.parcel_id stored as a TRUNCATED ~12-digit STRAP PREFIX
-- (sec-twn-rng-subdivision prefix only), each shared by 100s of real parcels
-- (VERIFIED: prefix "012630000101" alone matches 804 distinct STRAPs on
-- gis.osceola.org's Parcels FeatureServer), so no parcel_zones/GIS lookup by
-- that value could ever resolve. A 10th row, foreclosure case "2025 CA 001721
-- MF", has a wholly synthetic placeholder parcel_id ("OSC-2CEAE2B1037A") with
-- no real address on file.
--
-- METHOD -- NEW LEVER THIS SESSION (case-number-keyed tax deed lookup):
-- officialrecords.osceolaclerk.org/browserviewtd/ is Osceola Clerk's public Tax
-- Deed record browser (Angular SPA, NOT behind the Cloudflare Turnstile that
-- blocks www.osceolaclerk.com / osceola.realtaxdeed.com). Its search API
-- (POST .../browserviewtd/api/search) accepts RSA-PKCS1v1.5-encrypted search
-- criteria (JSEncrypt, public key embedded in Scripts/app/services.js) with
-- TaxNumType="taxnumber" (Tax Certificate Number search) + TaxValue=<our
-- case_number>. VERIFIED live this session: this returns the exact tax deed
-- application record for each of our 9 case numbers, including the FULL
-- 18-character STRAP (strap_num field), confirming each stored parcel_id was
-- indeed only the first 12 digits. Sale outcome shown as deed_status="REDEEM"
-- for all 9 (the certificate was redeemed prior to sale) -- real, non-fabricated
-- status, not a completed sale; sold_amount/outcome fields are NOT touched by
-- this migration, only the I-gating card fields.
--
-- Once the full STRAP was known per case, gis.osceola.org's Parcels
-- FeatureServer (.../hosting/rest/services/Parcels/FeatureServer/3/query,
-- confirmed live) resolved real property_address (StreetNumb/StreetName/
-- StreetSfx/LocCity/LocZip), AssessedVa (assessed_value), CurrJust (just/market
-- value), and a real polygon geometry (centroid used for latitude/longitude,
-- outSR=4326). Real zoning was then resolved via TWO authoritative sources
-- depending on jurisdiction:
--   - gis.osceola.org's own "Zoning" FeatureServer (.../Zoning/FeatureServer/13,
--     PRIM_ZON field), queried by the same parcel centroid point -- returns
--     either a real unincorporated-Osceola-County zone code, or "INCORP" +
--     the muni name (SEC_ZON) if the parcel is inside a city.
--   - For the 3 parcels flagged INCORP: City of Kissimmee's own ArcGIS
--     (cw.kissimmee.gov/arcgis/rest/services/Zoning_Districts/MapServer/10,
--     ZONING_COD field) for the 1 Kissimmee parcel, and City of St. Cloud's
--     ArcGIS Online hosted feature service (services1.arcgis.com/
--     9AYCAcYVeEGk3ZMt/.../City_of_St_Cloud_Zoning/FeatureServer/0, Zoning
--     field, queried by Strap) for the 2 St. Cloud parcels -- both are each
--     city's own authoritative zoning layer, not a mailing-address inference.
--
-- Resolved (case_number -> full STRAP -> jurisdiction -> real zone_code):
--   1302024    -> 012630000101060010 -> St. Cloud (jurisdiction_id=894)      -> R-3
--   27092022   -> 152529324000010150 -> Osceola County (jurisdiction_id=1186) -> RS-3
--   35922022   -> 192733273000010250 -> Osceola County (jurisdiction_id=1186) -> PD
--   40652024   -> 212632351900010080 -> Osceola County (jurisdiction_id=1186) -> PD
--   41922024   -> 223033000000400000 -> Osceola County (jurisdiction_id=1186) -> AC
--   43912024   -> 242629367000270175 -> Osceola County (jurisdiction_id=1186) -> E-1
--   48132023   -> 282529138700011480 -> Kissimmee (jurisdiction_id=957)       -> MUPUD
--   58662022   -> 012730495000010694 -> Osceola County (jurisdiction_id=1186) -> R-1
--   7772024    -> 042630495000011290 -> St. Cloud (jurisdiction_id=894)       -> R-4
--
-- R-3, RS-3, PD, AC, E-1, MUPUD, R-1(1186) all already existed as
-- zoning_districts rows with real zone_standards on file (no new blank rows
-- needed for 8 of the 9). ONLY R-4 (St. Cloud) did not previously exist in
-- our substrate.
--
-- G-REGRESSION SAFETY CHECK (per campaign precedent: a blank new
-- zoning_districts row silently inflates G's applicable-denominator without a
-- numerator). VERIFIED live via pg_get_viewdef('v_zoning_district_applicability')
-- BEFORE creating the R-4 row: far_applicable and pk1000_applicable both
-- default to FALSE for any district whose category is not
-- commercial/industrial/mixed-use (residential districts are excluded from
-- both denominators unless an explicit far_regulated/pk1000_regulated=true
-- override exists). The new R-4 district was created with category=
-- 'residential' specifically so it would NOT enter G's far/pk1000 applicable
-- sets. It DOES enter G's density-applicable set (density defaults TRUE for
-- non-commercial/industrial categories) with max_density_du_acre left NULL
-- (no real citable value found this session -- see residual note below), which
-- is a real, disclosed, bounded regression: G's density sub-metric moved
-- 100.0% -> 98.2% (51/51 -> 51/52 applicable-with-value parcels) -- confirmed
-- via a fresh pencil_dod_evaluate_county('osceola') call after this migration,
-- G remains PASS (98.2% >= 95% threshold, no pass->fail flip). Flagged
-- explicitly here for the osceola_g work item / a future session: St. Cloud
-- R-4 (zoning_districts.id=13639) needs a real max_density_du_acre value
-- researched (St. Cloud LDC Sec. 3.5.3, "R-3 and R-4 Multiple Family Dwelling
-- Districts" -- the same division that already sourced R-3's 10.00 du/acre
-- figure, id=13181/zone_standards id=5516) -- NOT researched to completion
-- this session (zoneomics.com and library.municode.com both serve this
-- section as an Angular SPA shell with no working direct-fetch content route
-- found in the time budgeted; Firecrawl API key present but account is out
-- of credits this session -- confirmed via a live /v1/scrape call returning
-- "Insufficient credits").
--
-- RESIDUAL (NOT fixed, reported honestly, not fabricated): foreclosure case
-- "2025 CA 001721 MF" (multi_county_auctions.parcel_id stays the synthetic
-- placeholder "OSC-2CEAE2B1037A"). VERIFIED this session: this case is not in
-- the current Osceola Clerk "Scheduled Mortgage Foreclosure Sales" PDF window
-- (courts.osceolaclerk.com/reports/CivilMortgageForeclosuresWeb.pdf, 8/7/2026
-- - 2/7/2027), and the only case-search tool found for civil/foreclosure
-- dockets (courts.osceolaclerk.com/BenchmarkWeb/Home.aspx/Search, "Benchmark"
-- by Journal Technologies) has a CAPTCHA gate on its CourtCase.aspx/CaseSearch
-- endpoint (CourtCase.aspx/CaptchaQuestion, confirmed live in
-- Scripts/home/search.js) -- per campaign rules, CAPTCHA-gated sources are not
-- attempted. No real address/STRAP found; multi_county_auctions row for this
-- case is left untouched.
--
-- AFTER (fresh pencil_dod_evaluate_county('osceola') call post-migration):
-- I = {"pass": true, "detail": "card_complete=136 of 137", "metric": 99.3}.
-- All other letters A-H, J unaffected/still PASS; full A-J JSON pasted in the
-- session report. osceola is now 10/10.

-- 1. Create the one genuinely-missing zoning district (St. Cloud R-4).
--    category='residential' is load-bearing for the G-safety analysis above --
--    do not change without re-checking v_zoning_district_applicability impact.
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category)
VALUES (894, 'R-4', 'St Cloud R-4 Multiple Family Dwelling District', 'residential')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- 2. Link each resolved full STRAP to its real jurisdiction + zone_code.
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT v.parcel_id, v.jurisdiction_id, v.zone_code,
       'osceola_shard5_5d40a513_officialrecords_taxnumber_search_verified'
FROM (VALUES
  ('012630000101060010', 894,  'R-3'),
  ('152529324000010150', 1186, 'RS-3'),
  ('192733273000010250', 1186, 'PD'),
  ('212632351900010080', 1186, 'PD'),
  ('223033000000400000', 1186, 'AC'),
  ('242629367000270175', 1186, 'E-1'),
  ('282529138700011480', 957,  'MUPUD'),
  ('012730495000010694', 1186, 'R-1'),
  ('042630495000011290', 894,  'R-4')
) AS v(parcel_id, jurisdiction_id, zone_code)
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v.jurisdiction_id
);

-- 3. Overwrite the truncated-prefix parcel_id with the real full STRAP, and
--    backfill property_address/latitude/longitude/assessed_value/market_value
--    from the gis.osceola.org Parcels FeatureServer record for that STRAP.
--    property_address overwrite is intentional (not COALESCE) because the
--    prior value was a non-address placeholder ("Osceola County, FL 34741"),
--    confirmed by the WHERE clause matching that exact literal string.
UPDATE public.multi_county_auctions m
SET parcel_id = v.strap,
    latitude = COALESCE(m.latitude, v.lat),
    longitude = COALESCE(m.longitude, v.lon),
    assessed_value = COALESCE(m.assessed_value, v.assessed),
    market_value = COALESCE(m.market_value, v.just_value)
FROM (VALUES
  ('1302024',   '012630000101060010', 28.250461989379357::double precision, -81.28043061667957::double precision, 158198::numeric, 213100::numeric),
  ('27092022',  '152529324000010150', 28.31374283572334,  -81.39820718189588, 9655,   45000),
  ('35922022',  '192733273000010250', 28.128849942470925, -81.05407228848529, 42500,  42500),
  ('40652024',  '212632351900010080', 28.212524161660788, -81.12223324217035, 609700, 609700),
  ('41922024',  '223033000000400000', 27.862409414725263, -81.01288594629185, 441600, 441600),
  ('43912024',  '242629367000270175', 28.202580649977072, -81.37578396120081, 398300, 398300),
  ('48132023',  '282529138700011480', 28.27454534484184,  -81.41194906000109, 281500, 281500),
  ('58662022',  '012730495000010694', 28.165772167851298, -81.2678482692322,  847,    2000),
  ('7772024',   '042630495000011290', 28.256418162782317, -81.31021181282486, 112300, 112300)
) AS v(case_number, strap, lat, lon, assessed, just_value)
WHERE m.county = 'osceola' AND m.case_number = v.case_number;

UPDATE public.multi_county_auctions m
SET property_address = v.address
FROM (VALUES
  ('1302024',  '802 OHIO AVE, SAINT CLOUD, FL 34769'),
  ('27092022', '0 ROSS ST, KISSIMMEE, FL 34744'),
  ('35922022', '0 CONCORD RD, SAINT CLOUD, FL 34773'),
  ('40652024', '2970 TALLY HO TRL, SAINT CLOUD, FL 34771'),
  ('41922024', '1295 LAKE MARIAN RD, KENANSVILLE, FL 34739'),
  ('43912024', '3194 TOHOPEKALIGA DR, SAINT CLOUD, FL 34772'),
  ('48132023', '918 HACIENDA CIR, KISSIMMEE, FL 34741'),
  ('58662022', '0 HENRY J AVE, SAINT CLOUD, FL 34772'),
  ('7772024',  '0 BROWN CHAPEL RD, SAINT CLOUD, FL 34769')
) AS v(case_number, address)
WHERE m.county = 'osceola' AND m.case_number = v.case_number
  AND m.property_address = 'Osceola County, FL 34741';
