-- Ops Dashboard Phase 2a/2b: least-privilege DB roles for workers/ops-dashboard/
--
-- dashboard_reader: SELECT-only on the four objects the read tiles pull from.
-- dashboard_agent:  EXECUTE-only on the three RPCs the action buttons fire —
--                    nothing broader (no table grants at all).
--
-- Passwords are generated and set out-of-band via the Supabase Management API
-- in the same session that applied this migration, then stored in
-- vault via ecu_set_vault_secret(). Never committed to source — see
-- CREDENTIAL HANDLING in CLAUDE.md.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dashboard_reader') THEN
    CREATE ROLE dashboard_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION CONNECTION LIMIT 5;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dashboard_agent') THEN
    CREATE ROLE dashboard_agent LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION CONNECTION LIMIT 5;
  END IF;
END$$;

-- dashboard_reader: SELECT-only on the 4 ops-dashboard read objects.
GRANT SELECT ON public.ssot_facts TO dashboard_reader;
GRANT SELECT ON public.v_ssot_master TO dashboard_reader;
GRANT SELECT ON public.agent_ops_log TO dashboard_reader;
GRANT SELECT ON public.gold_standard_scoreboard TO dashboard_reader;

-- ssot_facts has RLS enabled with zero existing policies, and agent_ops_log
-- has RLS forced with only a service_role-only ALL policy — both need an
-- explicit dashboard_reader SELECT policy or the GRANT above returns zero
-- rows.
--
-- v_ssot_master and gold_standard_scoreboard are both created with
-- `security_invoker=true` (deliberate RLS-safe hardening — the querying
-- role's own privileges apply, not the view owner's). That means a SELECT
-- grant on the view alone is not enough: dashboard_reader also needs SELECT
-- + an RLS policy on every base table the view reads through it —
-- ssot_registry_components + ssot_registry_projects (v_ssot_master) and
-- gold_standard_county_status (v_ssot_master's sibling gold_standard_scoreboard).
-- Discovered live via pg_depend during grant verification (SET ROLE test
-- failed with "permission denied for table ssot_registry_components" before
-- this block was added) — logged as a deviation in the session report.
DROP POLICY IF EXISTS dashboard_reader_select ON public.ssot_facts;
CREATE POLICY dashboard_reader_select ON public.ssot_facts
  FOR SELECT TO dashboard_reader USING (true);

DROP POLICY IF EXISTS dashboard_reader_select ON public.agent_ops_log;
CREATE POLICY dashboard_reader_select ON public.agent_ops_log
  FOR SELECT TO dashboard_reader USING (true);

GRANT SELECT ON public.ssot_registry_components TO dashboard_reader;
GRANT SELECT ON public.ssot_registry_projects TO dashboard_reader;
GRANT SELECT ON public.gold_standard_county_status TO dashboard_reader;

DROP POLICY IF EXISTS dashboard_reader_select ON public.ssot_registry_components;
CREATE POLICY dashboard_reader_select ON public.ssot_registry_components
  FOR SELECT TO dashboard_reader USING (true);

DROP POLICY IF EXISTS dashboard_reader_select ON public.ssot_registry_projects;
CREATE POLICY dashboard_reader_select ON public.ssot_registry_projects
  FOR SELECT TO dashboard_reader USING (true);

DROP POLICY IF EXISTS dashboard_reader_select ON public.gold_standard_county_status;
CREATE POLICY dashboard_reader_select ON public.gold_standard_county_status
  FOR SELECT TO dashboard_reader USING (true);

-- dashboard_agent: EXECUTE-only allowlist. No SELECT/INSERT/UPDATE/DELETE
-- grant on any table — this role can only fire these three SECURITY DEFINER
-- RPCs, each of which pulls its own credentials from vault internally.
GRANT EXECUTE ON FUNCTION public.gha_create_issue(text, text, text) TO dashboard_agent;
GRANT EXECUTE ON FUNCTION public.fire_workflow_dispatch(text, text, text, jsonb) TO dashboard_agent;
GRANT EXECUTE ON FUNCTION public.dispatch_skill_audit() TO dashboard_agent;

-- NOTE (finding, not fixed here — out of scope for this migration):
-- gha_create_issue and dispatch_skill_audit both already carry a PUBLIC
-- EXECUTE grant (proacl shows `=X/postgres`), i.e. anon/authenticated can
-- already call them today regardless of this migration. fire_workflow_dispatch
-- is correctly locked to postgres/service_role only. See session report.
