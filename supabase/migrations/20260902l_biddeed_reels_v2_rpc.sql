-- BidDeed Reels v2 (issue #19752) -- SECURITY DEFINER RPCs so the biddeed.ai
-- Cloudflare Worker (which only ever calls PostgREST with the public anon
-- key, per src/worker.js's existing upsert_lead_full/check_s5_report_access
-- pattern) can read winnerdata.biddeed_reels / winnerdata.reel_links and
-- write public.lead_profiles without those schemas/tables being directly
-- exposed via PostgREST (winnerdata is deliberately NOT in PostgREST's
-- db-schemas config -- see 20260824_winnerdata_ff_worker_rpc.sql's own note
-- that PATCHing that config previously broke a session).

begin;

-- Shared slug rule: lower-case, non [a-z0-9] runs collapse to a single '-',
-- leading/trailing '-' trimmed. Mirrored in scripts/biddeed_reels_lib.py's
-- slugify_case_number() for the pipeline to build landing_url identically.
create or replace function public.slugify_case_number(p text)
returns text
language sql
immutable
as $$
  select trim(both '-' from regexp_replace(lower(coalesce(p, '')), '[^a-z0-9]+', '-', 'g'));
$$;

grant execute on function public.slugify_case_number(text) to anon, authenticated, service_role;

-- GET /deal/{county}/{slug} landing-page lookup. Only pending_approval rows
-- gate on p_preview_id matching the row's own id (Ariel QA before approval,
-- per T2 spec) -- approved/posted rows always render, anything else (or a
-- status outside that set, or no match at all) returns null -> Worker 404s.
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
    'status', v_row.status
  );
end;
$$;

grant execute on function public.get_reel_landing(text, text, uuid) to anon, authenticated, service_role;

-- GET /r/{code} short-link resolve. Atomically increments clicks so a
-- single RPC round-trip both resolves the redirect target and counts the
-- hit -- no separate fire-and-forget increment call needed.
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
    'utm_campaign', v_row.utm_campaign
  );
end;
$$;

grant execute on function public.resolve_reel_link(text) to anon, authenticated, service_role;

-- POST landing-page email capture -- writes into the EXISTING
-- public.lead_profiles table (T2 instruction: "find it; don't create a
-- parallel one"), source='reel'.
create or replace function public.insert_reel_lead(
  p_email text, p_case_number text, p_county text,
  p_utm_source text, p_utm_medium text, p_utm_campaign text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id uuid;
begin
  insert into public.lead_profiles (
    email, county, source, case_number, utm_source, utm_medium, utm_campaign,
    email_consent, email_consent_at, marketing_consent, marketing_consent_at, score
  )
  values (
    p_email, p_county, 'reel', p_case_number, p_utm_source, p_utm_medium, p_utm_campaign,
    true, now(), true, now(), 50
  )
  on conflict (email) do update set
    case_number   = excluded.case_number,
    county        = coalesce(excluded.county, lead_profiles.county),
    utm_source    = coalesce(excluded.utm_source, lead_profiles.utm_source),
    utm_medium    = coalesce(excluded.utm_medium, lead_profiles.utm_medium),
    utm_campaign  = coalesce(excluded.utm_campaign, lead_profiles.utm_campaign),
    updated_at    = now()
  returning id into v_id;

  return jsonb_build_object('ok', true, 'id', v_id);
end;
$$;

grant execute on function public.insert_reel_lead(text, text, text, text, text, text) to anon, authenticated, service_role;

commit;
