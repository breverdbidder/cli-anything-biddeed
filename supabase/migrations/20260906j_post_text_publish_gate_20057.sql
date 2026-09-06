-- Issue #20057 (GTM-8 / M9): clickable deal-page link must ship IN THE POST
-- (description first line + pinned comment on YouTube, caption first line on
-- IG/TikTok/Facebook) -- gate the publish queue on it.
--
-- Ariel's own finding (2026-09-06): the end-card "See this deal ->" + QR +
-- biddeed.ai/r/<code> burned into the video frame is not clickable on any
-- platform. The redirect chain itself is fine (verified #20052) -- what was
-- missing is the one-tap path: the clickable short link living in the post
-- TEXT, not just the video pixels. This migration is schema-only (additive):
-- a jsonb column on the existing non-critical winnerdata.reel_variants table
-- (not in the M2 protected-objects list), a new table for the IG/TikTok/
-- Facebook link-in-bio rotation, a widened status CHECK constraint (additive
-- value, nothing removed), and a queue-view predicate addition.

begin;

-- ---------------------------------------------------------------------------
-- 1. winnerdata.reel_variants.post_text -- per-platform post text (title/
--    description/pinned_comment for YouTube; caption for IG/TikTok/
--    Facebook), built by agents/reel_studio/post_text_builder.py. Keyed by
--    platform only (see that module's build_post_text() docstring for why
--    lang is not a second jsonb key -- each row is already single-language).
-- ---------------------------------------------------------------------------
alter table winnerdata.reel_variants
    add column if not exists post_text jsonb;

comment on column winnerdata.reel_variants.post_text is
    'issue #20057 -- per-platform post text (youtube: {title, description, '
    'pinned_comment, pinned_comment_id, link}; instagram/facebook/tiktok: '
    '{caption, link_in_bio_target, note}), built by agents/reel_studio/'
    'post_text_builder.py::build_post_text(). The YouTube description''s '
    'first line and the pinned_comment both carry the variant''s own '
    'https://biddeed.ai/r/<code> short link -- the clickable one-tap path '
    'the end-card burn-in cannot provide on its own.';

-- ---------------------------------------------------------------------------
-- 2. Widen reel_variants.status to add 'publish_error' (additive value,
--    M2) -- a Short that uploaded but whose pinned-comment insert failed is
--    not "published" under M9 (issue deliverable 4), and needs a status
--    distinct from the pre-existing generic 'error' (which #19782 already
--    uses for render/QA pipeline failures) so the two failure classes don't
--    get confused in the LMS or in any future dashboard.
-- ---------------------------------------------------------------------------
alter table winnerdata.reel_variants
    drop constraint if exists reel_variants_status_check;
alter table winnerdata.reel_variants
    add constraint reel_variants_status_check
    check (status in ('pending_approval', 'approved', 'rejected', 'error', 'publish_error'));

-- ---------------------------------------------------------------------------
-- 3. winnerdata.link_in_bio_targets -- IG/TikTok/Facebook do not render a
--    clickable caption link (issue body); the one-tap path on those
--    platforms is the account's bio link, which must rotate to point at the
--    newest published deal. No IG/TikTok/Facebook publish lane exists
--    anywhere in this repo yet (only the dormant YouTube lane, #19788,
--    does) -- every row this migration or its backfill inserts is
--    status='pending' (a candidate target), never 'live', until a real
--    publish step for that platform exists to flip it. See
--    docs/spec/20057.md for why this session does not fabricate a live
--    state (Honesty Protocol V3).
-- ---------------------------------------------------------------------------
create table if not exists winnerdata.link_in_bio_targets (
    id           uuid primary key default gen_random_uuid(),
    platform     text not null check (platform in ('instagram', 'facebook', 'tiktok')),
    variant_id   uuid not null references winnerdata.reel_variants(id),
    target_url   text not null,
    status       text not null default 'pending' check (status in ('pending', 'live')),
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now(),
    unique (platform, variant_id)
);

create index if not exists link_in_bio_targets_platform_status_idx
    on winnerdata.link_in_bio_targets (platform, status);

alter table winnerdata.link_in_bio_targets enable row level security;
-- No anon/authenticated policy -- same default-deny posture as every other
-- winnerdata table (service_role/postgres bypass RLS).

comment on table winnerdata.link_in_bio_targets is
    'issue #20057 -- rotation candidates for the IG/TikTok/Facebook '
    'account bio link (those platforms do not render a clickable caption '
    'link). status=''live'' is set only by a real publish step for that '
    'platform, which does not exist in this repo yet -- every row from the '
    '#20057 backfill is status=''pending''.';

-- ---------------------------------------------------------------------------
-- 4. youtube_publish_queue -- gate on post_text existing and its
--    description's first line carrying the variant's own short_url. Column
--    list changes (adds rv.post_text), so DROP+CREATE (CREATE OR REPLACE
--    VIEW rejects a column-list change with 42P16, same issue #19788/#19804
--    already hit).
--
--    Gate implemented as "first line of the description contains the
--    variant's own short_url" rather than a strict string-PREFIX match
--    against the bare short_url: the issue's own format for that line (work
--    item 1) is "See this deal -> https://biddeed.ai/r/<code>", i.e. a label
--    precedes the URL, so requiring the raw description string to literally
--    start with the bare URL would contradict the format the same issue
--    specifies. INFERRED reconciliation, documented in docs/spec/20057.md.
-- ---------------------------------------------------------------------------
drop view if exists winnerdata.youtube_publish_queue;

create view winnerdata.youtube_publish_queue as
select *
from (
    select
        vs.variant_id,
        vs.reel_id,
        rv.variant_key,
        rv.title,
        rv.short_code,
        rv.short_url,
        rv.video_url,
        rv.hashtags,
        rv.is_draft,
        rv.lang,
        rv.post_text,
        br.sale_type,
        br.phase,
        br.auction_date,
        br.county,
        br.landing_url,
        br.page_http_status,
        coalesce(br.duration_bolt32_sec, br.duration_sec) as duration_sec,
        case
            when coalesce(br.duration_bolt32_sec, br.duration_sec, 0::numeric) <= 60::numeric then 'shorts'::text
            else 'longform'::text
        end as video_type,
        vs.ariel_decision,
        vs.plays,
        vs.p50_watch_through,
        vs.loop_rate,
        vs.ctr,
        vs.captures,
        rv.created_at,
        row_number() over (
            partition by br.sale_type
            order by
                (vs.ctr is null), vs.ctr desc,
                (vs.p50_watch_through is null), vs.p50_watch_through desc,
                (vs.plays is null), vs.plays desc,
                rv.created_at asc
        ) as sale_type_rank
    from winnerdata.v_variant_scoreboard vs
        join winnerdata.reel_variants rv on rv.id = vs.variant_id
        join winnerdata.biddeed_reels br on br.id = rv.reel_id
        left join youtube_uploads yu on yu.variant_id = rv.id
            and yu.upload_status = any (array['queued'::text, 'uploading'::text, 'uploaded'::text])
    where rv.qa_pass = true
        and rv.is_draft = false
        and rv.lang = 'en'
        and br.page_http_status = 200
        and vs.ariel_decision = 'approved'::text
        and yu.id is null
        -- issue #20057 -- clickable link must ship IN THE POST, not just the
        -- end-card burn-in.
        and rv.post_text is not null
        and rv.post_text -> 'youtube' ->> 'description' is not null
        and rv.post_text -> 'youtube' ->> 'pinned_comment' is not null
        and split_part(rv.post_text -> 'youtube' ->> 'description', E'\n', 1)
            like ('%' || rv.short_url || '%')
) ranked
where sale_type_rank <= 20
order by sale_type, sale_type_rank;

comment on view winnerdata.youtube_publish_queue is
    'issue #20057 -- adds the post_text publish gate (description first line '
    'must carry the variant''s own short_url; pinned_comment must exist) on '
    'top of #19804''s per-sale_type-ranked top-20/sale_type selection. Owner-'
    'rights view (not security_invoker): winnerdata is not exposed to anon/'
    'authenticated over PostgREST at all (permission denied for schema '
    'winnerdata, confirmed live), so this carries no elevated exposure '
    'beyond every other winnerdata view in this project. Read only via the '
    'Supabase Management API, same as every other winnerdata read in this '
    'repo.';

-- ---------------------------------------------------------------------------
-- 5. LMS reels review screen (issue deliverable 6) -- surface post_text so
--    Ariel approves the post description together with the video. CREATE OR
--    REPLACE is fine here: column list of the returned jsonb objects grows
--    (adds post_text), but this is a function return value, not a view
--    column list, so 42P16 does not apply.
-- ---------------------------------------------------------------------------
create or replace function public.lms_reel_variants_list()
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata, extensions
as $$
declare
  v_variants jsonb;
begin
  select coalesce(jsonb_agg(row_to_json(v) order by v.auction_date, v.county, v.sale_type, v.variant_key), '[]'::jsonb)
  into v_variants
  from (
    select
      rv.id as variant_id,
      rv.reel_id,
      rv.variant_key,
      rv.title,
      rv.archetype,
      rv.video_url,
      rv.short_code,
      rv.short_url,
      rv.qr_url,
      rv.qa_pass,
      rv.qa_scores,
      rv.is_draft,
      rv.lang,
      rv.post_text,
      rv.status as variant_status,
      br.county,
      br.sale_type,
      br.phase,
      br.auction_date,
      br.status as reel_status,
      br.page_http_status,
      rev.decision,
      rev.note,
      rev.decided_by,
      rev.decided_at
    from winnerdata.reel_variants rv
    join winnerdata.biddeed_reels br on br.id = rv.reel_id
    left join lateral (
      select r.decision, r.note, r.decided_by, r.decided_at
      from winnerdata.reel_variant_review r
      where r.variant_id = rv.id
      order by r.decided_at desc
      limit 1
    ) rev on true
    where rv.lang = 'en'
  ) v;

  return jsonb_build_object('ok', true, 'variants', v_variants);
end;
$$;

revoke all on function public.lms_reel_variants_list() from public;
grant execute on function public.lms_reel_variants_list() to service_role;

commit;
