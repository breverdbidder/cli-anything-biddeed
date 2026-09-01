-- P1 follow-up to 20260901g_lms_credential_reset_whitelist.sql: a real
-- Forgot Password button on the LMS's own 401 page (workers/winnerdata-lms
-- unauthorized()) and on winnerdataai-mvp's /admin gate, both of which POST
-- to the LMS Worker's new /admin/reset-request endpoint. That endpoint is
-- deliberately reachable WITHOUT Basic Auth (it's the recovery path for
-- when auth is lost) and dispatches the same lms-credential-reset.yml
-- workflow built for issue #19701. The only abuse guard is a 1-per-rolling-
-- hour rate limit — this migration adds the singleton state row + the
-- SECURITY DEFINER function that enforces it atomically (FOR UPDATE lock,
-- so two near-simultaneous requests can't both pass the check).
--
-- Worst case an attacker hits this endpoint: Ariel's own password gets
-- rotated and re-emailed to his own inbox. No data exposure, no auth
-- bypass — the new credentials only ever go to everestcapital8@gmail.com.

begin;

create table if not exists public.lms_reset_request_state (
  id boolean primary key default true,
  last_triggered_at timestamptz,
  constraint lms_reset_request_state_singleton check (id)
);

comment on table public.lms_reset_request_state is
  'Singleton row (id=true) tracking the last time the public, unauthenticated '
  'POST /admin/reset-request "Forgot password?" trigger on workers/winnerdata-lms '
  'fired the lms-credential-reset.yml workflow_dispatch (issue #19701). '
  'lms_reset_request_trigger() enforces a 1-per-rolling-hour rate limit against it.';

insert into public.lms_reset_request_state (id, last_triggered_at)
values (true, null)
on conflict (id) do nothing;

alter table public.lms_reset_request_state enable row level security;

create or replace function public.lms_reset_request_trigger()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_last timestamptz;
  v_retry_after int;
begin
  select last_triggered_at into v_last
  from public.lms_reset_request_state
  where id = true
  for update;

  if v_last is not null and now() - v_last < interval '1 hour' then
    v_retry_after := greatest(1, ceil(extract(epoch from (v_last + interval '1 hour' - now())))::int);
    return jsonb_build_object('ok', false, 'reason', 'rate_limited', 'retry_after_seconds', v_retry_after);
  end if;

  update public.lms_reset_request_state set last_triggered_at = now() where id = true;

  return jsonb_build_object('ok', true);
end;
$$;

comment on function public.lms_reset_request_trigger() is
  'Atomic 1-per-rolling-hour rate limit for the public LMS forgot-password '
  'trigger. Called by workers/winnerdata-lms with SUPABASE_SERVICE_KEY — not '
  'anon-callable, since this endpoint has no other gate.';

revoke all on function public.lms_reset_request_trigger() from public;
grant execute on function public.lms_reset_request_trigger() to service_role;

revoke all on table public.lms_reset_request_state from public, anon, authenticated;

commit;
