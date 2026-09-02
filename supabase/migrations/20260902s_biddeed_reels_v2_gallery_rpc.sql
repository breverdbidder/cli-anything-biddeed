-- BidDeed Reels v2 (issue #19752) -- directive #4C (Ariel, 2026-09-02 21:16
-- EDT, new T8): GET /reels gallery + GET /reels/:code single-reel page.
-- Neither MP4s nor TikTok/IG/Shorts allow a clickable overlay -- a page WE
-- host can. This RPC feeds both routes from the same field allow-list
-- get_reel_landing() already established (no name/vendor field is ever
-- selectable here either).

begin;

create or replace function public.list_public_reels(p_include_pending boolean default false)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_rows jsonb;
begin
  select coalesce(jsonb_agg(t order by t.auction_date desc, t.case_number), '[]'::jsonb)
  into v_rows
  from (
    select
      r.id, r.case_number, r.county, r.sale_type, r.auction_date,
      r.sold_amount, r.delta_pct, r.condition_json, r.condition_score,
      r.aerial_tight_url, r.video_v2_url, r.short_url, r.short_code,
      r.landing_url, r.status
    from winnerdata.biddeed_reels r
    where r.video_v2_url is not null
      and (
        r.status in ('approved', 'posted')
        or (p_include_pending and r.status = 'pending_approval')
      )
  ) t;

  return v_rows;
end;
$$;

grant execute on function public.list_public_reels(boolean) to anon, authenticated, service_role;

-- Single-reel lookup by short_code, reusing the same allow-list -- feeds
-- GET /reels/:code (distinct from resolve_reel_link, which 302s and
-- increments clicks; this one just reads for the player page and must NOT
-- double-count a click when the page is loaded, not shared/redirected to).
create or replace function public.get_reel_by_code(p_code text, p_preview_id uuid default null)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_row winnerdata.biddeed_reels%rowtype;
begin
  select r.* into v_row
  from winnerdata.biddeed_reels r
  join winnerdata.reel_links l on l.reel_id = r.id
  where l.code = p_code
    and r.status in ('pending_approval', 'approved', 'posted')
  limit 1;

  if not found then
    return null;
  end if;

  if v_row.status = 'pending_approval' and (p_preview_id is null or p_preview_id <> v_row.id) then
    return null;
  end if;

  return jsonb_build_object(
    'id', v_row.id, 'case_number', v_row.case_number, 'county', v_row.county,
    'sale_type', v_row.sale_type, 'auction_date', v_row.auction_date,
    'sold_amount', v_row.sold_amount, 'assessed_value', v_row.assessed_value,
    'delta_pct', v_row.delta_pct, 'condition_json', v_row.condition_json,
    'condition_score', v_row.condition_score, 'aerial_tight_url', v_row.aerial_tight_url,
    'video_v2_url', v_row.video_v2_url, 'short_url', v_row.short_url,
    'landing_url', v_row.landing_url, 'status', v_row.status
  );
end;
$$;

grant execute on function public.get_reel_by_code(text, uuid) to anon, authenticated, service_role;

commit;
