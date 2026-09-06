-- GTM-6 (#20052) -- /r/:code must land variant-minted short codes on the
-- DEAL PAGE, not the /reels/:code interstitial (Ariel decision #2, chat
-- 2026-09-06). Live-confirmed this session: resolve_reel_link()'s
-- reel_variants branch (added #19782, hardened #19796 PART 2 in migration
-- 20260905a) NEVER reads winnerdata.reel_links.target or
-- winnerdata.biddeed_reels.landing_url for a variant-matched code -- it
-- unconditionally returns 'https://biddeed.ai/reels/' || p_code. Direct RPC
-- call proof (bypassing the flaky biddeed.ai edge -- see docs/spec/20052.md):
--   resolve_reel_link('F5oeMD') -> target: 'https://biddeed.ai/reels/F5oeMD'
-- even though biddeed_reels.landing_url/page_http_status for that reel_id
-- are 'https://biddeed.ai/deal/polk/2024ca000341000000' / 200.
--
-- Fix: when the parent reel's landing_url is set AND its page_http_status
-- is 200 (a verified-live deal page), redirect there; otherwise keep the
-- existing /reels/:code fallback (issue #19796 PART 2 behavior, unchanged
-- for reels with no live deal page). All other return fields (utm_source/
-- utm_medium/utm_campaign/variant_id/archetype/county/sale_type) and the
-- click-counter upsert into reel_variant_metrics are byte-identical to
-- 20260905a -- FUNCTION replace only, no table/column change, no grant
-- change (already public.execute'd to anon/authenticated/service_role).
--
-- The second branch (code found in winnerdata.reel_links, not
-- reel_variants) already reads v_row.target directly since #19752 --
-- unchanged here.

begin;

create or replace function public.resolve_reel_link(p_code text)
returns jsonb
language plpgsql
security definer
set search_path to 'public', 'winnerdata'
as $function$
declare
  v_variant winnerdata.reel_variants%rowtype;
  v_row     winnerdata.reel_links%rowtype;
  v_reel    winnerdata.biddeed_reels%rowtype;
  v_target  text;
begin
  select * into v_variant
  from winnerdata.reel_variants
  where short_code = p_code;

  if found then
    insert into winnerdata.reel_variant_metrics (variant_id, day, platform, clicks)
    values (v_variant.id, current_date, 'short_link', 1)
    on conflict (variant_id, day, platform)
    do update set clicks = winnerdata.reel_variant_metrics.clicks + 1,
                  updated_at = now();

    select * into v_reel from winnerdata.biddeed_reels where id = v_variant.reel_id;

    -- GTM-6 (#20052): deal page when it's verified live, else the
    -- /reels/:code interstitial (issue #19796 PART 2 fallback, unchanged).
    if v_reel.landing_url is not null and v_reel.page_http_status = 200 then
      v_target := v_reel.landing_url;
    else
      v_target := 'https://biddeed.ai/reels/' || p_code;
    end if;

    return jsonb_build_object(
      'target', v_target,
      'utm_source', 'reel_variant',
      'utm_medium', 'short_link',
      'utm_campaign', v_variant.variant_key,
      'variant_id', v_variant.id,
      'archetype', v_variant.archetype,
      'county', v_reel.county,
      'sale_type', v_reel.sale_type
    );
  end if;

  update winnerdata.reel_links
  set clicks = clicks + 1, updated_at = now()
  where code = p_code
  returning * into v_row;

  if not found then
    return null;
  end if;

  select * into v_reel from winnerdata.biddeed_reels where id = v_row.reel_id;

  return jsonb_build_object(
    'target', v_row.target,
    'utm_source', v_row.utm_source,
    'utm_medium', v_row.utm_medium,
    'utm_campaign', v_row.utm_campaign,
    'utm_content', v_row.utm_content,
    'county', v_reel.county,
    'sale_type', v_reel.sale_type
  );
end;
$function$;

commit;
