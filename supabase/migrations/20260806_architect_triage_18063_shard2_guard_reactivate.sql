-- ARCHITECT TRIAGE for issue #18063 (dispatch ccb82791, SHARD-2:
-- broward/seminole/jefferson/clay/pasco)
--
-- DIAGNOSIS (VERIFIED live):
-- The 08:00Z engineer session (GHA run 31083164153, and 4 sibling runs
-- 31083164082/117/184/241 for the same 08:01:01Z fleet wave) never executed
-- any tool call. `claude -p` printed "You've hit your weekly limit · resets
-- 1pm (UTC)" and exited 1 within ~2s of starting. The retry loop in
-- cc-runner-ghonly.yml only retries on a transient-error regex
-- ('API Error: 5xx|server error|overloaded|rate.?limit|timeout'); "weekly
-- limit" does not match that pattern, so it fast-failed on attempt 1/1
-- instead of retrying. This is the same CC-OAuth-Max-plan weekly metering
-- ceiling documented in docs/FLEET-LANE-ROUTING.md and previously diagnosed
-- in decision_log id=634/635 (2026-07-27, issues #15030/#15031).
--
-- No code ran and no data changed for broward/seminole/jefferson/clay/pasco
-- this session, so there was nothing to root-cause on the DoD side beyond
-- confirming it: SELECT EXISTS(...) is false because none of the 5 counties
-- has certified=true in gold_standard_certifications (all still mid-flight
-- on real residual work per pencil_dod_evaluate_county: broward/seminole/
-- clay/pasco fail I on card-completeness, clay/pasco also fail C/D parity,
-- jefferson fails B/F on a genuine 0-closed-sold denominator — none of this
-- is a certification-gate anomaly like the charlotte precedent, it's real
-- remaining scraper/enrichment work for a future engineer session).
--
-- The cc_redispatch_guard row for #18063 is stuck: attempts=1/max_attempts=1,
-- status='blocked' (COST-FIX-3 default of max_attempts=1 means a single
-- fast-failed attempt permanently exhausts the guard). The auto-triage
-- dispatch that fired this session created a NEW issue (#18273) and its own
-- guard row rather than reactivating #18063's row (auto_register_cc_guard()
-- only reactivates on an INSERT whose github_issue_number matches an
-- existing blocked row — #18273 != #18063).
--
-- It is now 2026-08-06T14:2x:00Z, past the stated "resets 1pm (UTC)" reset
-- time; the fleet is confirmed live again (dozens of unrelated GHA runs
-- succeeded across 14:23-14:29Z, and a manual public.cc_redispatch_tick()
-- probe this session executed cleanly against 4 other active guards). The
-- correct fix is an operational retry, not a code/data bug fix: reactivate
-- #18063's guard with one more attempt so the next cron tick (jobid 232,
-- */20 * * * *) re-fires cc-runner-ghonly.yml for a real engineer session.
UPDATE public.cc_redispatch_guard
SET status = 'active',
    max_attempts = 2,
    last_error = 'architect_triage_18063: prior attempt fast-failed on CC Max-plan weekly OAuth limit ("You''ve hit your weekly limit · resets 1pm (UTC)"), not a code/data bug; reactivated for retry post-reset'
WHERE issue_number = 18063
  AND status = 'blocked';
