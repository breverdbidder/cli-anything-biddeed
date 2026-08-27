-- "The Daily Winner FFs" -- human-on-the-loop approval gate (issue #19482,
-- SCOPE CHANGE comment from Ariel, 2026-08-27). Supersedes the original
-- "auto-send by 8 AM ET" design from this same issue: the pipeline now
-- builds each day's qualifying batch as pending_approval and NEVER sends
-- automatically. Send only fires after Ariel approves via a Claude Cowork
-- scheduled task (built outside this repo) calling public.ff_approve_batch().
--
-- Design notes:
--  - batch_date is the auction day the batch covers (yesterday, from the
--    build script's own default), matching
--    scripts/winnerdata_daily_winner_ff_digest.py's existing convention --
--    NOT the day the batch is built/reviewed/sent.
--  - lead_count is a snapshot at build time for the Cowork report to show
--    without an extra query; the send step recomputes the real lead list
--    live off winnerdata.leads/routing_decisions rather than trusting a
--    cached blob, so a late guard/routing correction between build and
--    approval is still reflected in what actually gets sent.
--  - Approval -> send is wired two ways per the issue's own "trigger OR
--    short-poll" language: an AFTER UPDATE trigger fires the send workflow
--    immediately via the existing public.fire_workflow_dispatch() (same
--    proven mechanism as cc-cost-budget-alert/gold-48h-throughput-checkpoint),
--    and winnerdata-ff-send-approved.yml also carries its own bounded
--    morning-window poll as a backstop if the trigger's dispatch call ever
--    fails outbound. The send script is idempotent (only touches
--    status='approved' rows), so the backstop running redundantly is safe.

create table if not exists winnerdata.ff_batches (
  batch_date date primary key,
  status text not null default 'pending_approval'
    check (status in ('pending_approval', 'approved', 'sent')),
  lead_count integer not null default 0,
  approved_at timestamptz,
  approved_by text,
  sent_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table winnerdata.ff_batches is
  'Approval gate for "The Daily Winner FFs" (#19482 Aug 27 scope change). '
  'Build step (winnerdata_daily_winner_ff_digest.py) inserts pending_approval, '
  'even on zero-lead days. Only public.ff_approve_batch() may flip a row to '
  'approved. Nothing may send to Mariam without status=approved -- see '
  'winnerdata_ff_send_approved.py.';

-- Service-role-only RPC, callable from the Cowork task via the standard
-- Supabase RPC endpoint. Signature is pinned exactly as
-- `ff_approve_batch(batch_date date)` per the issue's own spec text --
-- Ariel is building a Cowork prompt against this literal name/signature.
create or replace function public.ff_approve_batch(batch_date date)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_target_date date := ff_approve_batch.batch_date;
  v_row winnerdata.ff_batches%rowtype;
  v_current_status text;
begin
  update winnerdata.ff_batches b
  set status = 'approved',
      approved_at = now(),
      approved_by = 'ariel',
      updated_at = now()
  where b.batch_date = v_target_date
    and b.status = 'pending_approval'
  returning b.* into v_row;

  if found then
    return jsonb_build_object(
      'ok', true, 'batch_date', v_row.batch_date,
      'status', v_row.status, 'approved_at', v_row.approved_at
    );
  end if;

  select b.status into v_current_status
  from winnerdata.ff_batches b
  where b.batch_date = v_target_date;

  if v_current_status is null then
    return jsonb_build_object(
      'ok', false, 'reason', 'no batch found for that date', 'batch_date', v_target_date
    );
  end if;

  return jsonb_build_object(
    'ok', false, 'reason', 'batch already ' || v_current_status,
    'batch_date', v_target_date, 'status', v_current_status
  );
end;
$$;

revoke all on function public.ff_approve_batch(date) from public;
grant execute on function public.ff_approve_batch(date) to service_role;

-- Fire the send workflow the instant a batch is approved (see
-- winnerdata-ff-send-approved.yml). Reuses the exact dispatch mechanism
-- already live for cc-cost-budget-alert / gold-48h-throughput-checkpoint --
-- no new secret-handling path introduced.
create or replace function winnerdata.notify_ff_batch_approved()
returns trigger
language plpgsql
security definer
set search_path = public, winnerdata
as $$
begin
  perform public.fire_workflow_dispatch(
    'breverdbidder/cli-anything-biddeed',
    'winnerdata-ff-send-approved.yml',
    'main',
    jsonb_build_object('batch_date', new.batch_date::text)
  );
  return new;
end;
$$;

drop trigger if exists ff_batches_notify_approved on winnerdata.ff_batches;
create trigger ff_batches_notify_approved
  after update of status on winnerdata.ff_batches
  for each row
  when (new.status = 'approved' and old.status is distinct from 'approved')
  execute function winnerdata.notify_ff_batch_approved();

-- ---------------------------------------------------------------------
-- Retire the old auto-send-era SLA alert. It checked ff_digest_log for a
-- 'sent'/'no_leads_sent' row by 7:15 AM ET -- under the approval-gated
-- design a normal day has NO digest_log row until Ariel approves (could be
-- well after 7:15), so this check would false-positive every day. Replaced
-- by the two alerts below, matching Ariel's Aug 27 P0 spec: 6:45 AM ET
-- "pipeline hasn't built a batch yet" and 7:45 AM ET "built but not yet
-- approved" -- two distinct conditions, not merged.
select cron.unschedule(jobid)
from cron.job
where jobname = 'winnerdata-daily-ff-digest-sla-alert';

-- Currently EDT (UTC-4, same DST caveat already accepted/documented in the
-- workflows this reuses): 6:45 AM ET = 10:45 UTC, 7:45 AM ET = 11:45 UTC.
-- batch_date convention is "yesterday" (see comment above), so both checks
-- look for (current_date - 1) -- the batch that should exist/be approved
-- by the time each alert fires.

select cron.schedule(
  'winnerdata-ff-pipeline-late-alert',
  '45 10 * * *',
  $cron$
  select public.fire_workflow_dispatch(
    'breverdbidder/cli-anything-biddeed',
    'telegram-notify.yml',
    'main',
    jsonb_build_object('message', format(
      E'⚠️ DAILY WINNER FFs PIPELINE LATE: no batch built yet for %s by 6:45 AM ET. winnerdata-daily-winner-ff-digest.yml should have run at 6:00 AM ET. Check the workflow run and winnerdata.ff_batches.',
      (current_date - 1)
    ))
  )
  where not exists (
    select 1 from winnerdata.ff_batches where batch_date = current_date - 1
  );
  $cron$
)
where not exists (select 1 from cron.job where jobname = 'winnerdata-ff-pipeline-late-alert');

select cron.schedule(
  'winnerdata-ff-unapproved-alert',
  '45 11 * * *',
  $cron$
  select public.fire_workflow_dispatch(
    'breverdbidder/cli-anything-biddeed',
    'telegram-notify.yml',
    'main',
    jsonb_build_object('message', format(
      E'⏳ DAILY WINNER FFs BUILT, NOT YET APPROVED: batch for %s (%s leads) is still pending_approval at 7:45 AM ET. Not a pipeline failure -- waiting on your approval via the Cowork task / public.ff_approve_batch(''%s''::date).',
      b.batch_date, b.lead_count, b.batch_date
    ))
  )
  from winnerdata.ff_batches b
  where b.batch_date = current_date - 1
    and b.status = 'pending_approval';
  $cron$
)
where not exists (select 1 from cron.job where jobname = 'winnerdata-ff-unapproved-alert');
