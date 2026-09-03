-- Issue #19804 -- CMO Factory: sale-type-slotted cadence (foreclosure +
-- tax_deed daily slots) as the primary spec, superseding #19793's PART 4
-- "1 Analyst-ranked winner + 1 exploration variant, globally ranked"
-- description. That amendment was posted as a comment on #19793 and was
-- correctly deprioritized there per M6 (issue body > comment) -- this issue
-- makes the sale-type-slotted version the primary, authoritative spec.
--
-- Live-verified before writing this migration (2026-09-03, via
-- public.clerk_ssot_sale_rows / winnerdata.biddeed_reels / mgmt_sql.py --
-- see docs/spec/19804.md for full evidence):
--   - winnerdata.biddeed_reels: 20 foreclosure rows, 5 tax_deed rows,
--     all-time and all within the last 28 days (small dataset).
--   - Zero rows anywhere in the pipeline currently have qa_pass=true AND
--     ariel_decision='approved' AND page_http_status=200 -- the
--     `winnerdata.youtube_publish_queue` view returns 0 rows for EITHER
--     sale_type today. This is a genuine pre-approval-stage data ceiling,
--     not a bug in this migration.
--   - #19794 (clerk_ssot_sale_rows wiring) has NOT landed -- its issue is
--     still OPEN with a single "conclusion: failure" GHA comment, no PR, no
--     new tax_deed rows in winnerdata.biddeed_reels beyond the pre-#19794
--     baseline of 5. public.clerk_ssot_sale_rows itself already holds 11,396
--     tax_deed rows (624 in the last 28 days by sale_date) -- confirming
--     #19794's own finding that this is a wiring gap, not a coverage gap,
--     and that the starvation ladder built here is not hypothetical: it is
--     the live, expected path until #19794 lands.
--
-- M2: additive-by-default. New columns are nullable-or-defaulted; the
-- pre-existing `winner_slots`/`exploration_slots` columns are left in place
-- (not dropped) since #19793's original 2/day global-ranking reading of them
-- is superseded, not deleted -- see the updated `notes` value below.

-- ---------------------------------------------------------------------------
-- 1. Cadence config: two independent per-sale_type slots, replacing the
-- global-ranking "1 winner + 1 exploration" reading of the pilot's 2/day
-- figure. `foreclosure_slots`/`tax_deed_slots` are each a FLOOR (issue
-- body: "Both are the floor, not the cap") -- the 6/day quota ceiling from
-- #19788 (youtube_lib.MAX_UPLOADS_PER_DAY, unchanged) still bounds the top;
-- nothing here raises `max_uploads_per_day` past what it already floors to
-- (1 + 1 = 2, same pilot value #19793 shipped).
-- ---------------------------------------------------------------------------
alter table public.youtube_publish_cadence
    add column if not exists foreclosure_slots integer not null default 1,
    add column if not exists tax_deed_slots integer not null default 1,
    add column if not exists starvation_lookback_days integer not null default 14;

comment on column public.youtube_publish_cadence.winner_slots is
    'SUPERSEDED by issue #19804 -- global-ranking reading retired. Left in '
    'place (M2 additive-by-default), no longer read by agents/youtube/uploader.py.';
comment on column public.youtube_publish_cadence.exploration_slots is
    'SUPERSEDED by issue #19804 -- the exploration/Thompson-sampling floor '
    'variant no longer consumes its own slot; it rides inside whichever of '
    'foreclosure_slots/tax_deed_slots has the weaker confidence interval '
    '(fewer plays) that day. Left in place (M2 additive-by-default), no '
    'longer read by agents/youtube/uploader.py.';

update public.youtube_publish_cadence
set notes = 'issue #19804 -- sale-type-slotted cadence is now the primary '
    || 'spec (supersedes #19793 PART 4''s global-ranking 1-winner+1-'
    || 'exploration description). SLOT 1 = best foreclosure of the day '
    || '(Analyst-ranked within sale_type=''foreclosure''). SLOT 2 = best '
    || 'tax_deed of the day (Analyst-ranked within sale_type=''tax_deed''), '
    || 'with a starvation ladder: (a) most recent unpublished tax_deed reel '
    || 'within starvation_lookback_days, labelled by its real sale date, '
    || 'never ''today''; (b) a presale tax_deed reel for an upcoming county '
    || 'sale; (c) publish slot 1 alone and log SLOT_STARVED. Never promotes '
    || 'a second foreclosure into slot 2. The exploration/Thompson-sampling '
    || 'floor variant rides inside whichever slot has the weaker confidence '
    || 'interval that day rather than consuming a third slot. Both slots are '
    || 'a FLOOR, not a cap -- the 6/day #19788 quota ceiling still bounds '
    || 'the top. same_property_per_day unchanged.'
where id = true;

-- ---------------------------------------------------------------------------
-- 2. winnerdata.youtube_publish_queue -- rank per sale_type independently
-- instead of one global ranking capped at LIMIT 6 (the bug this issue
-- fixes: a flat global LIMIT could starve tax_deed entirely any day
-- foreclosure rows simply scored higher on ctr/watch/plays, even with
-- inventory sitting unused on the tax_deed side). DROP+CREATE, not CREATE OR
-- REPLACE, because the column list changes (adds sale_type, phase,
-- auction_date, sale_type_rank) -- CREATE OR REPLACE VIEW refuses a
-- column-list change with 42P16 (same issue #19788's own migration hit).
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
) ranked
-- Bounded per M3.3 (no unbounded sweep): top 20 per sale_type is generous
-- headroom for the starvation ladder's lookback/presale fallback search
-- without being an unbounded selection.
where sale_type_rank <= 20
order by sale_type, sale_type_rank;

comment on view winnerdata.youtube_publish_queue is
    'issue #19804 -- per-sale_type-ranked YouTube candidates (top 20 each of '
    'foreclosure/tax_deed), superseding the single global top-6 ranking from '
    '#19788/#19793. agents/youtube/uploader.py partitions this by sale_type '
    'and applies the SLOT 1 (foreclosure)/SLOT 2 (tax_deed, with starvation '
    'ladder) selection. Owner-rights view (not security_invoker): winnerdata '
    'is not exposed to anon/authenticated over PostgREST at all (permission '
    'denied for schema winnerdata, confirmed live), so this carries no '
    'elevated exposure beyond every other winnerdata view in this project. '
    'Read only via the Supabase Management API, same as every other '
    'winnerdata read in this repo.';
