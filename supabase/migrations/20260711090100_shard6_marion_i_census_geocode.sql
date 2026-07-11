-- SHARD-6 (marion): I criterion — forward-geocode newly address-backfilled rows
-- via the free US Census Geocoder (geocoding.geo.census.gov/geocoder, no API key,
-- benchmark=Public_AR_Current). Companion to
-- 20260711090000_shard6_marion_cd_realtaxdeed_and_i_hygiene.sql -- those 126 rows
-- got real property_address from the verified realtaxdeed cross-match; of those,
-- 18 had genuine street addresses (not "NO SITUS" vacant-land placeholders) and
-- were missing lat/lon. 17 of 18 resolved to a real Census TIGER match (all
-- plausible Marion County, FL coordinates, ~29.0-29.3N / -82.2--81.7W); 1 address
-- ("15680 NE 150TH TER, FORT MCCOY, FL 32134") had no TIGER match and was left
-- NULL, not guessed.
-- dispatch_id: fb80bb9c-7d7d-469f-b3c0-493b5e4f9b3f
-- Session: architect-20260711T080000, loop run 3713
-- Applied live 2026-07-11 via PostgREST PATCH (service role); this migration is
-- the idempotent record (WHERE clauses only touch rows still missing lat/lon).

UPDATE public.multi_county_auctions AS mca
SET latitude = v.lat, longitude = v.lng, updated_at = now()
FROM (VALUES
  ('a3b9f191-a0bc-4bc3-b4d4-501682c75355'::uuid, 29.012834770592::double precision, -82.100726809756::double precision),
  ('5f7a07d7-d8de-467b-a1a9-6e2092a4755a', 29.029953871707, -82.067506516072),
  ('8aee792b-907e-46e7-968e-f33968a012f9', 29.16979955366, -81.865018875462),
  ('c2dc08a3-85e6-4d0c-abc2-f6fe8d4636af', 29.245680215416, -82.215392362153),
  ('49f9c6ee-c83c-466a-85f1-5005c67ba6d1', 29.234373314351, -82.111142436816),
  ('5af60bd0-ef21-40f8-8312-26578bcc5480', 29.189871014705, -82.157322641071),
  ('280cf3a1-4590-48ac-9a74-fc95bdab420e', 29.184846113273, -82.147333817416),
  ('0983c2b6-44b5-47fa-b89a-564803ecdcf1', 29.164491224456, -81.844592349888),
  ('f5108b46-a589-4326-a9fd-31aa285be053', 29.084888433841, -81.83275067816),
  ('931f1dfb-997e-4c9b-914d-9a35c43cf627', 29.018916264482, -82.042134037497),
  ('531a224e-00a5-443e-a5b2-dfbc55549831', 29.006006746501, -82.187319686678),
  ('6a225419-54a9-42a7-ac49-9fe65bc92009', 29.342340227758, -81.740592834794),
  ('590e9bfe-9997-4b13-acc5-8d4169e9ea08', 29.250241338809, -82.221901086171),
  ('796140d3-d3c1-46ab-a3ad-a2c4aa221f45', 29.240641242134, -82.212881257732),
  ('38c8cc78-48f4-4f0d-ae28-71786fbc32f6', 29.022340117818, -82.082918971453),
  ('0c301005-ae34-41da-a6a4-dc92c3e9b5cb', 29.088497869389, -82.088678919446),
  ('377e16ea-d62b-4491-bce5-cbfc3f8c40ee', 29.187496394235, -82.215550334983)
) AS v(id, lat, lng)
WHERE mca.id = v.id
  AND mca.latitude IS NULL;

-- 113 of 131 "ready" rows are "NO SITUS" vacant-land tax-deed parcels with no
-- geocodable street address -- flagged for a future Marion County Property
-- Appraiser parcel-centroid pull, NOT attempted this session (out of scope /
-- would require a new ArcGIS integration, not a quick geocode).

-- ── VERIFICATION QUERY ──────────────────────────────────────────────────────────
-- SELECT public.pencil_dod_evaluate_county('marion');
