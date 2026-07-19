-- GTM-22j shard-6 (hillsborough/flagler/bay, dispatch 1f302343): flagler letter I
-- 6 of 9 card_complete gap rows (131/140=93.6% -> projected 137/140=97.9%) resolved
-- via live Palm Coast ULDC zoning GIS (gis.palmcoast.gov, External/Op_ULDCZoning/
-- MapServer/3) point-in-polygon queries, verified 2026-07-19 by two independent
-- agents (finder + adversarial refuter, both re-ran the live ArcGIS queries and got
-- identical zone codes). jurisdiction_id=966=Palm Coast, zoning_districts 7614/7615
-- (SFR-2/SFR-3) already exist. Remaining 3 gap rows (1 genuine county GIS coverage
-- gap at 25 Pine Harbor Dr, 2 corrupted-parcel_id scraper-bug rows) are NOT fixed
-- here -- no verified real value exists for them; logged as residual.
--
-- Idempotent: NOT EXISTS guard on parcel_zones(parcel_id,jurisdiction_id), and the
-- lat/lon UPDATE only touches rows currently NULL on both columns.

INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source, effective_date)
SELECT v.parcel_id, NULL, 966, v.zone_code, 'Single-Family Residential District', 'palmcoast_gis_uldc_2026-07-19', NULL
FROM (VALUES
  ('07-11-31-7035-01660-0200', 'SFR-3'),
  ('07-11-31-7058-00090-0150', 'SFR-2'),
  ('07-11-31-7011-00120-0070', 'SFR-3'),
  ('07-11-31-7016-00100-0640', 'SFR-2'),
  ('07-11-31-7032-00510-0090', 'SFR-3'),
  ('07-11-31-7037-00080-0110', 'SFR-2')
) AS v(parcel_id, zone_code)
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = 966
);

UPDATE public.multi_county_auctions a
SET latitude = v.lat, longitude = v.lon
FROM (VALUES
  ('07-11-31-7035-01660-0200'::text, -81.23380828297284::double precision, 29.574538342991::double precision),
  ('07-11-31-7011-00120-0070', -81.23728732577781, 29.562962511701333),
  ('07-11-31-7016-00100-0640', -81.21898225219283, 29.59793846960949),
  ('07-11-31-7032-00510-0090', -81.25253743238169, 29.514406913478517),
  ('07-11-31-7037-00080-0110', -81.25088886730828, 29.602919487787652)
) AS v(parcel_id, lon, lat)
WHERE lower(a.county) = 'flagler'
  AND a.parcel_id = v.parcel_id
  AND a.latitude IS NULL
  AND a.longitude IS NULL;
