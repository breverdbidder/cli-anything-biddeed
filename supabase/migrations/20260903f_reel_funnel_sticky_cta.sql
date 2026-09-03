-- CMO Factory CP3e (issue #19786) -- CTA/link system columns + the 5 Sticky
-- Layers schema (reel -> deal page -> memory). Additive only per M2/M5, no
-- existing column dropped/retyped, no row touched by this migration itself.
--
-- 1. winnerdata.biddeed_reels gains CTA-system columns: `archetype` (S2
--    intent-routing tag), the off-video CTA strings (PART 1 item 5:
--    caption/pinned-comment/per-platform UTM'd links so posting is
--    copy-paste, never re-typed), the on-video chip text actually rendered
--    (so QA's OCR readback has a stored expected value to diff against),
--    and `cta_qa` (jsonb evidence: OCR readback + decoded QR string + live
--    HEAD status + the 2 extracted frame URLs, per reel -- the DoD's own
--    "post the OCR string and decoded QR string per reel" requirement).
-- 2. winnerdata.reel_links gains `utm_content` -- extends the existing
--    utm_source/medium/campaign trio so per-variant attribution survives
--    platform (PART 1 item 5).
-- 3. public.lead_profiles (existing table, extended per S1 -- "find it,
--    don't create a parallel one", same instruction 20260902k already
--    applied) gains: `visitor_id` (first-party cookie/localStorage id for
--    ANONYMOUS pre-email tracking -- email stays nullable/unique as-is,
--    visitor_id is a second, independent unique key so a visitor can be
--    remembered before they ever submit an email), `first_reel_code`,
--    `first_county`, `first_archetype`, `properties_viewed` (jsonb array of
--    case_numbers), `last_seen`.
-- 4. winnerdata.funnel_events is NOT schema-changed (issue's own step names
--    -- reel_click/deal_view/gate_view/gate_submit/report_view -- fit its
--    existing generic session_id/step/params shape, same pattern
--    reel_watch_pct already uses). `public.log_funnel_event()` is the new
--    generic RPC the Worker calls for all 5, mirroring
--    log_reel_watch_event()'s allow-list-then-insert shape.
-- 5. `public.upsert_visitor_profile()` -- S1 SECURITY DEFINER RPC, anon-
--    writable (matches insert_reel_lead's existing grant pattern), upserts
--    by visitor_id (email stays null until a real lead-capture submit).
-- 6. `winnerdata.v_reel_funnel` -- reel/variant -> clicks -> deal_views ->
--    gate_views -> submits -> conversion %, the number issue #19782's
--    Analyst agent and /spi read. security_invoker=true per M2, no anon
--    grant (same read pattern v_reel_retention already uses).

begin;

alter table winnerdata.biddeed_reels
  add column if not exists archetype text,
  add column if not exists caption_full text,
  add column if not exists pinned_comment_text text,
  add column if not exists cta_chip_line1 text,
  add column if not exists cta_chip_line2 text,
  add column if not exists qr_label_text text,
  add column if not exists utm_links jsonb,
  add column if not exists cta_qa jsonb;

comment on column winnerdata.biddeed_reels.archetype is
  'S2 intent-routing tag (shock_number|nobody_bid|red_flag_warning|presale_countdown) -- travels with the short link via public.resolve_reel_link() so the landing page reorders to match the promise made in the reel.';
comment on column winnerdata.biddeed_reels.cta_qa is
  'CTA Director-QA evidence: {ocr_26s, ocr_31_5s, qr_decoded, url_live_status, frame_26s_url, frame_31_5s_url}. Populated by scripts/biddeed_reels_pipeline_bolt32.py QA step; null until a bolt32 row has passed QA at least once.';

alter table winnerdata.reel_links
  add column if not exists utm_content text;

alter table public.lead_profiles
  add column if not exists visitor_id text,
  add column if not exists first_reel_code text,
  add column if not exists first_county text,
  add column if not exists first_archetype text,
  add column if not exists properties_viewed jsonb not null default '[]'::jsonb,
  add column if not exists last_seen timestamptz;

create unique index if not exists lead_profiles_visitor_id_uidx
  on public.lead_profiles(visitor_id) where visitor_id is not null;

-- ---------------------------------------------------------------------
-- S1: visitor-profile upsert (anonymous, pre-email). Never overwrites an
-- already-set first_reel_code/first_county/first_archetype (first touch
-- wins, matches attribution convention), always appends the viewed
-- case_number (deduped) and bumps last_seen.
-- ---------------------------------------------------------------------
create or replace function public.upsert_visitor_profile(
  p_visitor_id text, p_reel_code text, p_county text, p_archetype text, p_case_number text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row public.lead_profiles%rowtype;
  v_already_seen boolean;
begin
  if p_visitor_id is null or length(p_visitor_id) < 8 then
    return jsonb_build_object('ok', false, 'error', 'invalid_visitor_id');
  end if;

  select * into v_row from public.lead_profiles where visitor_id = p_visitor_id limit 1;

  if not found then
    insert into public.lead_profiles (
      visitor_id, source, county, first_reel_code, first_county, first_archetype,
      properties_viewed, last_seen, score
    )
    values (
      p_visitor_id, 'reel_visitor', p_county, p_reel_code, p_county, p_archetype,
      case when p_case_number is not null then jsonb_build_array(p_case_number) else '[]'::jsonb end,
      now(), 10
    )
    returning * into v_row;
    return jsonb_build_object(
      'ok', true, 'returning', false, 'first_county', v_row.first_county,
      'properties_viewed_count', jsonb_array_length(v_row.properties_viewed)
    );
  end if;

  v_already_seen := p_case_number is not null and v_row.properties_viewed @> to_jsonb(p_case_number);

  update public.lead_profiles set
    first_reel_code = coalesce(v_row.first_reel_code, p_reel_code),
    first_county = coalesce(v_row.first_county, p_county),
    first_archetype = coalesce(v_row.first_archetype, p_archetype),
    properties_viewed = case
      when p_case_number is not null and not v_already_seen
        then v_row.properties_viewed || to_jsonb(p_case_number)
      else v_row.properties_viewed
    end,
    last_seen = now(),
    updated_at = now()
  where visitor_id = p_visitor_id
  returning * into v_row;

  return jsonb_build_object(
    'ok', true, 'returning', true, 'first_county', v_row.first_county,
    'properties_viewed_count', jsonb_array_length(v_row.properties_viewed)
  );
end;
$$;

grant execute on function public.upsert_visitor_profile(text, text, text, text, text) to anon, authenticated, service_role;

-- ---------------------------------------------------------------------
-- Generic funnel-event RPC (reel_click/deal_view/gate_view/gate_submit/
-- report_view) -- same shape as log_reel_watch_event(), different
-- allow-list, writes to the same pre-existing winnerdata.funnel_events.
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
  if p_step not in ('reel_click', 'deal_view', 'gate_view', 'gate_submit', 'report_view') then
    return jsonb_build_object('ok', false, 'error', 'invalid_step');
  end if;

  insert into winnerdata.funnel_events (session_id, step, params)
  values (coalesce(p_session_id, gen_random_uuid()::text), p_step, coalesce(p_params, '{}'::jsonb));

  return jsonb_build_object('ok', true);
end;
$$;

grant execute on function public.log_funnel_event(text, text, jsonb) to anon, authenticated, service_role;

-- ---------------------------------------------------------------------
-- v_reel_funnel -- reel/variant -> clicks -> deal_views -> gate_views ->
-- submits -> conversion %. clicks comes from reel_links (the existing
-- click counter), the 4 funnel stages from funnel_events keyed by
-- params->>'code'. security_invoker=true, no anon/authenticated grant --
-- same pattern v_reel_retention already established.
-- ---------------------------------------------------------------------
create or replace view winnerdata.v_reel_funnel
with (security_invoker = true) as
select
  r.id as reel_id,
  r.short_code,
  r.template,
  r.archetype,
  rl.utm_content as variant_key,
  coalesce(rl.clicks, 0) as clicks,
  count(*) filter (where fe.step = 'deal_view') as deal_views,
  count(*) filter (where fe.step = 'gate_view') as gate_views,
  count(*) filter (where fe.step = 'gate_submit') as gate_submits,
  case
    when count(*) filter (where fe.step = 'deal_view') > 0
      then round(100.0 * count(*) filter (where fe.step = 'gate_submit')
                 / count(*) filter (where fe.step = 'deal_view'), 1)
    else null
  end as conversion_pct
from winnerdata.biddeed_reels r
left join winnerdata.reel_links rl on rl.reel_id = r.id
left join winnerdata.funnel_events fe
  on fe.step in ('deal_view', 'gate_view', 'gate_submit')
  and (fe.params ->> 'code') = r.short_code
group by r.id, r.short_code, r.template, r.archetype, rl.utm_content, rl.clicks;

commit;
