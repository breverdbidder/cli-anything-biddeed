-- GTM-2 (issue #20031) — funnel instrumentation + G-SPI daily + CFO unit
-- economics. VIEWS ONLY per docs/intent/20031.md guardrail #1: no new
-- tables, no ALTER on any production table. The only existing objects
-- touched are the public.log_funnel_event() FUNCTION (broadening its
-- step allow-list — a function replace, not a table/column change) and
-- brand-new views, all security_invoker=true, none anon-granted.
--
-- G-SPI stays distinct from the Founder D0 SPI (spi_gates/spi_task_registry/
-- spi_daily) per Ariel's Aug 26 directive and the intent doc's guardrail #2 —
-- this migration never writes to spi_daily.
--
-- Sources (all pre-existing, verified live via mgmt_sql.py Sep 5 2026):
--   winnerdata.funnel_events       -- generic step/params event log (existing)
--   winnerdata.reel_variant_metrics -- per-variant per-day per-platform plays/clicks/captures/views_ext
--   public.youtube_uploads          -- day_pacific, upload_status
--   public.youtube_quota_ledger     -- day_pacific, units_used
--   public.v_llm_cost_daily         -- day, total_cost_cents (existing view)
--   finance.expense_ledger          -- incurred_on, vendor, amount_cents (ElevenLabs/Maps/OpenRouter/Resend)
--   stripe.subscriptions            -- Stripe Sync Engine mirror; status, items, metadata, created, canceled_at
--   winnerdata.reel_variant_review  -- decision/note (best-effort never-list proxy; no dedicated table exists)

begin;

-- ---------------------------------------------------------------------
-- 1. Broaden public.log_funnel_event()'s step allow-list to cover the
--    GTM-2 event contract (email_capture, signup, checkout_started,
--    purchased) alongside the 5 steps issue #19786 already shipped
--    (reel_click, deal_view, gate_view, gate_submit, report_view).
--    winnerdata.funnel_events itself is NOT schema-changed — same table,
--    same session_id/step/params shape, matching the existing
--    reel_watch_pct convention this table already stores.
-- ---------------------------------------------------------------------
create or replace function public.log_funnel_event(
  p_session_id text, p_step text, p_params jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
begin
  if p_step not in (
    'reel_click', 'deal_view', 'gate_view', 'gate_submit', 'report_view',
    'email_capture', 'signup', 'checkout_started', 'purchased'
  ) then
    return jsonb_build_object('ok', false, 'error', 'invalid_step');
  end if;

  insert into winnerdata.funnel_events (session_id, step, params)
  values (coalesce(p_session_id, gen_random_uuid()::text), p_step, coalesce(p_params, '{}'::jsonb));

  return jsonb_build_object('ok', true);
end;
$$;

grant execute on function public.log_funnel_event(text, text, jsonb) to anon, authenticated, service_role;

-- ---------------------------------------------------------------------
-- public.v_gspi_daily -- one row per day (trailing 45 days), re-queried
-- from measured sources only. security_invoker=true, no anon grant
-- (same read-only pattern as winnerdata.v_reel_funnel / v_reel_retention).
--
-- MRR is computed AS OF each day from stripe.subscriptions: a
-- subscription counts if status='active' AND created on/before that day
-- AND (never canceled OR canceled after that day). Monthly-equivalent
-- amount = sum of subscription_items unit_amount*quantity, /12 when the
-- item's recurring interval is 'year' (this app only sells monthly or
-- annual, per stripe_products.stripe_price_id_monthly/_annual).
-- ---------------------------------------------------------------------
create or replace view public.v_gspi_daily
with (security_invoker = true) as
with days as (
  select generate_series((current_date - interval '44 days')::date, current_date, interval '1 day')::date as day
),
uploads as (
  select day_pacific as day, count(*) as uploads_youtube
  from public.youtube_uploads
  where upload_status = 'uploaded'
  group by day_pacific
),
reel_platform as (
  select day,
    sum(coalesce(views_ext, plays, 0)) as platform_views,
    sum(coalesce(captures, 0)) as variant_captures
  from winnerdata.reel_variant_metrics
  group by day
),
funnel as (
  select ts::date as day,
    count(*) filter (where step = 'reel_click') as link_clicks,
    count(*) filter (where step = 'deal_view') as deal_views,
    count(*) filter (where step = 'email_capture' or step = 'gate_submit') as email_captures,
    count(*) filter (where step = 'signup') as signups,
    count(*) filter (where step = 'checkout_started') as checkouts_started,
    count(*) filter (where step = 'purchased') as purchases
  from winnerdata.funnel_events
  group by ts::date
),
never_list as (
  -- Best-effort proxy: no dedicated never-list-hit table exists yet
  -- (verified live Sep 5 2026 -- confirmed gap, not a fabricated number).
  -- Counts Director/QA rejections whose note explicitly names the
  -- never-list scan; 0 rows today is a valid, honest reading.
  select decided_at::date as day, count(*) as never_list_hits
  from winnerdata.reel_variant_review
  where decision = 'rejected' and note ilike '%never%list%'
  group by decided_at::date
),
quota as (
  select day_pacific as day, units_used as youtube_quota_units_used
  from public.youtube_quota_ledger
),
llm as (
  select day, round(sum(total_cost_cents) / 100.0, 2) as llm_spend_usd
  from public.v_llm_cost_daily
  group by day
),
vendor_spend as (
  select incurred_on as day,
    round(sum(amount_cents) filter (where vendor ilike '%elevenlabs%') / 100.0, 2) as elevenlabs_spend_usd,
    round(sum(amount_cents) filter (where vendor ilike '%maps%' or vendor ilike '%google%') / 100.0, 2) as maps_spend_usd
  from finance.expense_ledger
  group by incurred_on
),
mrr_by_day as (
  select d.day,
    (
      select coalesce(sum(
        case when (item->'price'->'recurring'->>'interval') = 'year'
          then (item->'price'->>'unit_amount')::numeric * coalesce((item->>'quantity')::numeric, 1) / 100.0 / 12
          else (item->'price'->>'unit_amount')::numeric * coalesce((item->>'quantity')::numeric, 1) / 100.0
        end
      ), 0)
      from stripe.subscriptions s
      cross join lateral jsonb_array_elements(coalesce(s.items->'data', '[]'::jsonb)) as item
      where s.status = 'active'
        and to_timestamp(s.created) <= d.day + interval '1 day'
        and (s.canceled_at is null or to_timestamp(s.canceled_at) > d.day + interval '1 day')
    ) as mrr_usd,
    (
      select count(*)
      from stripe.subscriptions s
      where s.status = 'active'
        and to_timestamp(s.created) <= d.day + interval '1 day'
        and (s.canceled_at is null or to_timestamp(s.canceled_at) > d.day + interval '1 day')
    ) as paying_customers
  from days d
)
select
  d.day,
  coalesce(u.uploads_youtube, 0) as uploads_youtube,
  coalesce(rp.platform_views, 0) as views,
  coalesce(f.link_clicks, 0) as clicks,
  case when coalesce(rp.platform_views, 0) > 0
    then round(100.0 * coalesce(f.link_clicks, 0) / rp.platform_views, 2)
    else null end as view_to_click_pct,
  coalesce(f.deal_views, 0) as deal_views,
  coalesce(f.email_captures, 0) + coalesce(rp.variant_captures, 0) as captures,
  coalesce(f.signups, 0) as signups,
  coalesce(f.checkouts_started, 0) as checkouts_started,
  coalesce(f.purchases, 0) as purchases,
  m.mrr_usd,
  m.paying_customers,
  case when coalesce(m.paying_customers, 0) > 0 then round(m.mrr_usd / m.paying_customers, 2) else null end as arpu_usd,
  coalesce(nl.never_list_hits, 0) as never_list_hits,
  q.youtube_quota_units_used,
  ll.llm_spend_usd,
  vs.elevenlabs_spend_usd,
  vs.maps_spend_usd
from days d
left join uploads u on u.day = d.day
left join reel_platform rp on rp.day = d.day
left join funnel f on f.day = d.day
left join never_list nl on nl.day = d.day
left join quota q on q.day = d.day
left join llm ll on ll.day = d.day
left join vendor_spend vs on vs.day = d.day
left join mrr_by_day m on m.day = d.day
order by d.day desc;

-- ---------------------------------------------------------------------
-- finance.v_gtm_unit_economics -- current-snapshot MRR/ARPU/CAC/LTV
-- proxy for the CFO agent. Reads the same stripe.subscriptions +
-- finance.expense_ledger sources as v_gspi_daily above (today's slice),
-- so both stay consistent by construction.
-- ---------------------------------------------------------------------
create or replace view finance.v_gtm_unit_economics
with (security_invoker = true) as
with active_subs as (
  select s.id, s.customer, s.created, s.canceled_at,
    coalesce(sum(
      case when (item->'price'->'recurring'->>'interval') = 'year'
        then (item->'price'->>'unit_amount')::numeric * coalesce((item->>'quantity')::numeric, 1) / 100.0 / 12
        else (item->'price'->>'unit_amount')::numeric * coalesce((item->>'quantity')::numeric, 1) / 100.0
      end
    ), 0) as monthly_amount_usd
  from stripe.subscriptions s
  cross join lateral jsonb_array_elements(coalesce(s.items->'data', '[]'::jsonb)) as item
  where s.status = 'active'
  group by s.id, s.customer, s.created, s.canceled_at
),
cac_spend as (
  -- CAC numerator per SOP definition: ElevenLabs + Maps + OpenRouter +
  -- Resend spend, all-time (finance.expense_ledger is a thin, manually
  -- reconciled ledger today -- 2 rows live Sep 5 2026 -- so this number
  -- is INFERRED/partial until more vendor spend is logged; never fabricated).
  select round(sum(amount_cents) filter (
    where vendor ilike '%elevenlabs%' or vendor ilike '%maps%' or vendor ilike '%google%'
       or vendor ilike '%openrouter%' or vendor ilike '%resend%'
  ) / 100.0, 2) as cac_numerator_usd
  from finance.expense_ledger
),
lead_totals as (
  select count(*) filter (where email is not null) as emails_captured
  from public.lead_profiles
)
select
  (select count(*) from active_subs) as paying_customers,
  (select coalesce(sum(monthly_amount_usd), 0) from active_subs) as mrr_usd,
  case when (select count(*) from active_subs) > 0
    then round((select sum(monthly_amount_usd) from active_subs) / (select count(*) from active_subs), 2)
    else null end as arpu_usd,
  (select emails_captured from lead_totals) as emails_captured_total,
  case when (select emails_captured from lead_totals) > 0
    then round(100.0 * (select count(*) from active_subs) / (select emails_captured from lead_totals), 2)
    else null end as email_to_paid_pct,
  (select cac_numerator_usd from cac_spend) as cac_numerator_usd_alltime,
  case when (select count(*) from active_subs) > 0
    then round((select cac_numerator_usd from cac_spend) / (select count(*) from active_subs), 2)
    else null end as cac_usd_per_paying_customer,
  -- LTV proxy = ARPU x 12 (ASSUMED 12-month average tenure -- no churn
  -- history exists yet with 0 completed subscriptions; replace with a
  -- measured average tenure once subscription_events has cancellations).
  case when (select count(*) from active_subs) > 0
    then round(((select sum(monthly_amount_usd) from active_subs) / (select count(*) from active_subs)) * 12, 2)
    else null end as ltv_proxy_usd_assumed_12mo;

-- public schema's default privileges auto-grant anon/authenticated on new
-- objects (verified live: v_gspi_daily inherited SELECT for both roles
-- immediately on creation, finance.v_gtm_unit_economics did not, since
-- finance has no such default privilege configured) -- explicit revoke
-- closes that gap per M2 ("no anon-readable new view").
revoke all on public.v_gspi_daily from anon, authenticated;
grant select on public.v_gspi_daily to service_role;

commit;
