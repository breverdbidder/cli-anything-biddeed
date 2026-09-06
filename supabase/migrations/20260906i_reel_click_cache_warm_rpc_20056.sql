-- GTM-7 (#20056) -- /r/:code short-link Worker must never 404 on a DB blip.
-- The Worker now edge-caches resolve_reel_link()'s result (caches.default,
-- 24h TTL -- no Workers KV namespace is bound on this account yet and this
-- session has no Cloudflare API access to provision one, so Cache API is
-- the explicit fallback the issue itself allows). resolve_reel_link()
-- already increments the click counter as a side effect of the lookup
-- (winnerdata.reel_links.clicks, or winnerdata.reel_variant_metrics for a
-- variant short_code) -- correct for a cache MISS (a real Supabase round
-- trip happened) but wrong to call again on a cache HIT: re-running the
-- full lookup on every hit would (a) double-hit Supabase, defeating the
-- point of the cache, and (b) inflate clicks per hit instead of per request.
-- bump_reel_click() below is the increment-only half, safe to call
-- fire-and-forget on every cache hit.
--
-- list_reel_codes_for_cache_warm() feeds a one-time (and re-runnable)
-- backfill script that primes the edge cache for every code whose parent
-- reel has a verified-live deal page (page_http_status = 200), per the
-- issue's ask #3. Mirrors resolve_reel_link()'s two code namespaces
-- (reel_variants.short_code, winnerdata.reel_links.code) so no live code is
-- skipped.

begin;

create or replace function public.bump_reel_click(p_code text)
returns void
language plpgsql
security definer
set search_path to 'public', 'winnerdata'
as $function$
declare
  v_variant_id uuid;
begin
  select id into v_variant_id from winnerdata.reel_variants where short_code = p_code;

  if v_variant_id is not null then
    insert into winnerdata.reel_variant_metrics (variant_id, day, platform, clicks)
    values (v_variant_id, current_date, 'short_link', 1)
    on conflict (variant_id, day, platform)
    do update set clicks = winnerdata.reel_variant_metrics.clicks + 1,
                  updated_at = now();
    return;
  end if;

  update winnerdata.reel_links
  set clicks = clicks + 1, updated_at = now()
  where code = p_code;
end;
$function$;

grant execute on function public.bump_reel_click(text) to anon, authenticated, service_role;

create or replace function public.list_reel_codes_for_cache_warm()
returns text[]
language sql
security definer
set search_path to 'public', 'winnerdata'
as $function$
  select coalesce(array_agg(distinct code), array[]::text[])
  from (
    select v.short_code as code
    from winnerdata.reel_variants v
    join winnerdata.biddeed_reels r on r.id = v.reel_id
    where r.page_http_status = 200
    union
    select l.code
    from winnerdata.reel_links l
    join winnerdata.biddeed_reels r on r.id = l.reel_id
    where r.page_http_status = 200
  ) codes;
$function$;

grant execute on function public.list_reel_codes_for_cache_warm() to anon, authenticated, service_role;

commit;
