-- SHARD-1 (miami_dade): letter I (card_complete) diagnose + partial real-data fix
-- Session: architect-20260703T080000
--
-- SCOPE: Fix real parcel_id/geo/assessed_value for 3 of the 18 rows failing letter I
-- (card_complete = property_address + lat/lon + assessed/market value + zoning-card
-- match). All 3 values below are CONFIRMED against Miami-Dade's own authoritative
-- sources -- county ArcGIS FeatureServer (MD_LandInformation/MapServer/24, layer
-- "Property @ PaGis") and the official Property Appraiser public search proxy
-- (apps.miamidadepa.gov/PApublicServiceProxy). No PropertyOnion data used, no
-- fabrication/formula-derived values.
--
-- ═══════════════════════════════════════════════════════════════════════════
-- ROW 1 — id b29d59a5-bb2d-4394-97b3-3c5012f1eeb9, case 2024-016879-CA-01
-- ═══════════════════════════════════════════════════════════════════════════
-- Already had a real folio '04-3106-036-0020' (Miami-Dade format) and address
-- '3672 W 2 AVE, HIALEAH, FL- 33012'. Was missing lat/lon + assessed/market value.
-- SOURCE (geo, CONFIRMED via live query 2026-07-03):
--   https://gisweb.miamidade.gov/arcgis/rest/services/MD_LandInformation/MapServer/24/query?where=FOLIO%3D%270431060360020%27&outFields=*&outSR=4326&f=json
--   -> FOLIO=0431060360020, TRUE_SITE_ADDR='3672 W 2 AVE', TRUE_SITE_CITY=Hialeah,
--      TRUE_SITE_ZIP_CODE=33012-0000 (address match confirms folio is correct)
--   -> geometry (outSR=4326): x=-80.28678009877024, y=25.85556328023089
-- SOURCE (value, CONFIRMED via live query 2026-07-03):
--   https://apps.miamidadepa.gov/PApublicServiceProxy/PaServicesProxy.ashx?Operation=GetPropertySearchByFolio&folioNumber=0431060360020&clientAppName=PropertySearch
--   -> Assessment.AssessmentInfos[0]: Year=2026, AssessedValue=332142, TotalValue=332142
--   -> PropertyInfo.FolioNumber='04-3106-036-0020' (matches, dashed format)
--
-- ═══════════════════════════════════════════════════════════════════════════
-- ROW 2 — id e6e28ad4-50fa-4ff2-a852-54673f32ee82, case 2026-001741-CA-01
-- ═══════════════════════════════════════════════════════════════════════════
-- Had garbage parcel_id 'Property Appraiser' (upstream scraper field-label bug,
-- NOT reused) and real address '601 WASHINGTON AVE, MIAMI BEACH, FL- 33139'.
-- Resolved real folio via address match against county GIS.
-- SOURCE (parcel_id + geo, CONFIRMED via live query 2026-07-03):
--   https://gisweb.miamidade.gov/arcgis/rest/services/MD_LandInformation/MapServer/24/query?where=TRUE_SITE_ADDR%20LIKE%20%27601%20WASHINGTON%20AVE%25%27&outFields=*&outSR=4326&f=json
--   -> single match: FOLIO=0242030040810, TRUE_SITE_ADDR='601 WASHINGTON AVE',
--      TRUE_SITE_CITY='Miami Beach', TRUE_SITE_ZIP_CODE='33139-0000' (exact address match)
--   -> geometry (outSR=4326): x=-80.13342483064774, y=25.776292521962826
-- SOURCE (value, CONFIRMED via live query 2026-07-03):
--   https://apps.miamidadepa.gov/PApublicServiceProxy/PaServicesProxy.ashx?Operation=GetPropertySearchByFolio&folioNumber=0242030040810&clientAppName=PropertySearch
--   -> Assessment.AssessmentInfos[0]: Year=2026, AssessedValue=54100000, TotalValue=54100000
--   -> PropertyInfo.FolioNumber='02-4203-004-0810' (matches), SiteAddress='601 WASHINGTON AVE, Miami Beach, FL 33139-0000'
--
-- ═══════════════════════════════════════════════════════════════════════════
-- ROW 3 — id a48f0a40-76aa-4ad1-b847-db9cc04ef1a0, case 2025-001099-CA-01
-- ═══════════════════════════════════════════════════════════════════════════
-- Had parcel_id=NULL, real address '13701 KENDALE LAKES CIR B-405, MIAMI, FL- 33183'.
-- Condo unit designator 'B-405' is an exact, unambiguous match (unlike the other
-- two NULL-parcel_id condo rows at this session which were left UNKNOWN -- see
-- session findings).
-- SOURCE (parcel_id + geo, CONFIRMED via live query 2026-07-03):
--   https://gisweb.miamidade.gov/arcgis/rest/services/MD_LandInformation/MapServer/24/query?where=TRUE_SITE_ADDR%3D%2713701%20KENDALE%20LAKES%20CIR%20B-405%27&outFields=*&outSR=4326&f=json
--   -> single match: FOLIO=3049270360200, TRUE_SITE_ADDR='13701 KENDALE LAKES CIR B-405',
--      TRUE_SITE_CITY='Unincorporated County', TRUE_SITE_ZIP_CODE='33183-0000' (exact match)
--   -> geometry (outSR=4326): x=-80.41561013462353, y=25.70683322566675
-- SOURCE (value, CONFIRMED via live query 2026-07-03):
--   https://apps.miamidadepa.gov/PApublicServiceProxy/PaServicesProxy.ashx?Operation=GetPropertySearchByFolio&folioNumber=3049270360200&clientAppName=PropertySearch
--   -> Assessment.AssessmentInfos[0]: Year=2026, AssessedValue=213464, TotalValue=233500
--   -> PropertyInfo.FolioNumber='30-4927-036-0200' (matches), SiteAddress unit='B-405'
--
-- ═══════════════════════════════════════════════════════════════════════════
-- IMPORTANT CAVEAT — DOES NOT FLIP LETTER I (CONFIRMED, not a claim of success)
-- ═══════════════════════════════════════════════════════════════════════════
-- v_zoning_gold_standard_card (backed by parcel_zones/jurisdictions/zoning_districts/
-- zone_standards) has only 286 rows for miami_dade, and NONE of these 3 real folios
-- (0431060360020, 0242030040810, 3049270360200, dashed or undashed) appear in it --
-- CONFIRMED via live query against v_zoning_gold_standard_card before writing this
-- migration. Because card_complete requires a zoning-card match IN ADDITION to
-- address+geo+value, these 3 rows will remain card_complete=false after this fix.
-- This migration still ships because: (a) it replaces NULL/garbage parcel_id with
-- real, sourced data (strengthens E parcel-linkage integrity even though E already
-- passes), (b) it is a real prerequisite for I once zoning-card coverage is
-- expanded for these folios (out of scope this session -- would require INSERTing
-- into parcel_zones with a real zone_code sourced from Miami-Dade's own
-- MD_MDCZoning ArcGIS layer, a materially different intervention than the
-- parcel_id/geo/value scope given for this session).
--
-- RESIDUAL FINDING (flagged, not fixed): v_zoning_gold_standard_card itself
-- contains garbage placeholder rows ('Property Appraiser', 'MULTIPLE PARCELS' as
-- parcel_id) for miami_dade (and ~15 other counties: volusia, sarasota, orange,
-- broward, pinellas, escambia, marion, st lucie, nassau, walton, clay, putnam,
-- charlotte, citrus, seminole, polk, hillsborough, santa rosa, gilchrist, palm
-- beach, duval) -- CONFIRMED via live query. This causes false-positive
-- zoned_match=true collisions for auction rows that ALSO happen to carry the
-- same garbage parcel_id string (6 miami_dade rows currently benefit from this
-- coincidental collision, confirmed live). Per this session's explicit guardrail
-- ("garbage placeholder ... does NOT count as a real parcel_id even if it
-- happens to coincidentally match a zoning card row"), these are NOT treated as
-- real passes in this analysis, but the evaluator's raw SQL currently DOES count
-- them as passing. Not touched this session (upstream, multi-county, out of the
-- gadsden/miami_dade/flagler scope for this session).

SET statement_timeout = 0;

UPDATE multi_county_auctions
SET latitude = 25.85556328023089,
    longitude = -80.28678009877024,
    assessed_value = 332142,
    market_value = 332142,
    updated_at = now()
WHERE id = 'b29d59a5-bb2d-4394-97b3-3c5012f1eeb9'
  AND lower(county) = 'miami_dade'
  AND parcel_id = '04-3106-036-0020'
  AND latitude IS NULL;

UPDATE multi_county_auctions
SET parcel_id = '02-4203-004-0810',
    latitude = 25.776292521962826,
    longitude = -80.13342483064774,
    assessed_value = 54100000,
    market_value = 54100000,
    updated_at = now()
WHERE id = 'e6e28ad4-50fa-4ff2-a852-54673f32ee82'
  AND lower(county) = 'miami_dade'
  AND parcel_id = 'Property Appraiser';

UPDATE multi_county_auctions
SET parcel_id = '30-4927-036-0200',
    latitude = 25.70683322566675,
    longitude = -80.41561013462353,
    assessed_value = 213464,
    market_value = 233500,
    updated_at = now()
WHERE id = 'a48f0a40-76aa-4ad1-b847-db9cc04ef1a0'
  AND lower(county) = 'miami_dade'
  AND parcel_id IS NULL;

-- VERIFICATION (paste actual before/after JSON from pencil_dod_evaluate_county
-- in the session findings -- expected: I metric UNCHANGED at 94.9% (338/356)
-- because none of these 3 folios are in the zoning-card sample; E/other letters
-- unaffected since E was already passing).
