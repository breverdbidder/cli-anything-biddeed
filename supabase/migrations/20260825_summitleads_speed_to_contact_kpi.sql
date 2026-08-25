-- Speed-to-Contact KPI instrumentation.
--
-- SCHEMA NOTE (live-verified 2026-08-25, see PR body): the dispatching issue
-- says the schema was "renamed from summitleads to winnerdata." That is
-- stale/wrong per CC_META_PROMPT 2.3 -- live query confirms `summitleads` is
-- still the schema holding leads/lead_activity/quote_drafts/routing_decisions/
-- binds/signal_events (63 real rows in leads as of this session). A separate
-- `winnerdata` schema exists but holds only `owner_portfolio`. This migration
-- targets `summitleads` because that's where the real tables live today; the
-- rename itself is out of scope (high blast radius, not explicitly approved).
--
-- All changes additive per CC_META_PROMPT 3.4: new columns with safe
-- defaults, no drops, no type changes, no rewritten canonical views.

set search_path = summitleads, public;

-- ---------------------------------------------------------------------
-- 1. leads: delivery / notification / SLA columns
-- ---------------------------------------------------------------------
alter table summitleads.leads
  add column if not exists delivered_at timestamptz,
  add column if not exists notification_sent_at timestamptz,
  add column if not exists sla_tier text,
  add column if not exists sla_breach boolean not null default false;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'leads_sla_tier_check'
  ) then
    alter table summitleads.leads
      add constraint leads_sla_tier_check
      check (sla_tier is null or sla_tier in
        ('under_5min','5_to_30min','30_to_60min','over_60min','no_contact'));
  end if;
end $$;

comment on column summitleads.leads.sla_tier is
  'COMPUTED ONLY via summitleads.leads_recompute_sla() trigger -- never set directly. See negative test: a direct UPDATE of this column is silently overwritten on the same statement.';
comment on column summitleads.leads.sla_breach is
  'COMPUTED ONLY, same trigger as sla_tier.';

-- ---------------------------------------------------------------------
-- 2. quote_drafts: quote_shown_at
-- ---------------------------------------------------------------------
alter table summitleads.quote_drafts
  add column if not exists quote_shown_at timestamptz;

-- ---------------------------------------------------------------------
-- 3. lead_activity: contact_method
--    DEVIATION FROM BRIEF: lead_activity.channel (text, already exists,
--    verified live) already carries exactly this semantic ("call/text/email")
--    for the row where activity_type='contact_attempt'. Adding a second
--    "contact_method" column would duplicate `channel` for every row and
--    invite the two to drift. Per Karpathy K3 (surgical changes / no
--    speculative duplication), this migration does NOT add contact_method --
--    speed_kpis reads first_contact activity's `channel` value instead.
--    first_contact_at is likewise not a stored lead_activity column -- it is
--    derived (min(occurred_at) where activity_type='contact_attempt'), exactly
--    as the brief's own definition describes it ("= timestamp of first
--    lead_activity row of type contact_attempt"), computed in the trigger
--    and in speed_kpis below rather than duplicated as stored state that
--    could drift from the activity log it's derived from.
-- ---------------------------------------------------------------------

-- ---------------------------------------------------------------------
-- 4. routing_decisions: configurable SLA timer per org, default 5 min
-- ---------------------------------------------------------------------
alter table summitleads.routing_decisions
  add column if not exists sla_timeout_minutes integer not null default 5;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'routing_decisions_sla_timeout_positive'
  ) then
    alter table summitleads.routing_decisions
      add constraint routing_decisions_sla_timeout_positive check (sla_timeout_minutes > 0);
  end if;
end $$;

-- ---------------------------------------------------------------------
-- 5. sla_tier / sla_breach: computed-only via trigger (negative test 5)
-- ---------------------------------------------------------------------
create or replace function summitleads.leads_recompute_sla()
returns trigger
language plpgsql
as $$
declare
  v_first_contact_at timestamptz;
  v_timeout interval;
begin
  select min(la.occurred_at) into v_first_contact_at
  from summitleads.lead_activity la
  where la.lead_id = new.lead_id and la.activity_type = 'contact_attempt';

  select coalesce(max(rd.sla_timeout_minutes), 5) * interval '1 minute'
    into v_timeout
  from summitleads.routing_decisions rd
  where rd.lead_id = new.lead_id;

  if new.delivered_at is null then
    new.sla_tier := null;
    new.sla_breach := false;
  elsif v_first_contact_at is null then
    if now() - new.delivered_at > v_timeout then
      new.sla_tier := 'no_contact';
      new.sla_breach := true;
    else
      new.sla_tier := null;
      new.sla_breach := false;
    end if;
  else
    new.sla_breach := (v_first_contact_at - new.delivered_at) > v_timeout;
    new.sla_tier := case
      when v_first_contact_at - new.delivered_at <= interval '5 minutes' then 'under_5min'
      when v_first_contact_at - new.delivered_at <= interval '30 minutes' then '5_to_30min'
      when v_first_contact_at - new.delivered_at <= interval '60 minutes' then '30_to_60min'
      else 'over_60min'
    end;
  end if;
  return new;
end;
$$;

drop trigger if exists leads_sla_recompute on summitleads.leads;
create trigger leads_sla_recompute
  before insert or update on summitleads.leads
  for each row execute function summitleads.leads_recompute_sla();

-- When a contact_attempt lead_activity row lands (or a routing_decisions SLA
-- timeout changes), the owning lead's sla_tier/breach must be recomputed even
-- though no column on `leads` itself changed. A no-op self-UPDATE forces the
-- BEFORE UPDATE trigger above to re-run against current lead_activity state.
create or replace function summitleads.touch_lead_sla(p_lead_id uuid)
returns void
language sql
as $$
  update summitleads.leads set delivered_at = delivered_at where lead_id = p_lead_id;
$$;

create or replace function summitleads.lead_activity_recompute_parent_sla()
returns trigger
language plpgsql
as $$
begin
  if new.activity_type = 'contact_attempt' then
    perform summitleads.touch_lead_sla(new.lead_id);
  end if;
  return new;
end;
$$;

drop trigger if exists lead_activity_recompute_parent_sla on summitleads.lead_activity;
create trigger lead_activity_recompute_parent_sla
  after insert on summitleads.lead_activity
  for each row execute function summitleads.lead_activity_recompute_parent_sla();

create or replace function summitleads.routing_decisions_recompute_lead_sla()
returns trigger
language plpgsql
as $$
begin
  perform summitleads.touch_lead_sla(new.lead_id);
  return new;
end;
$$;

drop trigger if exists routing_decisions_recompute_lead_sla on summitleads.routing_decisions;
create trigger routing_decisions_recompute_lead_sla
  after insert or update of sla_timeout_minutes on summitleads.routing_decisions
  for each row execute function summitleads.routing_decisions_recompute_lead_sla();

-- Time-based transition into 'no_contact' happens with no new row (the clock
-- just runs out). pg_cron is installed on this project (verified live) --
-- sweep every 2 minutes and touch any lead past its timeout with no contact
-- yet and no sla_tier set. Bounded: only rows actually needing a flip.
select cron.schedule(
  'summitleads-sla-no-contact-sweep',
  '*/2 * * * *',
  $$
    select summitleads.touch_lead_sla(l.lead_id)
    from summitleads.leads l
    where l.delivered_at is not null
      and l.sla_tier is null
      and not exists (
        select 1 from summitleads.lead_activity la
        where la.lead_id = l.lead_id and la.activity_type = 'contact_attempt'
      )
      and now() - l.delivered_at > (
        coalesce((select max(rd.sla_timeout_minutes) from summitleads.routing_decisions rd where rd.lead_id = l.lead_id), 5)
        * interval '1 minute'
      );
  $$
) where not exists (select 1 from cron.job where jobname = 'summitleads-sla-no-contact-sweep');

-- ---------------------------------------------------------------------
-- 6. speed_kpis view (security_invoker=true, Hard Rule 7)
-- ---------------------------------------------------------------------
create or replace view summitleads.speed_kpis
with (security_invoker = true) as
select
  l.lead_id,
  l.org_id,
  l.product_line,
  l.signal_id,
  se.occurred_at as signal_triggered_at,
  l.delivered_at,
  l.notification_sent_at,
  fc.first_contact_at,
  fc.contact_method,
  qd.quote_shown_at,
  extract(epoch from (l.delivered_at - se.occurred_at))::bigint as signal_to_delivery_seconds,
  extract(epoch from (l.notification_sent_at - l.delivered_at))::bigint as delivery_to_notification_seconds,
  extract(epoch from (fc.first_contact_at - l.delivered_at))::bigint as delivery_to_first_contact_seconds,
  extract(epoch from (qd.quote_shown_at - fc.first_contact_at))::bigint as contact_to_quote_seconds,
  l.sla_tier,
  l.sla_breach
from summitleads.leads l
left join summitleads.signal_events se on se.signal_id = l.signal_id
left join lateral (
  select min(la.occurred_at) as first_contact_at,
         (array_agg(la.channel order by la.occurred_at))[1] as contact_method
  from summitleads.lead_activity la
  where la.lead_id = l.lead_id and la.activity_type = 'contact_attempt'
) fc on true
left join lateral (
  select min(qd.quote_shown_at) as quote_shown_at
  from summitleads.quote_drafts qd
  where qd.lead_id = l.lead_id and qd.quote_shown_at is not null
) qd on true;

revoke all on summitleads.speed_kpis from public, anon, authenticated;
grant select on summitleads.speed_kpis to service_role;

-- ---------------------------------------------------------------------
-- 7. conversion_by_speed_bucket view (security_invoker=true, Hard Rule 7)
--    Explicitly not gated on N/statistical significance per spec.
-- ---------------------------------------------------------------------
create or replace view summitleads.conversion_by_speed_bucket
with (security_invoker = true) as
select
  sk.org_id,
  coalesce(sk.sla_tier, 'pending') as sla_tier,
  rd.producer_id,
  count(distinct sk.lead_id) as leads,
  count(distinct b.bind_id) as binds,
  round(100.0 * count(distinct b.bind_id) / nullif(count(distinct sk.lead_id), 0), 1) as conversion_pct
from summitleads.speed_kpis sk
left join summitleads.routing_decisions rd on rd.lead_id = sk.lead_id
left join summitleads.binds b on b.lead_id = sk.lead_id
group by sk.org_id, coalesce(sk.sla_tier, 'pending'), rd.producer_id;

revoke all on summitleads.conversion_by_speed_bucket from public, anon, authenticated;
grant select on summitleads.conversion_by_speed_bucket to service_role;

-- ---------------------------------------------------------------------
-- 8. SLA escalation / reroute
--    Protection Partners live-checked this session: TWO active producer rows
--    exist ("Mariam Shapira" x2, different active_lines, org_id
--    032f4717-545f-4a18-b48b-28ea4257699d) -- NOT one, contradicting the
--    brief. Both rows are the same human. Distinct-backup-producer detection
--    below dedupes on lower(full_name) so this doesn't misfire a pointless
--    "reroute Mariam to Mariam" -- Protection Partners still correctly gets
--    the single-producer escalating-alert path the brief intends.
-- ---------------------------------------------------------------------
create or replace function summitleads.sla_escalation_candidates(p_org_id uuid default null)
returns table(
  lead_id uuid, org_id uuid, delivered_at timestamptz,
  minutes_overdue numeric, distinct_producer_count int
)
language sql stable
as $$
  select
    l.lead_id, l.org_id, l.delivered_at,
    round(extract(epoch from (now() - l.delivered_at)) / 60, 1) as minutes_overdue,
    (select count(distinct lower(p.full_name))
       from summitleads.producers p
       where p.org_id = l.org_id and p.active) as distinct_producer_count
  from summitleads.leads l
  where l.delivered_at is not null
    and l.sla_tier = 'no_contact'
    and (p_org_id is null or l.org_id = p_org_id);
$$;

create or replace function summitleads.run_sla_escalation_sweep()
returns table(lead_id uuid, action text, detail text)
language plpgsql
as $$
declare
  r record;
  v_backup_producer_id uuid;
begin
  for r in select * from summitleads.sla_escalation_candidates() loop
    -- idempotent: skip if already logged for this breach window
    if exists (
      select 1 from summitleads.lead_activity la
      where la.lead_id = r.lead_id and la.activity_type = 'sla_escalation'
        and la.occurred_at > r.delivered_at
    ) then
      continue;
    end if;

    if r.distinct_producer_count > 1 then
      select p.producer_id into v_backup_producer_id
      from summitleads.producers p
      where p.org_id = r.org_id and p.active
        and lower(p.full_name) not in (
          select lower(p2.full_name) from summitleads.producers p2
          join summitleads.routing_decisions rd2 on rd2.producer_id = p2.producer_id
          where rd2.lead_id = r.lead_id
        )
      limit 1;
    else
      v_backup_producer_id := null;
    end if;

    if v_backup_producer_id is not null then
      insert into summitleads.routing_decisions (lead_id, org_id, producer_id, product_line, routing_reason, sla_timeout_minutes)
      select r.lead_id, r.org_id, v_backup_producer_id, l.product_line, 'sla_breach_auto_reroute', 5
      from summitleads.leads l where l.lead_id = r.lead_id;

      insert into summitleads.lead_activity (lead_id, org_id, activity_type, channel, payload)
      values (r.lead_id, r.org_id, 'sla_escalation', 'system',
              jsonb_build_object('action', 'rerouted', 'backup_producer_id', v_backup_producer_id, 'minutes_overdue', r.minutes_overdue));
      lead_id := r.lead_id; action := 'rerouted'; detail := 'routed to distinct backup producer';
      return next;
    else
      -- Single-producer org (or no distinct backup found): brief calls for
      -- an escalating SMS-then-call alert. BLOCKED for real delivery -- no
      -- SMS/telephony vendor is provisioned anywhere in this repo (verified
      -- by repo-wide grep this session) and producers has no phone column.
      -- This logs the escalation decision as the integration point for
      -- whichever channel gets approved next; it does not fabricate a sent
      -- alert. See PR body BLOCKED section.
      insert into summitleads.lead_activity (lead_id, org_id, activity_type, channel, payload)
      values (r.lead_id, r.org_id, 'sla_escalation', 'system',
              jsonb_build_object(
                'action', 'escalating_alert_required', 'minutes_overdue', r.minutes_overdue,
                'note', 'single-producer org -- SMS-then-call escalation required by spec; no notification channel provisioned (BLOCKED, see PR)'
              ));
      lead_id := r.lead_id; action := 'escalating_alert_logged'; detail := 'no SMS/call channel provisioned -- logged only, see BLOCKED note';
      return next;
    end if;
  end loop;
  return;
end;
$$;

revoke all on function summitleads.sla_escalation_candidates(uuid) from public;
revoke all on function summitleads.run_sla_escalation_sweep() from public;
grant execute on function summitleads.sla_escalation_candidates(uuid) to service_role;
grant execute on function summitleads.run_sla_escalation_sweep() to service_role;

select cron.schedule(
  'summitleads-sla-escalation-sweep',
  '*/5 * * * *',
  $$select summitleads.run_sla_escalation_sweep();$$
) where not exists (select 1 from cron.job where jobname = 'summitleads-sla-escalation-sweep');

-- ---------------------------------------------------------------------
-- 9. delivered_at write path -- Acceptance A requires delivered_at populated
--    AT DELIVERY TIME, not backfilled. The only real "delivery" event in this
--    pipeline today is workers/winnerdata-ff/src/index.js's handleFF serving
--    the producer's /ff/{lead_id} page (confirmed live this session -- see
--    that file's own header comment, written 2026-08-24, for the schema-name
--    history). First-touch only (coalesce), idempotent on repeat views. Same
--    SECURITY DEFINER + anon-grant pattern as the other public.ff_* RPCs in
--    supabase/migrations/20260824_winnerdata_ff_worker_rpc.sql.
-- ---------------------------------------------------------------------
create or replace function public.ff_mark_delivered(p_org_id uuid, p_lead_id uuid)
returns timestamptz
language sql
security definer
set search_path = public, summitleads
as $$
  update summitleads.leads
  set delivered_at = coalesce(delivered_at, now())
  where lead_id = p_lead_id and org_id = p_org_id
  returning delivered_at;
$$;

revoke all on function public.ff_mark_delivered(uuid, uuid) from public;
grant execute on function public.ff_mark_delivered(uuid, uuid) to anon;

-- notification_sent_at intentionally has NO write-path RPC here. BLOCKED --
-- see PR body: no SMS/push/Telegram-to-producer channel exists anywhere in
-- this repo (verified by repo-wide grep this session; only ops-facing
-- Telegram alerts exist, and summitleads.producers has no phone/chat-id
-- column). Adding a fabricated "sent" timestamp with nothing behind it would
-- violate Hard Rule 2 (never fabricate). The column exists and is ready the
-- moment a real channel is approved and wired.
