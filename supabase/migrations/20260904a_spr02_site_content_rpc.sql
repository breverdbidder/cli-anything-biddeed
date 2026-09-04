-- SPR-02 (issue #19830) -- answer-asset renderer + content-sync.
--
-- site.site_content already exists (columns: slug, title, hero_copy,
-- body_jsonb, published, updated_at -- confirmed live via Management API
-- information_schema query, 2026-09-04) but the `site` schema is NOT in
-- PostgREST's exposed-schemas list (confirmed live: a direct
-- /rest/v1/site_content request with Accept-Profile: site returns PGRST106
-- "Invalid schema: site. Only the following schemas are exposed: public,
-- graphql_public, pascal, geo_tracker, finance, winnerdata"). The Worker
-- (src/worker.js) only ever calls PostgREST with the public anon key, so it
-- cannot read/write this table directly -- same situation already solved
-- for winnerdata.biddeed_reels by 20260902l_biddeed_reels_v2_rpc.sql
-- (get_reel_landing / resolve_reel_link): a SECURITY DEFINER function in
-- `public` bridges the gap without exposing the schema itself. No new
-- table, no PostgREST config change -- additive only.

begin;

-- READ: renderer calls this per request. Returns null for a missing slug
-- OR an unpublished row -- the Worker 404s on null either way, so an
-- unpublished draft is never distinguishable from "doesn't exist" (avoids
-- leaking which slugs are queued).
create or replace function public.get_published_content(p_slug text)
returns jsonb
language sql
stable
security definer
set search_path = public, site
as $$
  select jsonb_build_object(
    'slug', slug,
    'title', title,
    'hero_copy', hero_copy,
    'body_jsonb', body_jsonb,
    'updated_at', updated_at
  )
  from site.site_content
  where slug = p_slug
    and published = true
  limit 1;
$$;

grant execute on function public.get_published_content(text) to anon, authenticated, service_role;

-- READ: sitemap.xml build -- published slugs only, per SPR-02 spec ("Sitemap
-- entries for published rows only").
create or replace function public.list_published_content_slugs()
returns table(slug text, updated_at timestamptz)
language sql
stable
security definer
set search_path = public, site
as $$
  select slug, updated_at
  from site.site_content
  where published = true
  order by slug;
$$;

grant execute on function public.list_published_content_slugs() to anon, authenticated, service_role;

-- WRITE: content-sync.yml calls this with the service-role key on push to
-- main touching content/**. Not granted to anon/authenticated -- publishing
-- is a service_role-only operation, matching the vault-accessor pattern in
-- CLAUDE.md's CREDENTIAL HANDLING section (restrict EXECUTE, don't rely on
-- an internal gate alone). Idempotent (upsert on slug), so a re-run of the
-- workflow for the same content is a no-op beyond updated_at.
create or replace function public.upsert_site_content(
  p_slug text,
  p_title text,
  p_hero_copy text,
  p_body_jsonb jsonb,
  p_published boolean
)
returns jsonb
language plpgsql
security definer
set search_path = public, site
as $$
declare
  v_row site.site_content%rowtype;
begin
  insert into site.site_content (slug, title, hero_copy, body_jsonb, published, updated_at)
  values (p_slug, p_title, p_hero_copy, p_body_jsonb, p_published, now())
  on conflict (slug) do update set
    title = excluded.title,
    hero_copy = excluded.hero_copy,
    body_jsonb = excluded.body_jsonb,
    published = excluded.published,
    updated_at = now()
  returning * into v_row;

  return jsonb_build_object('slug', v_row.slug, 'published', v_row.published, 'updated_at', v_row.updated_at);
end;
$$;

revoke all on function public.upsert_site_content(text, text, text, jsonb, boolean) from public;
grant execute on function public.upsert_site_content(text, text, text, jsonb, boolean) to service_role;

-- WRITE: throwaway-slug cleanup for the SPR-02 A10 proof (insert a test row,
-- curl it, delete it). Same access rule as the upsert.
create or replace function public.delete_site_content(p_slug text)
returns void
language sql
security definer
set search_path = public, site
as $$
  delete from site.site_content where slug = p_slug;
$$;

revoke all on function public.delete_site_content(text) from public;
grant execute on function public.delete_site_content(text) to service_role;

commit;
