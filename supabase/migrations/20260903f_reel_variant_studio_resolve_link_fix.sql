-- CMO Factory CP3c (#19782) follow-up fix.
--
-- Live finding: between this migration's original apply and this point in
-- the same session, another concurrent process (not this session) replaced
-- public.resolve_reel_link() with a different body -- CREATE OR REPLACE
-- FUNCTION is a full overwrite, not a merge, and that version dropped the
-- reel_variants-first branch entirely while adding its own
-- archetype/utm_content lookups (winnerdata.biddeed_reels.archetype,
-- winnerdata.reel_links.utm_content -- both columns that did not exist
-- when this migration first ran). Detected live via
-- pg_get_functiondef('public.resolve_reel_link(text)'::regprocedure) no
-- longer containing 'reel_variants'.
--
-- Fix: re-apply the reel_variants-first branch as an additive prefix on
-- top of the CURRENT (other session's) fallback body, preserving its
-- archetype/utm_content additions rather than reverting them.

create or replace function public.resolve_reel_link(p_code text)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_variant winnerdata.reel_variants%rowtype;
  v_landing text;
  v_row winnerdata.reel_links%rowtype;
  v_archetype text;
begin
  -- reel_variants first (CP3c, #19782)
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

    return jsonb_build_object(
      'target', coalesce(v_variant.video_url, v_landing),
      'utm_source', 'reel_variant',
      'utm_medium', 'short_link',
      'utm_campaign', v_variant.variant_key
    );
  end if;

  -- biddeed_reels second -- current (other session's) behavior, preserved
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
