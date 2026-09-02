-- CFO v1 Issue C (CP4): everest-bank-engine RPC layer.
-- Issue #19737. Operating contract: CC_META_PROMPT.md.
--
-- service_role has NO USAGE on the finance schema (confirmed live via
-- has_schema_privilege('service_role','finance','USAGE') = false -- only
-- postgres and cfo_agent_ro do, and cfo_agent_ro is read-only per #19716's
-- cfo_agent_ro_select policies). The Cloudflare Worker built for this issue
-- talks to Supabase as service_role via PostgREST (no direct psql --
-- SUPABASE_DB_PASSWORD confirmed dead again this session, matching
-- decision_log 169/205/287), so it cannot write finance.bank_* tables
-- directly. These SECURITY DEFINER wrapper functions live in `public`
-- (service_role has USAGE there by default, confirmed live) and write into
-- finance.* as their owner (postgres), matching the existing
-- ecu_set_vault_secret / vault_secret pattern already in this project
-- rather than widening any finance schema-level grant.

begin;

create or replace function public.bank_engine_upsert_connection(
  p_plaid_item_id text,
  p_entity_code text,
  p_institution_name text
) returns uuid
language plpgsql
security definer
set search_path = pg_catalog, public, finance
as $$
declare
  v_id uuid;
begin
  insert into finance.bank_connections (plaid_item_id, entity_code, institution_name, status)
  values (p_plaid_item_id, p_entity_code, p_institution_name, 'active')
  on conflict (plaid_item_id) do update
    set institution_name = excluded.institution_name,
        status = 'active'
  returning id into v_id;
  return v_id;
end;
$$;

revoke all on function public.bank_engine_upsert_connection(text, text, text) from public;
grant execute on function public.bank_engine_upsert_connection(text, text, text) to service_role;

-- p_accounts: jsonb array of {plaid_account_id, name, mask, subtype, currency,
-- current_balance_cents, available_balance_cents}
create or replace function public.bank_engine_upsert_accounts(
  p_connection_id uuid,
  p_accounts jsonb
) returns int
language plpgsql
security definer
set search_path = pg_catalog, public, finance
as $$
declare
  v_count int := 0;
  v_acct jsonb;
begin
  for v_acct in select * from jsonb_array_elements(p_accounts)
  loop
    insert into finance.bank_accounts (
      connection_id, plaid_account_id, name, mask, subtype, currency,
      current_balance_cents, available_balance_cents
    ) values (
      p_connection_id,
      v_acct->>'plaid_account_id',
      v_acct->>'name',
      v_acct->>'mask',
      v_acct->>'subtype',
      v_acct->>'currency',
      nullif(v_acct->>'current_balance_cents','')::bigint,
      nullif(v_acct->>'available_balance_cents','')::bigint
    )
    on conflict (plaid_account_id) do update
      set name = excluded.name,
          mask = excluded.mask,
          subtype = excluded.subtype,
          currency = excluded.currency,
          current_balance_cents = excluded.current_balance_cents,
          available_balance_cents = excluded.available_balance_cents;
    v_count := v_count + 1;
  end loop;
  return v_count;
end;
$$;

revoke all on function public.bank_engine_upsert_accounts(uuid, jsonb) from public;
grant execute on function public.bank_engine_upsert_accounts(uuid, jsonb) to service_role;

-- p_upserts: jsonb array of Plaid /transactions/sync added+modified items, pre-shaped by the
-- Worker to {plaid_account_id, plaid_transaction_id, amount_cents, posted_on, authorized_on,
-- pending, name, merchant_name, category (jsonb array of text), raw (full original object)}.
-- amount_cents convention: Plaid's raw `amount` * 100, SIGN UNCHANGED (positive = money
-- leaving the account / outflow, negative = inflow) -- see finance.bank_transactions column
-- comment (#19716 migration) and workers/everest-bank-engine/README.md.
-- p_removed: jsonb array of plaid_transaction_id strings from Plaid's `removed` list.
create or replace function public.bank_engine_apply_sync(
  p_connection_id uuid,
  p_upserts jsonb,
  p_removed jsonb,
  p_cursor text
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
  v_removed_id text;
  v_removed_count int := 0;
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
          authorized_on = excluded.authorized_on,
          pending = excluded.pending,
          name = excluded.name,
          merchant_name = excluded.merchant_name,
          category = excluded.category,
          raw = excluded.raw;
    v_upserted := v_upserted + 1;
  end loop;

  for v_removed_id in select jsonb_array_elements_text(coalesce(p_removed, '[]'::jsonb))
  loop
    delete from finance.bank_transactions where plaid_transaction_id = v_removed_id;
    v_removed_count := v_removed_count + 1;
  end loop;

  update finance.bank_connections
  set cursor = p_cursor, last_synced_at = now(), status = 'active'
  where id = p_connection_id;

  return jsonb_build_object(
    'upserted', v_upserted,
    'skipped_no_account', v_skipped,
    'removed', v_removed_count
  );
end;
$$;

revoke all on function public.bank_engine_apply_sync(uuid, jsonb, jsonb, text) from public;
grant execute on function public.bank_engine_apply_sync(uuid, jsonb, jsonb, text) to service_role;

create or replace function public.bank_engine_list_active_connections()
returns table (id uuid, plaid_item_id text, cursor text, entity_code text)
language sql
security definer
set search_path = pg_catalog, public, finance
as $$
  select id, plaid_item_id, cursor, entity_code
  from finance.bank_connections
  where status = 'active';
$$;

revoke all on function public.bank_engine_list_active_connections() from public;
grant execute on function public.bank_engine_list_active_connections() to service_role;

commit;
