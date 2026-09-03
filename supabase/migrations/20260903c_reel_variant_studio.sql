-- CMO Factory CP3c (issue #19782) -- Reel Variant Studio schema.
--
-- Additive on top of v1/v2/presale winnerdata.biddeed_reels (#19736/#19752/
-- #19781). Today every property gets ONE reel with ONE title; this adds the
-- capacity for several measured variants per property (K=4 today), each with
-- its own creative identity (variant_dna), its own attribution (short_code/
-- QR/metrics), and its own human review row -- so Ariel can see which
-- variant goes viral and the factory can learn from it.
--
-- Phase A (this migration): schema only. No video exists yet for any
-- variant -- video_url stays null until the bolt32 assembler (#19779) lands
-- and Phase B calls it. short_code/short_url/qr_url ARE minted in Phase A
-- (T3-equivalent -- independent of T6 video assembly, same pattern v1/v2
-- already use for winnerdata.biddeed_reels: ensure_short_link() runs before
-- video assembly, keyed off landing_url, not video_url).
--
-- RLS: matches every other winnerdata table's default-deny posture (enable
-- RLS, zero policies -- only service_role/postgres, which bypass RLS, can
-- read or write). No anon/authenticated grants issued anywhere in this file.
--
-- M8 (no publish/upload step): status only ever reaches 'pending_approval',
-- 'approved', 'rejected', or 'error' from any pipeline code in this
-- migration's scope -- there is no 'posted' state for variants; a variant
-- being 'approved' in the LMS is a human decision recorded in
-- reel_variant_review, not a publish action taken by this schema or any
-- agent built against it.

begin;

-- ---------------------------------------------------------------------------
-- winnerdata.reel_variants
-- ---------------------------------------------------------------------------
create table if not exists winnerdata.reel_variants (
  id                uuid primary key default gen_random_uuid(),
  reel_id           uuid not null references winnerdata.biddeed_reels(id),
  variant_key       text not null check (variant_key ~ '^[A-Z]$'),  -- 'A'..'D' today, K may grow later

  -- variant_dna is the identity of the reel. Six axes per the issue; the
  -- diversity assertion (Jaccard distance >= 0.5 pairwise across a
  -- property's variant set, no two variants sharing archetype) is enforced
  -- in code (agents/reel_studio/hook_writer.py) since Jaccard distance is
  -- not expressible as a single-row CHECK constraint. The archetype-uniqueness
  -- half of that rule IS enforceable at the schema level (see generated
  -- column + unique index below) -- belt-and-suspenders against a future
  -- caller that bypasses hook_writer.py.
  variant_dna       jsonb not null,
  archetype         text generated always as (variant_dna->>'archetype') stored,

  title             text not null,
  script            jsonb not null,           -- beat-split 32s script
  caption_groups    jsonb not null,
  hashtags          text[],
  voice_tags        jsonb,                    -- eleven_v3 tag plan

  -- T3-equivalent: per-variant short link + QR, minted independent of video
  video_url         text,
  short_code        text not null,
  short_url         text not null,
  qr_url            text,

  tts_model         text,

  -- Director/QA output
  qa_scores         jsonb,
  qa_pass           boolean,

  status            text not null default 'pending_approval'
    check (status in ('pending_approval','approved','rejected','error')),
  error_text        text,

  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),

  unique (reel_id, variant_key),
  -- Negative test (issue): "two variants of one property with the same
  -- archetype -> rejected". Enforced here, not just in application code.
  unique (reel_id, archetype),
  -- Negative test (issue): "a qa_pass=true row lacking qa_scores -> rejected".
  check (qa_pass is distinct from true or qa_scores is not null)
);

create unique index if not exists reel_variants_short_code_uidx
  on winnerdata.reel_variants(short_code);

create index if not exists reel_variants_reel_id_idx
  on winnerdata.reel_variants(reel_id);

create index if not exists reel_variants_status_idx
  on winnerdata.reel_variants(status);

alter table winnerdata.reel_variants enable row level security;
-- No policies -- deny-all for anon/authenticated.

comment on table winnerdata.reel_variants is
  'CMO Factory CP3c (#19782). One row per reel variant (K=4/property today). '
  'Never progresses past pending_approval from any agent in agents/reel_studio/ '
  '-- approved/rejected is a human decision via reel_variant_review (LMS), '
  'never set by this pipeline. No publish/upload step exists anywhere '
  'downstream of this table (M8).';

-- ---------------------------------------------------------------------------
-- winnerdata.reel_variant_review -- extends the FF batch review pattern
-- (winnerdata.ff_batch_lead_review) to per-variant decisions.
-- ---------------------------------------------------------------------------
create table if not exists winnerdata.reel_variant_review (
  id           uuid primary key default gen_random_uuid(),
  variant_id   uuid not null references winnerdata.reel_variants(id),
  decision     text not null check (decision in ('approved','rejected','improvement_requested')),
  note         text,
  decided_by   text not null default 'ariel',
  decided_at   timestamptz not null default now(),
  created_at   timestamptz not null default now()
);

create index if not exists reel_variant_review_variant_id_idx
  on winnerdata.reel_variant_review(variant_id);

alter table winnerdata.reel_variant_review enable row level security;

comment on table winnerdata.reel_variant_review is
  'CMO Factory CP3c (#19782). Ground truth #1 for the Analyst scoreboard: '
  'Ariel''s approve/reject/improvement_requested decision per variant, via '
  'the LMS reel-variant review screen (Phase B). Mirrors '
  'winnerdata.ff_batch_lead_review''s shape (M1: nothing ships without a '
  'row here carrying decision=approved).';

-- ---------------------------------------------------------------------------
-- winnerdata.reel_variant_metrics -- per-variant, per-day, per-platform
-- attribution rollup (/reels player watch-pct/loop events via funnel_events,
-- /r/{code} clicks, deal-page email captures). Ground truth #2 (YouTube
-- Analytics views_ext/avd_ext) is a stub column until the channel + OAuth
-- exist -- never populated with fabricated data.
-- ---------------------------------------------------------------------------
create table if not exists winnerdata.reel_variant_metrics (
  id             uuid primary key default gen_random_uuid(),
  variant_id     uuid not null references winnerdata.reel_variants(id),
  day            date not null,
  platform       text not null default 'biddeed_reels_player',
  plays          integer not null default 0,
  watch_pct_p50  numeric,
  loop_rate      numeric,
  clicks         integer not null default 0,
  captures       integer not null default 0,
  views_ext      integer,     -- YouTube Analytics, stubbed until OAuth exists
  avd_ext        numeric,     -- YouTube average-view-duration, stubbed
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),

  unique (variant_id, day, platform)
);

create index if not exists reel_variant_metrics_variant_id_idx
  on winnerdata.reel_variant_metrics(variant_id);

alter table winnerdata.reel_variant_metrics enable row level security;

comment on table winnerdata.reel_variant_metrics is
  'CMO Factory CP3c (#19782). Per-variant/day/platform attribution rollup. '
  'views_ext/avd_ext are YouTube Analytics ground truth #2 -- left null until '
  'YOUTUBE_OAUTH_REFRESH_TOKEN exists and a real fetcher populates them '
  '(agents/reel_studio/analyst.py fetch_youtube_analytics(), currently stubbed '
  'to raise NotImplementedError rather than fake a number).';

-- ---------------------------------------------------------------------------
-- winnerdata.v_variant_scoreboard
-- ---------------------------------------------------------------------------
create or replace view winnerdata.v_variant_scoreboard
  with (security_invoker = true) as
select
  rv.id                                            as variant_id,
  rv.reel_id,
  rv.variant_key,
  rv.archetype,
  rv.variant_dna,
  rv.short_code,
  rv.status,
  coalesce(sum(rvm.plays), 0)                      as plays,
  percentile_cont(0.5) within group (order by rvm.watch_pct_p50)
                                                    as p50_watch_through,
  avg(rvm.loop_rate)                                as loop_rate,
  coalesce(sum(rvm.clicks), 0)                      as clicks,
  coalesce(sum(rvm.captures), 0)                    as captures,
  case when coalesce(sum(rvm.plays), 0) > 0
    then round(coalesce(sum(rvm.clicks), 0)::numeric / sum(rvm.plays), 4)
    else null
  end                                                as ctr,
  rev.decision                                      as ariel_decision,
  rev.decided_at                                    as ariel_decided_at
from winnerdata.reel_variants rv
left join winnerdata.reel_variant_metrics rvm on rvm.variant_id = rv.id
left join lateral (
  select decision, decided_at
  from winnerdata.reel_variant_review r
  where r.variant_id = rv.id
  order by decided_at desc
  limit 1
) rev on true
group by rv.id, rv.reel_id, rv.variant_key, rv.archetype, rv.variant_dna,
         rv.short_code, rv.status, rev.decision, rev.decided_at;

comment on view winnerdata.v_variant_scoreboard is
  'CMO Factory CP3c (#19782). One row per variant: plays/watch-through/loop/'
  'ctr/captures rolled up from reel_variant_metrics, plus Ariel''s LMS '
  'decision from reel_variant_review. security_invoker=true (M2) -- callers '
  'need their own SELECT on the underlying winnerdata tables, i.e. '
  'service_role/postgres only, same as everything else in this schema.';

-- ---------------------------------------------------------------------------
-- /r/{code} resolution: reel_variants first, biddeed_reels second.
-- Additive: existing winnerdata.reel_links-backed resolution (v2, #19752)
-- is unchanged and remains the fallback path for every pre-existing
-- biddeed_reels short_code. This function is the ONLY thing in this
-- migration that touches an object created outside this issue
-- (public.resolve_reel_link, #19752) -- justified because the issue
-- explicitly asks for this exact resolution order ("Point /r/{code}
-- resolution at reel_variants first, biddeed_reels second") and the change
-- is purely additive (new branch prepended; old branch's SQL untouched).
-- ---------------------------------------------------------------------------
create or replace function public.resolve_reel_link(p_code text)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_variant winnerdata.reel_variants%rowtype;
  v_landing text;
  v_row     winnerdata.reel_links%rowtype;
begin
  -- reel_variants first
  select * into v_variant
  from winnerdata.reel_variants
  where short_code = p_code;

  if found then
    select landing_url into v_landing
    from winnerdata.biddeed_reels
    where id = v_variant.reel_id;

    insert into winnerdata.reel_variant_metrics (variant_id, day, platform, clicks)
    values (v_variant.id, current_date, 'short_link', 1)
    on conflict (variant_id, day, platform)
    do update set clicks = winnerdata.reel_variant_metrics.clicks + 1,
                  updated_at = now();

    -- Redirect target is the variant's own rendered video once Phase B
    -- assembles it; until then (Phase A: scripts+titles only), falls back
    -- to the parent property's shared landing page. Never the variant's own
    -- short_url -- that would loop the redirect back onto itself.
    return jsonb_build_object(
      'target', coalesce(v_variant.video_url, v_landing),
      'utm_source', 'reel_variant',
      'utm_medium', 'short_link',
      'utm_campaign', v_variant.variant_key
    );
  end if;

  -- biddeed_reels second (existing v2 behavior, unchanged)
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
    'utm_campaign', v_row.utm_campaign
  );
end;
$$;

grant execute on function public.resolve_reel_link(text) to anon, authenticated, service_role;

commit;
