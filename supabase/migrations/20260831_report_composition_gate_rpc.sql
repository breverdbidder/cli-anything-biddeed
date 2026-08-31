-- Issue #19657 follow-on — RLS ship-gate fix for biddeed_report_composition.
--
-- Root cause (verified live 2026-08-31): biddeed_report_composition has RLS
-- enabled (relrowsecurity=true) with ZERO policies defined
-- (select * from pg_policies where tablename='biddeed_report_composition'
-- returns 0 rows). service_role bypasses RLS entirely, which is why local/CI
-- testing with the service-role key correctly saw ship_status='blocked'.
-- anon/authenticated (the key the Vercel runtime actually holds) get
-- zero rows back under Postgres's default-deny-when-RLS-enabled-with-no-
-- policies behavior — composer.js's sectionComposition() then falls back to
-- its `?? 'unknown'` default, which is the exact bug #19657 disclosed.
--
-- Fix matches the existing SECURITY DEFINER pattern already used by
-- check_s5_report_access (supabase/migrations/20260806_s5_report_access_gate.sql):
-- wrap the read in a definer-rights function instead of opening the table to
-- anon/authenticated or touching RLS policies. Marked STABLE (read-only, no
-- side effects) so PostgREST allows it to be called via GET, matching
-- composer.js's existing get(path) call shape.
create or replace function public.get_report_composition_gate(p_section_keys text[])
returns table(section_key text, ship_status text, disclosure_text text)
language sql
security definer
stable
set search_path = public
as $$
  select brc.section_key, brc.ship_status, brc.disclosure_text
  from public.biddeed_report_composition brc
  where brc.section_key = any(p_section_keys);
$$;

grant execute on function public.get_report_composition_gate(text[]) to anon, authenticated;
