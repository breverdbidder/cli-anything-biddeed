-- Gold Standard seminole C/D/I fix, 2026-08-26.
--
-- Idempotent reflection of live PostgREST PATCH/POST writes made this session
-- via scripts/gold_standard_seminole_cdi_20260826_ajax_geo_zone_backfill.py
-- (direct psql/pooler auth confirmed BROKEN this session per standing
-- constraint -- all writes executed via PostgREST REST, this file documents
-- them for replay/audit). See that script's module docstring for full
-- source-attribution detail (live AJAX RealAuction harvest URLs, ArcGIS
-- FeatureServer URLs, and every dead-end source attempted and ruled out).
--
-- BEFORE (VERIFIED live, pencil_dod_evaluate_county('seminole'), 2026-08-26
-- session start; auctions_total grew 148->157 since the 2026-08-24 session):
--   C: matched_clean=145 of 157 = 92.4%  FAIL
--   D: matched_any=145   of 157 = 92.4%  FAIL
--   I: card_complete=142 of 157 = 90.4%  FAIL
--
-- FIX METHOD (C/D): 12 case_numbers named in the dispatch, all
-- data_source=calendar_sweep_mca_v3 rows never yet reconciled against the
-- live RealAuction-family calendar. 9 matched exactly against a live AJAX
-- harvest of seminole.realforeclose.com (auction_date 2026-09-22) and
-- seminole.realtaxdeed.com (auction_date 2026-10-15) -- reused
-- scripts/shard2_run2450_ajax_realforeclose_harvest.py verbatim, same
-- technique as every prior seminole C/D session. The other 3
-- (2016CA000953, 2024CA002388, 2025CA002908) matched exactly against the
-- existing realforeclose_aids table (independent scrape-realauction-
-- county.yml pipeline). All 12 are genuine exact case_number matches
-- against a live/independently-scraped record for the SAME case -- no
-- PropertyOnion litmus involved.
--
-- FIX METHOD (I): of the 15 pre-existing I-gap rows named in the dispatch,
-- 6 were confirmed (live, this session) to have full card fields (address +
-- lat/lon + assessed_value + parcel_id) and be missing ONLY a parcel_zones
-- link. Of those 6, 5 have a real parcel_id and were resolved via municipal
-- (not county) ArcGIS Online zoning layers -- each target address sits
-- inside an INCORPORATED Seminole city (Sanford/Winter Springs/Lake Mary),
-- and each city publishes its own public, token-free ArcGIS Online hosted
-- Feature Service:
--   Sanford:        services1.arcgis.com/EPXb1p5YttfWtj8l/.../Zoning/FeatureServer/0
--   Winter Springs:  services5.arcgis.com/hbtBppF7t3PpouVf/.../Planning_WFL1/FeatureServer/5
--   Lake Mary:       services1.arcgis.com/v0YMSb0ovdJoIQKg/.../LM_Zoning/FeatureServer/0
-- Point-in-polygon queries (Sanford/Lake Mary) and a PIN-attribute query
-- cross-confirmed by point-in-polygon (Winter Springs) all returned live,
-- real zone codes:
--   2025CA001137  33-19-30-5QS-0000-0230  Sanford         -> SR-1  (raw SR1)
--   2025CA001187  10-20-30-5CT-0G00-0060  Sanford         -> SR-1A (raw SR1A)
--   2026CA000914  31-19-31-525-0J00-0030  Sanford         -> SR-1  (raw SR1)
--   2025CA002094  02-21-30-509-0000-1930  Winter Springs  -> R-1A  (verbatim)
--   2024CA002295  16-20-30-300-053A-0000  Lake Mary       -> RCE   (new district)
-- Sanford's raw codes render without hyphens; zoning_districts already
-- stores the canonical hyphenated form for Sanford (SR-1 id=6316, SR-1A
-- id=6315, both pre-existing from the 2026-08-24 session) -- the join in
-- v_zoning_gold_standard_card requires an exact string match, so
-- parcel_zones.zone_code uses the canonical hyphenated code, not the raw
-- ArcGIS label. Winter Springs' R-1A already existed verbatim (id=11870),
-- reused as-is. Lake Mary's RCE ("Rural Country Estates") did NOT exist
-- (checked live: zero rows for jurisdiction_id=928 code=RCE) -- ONE new
-- zoning_districts row created, category='Residential', description
-- sourced verbatim from the ArcGIS layer's own Description field. No
-- zone_standards row was added for RCE (no ordinance density/FAR value
-- sourced this session -- left absent, not fabricated).
--
-- The 6th zone-only row, SYN-SEM-2025CA000629 (case 2025CA000629), was NOT
-- fixed: it has a synthetic SYN- placeholder parcel_id, not a real parcel.
-- Confirmed live this session (realforeclose_aids AND a fresh AJAX harvest
-- of its own 2026-03-17 auction date) that the underlying case has no
-- resolvable property record at all (both sources return only a
-- "Property Appraiser" anchor-text scrape artifact) -- a genuine data
-- ceiling shared with C/D-style garbage-parcel rows, not a zoning-source
-- gap. Left untouched, honestly reported.
--
-- BONUS FIX (single-field, same Census-geocoder method as 2026-08-24):
-- 2025CA001957 (2657 BULLION LOOP, SANFORD, FL 32771) had parcel_id +
-- address + assessed_value but NULL lat/lon. US Census Bureau public
-- geocoder returned an exact match: y=28.793337441032, x=-81.209559433644.
-- Backfilled directly. Does NOT flip this row's I status alone -- a
-- point-in-polygon query against the same Sanford zoning layer at this
-- geocoded point returned zero features (this specific point falls outside
-- that layer's coverage despite the Sanford mailing address, likely
-- unincorporated county land with a Sanford postal address) -- left
-- zone-unlinked, no county-wide fallback zoning layer was found this
-- session (see script docstring's dead-end list).
--
-- ZONING SOURCES CONFIRMED DEAD THIS SESSION (all VERIFIED live,
-- 2026-08-26 -- documented so a future session does not re-attempt them):
--   gis.scpafl.org/arcgis/rest/services            -- TCP connection reset,
--     5/5 attempts (same blocker as 20260718k/20260718n migrations)
--   scpafl.org/search/parcels/details/?PID=...     -- Blazor Server app,
--     static GET returns an empty client-rendered shell, zero parcel data
--   Firecrawl                                      -- HTTP 402 insufficient
--     credits fleet-wide (documented since 2026-06-10)
--   map.scpafl.org/gis/rest/services               -- reachable but every
--     populated folder requires a token; unauthenticated folders have no
--     zoning/parcel service
--   www.seminolecountyfl.gov interactive-mapping    -- 404 (stale URL)
--   Seminole County ArcGIS Online org (services3.arcgis.com/n4VF6lyYfB5kizho)
--     -- 124 public services, none is a general parcel-level zoning layer;
--     closest hit "ChickenPermitZoningDissolved" is a 10-feature
--     unincorporated-county-only layer, confirmed empty at all 5 target
--     points (all 5 addresses are inside incorporated cities)
--   "Pinellas_Seminole_Zoning" ArcGIS Online layer  -- already documented
--     extent-mismatch dead end (20260718k migration)
--   "General Zoning Data" (Admin_Sanford)           -- reachable, correct
--     field names, but live layer is EMPTY (count=0)
--
-- AFTER (VERIFIED live, pencil_dod_evaluate_county('seminole'), immediately
-- after all writes, same session):
--   C: matched_clean=157 of 157 = 100.0%  PASS
--   D: matched_any=157   of 157 = 100.0%  PASS
--   I: card_complete=147 of 157 = 93.6%   FAIL (+5 rows; genuine residual
--      ceiling of 10 rows -- 6 garbage-parcel rows, 3 tax_deed rows missing
--      assessed_value [RealTaxDeed's own calendar does not publish this
--      field], 1 Sanford-address row whose geocoded point falls outside
--      the only zoning layer found for that city)
--
-- REGRESSION CHECK (all VERIFIED via the same live evaluator call):
--   A: fc=130 td=27 PASS (unchanged)
--   B: verified=63 closed_sold=63 100.0% PASS (unchanged)
--   E: parcel_linked=154 of 157 98.1% PASS (unchanged -- not touched this
--      session)
--   F: tier1_sold=63 closed_sold=63 100.0% PASS (unchanged)
--   G: density=96.3 far=100.0 pk1000=100.0 PASS (was 98.0%, still
--      comfortably >=95% -- expected/predicted dip from the 1 new RCE
--      district carrying no zone_standards density value; matches the
--      pre-write prediction made before this migration ran)
--   H: 0.0 hours since last_seen PASS (unchanged)
--   J: deal_complete=152 of 157 96.8% PASS (unchanged)
--   Zero regressions.

-- ── 1. Diagnostic before update ─────────────────────────────────────────────
DO $$
DECLARE
  v_before jsonb;
BEGIN
  SELECT public.pencil_dod_evaluate_county('seminole') INTO v_before;
  RAISE NOTICE 'Seminole BEFORE: C=% D=% I=%', v_before->'C', v_before->'D', v_before->'I';
END $$;

-- ── 2. C/D promotion: 9 rows, live AJAX-harvest-confirmed genuine ──────────
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:seminole_gold_standard_20260826_ajax_harvest'
WHERE county = 'seminole'
  AND case_number IN (
    '2025CA001957', '2026CA000914', '2025CA001187', '2025CA002094',
    '2025CA001137', '2024CA002295', '20260083/2024-001947',
    '20260069/2024-000064', '20260071'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean'
       OR parity_source NOT LIKE 'tier1%');

-- ── 3. C/D promotion: 3 rows, realforeclose_aids-confirmed genuine ─────────
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:seminole_gold_standard_20260826_realforeclose_aids'
WHERE county = 'seminole'
  AND case_number IN ('2016CA000953', '2024CA002388', '2025CA002908')
  AND (parity_status IS DISTINCT FROM 'matched_clean'
       OR parity_source NOT LIKE 'tier1%');

-- ── 4. I fix: lat/lon backfill (US Census geocoder, VERIFIED) ──────────────
UPDATE multi_county_auctions
SET latitude = 28.793337441032, longitude = -81.209559433644
WHERE lower(county) = 'seminole' AND case_number = '2025CA001957'
  AND parcel_id = '34-19-31-501-0000-2040' AND latitude IS NULL;

-- ── 5. I fix: new Lake Mary RCE zoning district (real ArcGIS description,
--    zero zone_standards row -- no ordinance value sourced) ───────────────
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description)
SELECT 928, 'RCE', 'Rural Country Estates', 'Residential',
       'Rural Country Estates (Lake Mary, FL) -- sourced verbatim from live LM_Zoning ArcGIS FeatureServer Description field, 2026-08-26.'
WHERE NOT EXISTS (
  SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 928 AND code = 'RCE'
);

-- ── 6. I fix: parcel_zones links, municipal ArcGIS-verified ────────────────
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT v.parcel_id, v.jurisdiction_id, v.zone_code, v.zone_name,
       'gold_standard_seminole_i_20260826_municipal_arcgis_verified'
FROM (VALUES
  ('33-19-30-5QS-0000-0230', 904, 'SR-1',  'Single-Family Dwelling Residential'),
  ('10-20-30-5CT-0G00-0060', 904, 'SR-1A', 'Single-Family Dwelling Residential'),
  ('31-19-31-525-0J00-0030', 904, 'SR-1',  'Single-Family Dwelling Residential'),
  ('02-21-30-509-0000-1930', 921, 'R-1A',  'One-Family Dwelling District'),
  ('16-20-30-300-053A-0000', 928, 'RCE',   'Rural Country Estates')
) AS v(parcel_id, jurisdiction_id, zone_code, zone_name)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = v.parcel_id
);

-- ── 7. Diagnostic after update (regression check on ALL letters) ──────────
DO $$
DECLARE
  v_after jsonb;
BEGIN
  SELECT public.pencil_dod_evaluate_county('seminole') INTO v_after;
  RAISE NOTICE 'Seminole AFTER: %', v_after;
END $$;
