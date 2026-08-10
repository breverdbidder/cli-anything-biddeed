-- GOLD STANDARD shard-5, martin, dispatch 32ef2b2a-3ee0-4ac9-8209-5ec91a35cf5c (2026-08-10)
--
-- Documents the fix applied live via PostgREST this session (see
-- scripts/shard5_32ef2b2a_martin_e_i_frondorf_fix.py for the actual idempotent
-- runner; psql/pooler access was unavailable from this session's sandbox, so
-- these statements were executed as equivalent REST PATCH/POST calls, not via
-- this file directly -- kept here for the repo's historical SQL record and for
-- reproducibility from an environment with working DB access).
--
-- E/I gap row 26000299CAAXMX (Frondorf) resolved via pamartinfl.gov real-property
-- JSON API (single unambiguous match, AIN 29570) + live geoweb.martin.fl.us ArcGIS
-- zoning point-in-polygon (single unanimous R-2B feature). Case-party match
-- (plaintiff "Frondorf as PR for Estate of Dorothy Miller, William" / defendant
-- "Frondorf, Natalie") independently confirmed live via court.martinclerk.com's
-- anonymous QuickSearch -> DetailsSummary AJAX endpoint. Full evidence chain in
-- GOLD_STANDARD_SHARD5_MARTIN_DISPATCH_32EF2B2A_SESSION_REPORT.md.
--
-- Result: E 85.4%->87.8% (35/41->36/41), I 85.4%->87.8% (35/41->36/41), both
-- still FAIL (95% threshold). A/B/C/D/F/G/H/J unchanged. 5 gap rows remain
-- (3 NON_REAL_PROPERTY dead end reconfirmed this session via 6 new angles;
-- 2 pre-judgment stubs left unresolved -- O'Neill ambiguous, De La Bahia HOA
-- co-defendant not the unit owner -- per BLANK > WRONG).

UPDATE public.multi_county_auctions
SET
  parcel_id = '18-38-41-009-002-00070-8',
  property_address = '3078 SW VIRGINIA AVE, PALM CITY, FL- 34990',
  city = 'PALM CITY',
  zip = '34990',
  legal_description = 'PALM HEIGHTS LOT 7 & N1/2 OF LOT 8 BLK 2',
  assessed_value = 103842,
  market_value = 254510,
  latitude = 27.1674734166,
  longitude = -80.2829634839,
  property_type = 'Single Family',
  bcpao_enriched = true,
  bcpao_url = 'https://www.pamartinfl.gov/app/search/real-property?format=json&search=FRONDORF&searchField=all&exact=false',
  assessed_value_source = 'pamartinfl_gov_real_property_json_api:AIN29570',
  plaintiff = 'FRONDORF AS PERSONAL REPRESENTATIVE FOR THE ESTATE OF DOROTHY MILLER, WILLIAM',
  owner_name = 'FRONDORF, NATALIE I'
WHERE id = 'aacd4b1b-775d-4f2a-92c6-edf1c2a268fd'
  AND county = 'martin'
  AND case_number = '26000299CAAXMX'
  AND parcel_id IS NULL;

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT
  '18-38-41-009-002-00070-8',
  1331,
  'R-2B',
  'Residential Estate Density (Martin County LDR)',
  'geoweb.martin.fl.us ArcGIS Administrative_Areas/MapServer/8 (Zoning) point-in-polygon lat=27.1674734166 lon=-80.2829634839 VERIFIED live 2026-08-10, single unanimous feature OBJECTID=85881'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones WHERE parcel_id = '18-38-41-009-002-00070-8'
);
