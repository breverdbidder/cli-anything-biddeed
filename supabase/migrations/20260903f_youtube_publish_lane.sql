-- issue #19788: CMO Factory CP3f -- YouTube upload lane, built dormant.
-- No youtube_* vault secrets exist yet (checked live via get_vault_secret_mcp,
-- 2026-09-03: youtube_client_id/youtube_client_secret/youtube_oauth_refresh_token
-- all resolve null). Every object below is inert until those three secrets
-- land -- nothing here performs a network call.
--
-- Schema posture: public.* (not winnerdata.*) for the three new tables below,
-- matching the issue body's own literal "table public.youtube_quota_ledger"
-- / "public.youtube_token_health" naming. winnerdata.reel_variants /
-- reel_variant_review / reel_variant_metrics / v_variant_scoreboard (issue
-- #19782 CP3c) already exist live -- confirmed via
-- information_schema.tables/pg_views before writing this migration -- and
-- are read-only here (M5: no schema change to a production table unless the
-- issue body names it; this issue only names a *write* into
-- winnerdata.reel_variant_metrics(views_ext, avd_ext), not a column add).
--
-- winnerdata.youtube_publish_queue lives in the winnerdata schema (grouped
-- with the tables it selects from) and is read the same way every other
-- winnerdata object in this repo is read: the Supabase Management API
-- (SUPABASE_ACCESS_TOKEN), never PostgREST -- live-confirmed this session
-- that service_role gets "permission denied for schema winnerdata" (42501)
-- over PostgREST, same restriction scripts/biddeed_reels_lib.py's module
-- docstring already documents for every other winnerdata read/write in this
-- pipeline. Not a security gap introduced here.

-- ---------------------------------------------------------------------------
-- 1. Quota ledger (deliverable 2)
-- ---------------------------------------------------------------------------
create table if not exists public.youtube_quota_ledger (
  day_pacific date primary key,
  units_used int not null default 0,
  calls jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.youtube_quota_ledger enable row level security;
-- No anon/authenticated policy -- deny-all at the table. service_role
-- bypasses RLS (Supabase default), which is the only writer (the RPC below
-- and the daily jobs run with SUPABASE_SERVICE_ROLE_KEY).

-- Atomic pre-flight + reserve in one statement (SELECT ... FOR UPDATE inside
-- the same transaction as the UPDATE): the issue's own math is
-- 10,000/day project cap - 400 reserved for Analytics/channel reads = 9,600
-- upload budget, and 9,600 / 1,600 per videos.insert = exactly 6/day, so
-- the unit-based check below IS the "6 uploads/day maximum" enforcement,
-- not a separate counter that could drift from it.
create or replace function public.youtube_quota_preflight_reserve(
  p_units int,
  p_call_name text,
  p_daily_cap int default 10000,
  p_reserve int default 400
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_day date := (now() at time zone 'America/Los_Angeles')::date;
  v_used int;
  v_new int;
  v_budget int := p_daily_cap - p_reserve;
begin
  insert into public.youtube_quota_ledger (day_pacific, units_used, calls)
    values (v_day, 0, '[]'::jsonb)
    on conflict (day_pacific) do nothing;

  select units_used into v_used
    from public.youtube_quota_ledger
    where day_pacific = v_day
    for update;

  v_new := v_used + p_units;

  if v_new > v_budget then
    return jsonb_build_object(
      'allow', false, 'reason', 'quota_exceeded',
      'day_pacific', v_day, 'units_used', v_used, 'projected', v_new,
      'budget', v_budget, 'daily_cap', p_daily_cap, 'reserve', p_reserve
    );
  end if;

  update public.youtube_quota_ledger
    set units_used = v_new,
        calls = calls || jsonb_build_array(jsonb_build_object(
          'call', p_call_name, 'units', p_units, 'at', now()
        )),
        updated_at = now()
    where day_pacific = v_day;

  return jsonb_build_object(
    'allow', true, 'day_pacific', v_day, 'units_used', v_new,
    'budget', v_budget, 'daily_cap', p_daily_cap, 'reserve', p_reserve
  );
end;
$$;

revoke all on function public.youtube_quota_preflight_reserve(int, text, int, int) from public;
grant execute on function public.youtube_quota_preflight_reserve(int, text, int, int) to service_role;

-- ---------------------------------------------------------------------------
-- 2. Token health (deliverable 3)
-- ---------------------------------------------------------------------------
create table if not exists public.youtube_token_health (
  id uuid primary key default gen_random_uuid(),
  checked_at timestamptz not null default now(),
  ok boolean not null,
  error text
);

create index if not exists youtube_token_health_checked_at_idx
  on public.youtube_token_health (checked_at desc);

alter table public.youtube_token_health enable row level security;
-- No anon/authenticated policy -- same deny-all pattern as youtube_quota_ledger.

-- ---------------------------------------------------------------------------
-- 3. Upload metadata + tracking (built to satisfy deliverable 4's "stored on
--    the row" requirement for title/description/tags/pinned-comment, and
--    deliverable 7's "all uploads privacyStatus='private'" as a hard DB
--    constraint, not just a code convention -- negative test (d)).
--    New table, not a reel_variants column add (K3 surgical scope: CP3c
--    #19782 owns reel_variants' schema; this issue does not name that table
--    for alteration).
-- ---------------------------------------------------------------------------
create table if not exists public.youtube_uploads (
  id uuid primary key default gen_random_uuid(),
  variant_id uuid not null,
  reel_id uuid,
  county text,
  variant_key text,
  video_type text not null check (video_type in ('shorts', 'longform')),
  title text not null,
  description text not null,
  tags text[] not null default '{}',
  category_id text not null default '22',
  pinned_comment_text text not null,
  utm_link text not null,
  privacy_status text not null default 'private' check (privacy_status = 'private'),
  quota_units_planned int not null default 1600,
  quota_units_spent int not null default 0,
  upload_status text not null default 'queued'
    check (upload_status in (
      'queued', 'uploading', 'uploaded',
      'skipped_quota', 'skipped_not_configured', 'failed'
    )),
  youtube_video_id text,
  error_text text,
  day_pacific date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  uploaded_at timestamptz,
  unique (variant_id)
);

create index if not exists youtube_uploads_status_idx on public.youtube_uploads (upload_status);
create index if not exists youtube_uploads_day_idx on public.youtube_uploads (day_pacific);

alter table public.youtube_uploads enable row level security;
-- No anon/authenticated policy -- same deny-all pattern.

-- ---------------------------------------------------------------------------
-- 4. Selection view (deliverable 5) -- winnerdata schema, Management-API-only
--    read path (see header note). Filters: qa_pass=true, deal-page HTTP 200,
--    Ariel-approved (v_variant_scoreboard.ariel_decision='approved'), and
--    not already queued/uploaded in public.youtube_uploads. Ranking: no
--    explicit composite-score column exists on v_variant_scoreboard (#19782
--    ships plays/p50_watch_through/loop_rate/ctr/captures as separate
--    fields, no single "rank"), so this orders by the engagement signals
--    most correlated with "worth publishing" (ctr, then watch-through, then
--    raw plays) with a stable creation-time tiebreak -- documented as an
--    INFERRED ranking formula (see docs/spec/19788.md) since the issue names
--    "the Analyst's variant ranking" without giving its exact formula.
-- ---------------------------------------------------------------------------
drop view if exists winnerdata.youtube_publish_queue;

create view winnerdata.youtube_publish_queue as
select
  vs.variant_id,
  vs.reel_id,
  rv.variant_key,
  rv.title,
  rv.short_code,
  rv.short_url,
  rv.video_url,
  rv.hashtags,
  br.county,
  br.landing_url,
  br.page_http_status,
  coalesce(br.duration_bolt32_sec, br.duration_sec) as duration_sec,
  case
    when coalesce(br.duration_bolt32_sec, br.duration_sec, 0) <= 60 then 'shorts'
    else 'longform'
  end as video_type,
  vs.ariel_decision,
  vs.plays,
  vs.p50_watch_through,
  vs.loop_rate,
  vs.ctr,
  vs.captures,
  rv.created_at
from winnerdata.v_variant_scoreboard vs
join winnerdata.reel_variants rv on rv.id = vs.variant_id
join winnerdata.biddeed_reels br on br.id = rv.reel_id
left join public.youtube_uploads yu
  on yu.variant_id = rv.id
  and yu.upload_status in ('queued', 'uploading', 'uploaded')
where rv.qa_pass = true
  and br.page_http_status = 200
  and vs.ariel_decision = 'approved'
  and yu.id is null
order by
  (vs.ctr is null), vs.ctr desc,
  (vs.p50_watch_through is null), vs.p50_watch_through desc,
  (vs.plays is null), vs.plays desc,
  rv.created_at asc
limit 6;

comment on view winnerdata.youtube_publish_queue is
  'issue #19788 -- top-6 daily YouTube candidates. Owner-rights view (not '
  'security_invoker): winnerdata is not exposed to anon/authenticated over '
  'PostgREST at all (permission denied for schema winnerdata, confirmed '
  'live) so this carries no elevated exposure beyond every other winnerdata '
  'view in this project (v_variant_scoreboard, v_reel_retention). Read only '
  'via the Supabase Management API, same as every other winnerdata read in '
  'this repo.';
