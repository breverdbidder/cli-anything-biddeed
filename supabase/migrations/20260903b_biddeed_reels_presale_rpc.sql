-- BidDeed Reels v3 (issue #19761) T2 -- presale deal-page RPC support.
--
-- 1. get_reel_landing() gains the new presale columns (phase, opening_bid,
--    judgment_amount, days_to_auction, presale_rank) in its returned jsonb.
--    Purely additive keys -- existing postsale callers (buildDealLandingHtml
--    in src/worker.js) already ignore unknown keys, so this is safe for v1/v2
--    rows. Gated presale intel (flip_rate_pct/avg_roi/zip_score/
--    anchors_in_zip/pa_link/ml estimate) is NOT a new column per T1's
--    explicit column list -- it travels inside the already-selected
--    condition_json.presale_intel (written by
--    scripts/biddeed_reels_pipeline_presale.py), so no RPC change was needed
--    for those fields specifically.
--
-- 2. check_paid_tier() -- the T2 "reuse the existing biddeed.ai auth +
--    Stripe tier check" gate. This site's only auth is the MCP API key
--    issued after a real Stripe checkout (mcp_api_keys, see
--    supabase/functions/stripe-webhook/index.ts issueKey()) -- there is no
--    cookie/session login anywhere in src/worker.js. This mirrors
--    check_s5_report_access's exact key_hash lookup pattern
--    (20260806_s5_report_access_gate.sql) rather than building new auth:
--    any row in mcp_api_keys is, by construction, a paid subscriber (rows
--    are only ever inserted by issueKey() post-payment) -- so "does an
--    active row exist for this key_hash" IS the paid-tier check.
--
-- 3. insert_reel_lead() gains p_source (default 'reel', preserving v1/v2
--    behavior byte-for-byte) so the presale "Set alert" capture can write
--    source='presale_deal' per the issue's explicit column value, without a
--    parallel insert function.

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
  order by (phase = 'presale') desc -- prefer a live presale row over a stale postsale row for the same slug, if both exist
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
    'phase', v_row.phase,
    'opening_bid', v_row.opening_bid,
    'judgment_amount', v_row.judgment_amount,
    'days_to_auction', v_row.days_to_auction,
    'presale_rank', v_row.presale_rank
  );
end;
$$;

grant execute on function public.get_reel_landing(text, text, uuid) to anon, authenticated, service_role;

-- T2 paid-tier gate -- see header note above. Never returns key material,
-- customer PII, or anything beyond a boolean + the tier label (matches
-- check_s5_report_access's "never raw key or billing rows" convention).
create or replace function public.check_paid_tier(p_key_hash text)
returns table(ok boolean, tier text)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_key record;
begin
  select mak.tier, mak.active, mak.is_active
    into v_key
    from public.mcp_api_keys mak
    where mak.key_hash = p_key_hash
    limit 1;

  if v_key is null or not coalesce(v_key.active, false) or not coalesce(v_key.is_active, false) then
    return query select false, null::text;
    return;
  end if;

  return query select true, v_key.tier;
end;
$$;

grant execute on function public.check_paid_tier(text) to anon, authenticated, service_role;

-- Drop the old 6-arg signature first -- PostgreSQL treats a 7th arg (even
-- with a default) as a distinct overload, and leaving both around makes any
-- 6-arg call ("insert_reel_lead(a,b,c,d,e,f)") ambiguous between the two.
drop function if exists public.insert_reel_lead(text, text, text, text, text, text);

create or replace function public.insert_reel_lead(
  p_email text, p_case_number text, p_county text,
  p_utm_source text, p_utm_medium text, p_utm_campaign text,
  p_source text default 'reel'
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
  -- allow-list, not free text -- a bad/forged form field must not land an
  -- arbitrary source string in lead_profiles.
  v_source := case when p_source in ('reel', 'presale_deal') then p_source else 'reel' end;

  insert into public.lead_profiles (
    email, county, source, case_number, utm_source, utm_medium, utm_campaign,
    email_consent, email_consent_at, marketing_consent, marketing_consent_at, score
  )
  values (
    p_email, p_county, v_source, p_case_number, p_utm_source, p_utm_medium, p_utm_campaign,
    true, now(), true, now(), 50
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

grant execute on function public.insert_reel_lead(text, text, text, text, text, text, text) to anon, authenticated, service_role;

commit;
