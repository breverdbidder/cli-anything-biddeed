-- Second half of the summitleads -> winnerdata retirement (#19486): rename
-- the pg_cron job NAMES themselves (not just the SQL inside them, which was
-- already fixed by the previous migration's CREATE OR REPLACE FUNCTION
-- calls -- these jobs call winnerdata.* functions correctly as of that
-- migration). Applied after 20260826d_rename_summitleads_to_winnerdata.sql
-- confirmed live (schema rename + function bodies verified working).
--
-- cron.job has no rename primitive -- unschedule by old name, reschedule
-- under the new name with the same cron expression and command text
-- (updated to reference winnerdata.* instead of summitleads.*, including
-- the Telegram alert message wording per the hard "no summitleads anywhere"
-- rule). jobid values change; schedule and behavior do not.

select cron.unschedule('summitleads-daily-ff-digest-sla-alert');
select cron.unschedule('summitleads-mls-sale-close-daily');
select cron.unschedule('summitleads-sla-escalation-sweep');
select cron.unschedule('summitleads-sla-no-contact-sweep');

select cron.schedule(
  'winnerdata-daily-ff-digest-sla-alert',
  '15 11 * * *',
  $cron$
  select public.fire_workflow_dispatch(
    'breverdbidder/cli-anything-biddeed',
    'telegram-notify.yml',
    'main',
    jsonb_build_object('message', format(
      E'⚠️ DAILY WINNER FFs SLA AT RISK: no digest sent for %s by 7:15 AM ET. Hard deadline 8:00 AM ET. Check winnerdata.ff_digest_log / winnerdata-daily-winner-ff-digest workflow run.',
      current_date
    ))
  )
  where not exists (
    select 1 from winnerdata.ff_digest_log
    where batch_date = current_date and status in ('sent', 'no_leads_sent')
  );
  $cron$
);

select cron.schedule(
  'winnerdata-mls-sale-close-daily',
  '40 10 * * *',
  $cron$SELECT public.sync_mls_sale_close_events();$cron$
);

select cron.schedule(
  'winnerdata-sla-escalation-sweep',
  '*/5 * * * *',
  $cron$select winnerdata.run_sla_escalation_sweep();$cron$
);

select cron.schedule(
  'winnerdata-sla-no-contact-sweep',
  '*/2 * * * *',
  $cron$
    select winnerdata.touch_lead_sla(l.lead_id)
    from winnerdata.leads l
    where l.delivered_at is not null
      and l.sla_tier is null
      and not exists (
        select 1 from winnerdata.lead_activity la
        where la.lead_id = l.lead_id and la.activity_type = 'contact_attempt'
      )
      and now() - l.delivered_at > (
        coalesce((select max(rd.sla_timeout_minutes) from winnerdata.routing_decisions rd where rd.lead_id = l.lead_id), 5)
        * interval '1 minute'
      );
  $cron$
);
