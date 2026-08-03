-- Security page gate (SUMMIT dispatch b7b02a64): the public Vendor &
-- Sub-Processor List link on /security is being replaced with a gated
-- request form. Every request is logged here. Inserts happen from the
-- CF Worker's public /security/subprocessor-request endpoint (anon key,
-- no auth — same trust model as lead_profiles), so anon needs INSERT but
-- never SELECT/UPDATE/DELETE. Reads are for internal review only.

BEGIN;

CREATE TABLE IF NOT EXISTS public.subprocessor_access_log (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  name text NOT NULL,
  company text NOT NULL,
  email text NOT NULL,
  reason text NOT NULL,
  requested_at timestamptz DEFAULT now(),
  ip_hash text
);

ALTER TABLE public.subprocessor_access_log ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.subprocessor_access_log FROM anon, authenticated;
GRANT INSERT ON public.subprocessor_access_log TO anon, authenticated;

CREATE POLICY anon_insert_only ON public.subprocessor_access_log
  FOR INSERT
  TO anon, authenticated
  WITH CHECK (true);

CREATE POLICY service_role_all ON public.subprocessor_access_log
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

COMMIT;
