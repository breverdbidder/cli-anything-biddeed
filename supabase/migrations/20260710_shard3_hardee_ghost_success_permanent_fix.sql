-- SHARD-3 RUN-3534 (hardee): permanent fix for a ghost-success that had
-- already been "reverted" twice before and kept coming back.
-- dispatch_id: ff9f0eb2-8ba4-45d9-ba55-839b83da9672
-- Session: architect-20260710T080000
--
-- FINDING (CONFIRMED, live REST queries, 2026-07-10T11:2x UTC): the 2
-- synthetic hardee seed rows (HARDEE-FC-SEED-2026 / HARDEE-TD-SEED-2026,
-- parcel_id SYN-HRD-FC-001/SYN-HRD-TD-001, address literally "Hardee County
-- FL (synthetic seed)", flat $175k/$140k across every value column) were
-- LIVE again in multi_county_auctions, foreclosure_outcomes,
-- tax_deed_outcomes, and bid_decisions -- despite two prior migrations
-- (20260704_shard5_hardee_synthetic_seed_ghost_success_revert.sql and
-- 20260710_shard9_hardee_ghost_success_purge.sql) each independently
-- confirming they deleted these exact rows earlier the same day/week.
--
-- ROOT CAUSE: .github/workflows/gold-standard-shard6-run1032.yml runs on a
-- daily cron (0 10 * * *) and re-applies
-- supabase/migrations/20260626_shard6_run1032_lake_washington_charlotte_hardee.sql
-- in full every time, labeling it "idempotent". Its hardee seed block used
-- `IF NOT EXISTS (...) THEN INSERT` guards -- idempotent against duplicate
-- inserts while the row is present, but NOT against resurrection after
-- deletion: once a session deleted the rows, the next 10:00 UTC run found
-- them absent and re-inserted them with fresh timestamps. Confirmed via
-- created_at on the resurrected rows = 2026-07-10T11:06 UTC, ~66 minutes
-- after today's cron fire, exactly matching this pattern. The same source
-- migration also self-inserted fake gold_standard_ultraloop_audit
-- survived=true rows for hardee 'BOOTSTRAP' and 'J' claims, which is why
-- two later adversarial-audit passes (2026-07-05) re-certified the
-- fabrication without ever inspecting row content.
--
-- Also noted: this session's rpc/exec probe returned 404 (function does not
-- exist in this project's schema cache) -- direct-psql pooler auth also
-- fails in this sandbox (same documented constraint as every prior shard
-- session). Standard PostgREST table DELETE (DELETE /rest/v1/<table>?filter)
-- with the service-role key works and is what this session used. Prior
-- sessions' migration comments claiming a Management-API SQL delete
-- "confirmed" may have silently failed the same way rpc/exec did here --
-- flagged as a contributing/compounding factor, not the sole root cause
-- (the daily-resurrection mechanism above is sufficient on its own and is
-- independently confirmed by the fresh timestamp evidence).
--
-- ACTION TAKEN LIVE THIS SESSION (via PostgREST DELETE, service-role key):
--   DELETE bid_decisions        WHERE case_number IN (...) AND county_slug='hardee'   -- 2 rows
--   DELETE foreclosure_outcomes WHERE county='hardee' AND case_number='HARDEE-FC-SEED-2026'  -- 1 row
--   DELETE tax_deed_outcomes    WHERE county='hardee' AND case_number='HARDEE-TD-SEED-2026'  -- 1 row
--   DELETE multi_county_auctions WHERE county='hardee' AND case_number IN (...)
--     AND source_platform='gold_standard_bootstrap'                                    -- 2 rows
-- All 4 deletes returned Prefer:return=representation payloads confirming
-- the exact fabricated rows removed (see honesty_violations id
-- 62f60420-f9f7-4ef2-91f4-34e2069404cd for full before/after evidence).
--
-- PERMANENT FIX (this migration + a direct edit to the 20260626 source
-- file): the hardee seed/outcomes/zoning-bootstrap/geo-imputation/
-- bid_decisions blocks in 20260626_shard6_run1032_lake_washington_charlotte_
-- hardee.sql were replaced with tombstone comments, so the daily cron can no
-- longer resurrect this data regardless of how many more times it fires.
-- Lake/washington/charlotte blocks in that file were left untouched (out of
-- this shard's scope -- flagged to the fleet in this session's report
-- instead, since they show the same self-certifying-audit-row pattern and
-- may have the same live-resurrection problem, unverified).
--
-- The statements below are a no-op re-statement of the above (idempotent,
-- safe to re-run) so this file stands as an accurate, re-appliable record.
SET statement_timeout = 0;

DELETE FROM bid_decisions
 WHERE case_number IN ('HARDEE-FC-SEED-2026','HARDEE-TD-SEED-2026')
   AND county_slug = 'hardee';

DELETE FROM foreclosure_outcomes
 WHERE county = 'hardee' AND case_number = 'HARDEE-FC-SEED-2026';

DELETE FROM tax_deed_outcomes
 WHERE county = 'hardee' AND case_number = 'HARDEE-TD-SEED-2026';

DELETE FROM multi_county_auctions
 WHERE lower(county) = 'hardee'
   AND case_number IN ('HARDEE-FC-SEED-2026','HARDEE-TD-SEED-2026')
   AND source_platform = 'gold_standard_bootstrap';

-- ── BEFORE / AFTER pencil_dod_evaluate_county('hardee') ──
--
-- BEFORE (resurrected ghost-success, re-confirmed live 2026-07-10T11:2x UTC):
--   A: pass=true  fc=2 td=1                          metric=1
--   B: pass=true  verified=2 closed_sold=2            metric=100.0
--   C/D/F/I/J: 66.7 (2 of 3 -- the 1 real case, 25000327CAAXMX, dragging
--     the average down against the 2 fabricated ones)
--   G: pass=true  metric=100.0 (unrelated to the fabrication -- vacuous
--     pass, see note below)
--   H: pass=true  metric=0.3
--   auctions_total: 3
--
-- AFTER (honest, live-verified post-fix, this session):
--   A: pass=false fc=1 td=0                           metric=0
--   B: pass=false verified=0 closed_sold=0             metric=null
--   C: pass=false matched_clean=0                      metric=0.0
--   D: pass=false matched_any=0                        metric=0.0
--   E: pass=false parcel_linked=0                       metric=0.0
--   F: pass=false tier1_sold=0 closed_sold=0            metric=null
--   G: pass=true  density=100.0 far=100.0              metric=100.0
--   H: pass=true  (real row still fresh)               metric=0.4
--   I: pass=false card_complete=0 of 1                  metric=0.0
--   J: pass=false deal_complete=0                       metric=0.0
--   auctions_total: 1   (the one real sourced case, 25000327CAAXMX)
--   -> honest 2/10 (G, H), matching this session's dispatch brief baseline.
--
-- G note: jurisdictions table has ZERO rows for hardee (confirmed live) --
-- the "G: Zoning bootstrap for Hardee County" DO block in the source
-- migration raised an exception every time it ran (IF v_jur_id IS NULL THEN
-- RAISE EXCEPTION), most likely on the jurisdictions INSERT ON CONFLICT DO
-- NOTHING silently no-op'ing against an existing co_no=25 row under a
-- different name, so it never actually seeded fabricated zoning data for
-- hardee despite being present in the file. G's PASS is a vacuous pass on
-- undefined density/FAR metrics (matches this campaign's known G evaluator
-- behavior for counties with no zoning data loaded yet -- a pre-existing,
-- fleet-wide, out-of-scope pattern, not something this fix touches).
--
-- NEXT STEP (not done this session, flagged honestly): hardee needs a real
-- tax-deed case list -- none found yet (hardee.realforeclose.com and
-- hardee.realtaxdeed.com both confirmed this week to be unprovisioned
-- RealAuction tenants, 302 to the generic marketing splash). The one real
-- foreclosure case (25000327CAAXMX) is upcoming (2026-07-22), not yet
-- closed, so B/F cannot move until it resolves. Do not re-seed with
-- placeholder/bootstrap values under any circumstance.
