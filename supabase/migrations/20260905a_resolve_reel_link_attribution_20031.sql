-- GTM-2 (#20031) -- enrich public.resolve_reel_link() to return
-- variant_id, county, sale_type, archetype (joined from
-- winnerdata.biddeed_reels via the existing reel_id FK) so the Worker's
-- /r/:code handler can carry them on the reel_click PostHog event
-- without a second round trip. FUNCTION replace only -- no table/column
-- change, no new grants (already public.execute'd to anon/authenticated/
-- service_role from the original migration).

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

    -- issue #19796 PART 2: point at this code's own /reels/ player page
    -- (which resolves and plays v_variant.video_url itself via
    -- get_reel_by_code()), never straight at the raw MP4.
    return jsonb_build_object(
      'target', 'https://biddeed.ai/reels/' || p_code,
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
