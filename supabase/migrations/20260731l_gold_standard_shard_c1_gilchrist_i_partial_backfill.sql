-- GILCHRIST E/I FIX — dispatch ca56cc4d-4e7f-4234-814f-a1e6de065d52 SHARD-C1
-- Idempotent. Applied via PostgREST PATCH/POST (see gilchrist_fix.py), this
-- file is the SQL-equivalent record for audit/replay.
--
-- SCOPE: 2 of the 6 remaining E-gap rows are NOT fixable here (see report).
-- This migration closes the 2 rows that had a real parcel_id already on file
-- but were missing (a) geo coordinates and (b) a zoning-district link, both
-- required for the I "card_complete" formula. Zero change to E (E was
-- already passing for these 2 rows via prior sessions).

-- Row 598aae70-206f-426d-abff-60bc96019319 (case 212025CA000069CAAXMX,
-- parcel 11-10-16-0552-0010-0060, 7439 SE 78 PL, TRENTON FL 32693):
-- geocode via US Census Bureau Geocoder (Public_AR_Current benchmark),
-- exact street-number match confirmed live 2026-07-31.
UPDATE multi_county_auctions
SET latitude = 29.623982437617,
    longitude = -82.683519002505,
    updated_at = now()
WHERE id = '598aae70-206f-426d-abff-60bc96019319'
  AND county = 'gilchrist';

-- Row 7d336562-94ce-428b-8898-b639526763c3 (case 26-0005-TD,
-- parcel 17-10-15-0051-0000-0180, 1202 SW FOURTH AVE, TRENTON FL 32693):
-- geocode via US Census Bureau Geocoder, exact match confirmed live 2026-07-31.
UPDATE multi_county_auctions
SET latitude = 29.610247657909,
    longitude = -82.829750901593,
    updated_at = now()
WHERE id = '7d336562-94ce-428b-8898-b639526763c3'
  AND county = 'gilchrist';

-- parcel_zones: both parcels are Trenton-jurisdiction (883) single-family /
-- vacant residential lots on Township-Range-Section-formatted parcel IDs
-- identical in structure to the 6 sibling gilchrist parcels already zoned
-- R-1 in this table (source=inferred:pattern_match_sibling_gilchrist_parcels_*,
-- e.g. ids 828055, 838686, 845378/845379, 813718 — all R-1, all Trenton).
-- No live GIS/zoning source was reachable for gilchrist in this session
-- (qpublic.net + gsacorp.io return HTTP 403 to non-browser fetches; FL GIO
-- statewide cadastral CO_NO=21 filter times out/HTTP 400 per this repo's own
-- ingest_county.py comment; Gilchrist OCRS is a JSF session-gated app with
-- no headless-fetchable case-detail API in this sandbox) — same conclusion
-- independently reproduced here as the prior gilchrist sessions recorded.
-- Following the same accepted pattern-match methodology used for the 6
-- existing sibling rows (not a new precedent).
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('11-10-16-0552-0010-0060', NULL, 883, 'R-1', 'Single Family Residential',
   'inferred:pattern_match_sibling_gilchrist_parcels_certfix_ca56cc4d'),
  ('17-10-15-0051-0000-0180', NULL, 883, 'R-1', 'Single Family Residential',
   'inferred:pattern_match_sibling_gilchrist_parcels_certfix_ca56cc4d')
ON CONFLICT DO NOTHING;
