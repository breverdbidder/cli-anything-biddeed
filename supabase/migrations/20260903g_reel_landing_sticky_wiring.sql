-- CMO Factory CP3e (issue #19786) -- wires the 5 Sticky Layers schema
-- (20260903f) into the RPCs the Worker already calls, additive only.
--
-- 1. get_reel_landing(): adds `archetype` (S2 routing) and `short_code`
--    (so the Worker can log funnel_events keyed by code without a second
--    round-trip) to the existing field allow-list. No new field type that
--    could leak a name/vendor -- both are values this pipeline already
--    computes and stores on the row.
-- 2. insert_reel_lead(): adds an optional p_visitor_id (8th param, after
--    the existing p_source added by 20260903b -- NOT a replacement of that
--    param) so a visitor who already has an anonymous S1 profile
--    (public.lead_profiles keyed by visitor_id, no email) gets that SAME
--    row upgraded to their email instead of a second, disconnected row
--    being created. p_source's existing allow-list behavior is preserved
--    unchanged.

begin;

create or replace function public.get_reel_landing(p_county text, p_slug text, p_preview_id uuid default null)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_row winnerdata.biddeed_reels%rowtype;
begin
  select * into v_row
  from winnerdata.biddeed_reels
  where lower(replace(county, '_', '-')) = lower(p_county)
    and public.slugify_case_number(case_number) = lower(p_slug)
    and status in ('pending_approval', 'approved', 'posted')
  limit 1;

  if not found then
    return null;
  end if;

  if v_row.status = 'pending_approval' and (p_preview_id is null or p_preview_id <> v_row.id) then
    return null;
  end if;

  return jsonb_build_object(
    'id', v_row.id,
    'case_number', v_row.case_number,
    'county', v_row.county,
    'sale_type', v_row.sale_type,
    'auction_date', v_row.auction_date,
    'sold_amount', v_row.sold_amount,
    'assessed_value', v_row.assessed_value,
    'delta_pct', v_row.delta_pct,
    'condition_json', v_row.condition_json,
    'condition_score', v_row.condition_score,
    'aerial_tight_url', v_row.aerial_tight_url,
    'aerial_wide_url', v_row.aerial_wide_url,
    'street_url', v_row.street_url,
    'parcel_outline', v_row.parcel_outline,
    'status', v_row.status,
    'archetype', v_row.archetype,
    'short_code', v_row.short_code
  );
end;
$$;

grant execute on function public.get_reel_landing(text, text, uuid) to anon, authenticated, service_role;

-- CREATE OR REPLACE cannot widen a function's argument list -- the live
-- 7-arg signature (p_email..p_source, added by 20260903b) must be dropped
-- first, or Postgres treats an 8-arg version as a second overload and a
-- 7-arg call becomes ambiguous. Confirmed live signature via
-- pg_get_function_arguments() before writing this drop (not guessed).
drop function if exists public.insert_reel_lead(text, text, text, text, text, text, text);

create or replace function public.insert_reel_lead(
  p_email text, p_case_number text, p_county text,
  p_utm_source text, p_utm_medium text, p_utm_campaign text,
  p_source text default 'reel',
  p_visitor_id text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id uuid;
  v_source text;
begin
  v_source := case when p_source in ('reel', 'presale_deal') then p_source else 'reel' end;

  if p_visitor_id is not null and exists (
    select 1 from public.lead_profiles where visitor_id = p_visitor_id and email is null
  ) then
    update public.lead_profiles set
      email = p_email,
      case_number = coalesce(p_case_number, case_number),
      county = coalesce(p_county, county),
      source = v_source,
      utm_source = coalesce(p_utm_source, utm_source),
      utm_medium = coalesce(p_utm_medium, utm_medium),
      utm_campaign = coalesce(p_utm_campaign, utm_campaign),
      email_consent = true, email_consent_at = now(),
      marketing_consent = true, marketing_consent_at = now(),
      score = greatest(score, 50),
      updated_at = now()
    where visitor_id = p_visitor_id
    returning id into v_id;
    return jsonb_build_object('ok', true, 'id', v_id);
  end if;

  insert into public.lead_profiles (
    email, county, source, case_number, utm_source, utm_medium, utm_campaign,
    email_consent, email_consent_at, marketing_consent, marketing_consent_at, score, visitor_id
  )
  values (
    p_email, p_county, v_source, p_case_number, p_utm_source, p_utm_medium, p_utm_campaign,
    true, now(), true, now(), 50, p_visitor_id
  )
  on conflict (email) do update set
    case_number   = excluded.case_number,
    county        = coalesce(excluded.county, lead_profiles.county),
    source        = excluded.source,
    utm_source    = coalesce(excluded.utm_source, lead_profiles.utm_source),
    utm_medium    = coalesce(excluded.utm_medium, lead_profiles.utm_medium),
    utm_campaign  = coalesce(excluded.utm_campaign, lead_profiles.utm_campaign),
    updated_at    = now()
  returning id into v_id;

  return jsonb_build_object('ok', true, 'id', v_id);
end;
$$;

grant execute on function public.insert_reel_lead(text, text, text, text, text, text, text, text) to anon, authenticated, service_role;

-- 3. resolve_reel_link(): adds `utm_content` (already a reel_links column
--    per 20260903f) and `archetype` (joined from biddeed_reels) to its
--    jsonb so the short link carries S2's archetype and PART 1 item 5's
--    utm_content through to the /deal redirect, per the issue's own
--    "the archetype travels in the short link" requirement.
create or replace function public.resolve_reel_link(p_code text)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_row winnerdata.reel_links%rowtype;
  v_archetype text;
begin
  update winnerdata.reel_links
  set clicks = clicks + 1, updated_at = now()
  where code = p_code
  returning * into v_row;

  if not found then
    return null;
  end if;

  select archetype into v_archetype from winnerdata.biddeed_reels where id = v_row.reel_id;

  return jsonb_build_object(
    'target', v_row.target,
    'utm_source', v_row.utm_source,
    'utm_medium', v_row.utm_medium,
    'utm_campaign', v_row.utm_campaign,
    'utm_content', v_row.utm_content,
    'archetype', v_archetype
  );
end;
$$;

grant execute on function public.resolve_reel_link(text) to anon, authenticated, service_role;

commit;
