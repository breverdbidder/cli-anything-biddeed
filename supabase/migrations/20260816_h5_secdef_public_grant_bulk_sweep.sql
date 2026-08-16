-- One-time live sweep for H5_SECDEF_PUBLIC_GRANT (issue #19168, DoD item 4).
--
-- assert_schema_health() found 199 SECURITY DEFINER functions in public with
-- PUBLIC EXECUTE (beyond the 7 elevenlabs_* functions already fixed manually).
-- Dry run confirmed all 199 already carry an explicit anon and/or authenticated
-- EXECUTE grant, so revoking PUBLIC removes zero currently-relied-upon access
-- path -- same shape as the elevenlabs_* precedent. anon/authenticated/
-- service_role/postgres grants are left untouched; only PUBLIC is revoked,
-- per H5's own scope and this issue's guardrail.
--
-- This is a one-time backfill for pre-existing findings. New functions going
-- forward are covered live by the auto-remediation event trigger added in
-- 20260816_h5_secdef_public_grant_autoremediate.sql.

DO $$
DECLARE
  r record;
  fn_ident text;
BEGIN
  FOR r IN
    SELECT p.oid
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.prosecdef = true
      AND has_function_privilege('public', p.oid, 'EXECUTE')
  LOOP
    fn_ident := r.oid::regprocedure::text;
    EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', fn_ident);

    INSERT INTO public.schema_health_enforcement_log(
      object_name, rule_code, severity, detail, introduced_by_tag,
      resolved_at, resolved_reason, resolved_by
    )
    VALUES (
      'public.' || fn_ident, 'H5_SECDEF_PUBLIC_GRANT', 'WARN',
      'SECURITY DEFINER function grants EXECUTE to PUBLIC -- REVOKE and GRANT to specific role',
      'MANUAL_SWEEP', now(),
      'bulk-swept issue #19168 -- pre-existing finding, explicit anon/authenticated grant already present',
      'issue-19168-bulk-sweep'
    )
    ON CONFLICT ON CONSTRAINT uniq_active_violation DO NOTHING;
  END LOOP;
END
$$;
