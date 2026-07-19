begin;

create table if not exists public.agent_ops_log (
  id           uuid primary key default gen_random_uuid(),
  dispatch_id  text not null,
  task         text not null,
  status       text not null
                 check (status in ('VERIFIED','BLOCKED','PARTIAL','SKIPPED')),
  evidence     text,
  severity     text
                 check (severity in ('info','warn','blocker')),
  created_at   timestamptz not null default now()
);

comment on table public.agent_ops_log is
  'Autonomous agent dispatch outcomes (GTM-22+). Ops log ONLY. '
  'Not analytics. Never write auction/anomaly data here — that is public.insights.';

comment on column public.agent_ops_log.dispatch_id is
  'Dispatch identifier, e.g. GTM-22, GTM-22C.';
comment on column public.agent_ops_log.task is
  'Task label, e.g. "TASK 2 IDEMPOTENCY".';
comment on column public.agent_ops_log.status is
  'Honesty Protocol V3 disposition. VERIFIED means output was observed, not that code was written.';
comment on column public.agent_ops_log.evidence is
  'Observed output, command run, test result, or root-cause finding. Free text.';

create index if not exists agent_ops_log_dispatch_created_idx
  on public.agent_ops_log (dispatch_id, created_at desc);

create index if not exists agent_ops_log_blockers_idx
  on public.agent_ops_log (created_at desc)
  where severity = 'blocker';

alter table public.agent_ops_log enable row level security;
alter table public.agent_ops_log force row level security;

revoke all on public.agent_ops_log from anon, authenticated;

drop policy if exists agent_ops_log_service_all on public.agent_ops_log;
create policy agent_ops_log_service_all
  on public.agent_ops_log
  for all
  to service_role
  using (true)
  with check (true);

commit;
