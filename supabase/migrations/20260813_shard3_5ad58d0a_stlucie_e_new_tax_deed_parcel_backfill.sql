-- GOLD STANDARD st_lucie: letter E (parcel_linked) backfill for 14 NEW
-- tax_deed cases that appeared after the 2026-08-11 clerk_ssot backfill
-- (dispatch 5ad58d0a, shard-3, 2026-08-13).
--
-- ROOT CAUSE (confirmed live): scripts/clerk_ssot/run_parity.py continues to
-- insert bare stub rows for any new St Lucie AcclaimWeb TributeWeb case
-- number it discovers (county, sale_type, case_number, auction_date,
-- auction_status only -- no enrichment, by design). Between 2026-08-11 and
-- 2026-08-13 the clerk docket advanced to include 14 new tax_deed cases
-- (26-145, 26-150, 26-153, 26-159, 26-162, 26-164, 26-165, 26-166, 26-168,
-- 26-169, 26-170, 26-172, 26-174, 26-176), each landing with parcel_id NULL
-- for the same reason documented in the 2026-08-11 migration
-- (20260811_gold_standard_stlucie_e_parcel_id_clerk_ssot_backfill.sql):
-- clerk_ssot's parser never reads the AcclaimWeb dgResults table's
-- cell[4] ("Parcel ID" column), only cells[0,1,2,5,6,8].
--
-- Combined with the 6 known non-tractable dead-end foreclosure rows
-- (2024CA001834, 2025CC001033, 2023CA002852, 2024CA000330, 2024CA000214,
-- 2025CA002738 -- aircraft/timeshare/multi-parcel/placeholder collateral,
-- Cloudflare/500/403/405-walled across many prior attempts, NOT touched
-- this session), st_lucie had 20 NULL-parcel_id rows total, dropping letter
-- E to 90.7% (196/216).
--
-- FIX (applied live via REST/PostgREST PATCH, this file is the record):
-- re-ran the exact known-good AcclaimWeb TributeWeb channel from the
-- 2026-08-11 migration -- GET https://acclaimweb.stlucieclerk.gov/TributeWeb/
-- to harvest the ASP.NET WebForms hidden fields (__VIEWSTATE etc.), then
-- POST GrpSaleDate=radDateRange, txtFrom=today-120d, txtTo=today+180d,
-- ddStatus=0 (<Select All>), txtPageSize=500 -- and read the returned
-- #dgResults table's cell[4] (Parcel ID, folio format e.g.
-- '3420-625-0735-000/9') keyed by cell[1] (Case Number). All 14 target case
-- numbers matched on the first fetch (116 total rows in the current
-- date-range window), all with status=SALE (still scheduled, none
-- cancelled/redeemed/pulled). Only the parcel_id column was written, scoped
-- to (county='st_lucie', sale_type='tax_deed', case_number=X) -- no other
-- columns touched, matching the 2026-08-11 fix's scope.
--
-- The 6 known dead-end foreclosure case numbers were NOT re-attempted --
-- no new channel was found this session, per the boundary instruction.
--
-- VERIFIED before/after (pencil_dod_evaluate_county, live RPC):
--   BEFORE: E {"pass": false, "metric": 90.7, "detail": "parcel_linked=196"}
--   AFTER:  E {"pass": true,  "metric": 97.2, "detail": "parcel_linked=210"}
-- All other letters (A/B/C/D/F/G/H/I/J) unchanged -- zero regression
-- (A=106 fc/td, B=100.0, C=82.4/false unchanged, D=98.1, F=100.0, G=96.0,
-- H=0.0, I=55.1/false unchanged, J=98.6 -- identical to the pre-fix read).
-- Remaining 6 unlinked rows are exactly the 6 known dead-ends; 216 - 210 = 6.
--
-- This file is a no-op / idempotent record migration (data was written via
-- PostgREST PATCH, not raw SQL, per HARD RULES preferring REST over psql in
-- this sandbox). Re-running it is safe: same VALUES, same idempotent
-- UPDATE ... WHERE, no destructive statements.

UPDATE public.multi_county_auctions AS mca
SET parcel_id = v.parcel_id
FROM (VALUES
  ('26-145', '3420-625-0735-000/9'),
  ('26-150', '2430-601-0039-000/4'),
  ('26-153', '3420-670-0069-000/9'),
  ('26-159', '4304-502-0141-000/6'),
  ('26-162', '1416-601-0042-000/1'),
  ('26-164', '2405-601-0185-000/4'),
  ('26-165', '2405-601-0186-000/1'),
  ('26-166', '2405-601-0244-010/9'),
  ('26-168', '2404-609-0098-000/8'),
  ('26-169', '1428-702-1274-000/0'),
  ('26-170', '3420-505-0815-000/5'),
  ('26-172', '2309-322-0005-000/8'),
  ('26-174', '4427-600-0093-000/3'),
  ('26-176', '2405-601-0126-000/3')
) AS v(case_number, parcel_id)
WHERE mca.county = 'st_lucie'
  AND mca.sale_type = 'tax_deed'
  AND mca.case_number = v.case_number
  AND mca.parcel_id IS NULL;
