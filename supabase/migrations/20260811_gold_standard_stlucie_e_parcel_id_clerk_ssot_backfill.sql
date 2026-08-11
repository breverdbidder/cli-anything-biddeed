-- GOLD STANDARD st_lucie: letter E parcel_id backfill for 73 clerk_ssot stub
-- rows (dispatch: architect-triage, 2026-08-11).
--
-- ROOT CAUSE (confirmed live): scripts/clerk_ssot/run_parity.py's
-- diff_and_reconcile() inserts a bare stub row (county, sale_type,
-- case_number, auction_date, auction_status, parity_status, parity_source
-- ONLY) whenever a clerk-source case_number is missing from
-- multi_county_auctions -- by design, additive/corrective-only, no
-- enrichment. On 2026-08-10T16:02Z this fired for 73 st_lucie tax_deed
-- cases (26-018 .. 26-144, the full then-current AcclaimWeb docket window)
-- that calendar_sweep_mca_v3 had never independently harvested, jumping
-- st_lucie from 111/126-ish rows (last touched 2026-08-06/07) to 198 rows.
-- Those 73 rows carry NULL parcel_id/property_address/lat/lon/assessed_value,
-- collapsing letter E (parcel_linked) from PASS to 60.1% (119/198).
--
-- Compounding parser gap: scripts/clerk_ssot/parsers/st_lucie.py's
-- parse_tax_deed() reads AcclaimWeb dgResults cells[0,1,2,5,6,8] (Applicant,
-- Case Number, Certificate Number, Sale Date, Status, Property Owners) but
-- SKIPS cells[4] ("Parcel ID"), which the live table populates on every row
-- (verified: 100% of 174 rows on the page carry a folio-format Parcel ID,
-- e.g. '2404-510-0031-000/8'). The parser never had a parcel_id to pass to
-- run_parity.py's INSERT, so the field was always going to land NULL for
-- every clerk_ssot-inserted st_lucie tax_deed row, not just this batch.
--
-- FIX (this migration is a record of a REST/PostgREST-applied fix, run live
-- via targeted PATCH calls before this file was written -- see session
-- report): backfilled ONLY the parcel_id column on the 73 case numbers
-- below, scoped to (county='st_lucie', sale_type='tax_deed', case_number=X),
-- sourced from a fresh AcclaimWeb TributeWeb dgResults fetch this session
-- (2 HTTP calls: GET form + POST search, 73/73 case numbers matched).
-- property_address/lat/lon/assessed_value/zone linkage NOT touched --
-- st_lucie's parcel_zones table keys on bare PA tax-account numbers
-- (e.g. '100082'), a different format from the AcclaimWeb folio format
-- (e.g. '2404-510-0031-000/8'), so a card_complete/zone fix (letter I)
-- requires a separate Property Appraiser/GIS crosswalk pass, scoped out
-- this session (see NOT TRACTABLE note in session report). Letter C's 32
-- non-clean rows are correctly excluded by design (31 are clerk-confirmed
-- CLERK_SSOT_CANCELLED sales, 1 is a legitimate matched_divergent) --
-- not a bug, not touched.
--
-- VERIFIED before/after (pencil_dod_evaluate_county, live RPC):
--   BEFORE: E {"pass": false, "metric": 60.1, "detail": "parcel_linked=119"}
--   AFTER:  E {"pass": true,  "metric": 97.0, "detail": "parcel_linked=192"}
-- All other letters (A/B/C/D/F/G/H/I/J) unchanged -- zero regression.
--
-- This file is a no-op / idempotent record migration (data was written via
-- PostgREST PATCH, not raw SQL, per HARD RULES preferring REST over psql in
-- this sandbox). Re-running it is safe: same VALUES, same idempotent
-- UPDATE ... WHERE, no destructive statements.

UPDATE public.multi_county_auctions AS mca
SET parcel_id = v.parcel_id
FROM (VALUES
  ('26-018', '3425-706-0193-000/0'),
  ('26-019', '1301-612-0386-000/5'),
  ('26-020', '3420-585-2163-000/1'),
  ('26-022', '3420-670-0725-000/6'),
  ('26-023', '2427-601-0022-010/5'),
  ('26-028', '1428-702-1198-000/3'),
  ('26-030', '2409-707-0048-000/9'),
  ('26-031', '2415-601-0414-000/0'),
  ('26-033', '2417-502-0010-000/0'),
  ('26-037', '3419-515-0274-000/7'),
  ('26-038', '3420-540-0422-000/2'),
  ('26-039', '3420-565-0148-000/4'),
  ('26-040', '3420-585-2553-000/2'),
  ('26-041', '3420-620-0042-000/9'),
  ('26-042', '3420-640-0068-000/9'),
  ('26-043', '3420-660-0146-000/2'),
  ('26-046', '4426-807-0039-000/9'),
  ('26-048', '4412-511-0005-000/1'),
  ('26-049', '4314-505-0175-000/3'),
  ('26-050', '4314-505-0176-000/0'),
  ('26-051', '4314-505-0177-000/7'),
  ('26-052', '4314-505-0178-000/4'),
  ('26-053', '4314-505-0179-000/1'),
  ('26-058', '1430-700-0012-000/0'),
  ('26-063', '2404-711-0022-000/9'),
  ('26-064', '2404-818-0026-000/5'),
  ('26-065', '3420-560-2336-000/8'),
  ('26-066', '3420-695-1461-000/1'),
  ('26-067', '2405-720-0004-000/8'),
  ('26-068', '2405-501-0170-000/9'),
  ('26-070', '2404-716-0006-000/6'),
  ('26-071', '2405-524-0007-000/7'),
  ('26-072', '1431-701-0266-000/1'),
  ('26-073', '1432-807-0085-000/6'),
  ('26-074', '2404-514-0007-000/3'),
  ('26-075', '2404-516-0022-000/0'),
  ('26-076', '2404-702-0139-000/4'),
  ('26-077', '2405-501-0076-000/0'),
  ('26-078', '2420-601-0036-000/2'),
  ('26-079', '3323-655-0008-000/9'),
  ('26-080', '2409-602-0110-000/3'),
  ('26-082', '2409-823-0020-000/4'),
  ('26-085', '2402-503-0089-000/1'),
  ('26-092', '2410-709-0108-000/8'),
  ('26-093', '2415-601-0368-000/2'),
  ('26-094', '2408-502-0052-000/8'),
  ('26-095', '2415-601-0207-000/6'),
  ('26-098', '4408-500-0002-000/3'),
  ('26-099', '1431-801-0194-100/3'),
  ('26-101', '2405-601-0499-000/8'),
  ('26-102', '2409-605-0076-000/1'),
  ('26-104', '2430-601-0021-000/5'),
  ('26-106', '3420-535-1107-000/9'),
  ('26-108', '2421-515-0040-000/2'),
  ('26-109', '3420-670-0089-000/5'),
  ('26-110', '1433-701-0086-000/1'),
  ('26-111', '2405-601-0325-000/8'),
  ('26-112', '2408-801-0126-000/6'),
  ('26-118', '3420-510-0322-000/8'),
  ('26-120', '2415-601-0246-000/1'),
  ('26-122', '2427-604-0267-000/0'),
  ('26-123', '3323-823-0030-000/7'),
  ('26-125', '3323-940-0074-000/7'),
  ('26-126', '3420-585-1234-000/3'),
  ('26-131', '4416-601-0020-000/0'),
  ('26-132', '4423-701-0014-000/4'),
  ('26-135', '4412-511-0004-000/4'),
  ('26-137', '2311-800-0031-000/3'),
  ('26-138', '2409-602-0001-000/6'),
  ('26-140', '3323-881-0030-000/7'),
  ('26-141', '3325-544-0052-000/7'),
  ('26-143', '3420-501-0027-000/2'),
  ('26-144', '3420-505-0589-000/1')
) AS v(case_number, parcel_id)
WHERE mca.county = 'st_lucie'
  AND mca.sale_type = 'tax_deed'
  AND mca.case_number = v.case_number
  AND mca.parcel_id IS NULL;
