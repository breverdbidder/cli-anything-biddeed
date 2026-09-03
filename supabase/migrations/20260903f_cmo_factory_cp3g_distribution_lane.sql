-- CMO FACTORY CP3g -- multimedia distribution lane (issue #19789)
--
-- QUEUE AUDIT (live, Sep 3 2026, via PostgREST select on social_content_queue):
--   684 rows total. status: pending=649, draft=35. target_platform:
--   linkedin_personal=237, telegram=202, reddit=125, bigger_pockets=120.
--   No 'pending_approval'/'approved' status exists today -- the existing
--   generator/worker pair (social-content-generator, social-publish-worker)
--   writes straight to status='pending' and social-publish-worker publishes
--   status='pending' rows immediately once linkedin_access_token lands in
--   the vault, with a code comment reading "No content review gate here by
--   design." That is an M1/M8 violation waiting to happen (fixed
--   separately in the same PR as this migration -- see
--   supabase/functions/social-publish-worker/index.ts). This migration
--   adds 'pending_approval' and 'approved' as valid statuses so the new
--   CP3g adapters (and, going forward, the legacy LinkedIn worker) can
--   express "drafted, held for Ariel's LMS click" without a second queue,
--   per the issue's explicit instruction not to create one.
--
-- The historical target_platform value 'linkedin_personal' predates the
-- CP3g requirement that LinkedIn posting go through a COMPANY PAGE
-- (w_organization_social), never a personal profile. Existing pending rows
-- are left untouched (not in scope, not destructive per M5) but this is
-- flagged loudly in docs/gtm/DISTRIBUTION_LANE.md as an open finding: the
-- 237 pending linkedin_personal rows should NOT be published by the new
-- LinkedIn org-page agent, and if/when personal LinkedIn posting is ever
-- re-authorized it needs its own explicit compliance review.

begin;

-- ---------------------------------------------------------------------
-- 1. social_content_queue: CP3g columns + status audit
-- ---------------------------------------------------------------------

alter table public.social_content_queue
  add column if not exists variant_key text,
  add column if not exists short_code text,
  add column if not exists utm_source text,
  add column if not exists utm_content text,
  add column if not exists approved_at timestamptz,
  add column if not exists approved_by text;

comment on column public.social_content_queue.variant_key is
  'bolt32 reel variant key this post was repurposed from (winnerdata.reel_variant_metrics.variant_key), null for text-only posts';
comment on column public.social_content_queue.short_code is
  'this row''s own /r/<code> short link (winnerdata.reel_links.code) -- distinct per platform, never shared, so attribution survives the platform (issue #19789)';
comment on column public.social_content_queue.approved_at is
  'set ONLY by Ariel''s approve click in the LMS (M1/M8). A scheduler/adapter may never set this column -- see negative test (e).';

alter table public.social_content_queue
  drop constraint if exists social_content_queue_status_check;

alter table public.social_content_queue
  add constraint social_content_queue_status_check
  check (status = any (array[
    'draft'::text,
    'pending'::text,
    'pending_approval'::text,
    'approved'::text,
    'published'::text,
    'failed'::text,
    'skipped_duplicate'::text,
    'not_configured'::text
  ]));

create index if not exists social_content_queue_variant_key_idx
  on public.social_content_queue (variant_key) where variant_key is not null;

-- ---------------------------------------------------------------------
-- 2. social_quota_ledger -- per-platform per-day post counter + cap
-- ---------------------------------------------------------------------

create table if not exists public.social_quota_ledger (
  id uuid primary key default gen_random_uuid(),
  platform text not null,
  ledger_date date not null default current_date,
  posts_used int not null default 0,
  daily_cap int not null,
  updated_at timestamptz not null default now(),
  unique (platform, ledger_date)
);

alter table public.social_quota_ledger enable row level security;
-- no anon/authenticated policy: service_role (adapters, GHA scheduler) is
-- the only writer/reader, same posture as agent_ops_log (M2).

-- ---------------------------------------------------------------------
-- 3. social_token_health -- one row per platform, daily refresh probe
-- ---------------------------------------------------------------------

create table if not exists public.social_token_health (
  platform text primary key,
  checked_at timestamptz,
  healthy boolean,
  detail text,
  consecutive_failures int not null default 0,
  updated_at timestamptz not null default now()
);

alter table public.social_token_health enable row level security;
-- no anon/authenticated policy, service_role only (same posture as above).

insert into public.social_token_health (platform, checked_at, healthy, detail, consecutive_failures)
values
  ('instagram', now(), false, 'NOT_CONFIGURED -- no credential in vault as of migration time', 0),
  ('facebook',  now(), false, 'NOT_CONFIGURED -- no credential in vault as of migration time', 0),
  ('tiktok',    now(), false, 'NOT_CONFIGURED -- no credential in vault as of migration time', 0),
  ('x',         now(), false, 'NOT_CONFIGURED -- no credential in vault; X API v2 also has no free tier as of Feb 2026 (pay-per-usage), see DISTRIBUTION_LANE.md open decision for Ariel', 0),
  ('linkedin_company', now(), false, 'NOT_CONFIGURED -- Community Management API is a Vetted Product requiring LinkedIn review + screencast, not yet requested', 0)
on conflict (platform) do nothing;

-- ---------------------------------------------------------------------
-- 4. winnerdata.reel_links: utm_content (per-variant attribution) +
--    a platform-short-link RPC adapters call instead of raw SQL.
-- ---------------------------------------------------------------------

alter table winnerdata.reel_links
  add column if not exists utm_content text;

create or replace function public.resolve_reel_link(p_code text)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_row winnerdata.reel_links%rowtype;
begin
  update winnerdata.reel_links
  set clicks = clicks + 1, updated_at = now()
  where code = p_code
  returning * into v_row;

  if not found then
    return null;
  end if;

  return jsonb_build_object(
    'target', v_row.target,
    'utm_source', v_row.utm_source,
    'utm_medium', v_row.utm_medium,
    'utm_campaign', v_row.utm_campaign,
    'utm_content', v_row.utm_content
  );
end;
$$;

-- Adapters call this instead of inserting into winnerdata.reel_links
-- directly (PostgREST has no winnerdata schema exposed -- see
-- docs/spec/19789.md -- so a public-schema SECURITY DEFINER wrapper is the
-- only write path available to a service_role-authenticated adapter).
-- Idempotent per (reel_id, platform, variant_key): re-running an adapter
-- for the same variant/platform reuses its existing code rather than
-- minting an orphan link, same idempotency contract as
-- scripts/biddeed_reels_pipeline_v2.py's ensure_short_link().
create or replace function public.create_platform_short_link(
  p_reel_id uuid,
  p_platform text,
  p_variant_key text,
  p_target text
)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_code text;
  v_existing winnerdata.reel_links%rowtype;
  v_base62 text := 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  v_attempt int := 0;
begin
  select * into v_existing
  from winnerdata.reel_links
  where reel_id = p_reel_id and utm_source = p_platform and utm_content = p_variant_key
  limit 1;

  if found then
    update winnerdata.reel_links
    set target = p_target, updated_at = now()
    where code = v_existing.code;
    return jsonb_build_object('code', v_existing.code, 'reused', true);
  end if;

  loop
    v_attempt := v_attempt + 1;
    v_code := '';
    for i in 1..6 loop
      v_code := v_code || substr(v_base62, (floor(random() * 62) + 1)::int, 1);
    end loop;
    exit when not exists (select 1 from winnerdata.reel_links where code = v_code) or v_attempt > 10;
  end loop;

  insert into winnerdata.reel_links (code, reel_id, target, utm_source, utm_medium, utm_campaign, utm_content)
  values (v_code, p_reel_id, p_target, p_platform, 'social', 'cmo_factory_distribution_v1', p_variant_key);

  return jsonb_build_object('code', v_code, 'reused', false);
end;
$$;

grant execute on function public.create_platform_short_link(uuid, text, text, text) to service_role;

commit;
