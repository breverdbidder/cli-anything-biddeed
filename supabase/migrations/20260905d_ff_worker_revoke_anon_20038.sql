-- LAUNCH-D (#20038): winnerdata-ff Worker lockdown, step 3 of 3.
--
-- Steps 1-2 already shipped and were live-verified before this migration was
-- written: workers/winnerdata-ff/wrangler.toml sets workers_dev = false (the
-- workers.dev hostname no longer serves this Worker -- confirmed 404 on
-- winnerdata-ff.brevardbidderai.workers.dev/portal), and
-- workers/winnerdata-ff/src/index.js now calls the ff_* RPCs below with
-- env.SUPABASE_SERVICE_ROLE_KEY (a Worker secret set by
-- .github/workflows/deploy-winnerdata-ff.yml) instead of the previously
-- hardcoded public anon JWT. ff.winnerdataai.com/portal, /healthz and
-- /ff/<uuid> all confirmed 200 on the new deploy before this file was run.
--
-- This step revokes anon/authenticated EXECUTE on the five ff_* SECURITY
-- DEFINER RPCs the Worker calls. Nothing else can regress from this: the
-- Worker no longer authenticates as anon, and no other consumer of these
-- functions exists (grep of the repo shows only workers/winnerdata-ff/src
-- calling them). service_role and postgres keep EXECUTE (unaffected by a
-- REVOKE targeting only anon/authenticated).
--
-- Order matters and was enforced in the issue and followed here: deploy the
-- secret-based Worker first, verify it live, THEN revoke -- never the
-- reverse, or the still-anon-keyed Worker would have broken mid-flight.

REVOKE EXECUTE ON FUNCTION public.ff_portal_leads(uuid) FROM anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.ff_get_lead(uuid, uuid) FROM anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.ff_record_bind(uuid, uuid, integer, text) FROM anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.ff_upsert_response(uuid, uuid, text, text, text, text) FROM anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.ff_healthz() FROM anon, authenticated;
