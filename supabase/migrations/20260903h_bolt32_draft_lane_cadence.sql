-- Issue #19793 CMO Factory CP3c-C -- kokoro draft-TTS lane, ES/PT-BR
-- language variants, and the 2/day YouTube publish cadence.
--
-- M2: additive-by-default. Every new column is nullable-or-defaulted so no
-- existing row/caller breaks. The two constraint replacements (variant_key,
-- archetype uniqueness) are widened, not narrowed -- old callers that never
-- pass `lang` still get the same behavior because `lang` defaults to 'en'
-- and every one of the 20 live rows is already 'en'.

-- ---------------------------------------------------------------------------
-- 1. Draft-TTS lane columns on winnerdata.reel_variants
-- ---------------------------------------------------------------------------
alter table winnerdata.reel_variants
    add column if not exists is_draft boolean not null default false,
    add column if not exists render_mode text not null default 'final',
    add column if not exists pending_final_voice boolean not null default false,
    add column if not exists lang text not null default 'en';

alter table winnerdata.reel_variants
    drop constraint if exists reel_variants_render_mode_check;
alter table winnerdata.reel_variants
    add constraint reel_variants_render_mode_check
    check (render_mode in ('draft', 'final'));

-- A draft row can never carry tts_model='eleven_v3' (the canonical FINAL
-- English voice, see scripts/bolt32_tts_fallback.py) and a non-draft row can
-- never carry tts_model='kokoro' -- DB-level enforcement of the issue's own
-- "a draft can never be mistaken for, or uploaded as, final" requirement,
-- independent of any application-level check in assert_bolt32_tts_model().
alter table winnerdata.reel_variants
    drop constraint if exists reel_variants_draft_tts_model_check;
alter table winnerdata.reel_variants
    add constraint reel_variants_draft_tts_model_check
    check (
        (is_draft = false and (tts_model is null or tts_model <> 'kokoro'))
        or
        (is_draft = true and tts_model = 'kokoro')
    );

-- ---------------------------------------------------------------------------
-- 2. Widen uniqueness to include lang -- a translated (es/pt-BR) variant of
-- an already-approved English archetype/variant_key must be able to coexist
-- as its own row on the same reel_id.
-- ---------------------------------------------------------------------------
alter table winnerdata.reel_variants
    drop constraint if exists reel_variants_reel_id_archetype_key;
alter table winnerdata.reel_variants
    add constraint reel_variants_reel_id_archetype_lang_key
    unique (reel_id, archetype, lang);

alter table winnerdata.reel_variants
    drop constraint if exists reel_variants_reel_id_variant_key_key;
alter table winnerdata.reel_variants
    add constraint reel_variants_reel_id_variant_key_lang_key
    unique (reel_id, variant_key, lang);

-- ---------------------------------------------------------------------------
-- 3. Exclude drafts from the YouTube publish queue (defense in depth -- the
-- upload CLI also refuses is_draft=true directly, see agents/youtube/
-- uploader.py). DROP+CREATE, not CREATE OR REPLACE, because the column list
-- changes (adds rv.is_draft, rv.lang) -- CREATE OR REPLACE VIEW refuses a
-- column-list change with 42P16, same issue #19788's own migration hit.
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
    rv.is_draft,
    rv.lang,
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
    rv.created_at
from winnerdata.v_variant_scoreboard vs
    join winnerdata.reel_variants rv on rv.id = vs.variant_id
    join winnerdata.biddeed_reels br on br.id = rv.reel_id
    left join youtube_uploads yu on yu.variant_id = rv.id
        and yu.upload_status = any (array['queued'::text, 'uploading'::text, 'uploaded'::text])
where rv.qa_pass = true
    and rv.is_draft = false
    and rv.lang = 'en'  -- YouTube native-localized titles/descriptions per-language is a
                          -- separate deliverable (issue #19793 PART 3 distribution note);
                          -- non-English rows never enter this queue today.
    and br.page_http_status = 200
    and vs.ariel_decision = 'approved'::text
    and yu.id is null
order by (vs.ctr is null), vs.ctr desc,
         (vs.p50_watch_through is null), vs.p50_watch_through desc,
         (vs.plays is null), vs.plays desc,
         rv.created_at
limit 6;

-- ---------------------------------------------------------------------------
-- 4. Launch cadence config -- issue #19793 PART 4. A single, human-readable
-- config row (not a hardcoded constant) so the "2/day, not 6" pilot window
-- is queryable and auditable, distinct from youtube_lib.MAX_UPLOADS_PER_DAY
-- (the hard 9,600-unit/1,600-per-upload QUOTA ceiling, unchanged at 6 --
-- see docs/gtm/YOUTUBE_LANE.md "two different numbers" section).
-- ---------------------------------------------------------------------------
create table if not exists public.youtube_publish_cadence (
    id boolean primary key default true,          -- singleton row pattern
    max_uploads_per_day integer not null default 2,
    weekdays_only boolean not null default true,
    window_start_date date not null,
    window_days integer not null default 14,
    winner_slots integer not null default 1,       -- Analyst-ranked top pick
    exploration_slots integer not null default 1,  -- Thompson-sampling floor pick
    same_property_per_day boolean not null default true,
    notes text,
    updated_at timestamptz not null default now(),
    constraint youtube_publish_cadence_singleton check (id = true)
);
alter table public.youtube_publish_cadence enable row level security;

insert into public.youtube_publish_cadence
    (window_start_date, notes)
values
    (current_date, 'issue #19793 PART 4 -- 2/day Mon-Fri pilot, 14 days, '
        || '1 Analyst-ranked winner + 1 exploration variant. Do not revert '
        || 'to 6/day (that figure is the Google quota CEILING, not a '
        || 'publishing target) without 30 days of real retention data.')
on conflict (id) do nothing;

comment on table public.youtube_publish_cadence is
    'issue #19793 PART 4 -- publish-rate governor, independent of the '
    'youtube_quota_preflight_reserve() unit-budget gate. Both must pass '
    'for an upload to proceed.';
