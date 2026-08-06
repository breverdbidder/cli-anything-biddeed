-- ARCHITECT TRIAGE (2nd firing) for issue #18063 (dispatch a85bdebe, SHARD-2:
-- broward/seminole/jefferson/clay/pasco)
--
-- DIAGNOSIS (VERIFIED live, via Supabase Management API SQL endpoint after
-- both the REST gateway (521 from Cloudflare edge) and direct/pooler psql
-- (password auth failure) were unreachable from this session -- the Mgmt
-- API confirmed the project itself is ACTIVE_HEALTHY and a direct psql
-- connection reached a real Postgres server, so neither was an outage of
-- the DB itself, just two blocked access paths for this session):
--
-- DoD is genuinely still false: SELECT EXISTS(...certified) = false for all
-- 5 counties. This is NOT the same class of problem as the prior firing
-- (id=995, commit e78a1db3) -- that was a code bug (a fast-failed weekly-
-- OAuth-limit attempt silently exhausting the guard with zero real work).
-- This time attempt 2/2 (GHA run 31111152769) ran to completion and did
-- real, verified work (commit 2548d5e1): broward's I letter fixed via BCPA
-- ArcGIS + Census Geocoder backfill, now 10/10 PASS on loop_run_id=9421
-- (gold_standard_certifications.consecutive_gold=1 of the 2 needed for
-- certified=true -- confirmed live, last_verified_run=9421, no newer run
-- exists yet). seminole/clay/pasco's I-letter root cause was correctly
-- re-diagnosed as v_zoning_gold_standard_card zoning-linkage (not simple
-- data completeness as previously assumed) and self-corrected before
-- shipping a false claim. clay/pasco C/D remain blocked on a genuine new
-- RealAuction AJAX JS-wall/403 (previously curl-scrapeable, now requires a
-- browser session). jefferson B/F was reconfirmed structurally blocked on
-- its 12th firing -- 0-closed-sold denominator until its sale date of
-- 2026-08-19 (13 days from this triage), no re-exhaustion attempted.
--
-- The guard is exhausted again (attempts=2/max_attempts=2, status=blocked)
-- but this is now NORMAL exhaustion after one legitimate engineer session,
-- not a bug -- multi-county gold-standard re-certification is designed as
-- iterative multi-session work (see the many prior gold-standard-shardN-*
-- SUMMIT dispatches already run against these same counties). Reactivating
-- once more lets the existing cron tick (jobid 232, */20 * * * *) redispatch
-- a real session to bank broward's 2nd confirming gold run and continue the
-- clay/pasco/seminole zoning-linkage and RealAuction-JS-wall work.
--
-- SCOPE NOTE (not a blocker, flagged for awareness): jefferson cannot reach
-- certified=true before 2026-08-19 under any circumstances (0-closed-sold
-- denominator is a hard structural fact, not a bug) -- so this specific
-- 5-county DoD is guaranteed to stay false until at least that date even if
-- broward/seminole/clay/pasco all certify sooner. Re-firing this guard
-- before then will keep making real progress on the other 4 counties but
-- cannot itself close the DoD; that is expected, not a defect.
UPDATE public.cc_redispatch_guard
SET status = 'active',
    max_attempts = 3,
    last_error = 'architect_triage_18063_2nd_firing: attempt 2/2 (run 31111152769) succeeded and did real work (broward I fixed, consecutive_gold=1/2; seminole/clay/pasco I root-caused to zoning-linkage; jefferson B/F reconfirmed time-gated to 2026-08-19). DoD still false because broward needs 1 more confirming gold run and seminole/clay/pasco need real fixes still in progress -- not a bug, reactivating for legitimate continued work'
WHERE issue_number = 18063
  AND status = 'blocked';
