-- Issue #19659 follow-up (verification session, 2026-09-02): CLAUDE.md M2
-- requires every new view to ship WITH (security_invoker=true). The
-- winnerdata.v_billable_ff_events_confirmation_status view added by
-- 20260901c_winnerdata_ff_confirmed_real_send_billing.sql shipped without
-- it -- closing that gap here. Read-only reporting view, winnerdata schema
-- is not PostgREST-exposed (service_role/postgres via Management API only),
-- so blast radius was low, but the mandate is unconditional.

ALTER VIEW winnerdata.v_billable_ff_events_confirmation_status
  SET (security_invoker = true);
