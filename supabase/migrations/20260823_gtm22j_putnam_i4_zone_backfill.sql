-- GTM-22J putnam letter I fix, 2026-08-23 shard session.
-- Root cause: NOT a broken zoning source or structural ceiling. Putnam letter I was verified
-- 10/10 (PASS) as recently as 2026-08-07 (commit 2899ac05). Since then, the county's ongoing
-- calendar_sweep_mca_v3 scraper feed has continuously inserted new multi_county_auctions rows
-- (created_at 2026-06-23 through 2026-08-19) faster than the periodic ArcGIS zone-linkage
-- backfill has re-run against them -- an ingestion/enrichment lag, not a regression.
--
-- Re-derived the exact live gap via pencil_dod_evaluate_county's own I-criterion SQL
-- (pg_get_functiondef): 30 rows fail (card_complete=639 of 673 = 94.9%). Breakdown:
--   - 19 rows: real well-formed parcel_id, genuinely unlinked in parcel_zones (jurisdiction_id
--     =931) -- confirmed via LEFT JOIN, never attempted by any prior backfill run
--   - 9 of those 19 also missing latitude/longitude/assessed_value (same Tax_Parcel_AGO
--     centroid query supplies both in one call)
--   - 11 rows OUT OF SCOPE for this GIS lever: parcel_id IS NULL (9 rows) or a placeholder
--     string ("MULTIPLE" / "Property Appraiser", 2 rows) -- needs a clerk/court-record parcel
--     lookup, different script family, logged as residual, not addressed here.
--
-- Ran scripts/gtm22j_putnam_i4_zone_backfill_20260823_batch.py (fork of the proven sibling
-- scripts/gtm22j_putnam_i3_zone_backfill_20260930_batch.py / gold_standard_shard2_putnam_i2_
-- zone_backfill.py -- identical Tax_Parcel_AGO -> Zoning_Districts_AGO centroid-intersect
-- method, same jurisdiction_id=931, same G-regression guard rail) against the 19 real-parcel_id
-- rows:
--   Tax_Parcel_AGO matched 17/19 (2 absent: 28-10-24-0000-0200-0000, 38-12-26-0000-0040-0002)
--   Zoning_Districts_AGO intersect matched 5/17 (12 no_zoning_polygon_at_centroid, honest
--     residual)
--   Zone codes returned: R-1A=1, R-2=3, R-2HA=1
--
-- First attempt (all 5) regressed G density 98.1 -> 98.0; the script's guard rail correctly
-- auto-reverted the whole batch (source-tag scoped DELETE) per CLAUDE.md constraint #4 rather
-- than accept a regression. Root-caused live via zoning_districts JOIN zone_standards
-- (jurisdiction_id=931): R-2HA (parcel 21-10-23-3646-0000-0010) is the ONLY one of the 3 codes
-- with zero zone_standards row (max_density_du_acre IS NULL) -- R-1A and R-2 both have full,
-- real standards (confidence_score=0.92, scraped 2026-02-08). This is the exact same failure
-- mode documented for R-2HA in scripts/gtm22j_putnam_i3_zone_backfill_20260930_batch.py's own
-- prior-run outcome note. Excluding only the single R-2HA parcel, manually inserted the
-- remaining 4 (R-1A x1, R-2 x3) via REST POST (same source tag, same script's intended INSERT
-- pattern) -- this migration captures that exact insert for idempotent replay.
--
-- Opportunistic fill-NULL-only PATCH (via the script's own REST PATCH path, NOT part of this
-- migration since it targets multi_county_auctions by id, not a schema/data migration in the
-- parcel_zones sense): mca_geo_patched=5, mca_value_patched=2. Never overwrote non-null values.
--
-- VERIFIED live before/after this session (pencil_dod_evaluate_county('putnam')):
--   BEFORE: I pass=false metric=94.9 (card_complete=639 of 673)   G pass=true metric=98.1
--   AFTER:  I pass=true  metric=95.5 (card_complete=643 of 673)   G pass=true metric=98.1 (unchanged)
-- I now PASSES (>=95% required, 95.5% achieved). Residual (honest, out of scope this run):
--   12 rows: real parcel_id, Tax_Parcel_AGO matched, but no_zoning_polygon_at_centroid
--   2 rows: parcel_id absent from Tax_Parcel_AGO entirely
--   1 row: R-2HA parcel excluded to avoid G regression (zone_standards gap for R-2HA jur 931)
--   11 rows: parcel_id NULL or placeholder string -- needs clerk/court-record lookup, different
--     script family (out of scope for this GIS lever)
--
-- Idempotent: guarded via NOT EXISTS on parcel_zones.parcel_id, safe to re-run.

INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source, effective_date)
SELECT v.parcel_id, v.parcel_id, 931, v.zone_code, v.zone_name,
       'gtm22j_i4/putnam_gis_live:Zoning_Districts_AGO+Tax_Parcel_AGO_centroid_intersect:20260823batch', '2026-08-23'
FROM (VALUES
  ('13-10-26-2550-0080-0210', 'R-1A', 'Residential, Single-Family'),
  ('18-13-28-3343-0070-0090', 'R-2', 'Residential, Mixed'),
  ('19-10-24-4074-0310-0250', 'R-2', 'Residential, Mixed'),
  ('26-09-24-4076-0710-0020', 'R-2', 'Residential, Mixed')
) AS v(parcel_id, zone_code, zone_name)
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones pz WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = 931
);
