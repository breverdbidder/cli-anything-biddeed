begin;

alter table winnerdata.ff_batches
  add column if not exists enrichment_status text not null default 'not_started';
alter table winnerdata.ff_batches
  add column if not exists enrichment_run_id text;
alter table winnerdata.ff_batches
  add column if not exists enrichment_started_at timestamptz;
alter table winnerdata.ff_batches
  add column if not exists enrichment_completed_at timestamptz;
alter table winnerdata.ff_batches
  add column if not exists enrichment_error text;

alter table winnerdata.ff_batches
  drop constraint if exists ff_batches_enrichment_status_check;
alter table winnerdata.ff_batches
  add constraint ff_batches_enrichment_status_check
  check (enrichment_status in ('not_started','running','complete','failed'));

create or replace function winnerdata.notify_ff_batch_approved()
returns trigger
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_dispatch jsonb;
begin
  if new.status = 'approved' and old.status is distinct from 'approved' then
    v_dispatch := public.fire_workflow_dispatch(
      'breverdbidder/cli-anything-biddeed',
      'winnerdata-nine-ff-enrichment.yml',
      'main',
      jsonb_build_object('batch_date', new.batch_date::text)
    );

    if coalesce(v_dispatch->>'status','') <> 'dispatched' then
      raise exception using
        errcode = 'external_routine_exception',
        message = format('Approval blocked: Tracerfy enrichment dispatch failed: %s', v_dispatch::text);
    end if;

    update winnerdata.ff_batches
       set enrichment_status = 'running',
           enrichment_started_at = now(),
           enrichment_error = null,
           updated_at = now()
     where batch_date = new.batch_date;
  end if;
  return new;
end;
$$;

revoke all on function winnerdata.notify_ff_batch_approved() from public;
grant execute on function winnerdata.notify_ff_batch_approved() to service_role;

commit;
