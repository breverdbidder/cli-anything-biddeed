-- Weekly pg_cron: promote Ariel corrections on ci_agent_runs into permanent
-- ci_agent_memory rows. Wrapped in a function (matching this repo's existing
-- cron-job convention, e.g. public.b2c_outbox_drain(),
-- public.recompute_usage_baselines()) rather than a raw multi-statement cron
-- body, so both statements commit or fail together per invocation.
begin;

create or replace function public.promote_ci_corrections_to_memory()
returns void
language sql
security definer
set search_path = public
as $$
  insert into public.ci_agent_memory (competitor, memory_type, observation, confidence, created_by)
  select
    competitor,
    'alert_threshold',
    'CORRECTION: ' || ariel_correction,
    0.9,
    'ariel_correction'
  from public.ci_agent_runs
  where ariel_verdict in ('partially_accurate', 'wrong')
    and ariel_correction is not null
    and correction_applied = false;

  update public.ci_agent_runs
  set correction_applied = true
  where ariel_verdict in ('partially_accurate', 'wrong')
    and correction_applied = false;
$$;

comment on function public.promote_ci_corrections_to_memory() is
  'Weekly pg_cron (ci-corrections-to-memory, Mon 9am) — promotes ci_agent_runs.ariel_correction rows into permanent ci_agent_memory observations.';

select cron.schedule(
  'ci-corrections-to-memory',
  '0 9 * * 1',
  $$select public.promote_ci_corrections_to_memory()$$
);

commit;
