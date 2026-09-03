-- Issue #19765 (CFO v1 Issue J): automated daily close pipeline + SimpleFIN cron fix.
--
-- Pre-flight finding (CC_META_PROMPT #2.3 -- "the DoD query itself may be wrong"): the issue
-- body asserts finance.simplefin_sync(p_days) "works" and asks the cron to call it via RPC as
-- "one code path, already proven." Live pg_get_functiondef inspection (this session) shows the
-- opposite: this is the SAME buggy function that produced the 338 wrong-sign, unprefixed-id
-- stub rows deleted in migrations/20260902p_cfo_bank_dedup_simplefin_stub_rows.sql (per
-- docs/spec/19755.md) -- plaid_transaction_id had no 'simplefin:' prefix (TS path always uses
-- one) and amount_cents used the OPPOSITE sign of the table's documented/verified convention
-- (positive=outflow, negative=inflow). Routing the cron through this function unmodified would
-- have re-introduced exactly the bug #19762 just cleaned up: every already-synced transaction
-- re-inserted as a *second*, differently-shaped, wrong-sign duplicate row (the on-conflict
-- guard is keyed on plaid_transaction_id, which would never collide across the two id shapes).
-- Fixed below to match the TS path's proven convention byte-for-byte, then wired into
-- finance.daily_close() as the one code path the issue actually wants.
--
-- Second pre-flight finding: live public.agent_ops_log shows the SimpleFIN cron is NOT
-- currently SKIPPED (contrary to the issue's stated suspicion) -- the most recent tick
-- (2026-09-03T00:01:30Z) logged status=VERIFIED, accounts=4, upserted=2. A manual
-- /simplefin/sync call during the #19755 session (2026-09-02 21:05-21:24Z) created the
-- finance.bank_connections rows with status='simplefin' that
-- public.bank_engine_simplefin_default_entity() needs, so the cron self-healed once those
-- existed. That said, the underlying fragility the issue is worried about is real: if
-- bank_connections ever has zero status='simplefin' rows again (fresh access-URL rotation,
-- disaster recovery), the TS entity-lookup path returns SKIPPED forever with no bootstrap.
-- Routing the recurring sync through finance.simplefin_sync() sidesteps that entirely -- it
-- reads the vault secret directly and matches accounts by plaid_account_id, with no dependency
-- on any pre-existing bank_connections row or entity_code default at all.

-- ---------------------------------------------------------------------------------------------
-- 1. Fix finance.simplefin_sync: simplefin: id prefix, correct sign, full raw payload,
--    distinguishable credential/auth errors, last_synced_at bookkeeping.
-- ---------------------------------------------------------------------------------------------
create or replace function finance.simplefin_sync(p_days integer default 90)
returns table(mask text, inserted bigint)
language plpgsql
security definer
as $function$
declare
  v_url text;
  v_resp jsonb;
  v_start bigint;
  v_end bigint;
  v_http extensions.http_response;
begin
  select decrypted_secret into v_url from vault.decrypted_secrets where name = 'simplefin_access_url';
  if v_url is null then
    raise exception 'simplefin_sync: no simplefin_access_url in vault (credential missing)';
  end if;

  v_end := extract(epoch from now())::bigint;
  v_start := extract(epoch from now() - (p_days || ' days')::interval)::bigint;

  select * into v_http from extensions.http(
    ('GET', v_url || '/accounts?start-date=' || v_start || '&end-date=' || v_end,
     ARRAY[]::extensions.http_header[], NULL, NULL)::extensions.http_request);

  if v_http.status in (401, 403) then
    raise exception 'simplefin_sync: SimpleFIN returned HTTP % (credential/auth error -- access URL may have expired)', v_http.status;
  end if;
  if v_http.status <> 200 then
    raise exception 'simplefin_sync: SimpleFIN /accounts returned HTTP %', v_http.status;
  end if;

  v_resp := v_http.content::jsonb;

  return query
  with flat as (
    select a->>'id' as aid, t as txn
    from jsonb_array_elements(coalesce(v_resp->'accounts', '[]'::jsonb)) a,
         jsonb_array_elements(coalesce(a->'transactions', '[]'::jsonb)) t
  ),
  ins as (
    insert into finance.bank_transactions (
      bank_account_id, plaid_transaction_id, amount_cents, posted_on, pending, name, merchant_name, raw
    )
    select
      ba.id,
      'simplefin:' || coalesce(
        nullif(f.txn->>'id', ''),
        md5(f.aid || ':' || (f.txn->>'posted') || ':' || (f.txn->>'amount') || ':' || coalesce(f.txn->>'description',''))
      ),
      -round((f.txn->>'amount')::numeric * 100)::bigint,
      to_timestamp((f.txn->>'posted')::bigint)::date,
      coalesce((f.txn->>'pending')::boolean, false),
      left(coalesce(f.txn->>'description', ''), 300),
      nullif(f.txn->>'payee', ''),
      jsonb_build_object('source', 'simplefin') || f.txn
    from flat f
    join finance.bank_accounts ba on ba.plaid_account_id = 'simplefin:' || f.aid
    on conflict (plaid_transaction_id) do nothing
    returning bank_account_id
  )
  select ba2.mask, count(*) from ins join finance.bank_accounts ba2 on ba2.id = ins.bank_account_id group by 1;

  update finance.bank_connections bc
  set last_synced_at = now()
  where bc.id in (
    select distinct ba.connection_id
    from finance.bank_accounts ba
    where ba.plaid_account_id in (
      select 'simplefin:' || (a->>'id') from jsonb_array_elements(coalesce(v_resp->'accounts', '[]'::jsonb)) a
    )
  );
end;
$function$;

grant execute on function finance.simplefin_sync(integer) to service_role;

-- ---------------------------------------------------------------------------------------------
-- 2. finance.cfo_daily_close -- one row per close run.
-- ---------------------------------------------------------------------------------------------
create table if not exists finance.cfo_daily_close (
  id uuid primary key default gen_random_uuid(),
  run_at timestamptz not null default now(),
  status text not null,
  synced_count integer not null default 0,
  categorized_count integer not null default 0,
  posted_count integer not null default 0,
  drafts_count integer not null default 0,
  matched_count integer not null default 0,
  exceptions_open integer not null default 0,
  uncategorized_open integer not null default 0,
  unbalanced_count integer not null default 0,
  duration_ms integer,
  error text
);

comment on table finance.cfo_daily_close is
  'One row per finance.daily_close() run -- issue #19765. status: VERIFIED | FAILED.';

alter table finance.cfo_daily_close enable row level security;

create policy cfo_agent_ro_select on finance.cfo_daily_close for select to cfo_agent_ro using (true);
grant select on finance.cfo_daily_close to cfo_agent_ro;
grant select on finance.cfo_daily_close to service_role;

-- ---------------------------------------------------------------------------------------------
-- 3. finance._send_close_alert -- Resend email, fires only on FAILED/unbalanced/
--    uncategorized>25/credential-error. Mirrors the existing sweep_security_alerts() pattern
--    (supabase/migrations/20260803_alerts_email_security_sweep.sql): vault-only key, never
--    printed or returned in the response body -- only the Resend response (message id, http
--    status) is returned/logged.
-- ---------------------------------------------------------------------------------------------
create or replace function finance._send_close_alert(p_status text, p_summary jsonb, p_reasons text[])
returns jsonb
language plpgsql
security definer
as $function$
declare
  v_resend_key text;
  v_from text;
  v_to text := 'everestcapital8@gmail.com';
  v_subject text;
  v_html text;
  v_resp extensions.http_response;
  v_result jsonb;
begin
  select decrypted_secret into v_resend_key from vault.decrypted_secrets where name = 'resend_api_key';
  select decrypted_secret into v_from from vault.decrypted_secrets where name = 'alerts_from_email';

  if v_resend_key is null then
    insert into public.finance_ops_log (dispatch_id, entity, task, status, source_event_id, evidence, severity)
    values ('19765', 'everest_capital', 'cfo_daily_close_alert', 'BLOCKED', null,
      jsonb_build_object('reason', 'vault_missing_resend_api_key'), 'error');
    return jsonb_build_object('sent', false, 'reason', 'vault_missing_resend_api_key');
  end if;

  v_subject := format('[Everest CFO] daily close %s %s', p_status, to_char(now(), 'YYYY-MM-DD'));
  v_html := format(
    '<h2>Everest CFO — Daily Close %s</h2>
     <p><b>Reasons:</b> %s</p>
     <pre style="font-family:monospace;font-size:12px;background:#f4f4f4;padding:12px;">%s</pre>
     <hr/><p style="color:#666;font-size:12px;">Everest CFO Daily Close — do not reply.</p>',
    p_status,
    coalesce(array_to_string(p_reasons, ', '), '(none)'),
    p_summary::text
  );

  select * into v_resp from extensions.http((
    'POST',
    'https://api.resend.com/emails',
    ARRAY[
      extensions.http_header('Authorization', 'Bearer ' || v_resend_key),
      extensions.http_header('Content-Type', 'application/json')
    ],
    'application/json',
    jsonb_build_object(
      'from', coalesce(v_from, 'Everest CFO <alerts@biddeed.ai>'),
      'to', jsonb_build_array(v_to),
      'subject', v_subject,
      'html', v_html
    )::text
  )::extensions.http_request);

  v_result := jsonb_build_object(
    'sent', v_resp.status = 200,
    'http_status', v_resp.status,
    'resend_response', v_resp.content::jsonb
  );

  insert into public.finance_ops_log (dispatch_id, entity, task, status, source_event_id, evidence, severity)
  values ('19765', 'everest_capital', 'cfo_daily_close_alert',
    case when v_resp.status = 200 then 'VERIFIED' else 'BLOCKED' end,
    null, v_result, case when v_resp.status = 200 then 'warn' else 'error' end);

  return v_result;
end;
$function$;

grant execute on function finance._send_close_alert(text, jsonb, text[]) to service_role;

-- ---------------------------------------------------------------------------------------------
-- 4. finance.daily_close -- the orchestrator. Order per issue: (a) simplefin_sync(7),
--    (b)+(c) categorize+post via process_bank_transactions, (d) recon_run, (e) verify the two
--    cost views compute, (f) assert_balanced -- abort/rollback this run's posting step if not
--    balanced. (b)+(c)+(f) are wrapped in a nested BEGIN/EXCEPTION block: plpgsql gives that
--    block an implicit subtransaction, so RAISE EXCEPTION there rolls back every posting made
--    by process_bank_transactions() in this run while the outer function keeps running to log
--    the FAILED row and fire the alert. Idempotent: re-running finds no un-posted/un-matched
--    rows left over from a failed run's rollback, so a retry is a clean re-attempt.
-- ---------------------------------------------------------------------------------------------
create or replace function finance.daily_close(p_from date default null)
returns jsonb
language plpgsql
security definer
as $function$
declare
  v_run_start timestamptz := clock_timestamp();
  v_run_at timestamptz := now();
  v_from date := coalesce(p_from, '2026-01-01'::date);
  v_synced_count bigint := 0;
  v_categorized_count integer := 0;
  v_posted_count integer := 0;
  v_drafts_count integer := 0;
  v_matched_count integer := 0;
  v_exceptions_open integer := 0;
  v_uncategorized_open integer := 0;
  v_unbalanced_count integer := 0;
  v_status text := 'VERIFIED';
  v_error text := null;
  v_alert_reasons text[] := '{}';
  v_pipeline_start timestamptz;
  v_proc record;
  v_recon record;
  v_recurring_count integer;
  v_commingled_count integer;
  v_summary jsonb;
  v_alert_result jsonb;
begin
  -- (a) SimpleFIN sync -- failure here does not abort the run (categorization/posting should
  -- still process whatever was already synced by an earlier tick), but IS reported/alerted.
  begin
    select coalesce(sum(inserted), 0) into v_synced_count from finance.simplefin_sync(7);
  exception when others then
    v_error := coalesce(v_error, '') || format('simplefin_sync: %s; ', sqlerrm);
    v_alert_reasons := array_append(v_alert_reasons,
      case when sqlerrm ilike '%credential%' or sqlerrm ilike '%auth%'
        then 'simplefin_credential_error' else 'simplefin_sync_error' end);
  end;

  -- (b)+(c)+(f) categorize, post, balance-check -- rolled back together on imbalance.
  v_pipeline_start := clock_timestamp();
  begin
    for v_proc in select * from finance.process_bank_transactions(null) loop
      v_categorized_count := coalesce(v_proc.categorized, 0);
    end loop;

    select
      count(*) filter (where posted_at is not null),
      count(*) filter (where posted_at is null)
      into v_posted_count, v_drafts_count
      from finance.journal_entries
      where created_at >= v_pipeline_start;

    select count(*) into v_unbalanced_count from finance.assert_balanced();
    if v_unbalanced_count > 0 then
      raise exception 'daily_close: % unbalanced journal entries after posting -- aborting this run''s posting step', v_unbalanced_count;
    end if;
  exception when others then
    v_error := coalesce(v_error, '') || format('posting: %s; ', sqlerrm);
    v_status := 'FAILED';
    v_posted_count := 0;
    v_drafts_count := 0;
    v_categorized_count := 0;
    v_alert_reasons := array_append(v_alert_reasons, 'unbalanced_or_posting_error');
  end;

  -- (d) recon
  begin
    for v_recon in select * from finance.recon_run(null, v_from) loop
      v_matched_count := v_matched_count + coalesce(v_recon.matched, 0);
    end loop;
  exception when others then
    v_error := coalesce(v_error, '') || format('recon_run: %s; ', sqlerrm);
    v_alert_reasons := array_append(v_alert_reasons, 'recon_run_error');
  end;

  select count(*) into v_exceptions_open from finance.recon_exceptions where status = 'open';
  select count(*) into v_uncategorized_open from finance.recon_exceptions where status = 'open' and reason = 'uncategorized';

  -- (e) verify the two cost views still compute without error (plain views -- "refresh" is a
  -- no-op by construction, so this step is a liveness check, not a materialized-view refresh).
  begin
    select count(*) into v_recurring_count from finance.v_recurring_costs;
    select count(*) into v_commingled_count from finance.v_commingled_business_costs;
  exception when others then
    v_error := coalesce(v_error, '') || format('cost_views: %s; ', sqlerrm);
    v_alert_reasons := array_append(v_alert_reasons, 'cost_view_error');
  end;

  -- Final re-check: assert_balanced() again post-recon (recon_run only inserts recon_matches,
  -- never postings, so this should be identical to the mid-pipeline check -- re-verified anyway
  -- rather than assumed).
  select count(*) into v_unbalanced_count from finance.assert_balanced();
  if v_unbalanced_count > 0 then
    v_status := 'FAILED';
    if not ('unbalanced_or_posting_error' = any(v_alert_reasons)) then
      v_alert_reasons := array_append(v_alert_reasons, 'unbalanced_after_recon');
    end if;
  end if;

  if v_status <> 'FAILED' and v_uncategorized_open > 25 then
    v_alert_reasons := array_append(v_alert_reasons, format('uncategorized_open=%s > 25', v_uncategorized_open));
  end if;

  v_summary := jsonb_build_object(
    'run_at', v_run_at,
    'status', v_status,
    'synced_count', v_synced_count,
    'categorized_count', v_categorized_count,
    'posted_count', v_posted_count,
    'drafts_count', v_drafts_count,
    'matched_count', v_matched_count,
    'exceptions_open', v_exceptions_open,
    'uncategorized_open', v_uncategorized_open,
    'unbalanced_count', v_unbalanced_count,
    'duration_ms', round(extract(epoch from (clock_timestamp() - v_run_start)) * 1000),
    'error', v_error,
    'alert_reasons', v_alert_reasons,
    'recurring_costs_rows', v_recurring_count,
    'commingled_costs_rows', v_commingled_count
  );

  insert into finance.cfo_daily_close (
    run_at, status, synced_count, categorized_count, posted_count, drafts_count,
    matched_count, exceptions_open, uncategorized_open, unbalanced_count, duration_ms, error
  ) values (
    v_run_at, v_status, v_synced_count, v_categorized_count, v_posted_count, v_drafts_count,
    v_matched_count, v_exceptions_open, v_uncategorized_open, v_unbalanced_count,
    round(extract(epoch from (clock_timestamp() - v_run_start)) * 1000)::integer, v_error
  );

  if v_status = 'FAILED' or array_length(v_alert_reasons, 1) > 0 then
    v_alert_result := finance._send_close_alert(v_status, v_summary, v_alert_reasons);
    v_summary := v_summary || jsonb_build_object('alert', v_alert_result);
  end if;

  return v_summary;
end;
$function$;

grant execute on function finance.daily_close(date) to service_role;

-- ---------------------------------------------------------------------------------------------
-- 5. public wrapper -- PostgREST only exposes the 'public' schema for RPC (db.ts comment,
--    everest-bank-engine's rpc() helper); the Worker's cron calls this, never finance.* directly.
-- ---------------------------------------------------------------------------------------------
create or replace function public.bank_engine_run_daily_close(p_from date default null)
returns jsonb
language sql
security definer
set search_path to 'pg_catalog', 'public', 'finance'
as $function$
  select finance.daily_close(p_from);
$function$;

revoke all on function public.bank_engine_run_daily_close(date) from public;
grant execute on function public.bank_engine_run_daily_close(date) to service_role;
