-- Issue #19490 ("The Daily Winner FFs" email delivery to Mariam, hard 8 AM ET SLA).
--
-- This migration ships the two pieces that do NOT depend on the blocked
-- item (Mariam's email address -- confirmed live 2026-08-26 that
-- summitleads.producers.email is null for both of her producer rows and
-- summitleads.organizations has no email column at all; see the session
-- report for this issue for the exact query run):
--   1. summitleads.ff_digest_log -- one row per digest send attempt, so the
--      SLA-alert sweep below has something to check and so re-runs are
--      idempotent-observable (not idempotent-enforcing -- the sender script
--      itself decides whether to skip a re-send for a batch_date already
--      logged 'sent'/'no_leads_sent').
--   2. summitleads-daily-ff-digest-sla-alert pg_cron job -- fires the exact
--      same public.fire_workflow_dispatch(...) -> telegram-notify.yml
--      pattern already live for cc-cost-budget-alert (jobid 10636) and
--      gold-48h-throughput-checkpoint (jobid 165), so it reuses a proven
--      mechanism rather than inventing a new one.
--
-- Scheduled 11:15 UTC. Same DST caveat already accepted and documented in
-- .github/workflows/summitleads-daily.yml's own header comment: this repo's
-- existing cron jobs run at a fixed UTC time year-round rather than solving
-- true US/Eastern local time, so the labeled ET time drifts by an hour
-- across the DST boundary (currently EDT, UTC-4, so 11:15 UTC = 7:15 AM
-- ET -- exactly the issue's requested SLA-check time). Flagged here, not
-- silently assumed.

create table if not exists summitleads.ff_digest_log (
  id bigint generated always as identity primary key,
  batch_date date not null,
  org_id uuid not null references summitleads.organizations(org_id),
  recipient text,
  lead_count integer not null default 0,
  resend_message_id text,
  status text not null check (status in ('sent', 'no_leads_sent', 'blocked_no_email', 'error')),
  error text,
  sent_at timestamptz not null default now()
);

comment on table summitleads.ff_digest_log is
  'One row per "The Daily Winner FFs" digest-email send attempt (issue #19490). status=blocked_no_email means the producer has no email on file -- the sender script must never fabricate a recipient, it logs this and exits non-fatally instead. Checked by the SLA-alert cron job below.';

create index if not exists ff_digest_log_batch_date_idx on summitleads.ff_digest_log (batch_date);

-- SLA-alert sweep: if no 'sent' or 'no_leads_sent' row exists for today by
-- 7:15 AM ET, tell Ariel via Telegram before Mariam notices a miss. A
-- 'blocked_no_email'/'error' row does NOT satisfy this check -- those are
-- exactly the conditions Ariel needs to hear about.
select cron.schedule(
  'summitleads-daily-ff-digest-sla-alert',
  '15 11 * * *',
  $cron$
  select public.fire_workflow_dispatch(
    'breverdbidder/cli-anything-biddeed',
    'telegram-notify.yml',
    'main',
    jsonb_build_object('message', format(
      E'⚠️ DAILY WINNER FFs SLA AT RISK: no digest sent for %s by 7:15 AM ET. Hard deadline 8:00 AM ET. Check summitleads.ff_digest_log / summitleads-daily-winner-ff-digest workflow run.',
      current_date
    ))
  )
  where not exists (
    select 1 from summitleads.ff_digest_log
    where batch_date = current_date and status in ('sent', 'no_leads_sent')
  );
  $cron$
)
where not exists (select 1 from cron.job where jobname = 'summitleads-daily-ff-digest-sla-alert');
