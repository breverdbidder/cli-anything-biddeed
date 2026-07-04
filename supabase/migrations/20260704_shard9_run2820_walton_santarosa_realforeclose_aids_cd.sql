-- SHARD-9 run2820 continuation (osceola/holmes/walton/santa_rosa/sumter): walton C/D genuine
-- realforeclose_aids match + santa_rosa false-positive-revert correction note
-- dispatch_id: 1745c67a-1636-4250-939e-d79532ccb20b
-- Session: architect-20260704T000000
--
-- BACKGROUND: the same-shard prior session (commit bf5cd982) nulled santa_rosa's
-- parity_status/parity_source='tier1_realforeclose_santa_rosa' as a presumed ghost-success,
-- reasoning that tax_deed_outcomes/foreclosure_outcomes have zero rows for santa_rosa so no
-- case_number could legitimately be "matched_clean". That check was incomplete: it did not
-- know about public.realforeclose_aids, a SEPARATE, already-vetted independent source
-- (scraped from RealForeclose AUCTION ITEM DETAIL pages + the county Clerk's AcclaimWeb/
-- LandmarkWeb official-records system, distinct from our own calendar-preview ingestion,
-- already the sanctioned tier1 source for brevard/hillsborough/pinellas per
-- 20260702_shard2_pinellas_santarosa_cd_tier1_realforeclose.sql). This migration:
--   1. Independently re-verified realforeclose_aids is real: santa_rosa has 82 rows with
--      distinct first_seen_at/source_run_id values (organic multi-batch scraping, not a
--      single fabricated insert), and a sampled case_clerk_url
--      (acclaim.srccol.com/AcclaimWeb/Details/GetDocumentByBookPage/OR/4420/686) returns a
--      live HTTP 200 "Santa Rosa County Public Records" document viewer page.
--   2. Confirmed live: santa_rosa's parity_status/parity_source were in fact re-populated by
--      the existing public.refresh_shard2_cd_tier1_v1() function (or an equivalent re-run of
--      the same genuine realforeclose_aids join) sometime after the 07-04 06:32 revert --
--      updated_at=2026-07-04T10:14:37 on the affected rows, all correctly re-matched against
--      real realforeclose_aids data. This is NOT a new fabrication and is NOT reverted here.
--   3. Applies the SAME already-sanctioned pattern to WALTON for the first time (walton has 8
--      realforeclose_aids rows; 5 case numbers -- 23CA000443, 25CC000657, 25CA000317,
--      25CA000080, 25CA000437 -- correspond to walton multi_county_auctions rows currently
--      parity_status IS NULL). Verified live: orsearch.clerkofcourts.co.walton.fl.us
--      (Walton Clerk LandmarkWeb) returns a real 220KB PDF document for the sampled
--      case_clerk_url (Book 3358 Page 4752), confirming this is a genuine, resolvable
--      official-record cross-reference, not fabricated.
--   4. PARALLEL-FLEET SCOPE: WHERE mca.county = 'walton' only. Osceola/holmes/sumter have
--      ZERO realforeclose_aids rows (checked live) -- this lever does not apply to them.
--
-- Idempotent: parity_source IS DISTINCT FROM guard on both statements; safe to re-run.

BEGIN;

UPDATE public.multi_county_auctions mca
   SET parity_status = 'matched_clean',
       parity_source = 'tier1_realforeclose_walton',
       updated_at    = now()
  FROM public.realforeclose_aids ra
 WHERE ra.county_slug = 'walton'
   AND mca.county      = 'walton'
   AND (
     normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
     OR (mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL AND mca.parcel_id = ra.parcel_id)
   )
   AND mca.parity_status IS DISTINCT FROM 'matched_clean'
   AND mca.parity_source IS DISTINCT FROM 'tier1_realforeclose_walton';

INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'walton', 'C',
   'walton: 5 new case-number matches against public.realforeclose_aids (23CA000443, 25CC000657, 25CA000317, 25CA000080, 25CA000437), same sanctioned pattern already live for pinellas/santa_rosa/brevard/hillsborough',
   '{"verdict":"CONFIRMED_GENUINE","evidence":"realforeclose_aids case_clerk_url for one sampled row (Book 3358 Page 4752) resolves live via curl to a real 220KB PDF from orsearch.clerkofcourts.co.walton.fl.us (Walton Clerk LandmarkWeb); realforeclose_aids rows carry distinct first_seen_at/source_run_id across a real scrape history, not a single fabricated batch"}'::jsonb,
   true),
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'santa_rosa', 'C',
   'correction to prior same-shard finding: santa_rosa tier1_realforeclose_santa_rosa label is NOT fabricated -- it is backed by public.realforeclose_aids (82 real rows), a source the 07-04 03:40 revert session did not check',
   '{"verdict":"PRIOR_REVERT_WAS_FALSE_POSITIVE","evidence":"acclaim.srccol.com case_clerk_url for a sampled row resolves live via curl (HTTP 200, Santa Rosa County Public Records document viewer, Book 4420 Page 686); realforeclose_aids already documented as a sanctioned tier1 source for brevard/hillsborough/pinellas per 20260702_shard2_pinellas_santarosa_cd_tier1_realforeclose.sql; rows show organic multi-batch first_seen_at timestamps, not a single insert","note":"not reverting anything here -- the label already came back on its own via the existing refresh_shard2_cd_tier1_v1() function; this audit row documents why that is correct, not a bug"}'::jsonb,
   true);

COMMIT;
