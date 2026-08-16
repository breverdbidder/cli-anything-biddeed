-- H5_SECDEF_PUBLIC_GRANT: wire the existing detector into active enforcement.
--
-- Root cause (issue #19168): ALTER DEFAULT PRIVILEGES ... REVOKE EXECUTE ON
-- FUNCTIONS FROM PUBLIC is correctly recorded in pg_default_acl (confirmed via
-- direct pg_default_acl/aclexplode inspection -- grants to named roles like
-- postgres/service_role DO get applied to new functions from that default-acl
-- row), but the implicit "PUBLIC gets EXECUTE" default that PostgreSQL applies
-- to every newly created function is NOT suppressible via that mechanism in
-- this instance (PostgreSQL 17.6) -- reproduced repeatedly and consistently:
-- toggling GRANT/REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC at the default-acl
-- layer made zero difference to whether new functions carried PUBLIC EXECUTE,
-- in both the public schema and a brand-new throwaway schema, while the same
-- default-acl mechanism DOES work correctly for TABLES (relation objtype) in
-- the same schema. No event trigger, pg_cron job, or migration template was
-- found to be re-granting PUBLIC (all 8 registered event triggers and all
-- cron.job rows were inspected; none touch generic public-schema function
-- grants). This matches known Postgres behavior where CREATE FUNCTION's
-- hard-wired "world default" (EXECUTE to PUBLIC) can only be added to via
-- default-privilege GRANTs, never suppressed by default-privilege REVOKEs --
-- the only way to prevent it is an explicit REVOKE issued after each function
-- is created. That is exactly the event-trigger-based safety net this issue
-- already anticipated as a fallback; it is now the actual and only fix, not
-- just a safety net for an otherwise-working default-privilege reconfiguration.
--
-- Fix: extend the existing ddl_command_end event trigger function
-- (evt_capture_schema_health_on_ddl, fired by trg_event_capture_schema_health)
-- to identify newly created/altered SECURITY DEFINER functions in the public
-- schema that still carry PUBLIC EXECUTE (H5's own definition), issue
-- REVOKE EXECUTE ... FROM PUBLIC on them immediately, and log the auto-
-- remediation to schema_health_enforcement_log as an already-resolved row
-- (auditable, matches the table's existing resolved_at/resolved_reason/
-- resolved_by columns). Identification uses cmd.objid::regprocedure directly
-- from pg_event_trigger_ddl_commands() rather than assert_schema_health()'s
-- text-based object_name (which always renders "name()" regardless of actual
-- argument list, and would misidentify overloaded functions for a REVOKE).
-- H5 is excluded from the generic H1-H4 logging loop below to avoid a
-- duplicate/conflicting unresolved row for the same object+rule_code.
--
-- Scope: PUBLIC only, per H5's own definition and this issue's guardrail --
-- anon/authenticated are never touched here.

CREATE OR REPLACE FUNCTION public.evt_capture_schema_health_on_ddl()
 RETURNS event_trigger
 LANGUAGE plpgsql
 SET search_path TO 'public', 'pg_catalog'
AS $function$
DECLARE
  affected_names text[];
  cmd record;
  finding record;
  fn_oid oid;
  fn_ident text;
BEGIN
  -- Only consider DDL that touched public schema objects
  FOR cmd IN SELECT * FROM pg_event_trigger_ddl_commands() LOOP
    IF cmd.schema_name = 'public' OR cmd.schema_name IS NULL THEN
      affected_names := array_append(affected_names, cmd.object_identity);
    END IF;

    -- H5 auto-remediation: revoke PUBLIC EXECUTE right now, not just log it.
    IF cmd.object_type = 'function' AND cmd.schema_name = 'public' THEN
      SELECT p.oid INTO fn_oid
      FROM pg_proc p
      WHERE p.oid = cmd.objid
        AND p.prosecdef = true
        AND has_function_privilege('public', p.oid, 'EXECUTE');

      IF fn_oid IS NOT NULL THEN
        fn_ident := fn_oid::regprocedure::text;
        EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', fn_ident);

        INSERT INTO public.schema_health_enforcement_log(
          object_name, rule_code, severity, detail, introduced_by_tag,
          resolved_at, resolved_reason, resolved_by
        )
        VALUES (
          'public.' || fn_ident, 'H5_SECDEF_PUBLIC_GRANT', 'WARN',
          'SECURITY DEFINER function grants EXECUTE to PUBLIC -- REVOKE and GRANT to specific role',
          tg_tag, now(), 'auto-revoked EXECUTE FROM PUBLIC on ddl_command_end', 'trg_event_capture_schema_health'
        )
        ON CONFLICT ON CONSTRAINT uniq_active_violation DO NOTHING;
      END IF;
    END IF;
  END LOOP;

  IF affected_names IS NULL OR array_length(affected_names, 1) IS NULL THEN
    RETURN;
  END IF;

  -- Run assert_schema_health and record any ERROR/WARN findings for those objects
  FOR finding IN
    SELECT h.severity, h.object_name, h.rule_code, h.detail
    FROM public.assert_schema_health() h
    WHERE h.severity IN ('ERROR','WARN')
      AND h.rule_code <> 'H5_SECDEF_PUBLIC_GRANT'  -- handled above with precise auto-remediation
      AND EXISTS (
        SELECT 1 FROM unnest(affected_names) obj
        -- Match object name flexibly — affected_names has fully qualified names,
        -- assert_schema_health returns names like 'public.foo()' or 'public.foo'
        WHERE h.object_name LIKE '%' || regexp_replace(obj, '\(.*\)', '') || '%'
          OR h.object_name = obj
      )
  LOOP
    -- Insert or update (if already present unresolved, we keep the earlier timestamp)
    INSERT INTO public.schema_health_enforcement_log(
      object_name, rule_code, severity, detail, introduced_by_tag
    )
    VALUES (
      finding.object_name, finding.rule_code, finding.severity, finding.detail, tg_tag
    )
    ON CONFLICT ON CONSTRAINT uniq_active_violation DO NOTHING;
  END LOOP;
END
$function$;
