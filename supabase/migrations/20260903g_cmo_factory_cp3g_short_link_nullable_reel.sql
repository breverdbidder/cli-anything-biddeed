-- CMO FACTORY CP3g follow-up (issue #19789): winnerdata.reel_links.reel_id
-- was NOT NULL, which blocks short links for non-reel-sourced content --
-- e.g. LinkedIn B2B text posts, which per the issue are explicitly NOT
-- built from the bolt32 reel ("LinkedIn is NOT a place for the Bolt
-- grammar") but still need "ITS OWN short code /r/<code> with
-- utm_source=<platform> and utm_content=<variant_key>" for attribution.
-- Discovered live while wiring create_platform_short_link() for the
-- LinkedIn agent -- a fake-UUID probe against the function in the prior
-- migration (20260903f) surfaced the FK/NOT NULL constraint before any
-- real row was written, so this is a same-session correction, not a
-- production incident.

begin;

alter table winnerdata.reel_links
  alter column reel_id drop not null;

create or replace function public.create_platform_short_link(
  p_reel_id uuid,
  p_platform text,
  p_variant_key text,
  p_target text
)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_code text;
  v_existing winnerdata.reel_links%rowtype;
  v_base62 text := 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  v_attempt int := 0;
begin
  select * into v_existing
  from winnerdata.reel_links
  where reel_id is not distinct from p_reel_id
    and utm_source = p_platform
    and utm_content = p_variant_key
  limit 1;

  if found then
    update winnerdata.reel_links
    set target = p_target, updated_at = now()
    where code = v_existing.code;
    return jsonb_build_object('code', v_existing.code, 'reused', true);
  end if;

  loop
    v_attempt := v_attempt + 1;
    v_code := '';
    for i in 1..6 loop
      v_code := v_code || substr(v_base62, (floor(random() * 62) + 1)::int, 1);
    end loop;
    exit when not exists (select 1 from winnerdata.reel_links where code = v_code) or v_attempt > 10;
  end loop;

  insert into winnerdata.reel_links (code, reel_id, target, utm_source, utm_medium, utm_campaign, utm_content)
  values (v_code, p_reel_id, p_target, p_platform, 'social', 'cmo_factory_distribution_v1', p_variant_key);

  return jsonb_build_object('code', v_code, 'reused', false);
end;
$$;

commit;
