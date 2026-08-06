-- Issue #18307 (S5 v1.2 interactive HTML report) — server-side ownership gate
-- for GET /report/:mca_id on the Cloudflare Worker.
--
-- mcp_api_keys and s5_pdf_cache are both RLS-locked to service_role only
-- (verified live 2026-08-06 via pg_policy: anon_key_lookup on mcp_api_keys
-- requires active=true but the worker also needs the customer_id join into
-- s5_pdf_cache, which anon cannot read at all — service_role_only_pdf_cache).
-- The Worker only has the anon key (same pattern as every other route in
-- src/worker.js), so the lookup+ownership check is wrapped in one
-- SECURITY DEFINER RPC that returns a minimal verdict — never raw key or
-- billing rows — matching the existing RPC-gated pattern already used by
-- chat_rate_check_v2 / claim_key_for_session / get_all_counties_with_status.
create or replace function public.check_s5_report_access(p_key_hash text, p_mca_id uuid)
returns table(ok boolean, customer_id uuid, reason text)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_key record;
  v_owns boolean;
begin
  select mak.customer_id, mak.active, mak.is_active
    into v_key
    from public.mcp_api_keys mak
    where mak.key_hash = p_key_hash
    limit 1;

  if v_key is null then
    return query select false, null::uuid, 'invalid_key';
    return;
  end if;

  if not coalesce(v_key.active, false) or not coalesce(v_key.is_active, false) then
    return query select false, v_key.customer_id, 'key_inactive';
    return;
  end if;

  select exists(
    select 1 from public.s5_pdf_cache spc
    where spc.mca_id = p_mca_id and spc.customer_id = v_key.customer_id
  ) into v_owns;

  if not v_owns then
    return query select false, v_key.customer_id, 'no_purchase';
    return;
  end if;

  return query select true, v_key.customer_id, 'ok';
end;
$$;

grant execute on function public.check_s5_report_access(text, uuid) to anon, authenticated;
