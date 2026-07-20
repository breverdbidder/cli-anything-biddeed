-- Gold Standard SHARD-8: Marion G (pk1000=0.0) + Nassau I (card_complete=7/34)
-- dispatch_id: 0ddd603c-68ec-45c0-86b8-3b643c98faf3
-- Session: architect-20260720T210000
--
-- MARION STATE (live-verified via pencil_dod_evaluate_county, 2026-07-20):
--   9/10 PASS — G FAIL (density=100.0 far=100.0 pk1000=0.0)
--   Root cause (4th confirmed session, per SECOND_CONTINUATION.md):
--   Marion's commercial/industrial districts have NULL parking_per_1000sf in
--   zone_standards, and Marion LDC Art.6 Table 6.11-4/6.11-5 is blocked at every
--   known URL (Municode 403, marionfl.org 403, elaws.us ECONNRESET, codelibrary
--   amlegal.com timeout). The relevant districts under Ocala jurisdiction (id=900):
--     - B-2 Community Business (not "General Business" — verified from LDC §4.2.18)
--     - B-4 Regional Business
--     - B-5 Heavy Business
--     - M-1 Light Industrial
--     - M-2 Medium Industrial
--   Marion's Table 6.11-5 is organized by land-use type (not by zoning district),
--   so there may be no single "B-2 parking ratio" — applicable ratio depends on
--   which of B-2's 200+ permitted uses occupies the specific site. This structural
--   finding was first documented in the SECOND_CONTINUATION.md and means hunting
--   for "B-2 parking ratio" is likely the wrong search.
--
-- APPROACH TAKEN: PD/PUD pk1000_regulated=false (legitimate fix for Planned
-- Development districts that cannot have a fixed base-code parking ratio, same
-- pattern as Hendry CLEWISTON-CITY-ZONED / Sanford PD precedents). Commercial/
-- industrial districts remain NULL — BLANK > WRONG; not fabricated.
--
-- NASSAU STATE (live-verified via pencil_dod_evaluate_county, 2026-07-20):
--   7/10 PASS — B FAIL (null), F FAIL (null), I FAIL (card_complete=7/34=20.6%)
--   Root cause confirmed:
--   1. I regression: 2026-07-18 ghost purge
--      (20260718_gold_standard_shard5_sarasota_nassau_bay_gulf_ghost_success_purge.sql)
--      deleted 'shard4_run581_v2/nassau_synthetic' parcel_zones rows. New nassau
--      auction rows added since July also lack parcel_zones coverage.
--   2. B/F structural block: only 1 completed nassau auction on record
--      (452025CA000382CAAXYX — private resale WD, not courthouse CT), so
--      pct_closed_sold=null and pct_tier1_sold=null. No scraping path without
--      Firecrawl/browser automation. Not fixed here.
--
-- NASSAU I FIX: Re-establish parcel_zones coverage via Nassau County PA ArcGIS
-- (maps.ncpafl.com/ncflpa_arcgis/rest/services). The live executor script
-- (scripts/shard8_marion_nassau_executor.py) queries ArcGIS for zone codes per
-- uncovered parcel_id, registers any unknown zone codes in zoning_districts
-- (jurisdiction_id=865), and inserts parcel_zones rows.
--
-- This migration file documents the structural context. The actual data writes
-- are performed by the GHA workflow gold-standard-shard8-marion-nassau.yml
-- which is checked in on the claude/issue-12896-20260720-2108 branch and
-- pending merge to main.
--
-- VERIFICATION (run after workflow execution):
-- SELECT public.pencil_dod_evaluate_county('marion');
-- SELECT public.pencil_dod_evaluate_county('nassau');
-- SELECT count(*) FROM parcel_zones WHERE jurisdiction_id = 865
--   AND source LIKE 'shard8%'; -- expect >= 20 new rows for nassau
--
-- HONESTY MARKERS:
--   Marion G: BLOCKED (4th session). No parking values fabricated. pk1000=0.0
--     remains until real ordinance source becomes accessible. PD/PUD rows
--     marked pk1000_regulated=false (structural, not numeric).
--   Nassau I: INFERRED zone codes from Nassau PA ArcGIS (authoritative source,
--     same as shard10_run2346 which produced the genuine rows surviving the purge).
--   Nassau B/F: genuinely blocked (structural data gap). No fix claimed.

BEGIN;

-- Marion: mark any PD-type districts pk1000_regulated=false so they stop
-- appearing as "applicable but missing" (same fix pattern as Seminole PUD-MO
-- and Hendry CLEWISTON-CITY-ZONED precedents).
-- This is safe and honest: PD/PUD districts are negotiated per-plan, no fixed
-- base-code parking ratio exists. pk1000_regulated=false means not applicable.
UPDATE zone_standards
SET pk1000_regulated = false
FROM zoning_districts zd
WHERE zone_standards.zoning_district_id = zd.id
  AND zd.jurisdiction_id = 900  -- Ocala / Marion County unincorporated
  AND zd.category = 'Planned Development'
  AND zone_standards.parking_per_1000sf IS NULL
  AND (zone_standards.pk1000_regulated IS NULL OR zone_standards.pk1000_regulated = true);

-- Note: The above UPDATE may affect 0 rows if Marion PD districts already
-- have pk1000_regulated set, or if there are no PD-category zone_standards
-- rows for jurisdiction 900. This is idempotent and safe.

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (run after workflow execution adds nassau parcel_zones)
-- ============================================================================
--
-- SELECT public.pencil_dod_evaluate_county('marion');
-- -- Expected: G metric — density=100.0 far=100.0, pk1000 still 0.0 unless real
-- --   commercial parking values are found in this run (INFERRED: unlikely, same
-- --   structural block as 4 prior sessions). 9/10 unchanged. If commercial
-- --   values were found and applied by the executor script, pk1000 will improve.
--
-- SELECT public.pencil_dod_evaluate_county('nassau');
-- -- Expected: I metric improves from 7/34 (20.6%) to >= 27/34 (79.4%)+ if
-- --   ArcGIS returned zone codes for uncovered parcels. B/F unchanged (null).
--
-- SELECT count(*), source FROM parcel_zones WHERE jurisdiction_id = 865
--   GROUP BY source ORDER BY count DESC;
-- -- Shows parcel_zones coverage by source for Nassau (jurisdiction 865)
