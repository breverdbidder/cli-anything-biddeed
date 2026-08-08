-- GOLD STANDARD shard-3 (dispatch 9f7b5985-3765-4e7b-955c-10e2f2aca59e), county=columbia.
--
-- I (73.5% -> ~88.2%, 25/34 -> 30/34): the 9 rows failing card_complete all
-- already had property_address/lat/lon/assessed_value -- the only gap was
-- zoning linkage (parcel_id not present in v_zoning_gold_standard_card).
-- 1 of the 9 is the pre-existing, repeatedly-reconfirmed Fort White
-- structural gap (case 2025-2196-CC / parcel 04023-000) -- Fort White is
-- incorporated and has zero coverage in the county's Zoning_Atlas GIS
-- layer, re-confirmed live this session via a tight point-buffer ArcGIS
-- query (0 features).
--
-- The other 8 are new Lake City tax-deed parcels (columbia_clerk_html
-- LIVE-SESSION-20260803 harvest). Lake City is ALSO incorporated and has
-- zero coverage in the county GIS zoning layer (confirmed live: 0 features
-- in a ~100ft buffer around each of the 8 parcel centroids) -- Lake City
-- zoning has no live API, only a static "City of Lake City Official Zoning
-- Atlas" PDF (lcfla.com/growth-management/page/zoning-atlas, lczn13.pdf).
--
-- METHOD: the PDF has real extractable text for street labels (not a raster
-- scan). Built an affine transform from PDF-page-point space to real
-- lon/lat using two independent control-point sets (named-lake centroids
-- geocoded via Nominatim, and street-label text positions matched to their
-- corresponding parcel's own geocoded address), then rendered high-res
-- crops of the atlas around each of the 8 parcels' predicted location.
-- A Workflow ran one identification agent + one independent adversarial
-- verifier agent per parcel (agents blind to each other's tool calls,
-- verifier explicitly instructed to try to refute, not rubber-stamp).
--
-- RESULT: 5 of 8 survived adversarial verification (identifier and verifier
-- independently agreed on the same zone code, both citing legible street
-- labels actually visible in frame). 3 did NOT survive -- the verifier
-- found real zoning-boundary lines running directly along the target
-- street's centerline (Aggie Ave, Simms Dr) that the first-pass identifier
-- missed, meaning the parcel could be on either side and the atlas alone
-- (no parcel-level geometry) cannot resolve which; the 3rd (11388-000) has
-- no legible landmark anchor in frame at all. Per BLANK > WRONG, these 3
-- are NOT backfilled here -- forcing a zone_code would be a coin flip, not
-- a verified read. Left as a documented residual for a future session with
-- parcel-level GIS geometry (Columbia County Property Appraiser interactive
-- search) to resolve street-side.
--
-- No zone code was inserted for a parcel whose read did not survive
-- adversarial verification. No values fabricated.
--
-- J (44.1%, 15/34): RE-VERIFIED FRESH this session, still structurally
-- blocked -- unchanged from the 2026-08-03 finding
-- (20260803_gold_standard_shard_df5a4f3a_columbia_bfij_fix.sql). All 19
-- tax-deed rows have case_number=NULL because columbiaclerk.com's
-- Vue-rendered tax-deed list page only exposes Cert # + Parcel ID (live
-- Chrome DOM dump taken today, 2026-08-08, confirms the card markup still
-- has zero file/case-number field -- Vue renders `<!---->` in its place,
-- meaning the underlying record has no such value, not that it's hidden).
-- pencil_dod_evaluate_county's J CTE joins strictly on
-- bd.case_number = mca.case_number; NULL = NULL is not true in SQL. Checked
-- for a new lever this session (columbiataxcollector.com, county-taxes.com
-- tax-deed search) -- none expose a real case/file number either. Using
-- cert_number as a case_number substitute was considered and rejected
-- again: a prior session explicitly weighed and rejected this as a
-- semantic fabrication, and no new evidence justifies reversing that call.
-- No bid_decisions or case_number changes made this session for J.

SET statement_timeout = 0;

BEGIN;

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT v.parcel_id, 974, v.zone_code, NULL, 'lcfla_zoning_atlas_pdf_visual:lczn13:2026-08-08'
FROM (VALUES
  ('10846-104', 'RSF-3'),
  ('11375-000', 'RSF-3'),
  ('11612-000', 'RSF-3'),
  ('11651-000', 'RSF-1'),
  ('13831-000', 'RO')
) AS v(parcel_id, zone_code)
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones pz WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = 974
);

COMMIT;
