-- SHARD-9 run2820 3rd continuation (osceola/holmes/walton/santa_rosa/sumter)
-- dispatch_id: 1745c67a-1636-4250-939e-d79532ccb20b
-- Session: architect-20260704T000000
--
-- NET DB EFFECT OF THIS SESSION: zero drift vs the true pre-session state, after a
-- self-inflicted mid-session mistake was found and corrected. Documented here in full
-- per HONESTY PROTOCOL / SHIP GATE -- this session made a real error and is not hiding it.
--
-- WHAT HAPPENED:
--   1. This session ran the shared, county-parameterized public.refresh_parity_tier1_outcomes()
--      against all 5 shard counties as part of an ULTRALOOP-orchestrated harvest+refresh+verify
--      pipeline. For santa_rosa and walton, this function's unconditional wipe-first design
--      (UPDATE ... SET parity_status=NULL, parity_source=NULL WHERE auction_status IN (closed
--      statuses)) nulled parity_status/parity_source on rows that were matched via
--      public.realforeclose_aids (a DIFFERENT, already-vetted tier1 source this function does
--      not know about), and the function's own rematch logic (which only joins
--      tax_deed_outcomes/foreclosure_outcomes) could not restore them.
--   2. The adversarial verify stage of this session's workflow correctly caught the santa_rosa
--      drop (100.0% -> 51.7%) as a metric change, but WRONGLY concluded (based on reading only
--      an OLDER same-shard session report, commit 66822de3 / SHARD9_RUN2820_SESSION_REPORT.md,
--      which predates the realforeclose_aids discovery) that the pre-session 100.0% figure was
--      itself a ghost-success and that the wipe had "correctly" exposed it. Acting on that
--      conclusion, this session RESTORED the wipe (re-nulled all 58 santa_rosa rows) --
--      compounding the error instead of fixing it.
--   3. Before finalizing, this session discovered a NEWER same-shard migration
--      (20260704_shard9_run2820_walton_santarosa_realforeclose_aids_cd.sql, commit a11ab113)
--      that supersedes the older report: it independently verified realforeclose_aids as a
--      real, resolvable source (live clerk document URLs, organic multi-batch scrape history)
--      for both santa_rosa and walton, and had already re-populated santa_rosa's labels and
--      added 5 new walton matches on that basis. That migration is the correct, most-current
--      finding.
--   4. This migration re-applies that same, already-idempotent UPDATE pattern to restore both
--      counties to their true, verified-genuine state, undoing this session's own collateral
--      damage (walton lost 2 rows to the same wipe-without-restore mechanism; santa_rosa was
--      restored then wrongly re-reverted, now restored again).
--
-- VERIFIED FINAL STATE (pencil_dod_evaluate_county, live, this session):
--   santa_rosa: C=100.0% D=100.0% (matched_clean=58) -- matches this session's own PRE-change
--               baseline exactly. Net zero drift.
--   walton:     C=30.0% D=30.0% (matched_clean=9) -- matches this session's own PRE-change
--               baseline exactly. Net zero drift caused by this session.
--               (Walton's C/D floor as of a11ab113/50.0% (matched_clean=15) was ALREADY gone
--               before this session began -- pre-existing gap, not diagnosed here, not caused
--               by this session. Flagged for a dedicated follow-up.)
--
-- LESSON (for future sessions targeting these counties or reusing
-- refresh_parity_tier1_outcomes): before running that function against ANY county, check
-- `SELECT count(*) FROM realforeclose_aids WHERE county_slug = '<county>'` first. If non-zero,
-- the function's wipe-first design WILL destroy realforeclose_aids-backed matches that its own
-- rematch pass cannot restore -- re-apply the realforeclose_aids UPDATE pattern from
-- 20260704_shard9_run2820_walton_santarosa_realforeclose_aids_cd.sql immediately afterward, in
-- the same session, before evaluating/reporting the letter.
--
-- Idempotent: parity_status IS DISTINCT FROM guard; safe to re-run.

BEGIN;

UPDATE public.multi_county_auctions mca
   SET parity_status = 'matched_clean',
       parity_source = 'tier1_realforeclose_santa_rosa',
       updated_at    = now()
  FROM public.realforeclose_aids ra
 WHERE ra.county_slug = 'santa_rosa'
   AND mca.county      = 'santa_rosa'
   AND (
     normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
     OR (mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL AND mca.parcel_id = ra.parcel_id)
   )
   AND mca.parity_status IS DISTINCT FROM 'matched_clean';

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
   AND mca.parity_status IS DISTINCT FROM 'matched_clean';

COMMIT;
