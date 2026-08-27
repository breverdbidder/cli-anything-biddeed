-- Gold Standard dispatch 8da482b6-8cff-45ea-9950-4e8fed552f37 — pasco letter I
-- key=pasco-I (county=pasco, letter=I, property card completeness)
--
-- BASELINE (pencil_dod_evaluate_county('pasco') before fix):
--   I: card_complete=346/368 = 94.0% (FAIL, threshold >=95%)
--
-- DIAGNOSIS (live re-derivation of the exact card_complete predicate from
-- pencil_dod_evaluate_county, CTE `c`/`zc`): 20 gap rows found (dispatch
-- text estimated ~22; live count is 20). Two distinct patterns:
--
--   Pattern 1 (14 rows) — property_address + parcel_id present, and the
--     parcel HAS a real zone_code in zoning_assignments (zone_source=
--     'county_gis_pasco_pascopa_arcgis', i.e. the Pasco Property Appraiser
--     GIS scrape already ran for these folios), BUT the gold-standard-card
--     view (v_zoning_gold_standard_card) reads from a DIFFERENT table --
--     parcel_zones -- not zoning_assignments. parcel_zones for pasco only
--     has 345 rows (all jurisdiction_id=1258 "Unincorporated Pasco County"),
--     while zoning_assignments has 268,029 pasco rows. These 14 parcels were
--     simply never copied from the bulk-ingestion table into the curated
--     parcel_zones table used by the card view. This is a REAL DATA gap in
--     a join, not a fabrication -- the zone_code itself already exists,
--     scraped from the same county ArcGIS source (services9.arcgis.com/
--     .../Parcels_2023) that populated the other 345 parcel_zones rows for
--     this county. All 14 addresses use unincorporated postal cities (Port
--     Richey, New Port Richey, Holiday, Zephyrhills-unincorporated, Spring
--     Hill, Land O Lakes, Lutz) matching the existing 345 rows' single
--     jurisdiction (1258), and 4 of the 7 zone codes involved (AR, MPUD,
--     PUD, RMH) already have zoning_districts rows under jurisdiction 1258,
--     confirming this is the correct jurisdiction for the standard Pasco
--     County zoning code set.
--     Of these 14, 10 already had address+geo+value complete from a prior
--     session (scripts/gold_standard_shard4_ecbe151d_pasco_i_geocode_
--     assessed_backfill.py, 2026-08-25) and only needed the parcel_zones
--     link. The other 4 (see Pattern 2) needed geo/value too.
--
--   Pattern 2 (4 of the 14 above) — address+parcel_id present but
--     latitude/longitude/assessed_value all NULL. Re-fetched live this
--     session from two independent real sources, cross-checked by address:
--       - search.pascopa.com/parcel.aspx (Pasco County Property Appraiser
--         official parcel card) -> assessed_value + physical address match
--       - services9.arcgis.com/.../Parcels_2023/FeatureServer/0/query
--         (Pasco County GIS parcel polygons) -> centroid lat/lon, address
--         match cross-checked against the PA card
--     31-25-17-0220-00000-2180 (7615 TOLAR DRIVE): $209,715, centroid
--       28.267878,-82.639030 (address match: "7615 TOLAR DRIVE")
--     14-25-16-0210-00000-0200 (10251 PEOPLES LOOP): $266,973, centroid
--       28.306805,-82.680600 (address match: "10251 PEOPLES LOOP")
--     21-25-16-0550-00000-1290 (6421 STONE ROAD): $169,645, centroid
--       28.288030,-82.708217 (address match: "6421 STONE ROAD")
--     35-26-18-0070-00F00-0080 (20921 HAULOVER COVE #8): $93,652, centroid
--       28.185667,-82.471210 (address match: "20921 HAULOVER COVE UNIT 8
--       BUILDING F")
--
--   6 rows left BLOCKED / not fixed this session (structural ceiling, not
--   fabricated):
--     - 51-2023-CA-003726-CAAX-ES, 51-2024-CA-000530-CAAX-WS: parcel_id=
--       'IPLTMULE' (placeholder, not a real folio), no address to search by.
--     - 51-2025-CC-004715-CCAX-ES, 51-2025-CA-000763-CAAX-WS (case checked,
--       not in final target list),
--       51-2025-CA-002914-CAAX-WS: parcel_id IS NULL, no confident GIS/PA
--       parcel match by address attempted (PropertyOnion-style orphan rows
--       per dispatch instructions -- left alone rather than guessing a
--       parcel_id). Two of these (...002914-CAAX-WS "4371 TAHITIAN GARDENS
--       CIR" and a realforeclose sibling row "6824 BEACH BLVD") already
--       carry an identical placeholder lat/lon (28.308,-82.4396) and
--       identical assessed_value ($150,000) pre-existing from the
--       'realforeclose' scraper for two addresses 15 miles apart -- flagged
--       here as a pre-existing data-quality issue in that scraper, NOT
--       something this migration touches or relies on.
--     - 51-2025-CC-008556-CCAX-WS: parcel_id IS NULL, has partial
--       assessed_value but no confident parcel match found this session.
--
-- EXPECTED RESULT: card_complete 346 -> 360 of 368 = 97.8% (clears >=95%
-- threshold). 6 rows remain BLANK (structural ceiling), not fabricated.
--
-- HONESTY MARKERS:
--   Pattern 1 (parcel_zones INSERT, zone_code copy): CONFIRMED -- zone_code
--     values are copied verbatim from zoning_assignments rows already
--     sourced from county_gis_pasco_pascopa_arcgis for these exact
--     parcel_ids; jurisdiction_id=1258 match is INFERRED from unanimous
--     precedent (100% of existing pasco parcel_zones rows use 1258) plus
--     postal-city cross-check (none of the 14 addresses fall in an
--     incorporated Pasco municipality).
--   Pattern 2 (geo/value UPDATE): CONFIRMED -- live-fetched this session
--     from search.pascopa.com and services9.arcgis.com/.../Parcels_2023,
--     both independently address-matched before use.
--
-- HARD GUARDRAILS FOLLOWED:
--   - No fabricated parcel_id, address, geo, or value for any of the 6
--     BLOCKED rows (BLANK > WRONG).
--   - No PropertyOnion-sourced values used (po_* columns not referenced).
--   - Scoped only to county='pasco' (owned county for this dispatch).
--   - No shared/fleet-wide function, cron job, or gold_standard_loop/
--     certify touched. v_zoning_gold_standard_card view definition left
--     unmodified -- documenting the parcel_zones/zoning_assignments split
--     as a structural finding, not patching the view (fleet-wide impact
--     out of scope for this dispatch).
--   - Idempotent: parcel_zones inserts guarded by NOT EXISTS on parcel_id+
--     jurisdiction_id; multi_county_auctions updates only touch rows where
--     the target field is currently NULL.
-- ============================================================================

SET statement_timeout = 0;

-- Pattern 1: link 14 already-zoned parcels into the curated parcel_zones
-- table (source: zoning_assignments, zone_source='county_gis_pasco_pascopa_arcgis',
-- jurisdiction 1258 = Unincorporated Pasco County, matching 100% of existing rows).
INSERT INTO public.parcel_zones (jurisdiction_id, parcel_id, zone_code, source)
SELECT 1258, za.parcel_id, za.zone_code, 'gold_standard_pasco_i_8da482b6:zoning_assignments_sync'
FROM public.zoning_assignments za
WHERE lower(za.county) = 'pasco'
  AND za.parcel_id IN (
    '02-24-17-0010-00001-1520', '13-25-17-0010-01000-0170', '11-25-16-0150-00000-0820',
    '29-26-16-0050-00000-5360', '08-25-17-0140-00000-1400', '04-26-21-0150-00800-0080',
    '35-25-16-0100-00000-0310', '31-26-16-0030-00000-0700', '01-26-21-0010-07300-0080',
    '09-26-21-005F-00000-1280', '04-26-21-0140-00100-0470', '04-26-21-0120-00000-0250',
    '31-25-17-0220-00000-2180', '14-25-16-0210-00000-0200', '21-25-16-0550-00000-1290',
    '35-26-18-0070-00F00-0080'
  )
  AND za.zone_code IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM public.parcel_zones pz
    WHERE pz.parcel_id = za.parcel_id AND pz.jurisdiction_id = 1258
  );

-- Pattern 2: backfill geo/value for the 4 rows still missing them, from
-- Pasco PA (search.pascopa.com) + Pasco GIS (Parcels_2023 FeatureServer)
-- fetched live this session, address-matched before write.
UPDATE public.multi_county_auctions
SET latitude = 28.267877832515726,
    longitude = -82.6390298971752,
    assessed_value = 209715.0,
    updated_at = NOW()
WHERE lower(county) = 'pasco' AND case_number = '51-2025-CA-002281-CAAX-WS'
  AND parcel_id = '31-25-17-0220-00000-2180'
  AND latitude IS NULL AND longitude IS NULL AND assessed_value IS NULL;

UPDATE public.multi_county_auctions
SET latitude = 28.306805300228774,
    longitude = -82.68059984484317,
    assessed_value = 266973.0,
    updated_at = NOW()
WHERE lower(county) = 'pasco' AND case_number = '51-2025-CA-003079-CAAX-WS'
  AND parcel_id = '14-25-16-0210-00000-0200'
  AND latitude IS NULL AND longitude IS NULL AND assessed_value IS NULL;

UPDATE public.multi_county_auctions
SET latitude = 28.288030197871223,
    longitude = -82.7082166720648,
    assessed_value = 169645.0,
    updated_at = NOW()
WHERE lower(county) = 'pasco' AND case_number = '51-2025-CA-003924-CAAX-WS'
  AND parcel_id = '21-25-16-0550-00000-1290'
  AND latitude IS NULL AND longitude IS NULL AND assessed_value IS NULL;

UPDATE public.multi_county_auctions
SET latitude = 28.185667114352928,
    longitude = -82.47120993460973,
    assessed_value = 93652.0,
    updated_at = NOW()
WHERE lower(county) = 'pasco' AND case_number = '51-2025-CC-004408-CCAX-ES'
  AND parcel_id = '35-26-18-0070-00F00-0080'
  AND latitude IS NULL AND longitude IS NULL AND assessed_value IS NULL;

-- ============================================================================
-- VERIFICATION (run after applying)
-- ============================================================================
-- SELECT public.pencil_dod_evaluate_county('pasco');
-- Expect I pass=true, metric>=95.0 (target 97.8, card_complete=360/368).
--
-- OBSERVED SIDE EFFECT (disclosed, out of scope for this dispatch -- letter I
-- only): applying this migration moved letter G (zoning FAR/parking density
-- coverage) from PASS (density=95.6 far=100.0 pk1000=100.0) to FAIL
-- (density=93.3 far=30.0 pk1000=30.0). Root cause: the 14 parcel_zones rows
-- inserted above introduce 6 new distinct zone codes (AR, MPUD, PUD, R3, R4,
-- RMH, ZH -- via v_zoning_gold_standard_kpi_v3's "applicable" denominator)
-- that do not yet have matching zone_standards rows (max_far,
-- parking_per_1000sf) for jurisdiction 1258, dragging those two KPI
-- percentages down. This was NOT reverted -- letter I is the assigned
-- target and correctly reflects real, non-fabricated data; letter G needs a
-- separate zone_standards enrichment pass (ordinance/FAR/parking research
-- for AR/MPUD/PUD/R3/R4/RMH/ZH under Unincorporated Pasco County) which is
-- out of scope for dispatch 8da482b6 (letter I only). Flagged here for the
-- next pasco-G dispatch, not silently absorbed.
