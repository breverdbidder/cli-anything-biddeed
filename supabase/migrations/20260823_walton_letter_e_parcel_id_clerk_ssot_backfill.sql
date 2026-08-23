-- GOLD STANDARD walton: letter E parcel_id backfill for 6 tax_deed rows
-- stamped "matched_clean" via the walton_post_auction_harvest RealForeclose-AID
-- pipeline (FORECLOSURE venue only), whose parcel_id was never populated
-- because Walton tax-deed sales are held on a separate clerk platform
-- (taxsmart.clerkofcourts.co.walton.fl.us, a Pioneer Technology Group jqGrid
-- ATS app) with its own parser (scripts/clerk_ssot/parsers/walton.py).
--
-- ROOT CAUSE (VERIFIED live, structural analog of the already-fixed st_lucie
-- E bug, see 20260811_gold_standard_stlucie_e_parcel_id_clerk_ssot_backfill.sql):
-- walton.py's parse_tax_deed() extracts ParcelID into CELL_FIELDS (the raw
-- jqGrid cell dict) but never forwards it into the rows_out dict that
-- run_parity.py inserts from -- so every clerk_ssot-inserted walton
-- tax_deed row was always going to land with parcel_id=NULL, not just this
-- batch. Companion code fix (forwards parcel_id into rows_out) shipped in
-- the same commit as this migration.
--
-- 7 additional E-gap rows (26CA000030, 25CA000608, 25CA000142, 19CA000472,
-- 25CA000348, 25CA000044, 26CA000062) are NOT fixed here -- confirmed live
-- this session that Walton's RealForeclose (walton.realforeclose.com) Parcel
-- ID field is genuinely empty or literal "MULTIPLE PARCELS" for all 7 across
-- 5 auction dates. No independently-scraped source currently carries a real
-- parcel_id for these. Reconfirms 3+ prior Walton sessions' documented
-- finding for 26CA000030/25CA000608, now extended to 5 more rows ingested
-- since. This is a genuine structural blocker, not a bug -- left untouched.
--
-- Fix (this session, VALUES sourced from a fresh
-- taxsmart.clerkofcourts.co.walton.fl.us GridSearchData JSON fetch via
-- walton.py's own _fetch_sale_status_rows() helper, re-confirmed live
-- immediately before writing this migration):
--   2026-0119TD -> 25-3N-19-19070-001-5200  (EnerGov Layer-4 APPRAISED_VALUE 400000)
--   2026-0121TD -> 25-3N-19-19070-000-8140  (EnerGov Layer-4 APPRAISED_VALUE 343403)
--   2026-0122TD -> 15-3N-17-06000-004-0010  (EnerGov Layer-4 APPRAISED_VALUE 88681)
--   2026-0125TD -> 19-1N-17-04000-001-0110  (EnerGov Layer-4 APPRAISED_VALUE 6323)
--   2026-0126TD -> 15-3N-20-28070-034-0310  (EnerGov Layer-4 APPRAISED_VALUE 7500)
--   2026-0127TD -> 36-3N-20-28140-000-014A  (EnerGov Layer-4 APPRAISED_VALUE 15200)
-- All 6 parcel_ids resolved live to a real EnerGov ArcGIS Layer-4 parcel
-- feature (services1.arcgis.com/TaXHPwWfIMuzJ7Ov/.../FeatureServer/4) with
-- non-null APPRAISED_VALUE/JUST_VALUE and geometry.
--
-- VERIFIED before/after (pencil_dod_evaluate_county, live RPC):
--   BEFORE: E {"pass": false, "metric": 91.5, "detail": "parcel_linked=140"}
--   AFTER:  see session report for exact post-migration figures.
-- Letter I is NOT expected to fully PASS from this migration alone (still
-- structurally capped by the same 7 RealForeclose-blocked rows plus a
-- genuine TIMESHARE-sentinel row, 25CA000531A) -- geo/value/zoning
-- enrichment for I is a separate follow-on pass (scripts/shard9_walton_cd_i_backfill.py),
-- out of scope for this migration, which touches ONLY parcel_id.
--
-- Idempotent: WHERE ... AND parcel_id IS NULL guards against double-apply.

UPDATE public.multi_county_auctions AS mca
SET parcel_id = v.parcel_id
FROM (VALUES
  ('2026-0119TD', '25-3N-19-19070-001-5200'),
  ('2026-0121TD', '25-3N-19-19070-000-8140'),
  ('2026-0122TD', '15-3N-17-06000-004-0010'),
  ('2026-0125TD', '19-1N-17-04000-001-0110'),
  ('2026-0126TD', '15-3N-20-28070-034-0310'),
  ('2026-0127TD', '36-3N-20-28140-000-014A')
) AS v(case_number, parcel_id)
WHERE mca.county = 'walton'
  AND mca.sale_type = 'tax_deed'
  AND mca.case_number = v.case_number
  AND mca.parcel_id IS NULL;
