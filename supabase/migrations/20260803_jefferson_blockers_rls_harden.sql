-- Adversarial-verify follow-up (both refuters flagged the same residual gap,
-- see gold_standard_ultraloop_audit for this session): gold_standard_county_blockers
-- (added in 20260803_jefferson_autopilot_blocked_until_gate.sql) inherited default
-- public-schema grants giving anon/authenticated full INSERT/UPDATE/DELETE via
-- PostgREST, unlike sibling operational-control tables in the same subsystem
-- (gold_standard_campaign, gold_standard_certifications) which have RLS enabled.
-- Since this table gates which counties the autopilot dispatcher will (not)
-- re-fire, an anon-key caller could otherwise suppress or un-suppress any
-- county's dispatch. Lock it to postgres/service_role only, same as its siblings.

BEGIN;

ALTER TABLE public.gold_standard_county_blockers ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.gold_standard_county_blockers FROM anon, authenticated;

CREATE POLICY service_role_only ON public.gold_standard_county_blockers
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

COMMIT;
