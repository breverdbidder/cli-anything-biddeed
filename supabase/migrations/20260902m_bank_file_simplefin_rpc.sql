-- CFO v1 Issue E (#19749): bank file importer (WF CSV/QFX/OFX) + SimpleFIN Bridge connector.
-- Same reasoning as 20260902i_bank_engine_rpc.sql (issue #19737): service_role has NO USAGE on
-- the finance schema (confirmed still true live, has_schema_privilege('service_role','finance',
-- 'USAGE') = false), and this Worker talks to Supabase over PostgREST as service_role only (no
-- direct psql -- SUPABASE_DB_PASSWORD confirmed dead again this session, decision_log
-- 169/205/287). These SECURITY DEFINER wrapper functions live in `public` and write into
-- finance.* as their owner (postgres), same pattern as bank_engine_upsert_connection etc.

begin;

-- Generic connection upsert with an explicit status, distinct from the existing
-- bank_engine_upsert_connection (Plaid-only, hardcodes status='active'). File import needs
-- status='manual' and SimpleFIN needs status='simplefin' specifically so that NEITHER is ever
-- picked up by bank_engine_list_active_connections (status='active' filter, the Plaid-only 6h
-- cron sweep from #19737) -- a file-imported or SimpleFIN connection has no Plaid access token
-- in vault, so letting the Plaid cron touch it would just produce a noisy BLOCKED result every
-- 6h for no reason.
create or replace function public.bank_engine_upsert_connection_status(
  p_plaid_item_id text,
  p_entity_code text,
  p_institution_name text,
  p_status text
) returns uuid
language plpgsql
security definer
set search_path = pg_catalog, public, finance
as $$
declare
  v_id uuid;
begin
  insert into finance.bank_connections (plaid_item_id, entity_code, institution_name, status)
  values (p_plaid_item_id, p_entity_code, p_institution_name, p_status)
  on conflict (plaid_item_id) do update
    set institution_name = excluded.institution_name,
        status = excluded.status
  returning id into v_id;
  return v_id;
end;
$$;

revoke all on function public.bank_engine_upsert_connection_status(text, text, text, text) from public;
grant execute on function public.bank_engine_upsert_connection_status(text, text, text, text) to service_role;

-- Transaction upsert for non-Plaid sources (file import, SimpleFIN). Unlike
-- bank_engine_apply_sync (#19737), this never touches bank_connections.cursor/status -- cursor
-- pagination and status='active' are Plaid /transactions/sync concepts that don't apply to a
-- one-shot file upload or a SimpleFIN accounts pull. It only stamps last_synced_at so /import
-- and /simplefin/sync show up in finance.bank_connections the same way a Plaid sync does.
-- p_upserts shape matches bank_engine_apply_sync's p_upserts exactly (same column set), so both
-- the file importer and the SimpleFIN connector can reuse fileImport.ts/simplefin.ts's shaping
-- logic without a third shape.
create or replace function public.bank_engine_import_transactions(
  p_connection_id uuid,
  p_upserts jsonb
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, finance
as $$
declare
  v_txn jsonb;
  v_bank_account_id uuid;
  v_upserted int := 0;
  v_skipped int := 0;
begin
  for v_txn in select * from jsonb_array_elements(coalesce(p_upserts, '[]'::jsonb))
  loop
    select id into v_bank_account_id
    from finance.bank_accounts
    where plaid_account_id = v_txn->>'plaid_account_id';

    if v_bank_account_id is null then
      v_skipped := v_skipped + 1;
      continue;
    end if;

    insert into finance.bank_transactions (
      bank_account_id, plaid_transaction_id, amount_cents, posted_on,
      authorized_on, pending, name, merchant_name, category, raw
    ) values (
      v_bank_account_id,
      v_txn->>'plaid_transaction_id',
      (v_txn->>'amount_cents')::bigint,
      (v_txn->>'posted_on')::date,
      nullif(v_txn->>'authorized_on','')::date,
      coalesce((v_txn->>'pending')::boolean, false),
      v_txn->>'name',
      v_txn->>'merchant_name',
      case when v_txn ? 'category' and jsonb_typeof(v_txn->'category') = 'array' then
        (select array_agg(x) from jsonb_array_elements_text(v_txn->'category') x)
      else null end,
      v_txn->'raw'
    )
    on conflict (plaid_transaction_id) do update
      set amount_cents = excluded.amount_cents,
          posted_on = excluded.posted_on,
          pending = excluded.pending,
          name = excluded.name,
          merchant_name = excluded.merchant_name,
          raw = excluded.raw;
    v_upserted := v_upserted + 1;
  end loop;

  update finance.bank_connections
  set last_synced_at = now()
  where id = p_connection_id;

  return jsonb_build_object('upserted', v_upserted, 'skipped_no_account', v_skipped);
end;
$$;

revoke all on function public.bank_engine_import_transactions(uuid, jsonb) from public;
grant execute on function public.bank_engine_import_transactions(uuid, jsonb) to service_role;

-- GET /import renders an entity dropdown (issue #19749 scope: "entity dropdown from
-- finance.entities"). service_role cannot select finance.entities directly (no schema USAGE),
-- so this thin read-only wrapper exists for the same reason the write RPCs above do.
create or replace function public.bank_engine_list_entities()
returns table (code text, name text)
language sql
security definer
set search_path = pg_catalog, public, finance
as $$
  select code, name from finance.entities order by code;
$$;

revoke all on function public.bank_engine_list_entities() from public;
grant execute on function public.bank_engine_list_entities() to service_role;

-- Cron entity attribution for SimpleFIN (issue #19749 Part 2: "cron every 6h alongside Plaid
-- sync"). A SimpleFIN access URL is one Basic-Auth credential for one bank login, claimed once
-- via /simplefin/claim and always synced with a single entity_code (POST /simplefin/sync body).
-- The 6h cron has no caller to supply that entity_code, so it reads back whichever entity_code
-- the most recent status='simplefin' connection already used, rather than guessing or requiring
-- a second place to store it.
create or replace function public.bank_engine_simplefin_default_entity()
returns text
language sql
security definer
set search_path = pg_catalog, public, finance
as $$
  select entity_code
  from finance.bank_connections
  where status = 'simplefin'
  order by created_at desc
  limit 1;
$$;

revoke all on function public.bank_engine_simplefin_default_entity() from public;
grant execute on function public.bank_engine_simplefin_default_entity() to service_role;

commit;
