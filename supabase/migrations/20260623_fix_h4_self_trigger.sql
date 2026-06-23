-- Fix H4_NULL_UNSAFE_CMP false-positive self-trigger in assert_schema_health
--
-- Root cause: the H4 regex scanned all public functions including
-- assert_schema_health itself. Its body contains the detection regex patterns
-- as string literals (e.g. 'current_setting\s*\(' and '= ''lit''' appear
-- verbatim in the H4 WHERE clause), causing the checker to flag itself.
--
-- Fix: add p.proname <> 'assert_schema_health' to the H4 candidate scan.
-- The schema_health_exceptions row (id 76a49e13) was a workaround; it stays
-- as belt-and-suspenders but is no longer load-bearing.

CREATE OR REPLACE FUNCTION public.assert_schema_health(p_only_public boolean DEFAULT true)
 RETURNS TABLE(severity text, object_name text, rule_code text, detail text)
 LANGUAGE plpgsql
 SET search_path TO 'public', 'pg_catalog'
AS $function$
BEGIN
  RETURN QUERY
  WITH raw_findings AS (
    -- H1: functions in public schema with mutable search_path
    SELECT 'WARN'::text AS severity,
           n.nspname || '.' || p.proname || '()' AS object_name,
           'H1_MUTABLE_SEARCH_PATH'::text AS rule_code,
           'function lacks SET search_path -- pin with SET search_path = public, pg_catalog at declaration'::text AS detail
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.prokind IN ('f','p')
      AND NOT EXISTS (
        SELECT 1 FROM unnest(coalesce(p.proconfig, ARRAY[]::text[])) AS cfg
        WHERE cfg LIKE 'search_path=%'
      )
    UNION ALL
    -- H2: views NOT using security_invoker
    SELECT 'ERROR'::text,
           schemaname || '.' || viewname,
           'H2_VIEW_SEC_DEFINER'::text,
           'view must be created WITH (security_invoker = true) -- else bypasses RLS'::text
    FROM pg_views v
    WHERE v.schemaname = 'public'
      AND NOT EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = v.schemaname AND c.relname = v.viewname
          AND c.reloptions IS NOT NULL
          AND EXISTS (SELECT 1 FROM unnest(c.reloptions) o WHERE o = 'security_invoker=true')
      )
    UNION ALL
    -- H3: tables without RLS
    SELECT 'ERROR'::text,
           schemaname || '.' || tablename,
           'H3_RLS_DISABLED'::text,
           'public table without RLS -- ALTER TABLE ENABLE ROW LEVEL SECURITY plus policies'::text
    FROM pg_tables t
    WHERE t.schemaname = 'public'
      AND NOT EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = t.schemaname AND c.relname = t.tablename AND c.relrowsecurity
      )
    UNION ALL
    -- H4: NULL-unsafe comparison involving current_setting
    -- Self-exclusion: assert_schema_health contains these regex patterns as string
    -- literals in its own body, causing false-positive self-detection without the guard.
    SELECT 'WARN'::text,
           n.nspname || '.' || p.proname || '()',
           'H4_NULL_UNSAFE_CMP'::text,
           'function body uses var <> lit or var = lit near current_setting() -- use IS DISTINCT FROM for NULL safety'::text
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.prokind IN ('f','p')
      AND p.proname <> 'assert_schema_health'
      AND p.prosrc ~ 'current_setting\s*\('
      AND p.prosrc ~ '\m\w+\s*(<>|=)\s*''[^'']+'''
      AND p.prosrc !~ '\m\w+\s+IS\s+(NOT\s+)?DISTINCT\s+FROM\s+''[^'']+'''
    UNION ALL
    -- H5: SECURITY DEFINER with PUBLIC EXECUTE
    SELECT 'WARN'::text,
           n.nspname || '.' || p.proname || '()',
           'H5_SECDEF_PUBLIC_GRANT'::text,
           'SECURITY DEFINER function grants EXECUTE to PUBLIC -- REVOKE and GRANT to specific role'::text
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.prosecdef = true
      AND has_function_privilege('public', p.oid, 'EXECUTE')
  )
  SELECT r.severity, r.object_name, r.rule_code, r.detail
  FROM raw_findings r
  WHERE NOT EXISTS (
    SELECT 1 FROM public.schema_health_exceptions e
    WHERE e.object_name = r.object_name
      AND e.rule_code = r.rule_code
      AND (e.expires_at IS NULL OR e.expires_at > now())
  );
  RETURN;
END
$function$;
