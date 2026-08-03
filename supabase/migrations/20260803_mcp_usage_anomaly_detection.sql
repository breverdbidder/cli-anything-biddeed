-- GTM-22 / SECURITY: Behavioural anomaly detection for BidDeed MCP.
-- Pure SQL window functions + pg_cron — no ML libraries. Detects attackers
-- with valid API keys who stay under rate limits by analysing usage
-- PATTERNS (volume shape, timing, county spread) rather than raw volume.
--
-- Schema deviation from brief: mcp_usage_log.customer_id is `uuid`, not
-- `text` as originally drafted. public.mcp_api_keys.customer_id is uuid and
-- public.log_security_event(p_user_id uuid, ...) requires uuid — a text
-- column here would either fail to bind or silently never match the
-- watchlist join. Verified live via information_schema.columns before writing
-- this file (CC_META_PROMPT §1.3 — inspect before you assume).
--
-- Second deviation, found during live-fire testing: public.security_events
-- has event_type CHECK (event_type = ANY (ARRAY['auth_failure', ...])) — a
-- fixed 24-value allow-list that does NOT include the brief's proposed
-- 'volume_spike_anomaly' / 'offhours_s5_anomaly' / 'new_county_anomaly' /
-- 'bulk_county_sweep' strings. Inserting any of them made the whole
-- detect_usage_anomalies() call error and roll back (PL/pgSQL functions are
-- atomic per top-level call) — every anomaly detected in that tick, not just
-- the offending one, would have been silently lost every 30 minutes forever.
-- Fixed by mapping onto the nearest allowed event_type (session_anomaly for
-- the two behavioural/timing anomalies, scraping_detected for the two
-- data-harvesting-footprint anomalies) and carrying the original fine-grained
-- label in p_details->>'anomaly_subtype' instead, so nothing downstream loses
-- the distinction.
--
-- Third deviation, also found during live-fire testing, architectural not
-- cosmetic: security_events.user_id has FOREIGN KEY (user_id) REFERENCES
-- auth.users(id). mcp_api_keys.customer_id / mcp_customers.customer_id is a
-- SEPARATE identity space (WorkOS-authenticated B2B API customers) with zero
-- overlap with auth.users — verified live: 0 of 13 real mcp_api_keys rows
-- join to auth.users on customer_id. Passing customer_id as p_user_id would
-- have made every single real MCP anomaly insert fail the FK and roll back
-- the entire detect_usage_anomalies() tick, forever — the feature would have
-- shipped permanently non-functional for its actual target population. Fixed
-- by passing p_user_id := NULL and carrying customer_id in
-- p_details->>'mcp_customer_id' instead. Telegram alerting (sweep_security_alerts
-- reads security_events directly) is unaffected; the user_watchlist auto-ban-
-- at-3-flags mechanism does NOT extend to MCP customers as a result — flagged
-- as a follow-up recommendation (a parallel mcp_key_watchlist + auto-suspend-
-- via-mcp_api_keys.is_active), not built here (separate feature, own brief).
begin;

-- ============================================================
-- DELIVERABLE 1 — mcp_usage_log (per-tool-call metadata)
-- ============================================================

create table if not exists public.mcp_usage_log (
  id            bigserial primary key,
  called_at     timestamptz not null default now(),
  api_key_hash  text not null,
  customer_id   uuid,
  tool_name     text not null,
  county_slug   text,
  ip_address    text,
  response_ms   integer,
  success       boolean not null default true,
  tier_id       text
);

comment on table public.mcp_usage_log is
  'Per-MCP-tool-call metadata for behavioural anomaly detection (GTM-22 SECURITY, 2026-08-03). '
  'No raw property data or PII — hashes, slugs, and tool names only. Auto-purged after 90 days.';

create index if not exists mcp_usage_log_key_called_idx
  on public.mcp_usage_log (api_key_hash, called_at desc);

create index if not exists mcp_usage_log_called_idx
  on public.mcp_usage_log (called_at desc);

alter table public.mcp_usage_log enable row level security;
alter table public.mcp_usage_log force row level security;

revoke all on public.mcp_usage_log from anon, authenticated;

drop policy if exists mcp_usage_log_service_all on public.mcp_usage_log;
create policy mcp_usage_log_service_all
  on public.mcp_usage_log
  for all
  to service_role
  using (true)
  with check (true);

select cron.schedule(
  'mcp-usage-log-purge',
  '0 3 * * *',
  $$delete from public.mcp_usage_log where called_at < now() - interval '90 days'$$
);

-- ============================================================
-- DELIVERABLE 2 — mcp_usage_baseline (per-customer-per-tool "normal" model)
-- ============================================================

create table if not exists public.mcp_usage_baseline (
  api_key_hash        text not null,
  tool_name           text not null,
  day_of_week         integer,           -- 0=Sun..6=Sat, NULL = any (unused by recompute today — reserved for future day-of-week baselines)
  hour_of_day         integer,           -- 0-23 ET, NULL = any (same reservation as day_of_week)
  avg_calls_per_day   numeric,
  p95_calls_per_hour  numeric,
  typical_counties    text[],
  first_seen_at       timestamptz,
  last_computed_at    timestamptz not null default now(),
  primary key (api_key_hash, tool_name)
);

comment on table public.mcp_usage_baseline is
  'Rolling 30-day "normal usage" model per api_key_hash+tool_name, recomputed nightly. '
  'day_of_week/hour_of_day columns reserved for a future finer-grained baseline — recompute_usage_baselines() leaves them NULL today.';

alter table public.mcp_usage_baseline enable row level security;
alter table public.mcp_usage_baseline force row level security;

revoke all on public.mcp_usage_baseline from anon, authenticated;

drop policy if exists mcp_usage_baseline_service_all on public.mcp_usage_baseline;
create policy mcp_usage_baseline_service_all
  on public.mcp_usage_baseline
  for all
  to service_role
  using (true)
  with check (true);

create or replace function public.recompute_usage_baselines()
returns void
language sql
security definer
set search_path = public
as $$
  insert into public.mcp_usage_baseline
    (api_key_hash, tool_name, avg_calls_per_day, p95_calls_per_hour, typical_counties, first_seen_at)
  select
    api_key_hash,
    tool_name,
    count(*)::numeric / nullif(count(distinct called_at::date), 0) as avg_calls_per_day,
    percentile_cont(0.95) within group (order by hourly_count) as p95_calls_per_hour,
    array_agg(distinct county_slug) filter (where county_slug is not null) as typical_counties,
    min(called_at) as first_seen_at
  from (
    select *, count(*) over (partition by api_key_hash, tool_name, date_trunc('hour', called_at)) as hourly_count
    from public.mcp_usage_log
    where called_at > now() - interval '30 days'
  ) sub
  group by api_key_hash, tool_name
  on conflict (api_key_hash, tool_name) do update set
    avg_calls_per_day  = excluded.avg_calls_per_day,
    p95_calls_per_hour = excluded.p95_calls_per_hour,
    typical_counties   = excluded.typical_counties,
    last_computed_at   = now();
$$;

comment on function public.recompute_usage_baselines() is
  'Nightly (pg_cron 0 2 * * *) — rebuilds the 30-day normal-usage model per api_key_hash+tool_name.';

select cron.schedule(
  'mcp-usage-baseline-recompute',
  '0 2 * * *',
  $$select public.recompute_usage_baselines()$$
);

-- ============================================================
-- DELIVERABLE 3 — detect_usage_anomalies() (core detection engine)
-- ============================================================

create or replace function public.detect_usage_anomalies()
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_window_start timestamptz := now() - interval '1 hour';
  v_rec record;
begin

  -- ANOMALY 1: Volume spike — current hour > 3x p95 baseline
  for v_rec in
    select
      u.api_key_hash, u.tool_name, u.customer_id,
      count(*) as calls_this_hour,
      b.p95_calls_per_hour as baseline,
      count(*) / nullif(b.p95_calls_per_hour, 0) as spike_ratio
    from public.mcp_usage_log u
    left join public.mcp_usage_baseline b
      on b.api_key_hash = u.api_key_hash and b.tool_name = u.tool_name
    where u.called_at > v_window_start
    group by u.api_key_hash, u.tool_name, u.customer_id, b.p95_calls_per_hour
    having count(*) > 10
    and (b.p95_calls_per_hour is null or count(*) > b.p95_calls_per_hour * 3)
  loop
    perform public.log_security_event(
      p_event_type := 'session_anomaly',
      p_severity := 'p1',
      p_user_id := null,
      p_ip_address := null,
      p_details := jsonb_build_object('anomaly_subtype', 'volume_spike', 'tool', v_rec.tool_name, 'calls_this_hour', v_rec.calls_this_hour, 'baseline_p95', v_rec.baseline, 'spike_ratio', v_rec.spike_ratio, 'api_key_hash', v_rec.api_key_hash, 'mcp_customer_id', v_rec.customer_id),
      p_platform := 'biddeed',
      p_request_path := '/api/mcp/' || v_rec.tool_name
    );
  end loop;

  -- ANOMALY 2: Off-hours bulk S5 calls (predict_auction_outcome outside 6am-10pm ET)
  for v_rec in
    select api_key_hash, customer_id, count(*) as s5_calls
    from public.mcp_usage_log
    where called_at > v_window_start
    and tool_name = 'predict_auction_outcome'
    and extract(hour from called_at at time zone 'America/New_York') not between 6 and 22
    group by api_key_hash, customer_id
    having count(*) >= 3
  loop
    perform public.log_security_event(
      p_event_type := 'session_anomaly',
      p_severity := 'p1',
      p_user_id := null,
      p_ip_address := null,
      p_details := jsonb_build_object('anomaly_subtype', 'offhours_s5', 's5_calls', v_rec.s5_calls, 'window', 'off-hours', 'api_key_hash', v_rec.api_key_hash, 'mcp_customer_id', v_rec.customer_id),
      p_platform := 'biddeed',
      p_request_path := '/api/mcp/predict_auction_outcome'
    );
  end loop;

  -- ANOMALY 3: New county never seen before in baseline (data harvesting signal)
  for v_rec in
    select u.api_key_hash, u.customer_id, u.county_slug, u.tool_name
    from public.mcp_usage_log u
    join public.mcp_usage_baseline b
      on b.api_key_hash = u.api_key_hash and b.tool_name = u.tool_name
    where u.called_at > v_window_start
    and u.county_slug is not null
    and not (u.county_slug = any(b.typical_counties))
    and array_length(b.typical_counties, 1) >= 3
    group by u.api_key_hash, u.customer_id, u.county_slug, u.tool_name
  loop
    perform public.log_security_event(
      p_event_type := 'scraping_detected',
      p_severity := 'p2',
      p_user_id := null,
      p_ip_address := null,
      p_details := jsonb_build_object('anomaly_subtype', 'new_county', 'county', v_rec.county_slug, 'tool', v_rec.tool_name, 'api_key_hash', v_rec.api_key_hash, 'mcp_customer_id', v_rec.customer_id),
      p_platform := 'biddeed',
      p_request_path := '/api/mcp/' || v_rec.tool_name
    );
  end loop;

  -- ANOMALY 4: Bulk county sweep — >10 distinct counties in 1 hour (data exfil signal)
  for v_rec in
    select api_key_hash, customer_id, count(distinct county_slug) as county_count
    from public.mcp_usage_log
    where called_at > v_window_start
    and county_slug is not null
    group by api_key_hash, customer_id
    having count(distinct county_slug) > 10
  loop
    perform public.log_security_event(
      p_event_type := 'scraping_detected',
      p_severity := 'p0',
      p_user_id := null,
      p_ip_address := null,
      p_details := jsonb_build_object('anomaly_subtype', 'bulk_county_sweep', 'distinct_counties', v_rec.county_count, 'window_minutes', 60, 'api_key_hash', v_rec.api_key_hash, 'mcp_customer_id', v_rec.customer_id),
      p_platform := 'biddeed',
      p_request_path := '/api/mcp'
    );
  end loop;

end;
$$;

comment on function public.detect_usage_anomalies() is
  'Runs every 30min via pg_cron. Flags 4 behavioural anomaly classes into public.security_events '
  '(p_user_id is NULL — mcp_customer_id lives in p_details, see migration header re: the '
  'auth.users FK; user_watchlist auto-ban therefore does NOT extend to MCP customers yet). '
  'Telegram alerting via sweep_security_alerts still fires — that reads security_events directly, '
  'not user_watchlist. Does not block or slow down any MCP tool call — reads mcp_usage_log only.';

select cron.schedule(
  'mcp-anomaly-detect-30min',
  '*/30 * * * *',
  $$select public.detect_usage_anomalies()$$
);

commit;
