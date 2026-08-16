-- Gold Standard shard-1 (dispatch 3eefe79f-65ee-4e6f-b194-cc8d8db9fb0e, loop run 11871)
-- brevard, letter I (property card completeness), 2026-08-16
--
-- FIX PHASE for the diagnose-pass lever: Palm Bay / Titusville municipal ArcGIS
-- address-point layers, exact parcel-number match (safer/simpler technique than the
-- diagnose's proposed bounding-box + custom-projection proximity search -- this
-- session confirmed both endpoints accept inSR=4326/outSR=4326 directly, so no manual
-- SPF/pyproj projection was needed at all; pyproj also installs cleanly in this
-- sandbox, contradicting the prior session's "not installed" note, so that part of
-- the diagnose plan is retired as unnecessary rather than executed as written).
--
-- Live universe check (this session): of the 985 rows the diagnose plan estimated as
-- address-missing, only 164 are non-propertyonion (data_source != 'propertyonion');
-- the remaining ~836 are PropertyOnion litmus rows and are correctly out of scope
-- per the hard guardrail (PropertyOnion is comparison-only, never a data source).
-- Of the 164, 146 have usable latitude/longitude.
--
-- Palm Bay: https://gis.palmbayflorida.org/arcgis/rest/services/CommonServices/
--   AddressesOnly/FeatureServer/0 ("HTE Addresses", municipal permitting/911 feed).
--   Field `Renum` = Brevard tax-account number, exact match to our parcel_id.
--   Queried `Renum IN (<all 146 candidate parcel_ids>)` -- 2 exact hits.
-- Titusville: https://gis.titusville.com/arcgis/rest/services/AddressPoints/
--   MapServer/0. Field `TaxAcct` = same tax-account number.
--   Queried `TaxAcct IN (<all numeric candidate parcel_ids>)` -- 0 hits (honest
--   negative; not a single candidate parcel resolved against Titusville's layer).
--
-- The 2 Palm Bay hits (parcel_id=2811986 -> "1833 FIRETHORN RD NW", ZipCode 32907;
-- parcel_id=2852162 -> "1983 DANR DR NE", ZipCode 32905) were verified: neither
-- collides with an existing non-null property_address, neither row is
-- data_source='propertyonion', both already carry real assessed_value/market_value
-- from BCPAO, so writing the address alone completes the letter-I card check.
-- Each parcel_id has 2 duplicate rows in multi_county_auctions (same case_number,
-- same coords, one data_source=NULL / one data_source='realforeclose') -- both
-- updated, 4 rows total written.
--
-- Already applied live via PostgREST during this session; statements below are an
-- idempotent record (guarded by parcel_id + property_address IS NULL, so re-running
-- is a no-op if already applied).

UPDATE multi_county_auctions
SET property_address = '1833 FIRETHORN RD NW, PALM BAY, FL 32907', updated_at = NOW()
WHERE county = 'brevard' AND parcel_id = '2811986' AND property_address IS NULL;

UPDATE multi_county_auctions
SET property_address = '1983 DANR DR NE, PALM BAY, FL 32905', updated_at = NOW()
WHERE county = 'brevard' AND parcel_id = '2852162' AND property_address IS NULL;

-- Live evaluator (public.pencil_dod_evaluate_county('brevard'), letter I):
--   before this run: metric=85.5, card_complete=6198 of 7252 -- FAIL
--   after this run:  metric=85.5, card_complete=6202 of 7252 -- still FAIL
--     (needs >=95%, i.e. ~6890 of 7252; genuine but small +4-row gain, exactly the
--     "low double digits to low hundreds, not the full gap" yield the diagnose
--     honestly predicted for this lever)
-- No regression: A/B/C/D/E/F/G/H/J all reconfirmed PASS, unchanged, same session.

-- Residual, NOT fixed this session (reconfirmed structural, not fabricated):
--   ~1050 rows still failing letter I. Of the 146 address-missing rows with
--   coordinates, 144 returned zero hits from BOTH municipal address-point layers by
--   exact parcel-number match -- either genuinely outside Palm Bay/Titusville city
--   limits (unincorporated county, where gis.brevardfl.gov's own STREET_NAME=UNKNOWN
--   dead end already applies -- confirmed by 3+ prior sessions) or unaddressed vacant
--   parcels with no 911/permitting address point at all. This lever is now
--   EXHAUSTED for Brevard I (unlike the diagnose's untested "403 candidates" estimate,
--   which was based on a rough lat/lng bounding-box guess and did not reflect the
--   true 146-row non-propertyonion universe with coordinates).
--   A separate, distinct bucket -- 15 brevard_clerk rows with parcel_id, address,
--   coords, AND value all NULL (clerk-scraped stubs, case-number only) -- is not
--   addressable via any GIS address-point lookup (nothing to key a spatial or
--   parcel-number query on) and was left untouched, not fabricated. Would need
--   clerk-document research (case filing lookup) in a future session, a genuinely
--   different technique from this session's GIS lever.
