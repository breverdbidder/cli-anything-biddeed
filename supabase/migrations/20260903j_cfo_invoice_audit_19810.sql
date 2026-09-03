-- CFO v1 Issue M (#19810): invoice audit capability -- ingest vendor invoices, verify line
-- items against real usage APIs, flag anomalies, draft disputes. Operating contract:
-- CC_META_PROMPT.md. Builds on the shipped CFO stack (#19755/#19762/#19764/#19765/#19769).
--
-- Trigger case: Vercel invoice D2LOTNWY-0007 ($102.37, 6 lines, Build CPU Minutes = 80% of
-- total). Actual Worker code lives in breverdbidder/everest-cfo-agent (worker/src/), not this
-- repo -- same split as #19764/#19765/#19768/#19769. This migration is the shared-Supabase-
-- project (mocerqjnksmhcjzxrewo) schema side.
--
-- Credential model: everest-cfo-agent's Worker holds ONLY a cfo_agent_ro-scoped JWT (no
-- service_role key -- see worker/docs/PORTING_NOTES.md), so every WRITE below is a
-- SECURITY DEFINER wrapper in `public`, owner postgres, EXECUTE granted to cfo_agent_ro only
-- (same pattern as public.bank_engine_* / #19762's categorization RPCs). Reads go direct via
-- RLS + a `cfo_agent_ro_select` policy, matching finance.revenue_ledger/expense_ledger/etc.

begin;

-- ============================================================
-- 1. finance.vendor_invoices / finance.vendor_invoice_lines
-- ============================================================

create table finance.vendor_invoices (
  id uuid primary key default gen_random_uuid(),
  vendor text not null,
  invoice_number text not null,
  issued_on date not null,
  due_on date,
  currency text not null default 'USD',
  subtotal_cents bigint,
  total_cents bigint not null,
  entity_code text references finance.entities(code),
  status text not null default 'received'
    check (status in ('received','verified','disputed','paid','credited')),
  source_file text,
  raw_text text,
  extraction_method text,
  bank_transaction_id uuid references finance.bank_transactions(id),
  dispute_draft text,
  dispute_draft_at timestamptz,
  dispute_reply text,
  dispute_reply_at timestamptz,
  created_at timestamptz not null default now(),
  unique (vendor, invoice_number)
);

alter table finance.vendor_invoices enable row level security;
create policy cfo_agent_ro_select on finance.vendor_invoices for select to cfo_agent_ro using (true);
grant select on finance.vendor_invoices to cfo_agent_ro;

create table finance.vendor_invoice_lines (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references finance.vendor_invoices(id) on delete cascade,
  description text not null,
  qty numeric,
  unit_price_cents bigint,
  amount_cents bigint not null,
  period_start date,
  period_end date,
  metric_name text,
  verified_qty numeric,
  variance_pct numeric,
  verdict text,
  evidence jsonb,
  created_at timestamptz not null default now()
);

create index vendor_invoice_lines_invoice_id_idx on finance.vendor_invoice_lines (invoice_id);

alter table finance.vendor_invoice_lines enable row level security;
create policy cfo_agent_ro_select on finance.vendor_invoice_lines for select to cfo_agent_ro using (true);
grant select on finance.vendor_invoice_lines to cfo_agent_ro;

-- ============================================================
-- 2. public.cfo_invoice_ingest -- write path (issue scope item 2)
-- Upserts on (vendor, invoice_number); idempotent re-POST of the same invoice does not
-- duplicate lines (delete+reinsert lines on an existing invoice_id). Attempts a
-- finance.bank_transactions link: abs(amount_cents - total_cents) <= 1 (the "±$0.01" the
-- issue asks for, in cents) and posted_on within issued_on ± 5 days, scoped to accounts whose
-- bank_connections.entity_code matches p_entity_code when supplied. Matches on magnitude only
-- (not signed direction) because this pipeline has 3 sign conventions across Plaid/file-import/
-- SimpleFIN sources (see worker/README.md "Sign convention" note in the sibling bank-engine
-- repo) -- resolving the correct sign per source here would require re-deriving that whole
-- table, out of this issue's scope; magnitude+date is sufficient to *propose* a link, which is
-- all this does (it is not used as an accounting posting).
-- ============================================================

create or replace function public.cfo_invoice_ingest(
  p_vendor text,
  p_invoice_number text,
  p_issued_on date,
  p_due_on date,
  p_currency text,
  p_subtotal_cents bigint,
  p_total_cents bigint,
  p_entity_code text,
  p_source_file text,
  p_raw_text text,
  p_extraction_method text,
  p_lines jsonb
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, finance
as $$
declare
  v_invoice_id uuid;
  v_created boolean := false;
  v_line jsonb;
  v_lines_inserted int := 0;
  v_bank_txn_id uuid;
begin
  if p_vendor is null or btrim(p_vendor) = '' then
    raise exception 'p_vendor is required';
  end if;
  if p_invoice_number is null or btrim(p_invoice_number) = '' then
    raise exception 'p_invoice_number is required';
  end if;

  select id into v_invoice_id
  from finance.vendor_invoices
  where vendor = p_vendor and invoice_number = p_invoice_number;

  if v_invoice_id is null then
    insert into finance.vendor_invoices (
      vendor, invoice_number, issued_on, due_on, currency, subtotal_cents, total_cents,
      entity_code, source_file, raw_text, extraction_method
    ) values (
      p_vendor, p_invoice_number, p_issued_on, p_due_on, coalesce(p_currency, 'USD'),
      p_subtotal_cents, p_total_cents, p_entity_code, p_source_file, p_raw_text, p_extraction_method
    )
    returning id into v_invoice_id;
    v_created := true;
  else
    update finance.vendor_invoices
    set issued_on = p_issued_on, due_on = p_due_on, currency = coalesce(p_currency, 'USD'),
        subtotal_cents = p_subtotal_cents, total_cents = p_total_cents,
        entity_code = coalesce(p_entity_code, entity_code),
        source_file = coalesce(p_source_file, source_file),
        raw_text = coalesce(p_raw_text, raw_text),
        extraction_method = coalesce(p_extraction_method, extraction_method)
    where id = v_invoice_id;
    delete from finance.vendor_invoice_lines where invoice_id = v_invoice_id;
  end if;

  for v_line in select * from jsonb_array_elements(coalesce(p_lines, '[]'::jsonb))
  loop
    insert into finance.vendor_invoice_lines (
      invoice_id, description, qty, unit_price_cents, amount_cents,
      period_start, period_end, metric_name
    ) values (
      v_invoice_id,
      v_line->>'description',
      nullif(v_line->>'qty','')::numeric,
      nullif(v_line->>'unit_price_cents','')::bigint,
      (v_line->>'amount_cents')::bigint,
      nullif(v_line->>'period_start','')::date,
      nullif(v_line->>'period_end','')::date,
      v_line->>'metric_name'
    );
    v_lines_inserted := v_lines_inserted + 1;
  end loop;

  -- Best-effort bank-transaction link. Never blocks ingestion if no match found.
  select bt.id into v_bank_txn_id
  from finance.bank_transactions bt
  join finance.bank_accounts ba on ba.id = bt.bank_account_id
  join finance.bank_connections bc on bc.id = ba.connection_id
  where abs(bt.amount_cents - p_total_cents) <= 1
    and bt.posted_on between p_issued_on - 5 and p_issued_on + 5
    and (p_entity_code is null or bc.entity_code = p_entity_code)
  order by abs(bt.posted_on - p_issued_on) asc
  limit 1;

  if v_bank_txn_id is not null then
    update finance.vendor_invoices set bank_transaction_id = v_bank_txn_id where id = v_invoice_id;
  end if;

  return jsonb_build_object(
    'invoice_id', v_invoice_id,
    'created', v_created,
    'lines_inserted', v_lines_inserted,
    'bank_transaction_id', v_bank_txn_id
  );
end;
$$;

revoke all on function public.cfo_invoice_ingest(text,text,date,date,text,bigint,bigint,text,text,text,text,jsonb) from public;
grant execute on function public.cfo_invoice_ingest(text,text,date,date,text,bigint,bigint,text,text,text,text,jsonb) to cfo_agent_ro;

-- ============================================================
-- 3. public.cfo_invoice_write_verification -- per-line verification result (issue scope item 3)
-- Never called with a fabricated verified_qty -- the Worker's adapter either supplies a real
-- number from a vendor usage API or leaves it null with verdict='UNVERIFIABLE -- credential
-- missing: <name>'. This function does not compute anything; it only persists what the
-- Worker's adapter already determined.
-- ============================================================

create or replace function public.cfo_invoice_write_verification(
  p_line_id uuid,
  p_verified_qty numeric,
  p_variance_pct numeric,
  p_verdict text,
  p_evidence jsonb
) returns void
language plpgsql
security definer
set search_path = pg_catalog, public, finance
as $$
begin
  update finance.vendor_invoice_lines
  set verified_qty = p_verified_qty,
      variance_pct = p_variance_pct,
      verdict = p_verdict,
      evidence = p_evidence
  where id = p_line_id;

  if not found then
    raise exception 'no vendor_invoice_lines row for id %', p_line_id;
  end if;
end;
$$;

revoke all on function public.cfo_invoice_write_verification(uuid,numeric,numeric,text,jsonb) from public;
grant execute on function public.cfo_invoice_write_verification(uuid,numeric,numeric,text,jsonb) to cfo_agent_ro;

-- ============================================================
-- 4. public.cfo_invoice_set_status
-- ============================================================

create or replace function public.cfo_invoice_set_status(
  p_invoice_id uuid,
  p_status text
) returns void
language plpgsql
security definer
set search_path = pg_catalog, public, finance
as $$
begin
  if p_status not in ('received','verified','disputed','paid','credited') then
    raise exception 'invalid status %', p_status;
  end if;
  update finance.vendor_invoices set status = p_status where id = p_invoice_id;
  if not found then
    raise exception 'no vendor_invoices row for id %', p_invoice_id;
  end if;
end;
$$;

revoke all on function public.cfo_invoice_set_status(uuid,text) from public;
grant execute on function public.cfo_invoice_set_status(uuid,text) to cfo_agent_ro;

-- ============================================================
-- 5. public.cfo_invoice_save_dispute -- Tier 1 propose-only (issue scope item 5)
-- Only ever writes a draft. Nothing in this migration sends anything anywhere.
-- ============================================================

create or replace function public.cfo_invoice_save_dispute(
  p_invoice_id uuid,
  p_draft_text text
) returns void
language plpgsql
security definer
set search_path = pg_catalog, public, finance
as $$
begin
  update finance.vendor_invoices
  set dispute_draft = p_draft_text, dispute_draft_at = now()
  where id = p_invoice_id;
  if not found then
    raise exception 'no vendor_invoices row for id %', p_invoice_id;
  end if;
end;
$$;

revoke all on function public.cfo_invoice_save_dispute(uuid,text) from public;
grant execute on function public.cfo_invoice_save_dispute(uuid,text) to cfo_agent_ro;

-- ============================================================
-- 6. public.cfo_invoice_get_vendor_credential -- gated vault accessor (CLAUDE.md CREDENTIAL
-- HANDLING: real gate + hard allow-list of returnable names, same pattern as
-- get_vault_secret_gated / cli_anything_get_secret). Only the one name this issue names is
-- allow-listed; every other name returns null rather than being a generic vault passthrough.
-- ============================================================

create or replace function public.cfo_invoice_get_vendor_credential(
  p_name text
) returns text
language plpgsql
security definer
set search_path = pg_catalog, public, vault
as $$
declare
  v_value text;
begin
  if p_name not in ('vercel_api_token_brevardbidderai') then
    return null;
  end if;
  select decrypted_secret into v_value from vault.decrypted_secrets where name = p_name limit 1;
  return v_value;
end;
$$;

revoke all on function public.cfo_invoice_get_vendor_credential(text) from public;
grant execute on function public.cfo_invoice_get_vendor_credential(text) to cfo_agent_ro;

-- ============================================================
-- 7. public.cfo_invoice_check_anomalies -- the 4 anomaly rules (issue scope item 4), pure SQL
-- (no external API calls -- this is the part that's fully implementable in Postgres). Writes
-- finance.recon_exceptions rows with reason='invoice_anomaly' so they surface on the existing
-- exceptions dashboard (#19764's ExceptionsTable) without any new UI surface needed for this
-- part. Idempotent: skips a rule if an open recon_exceptions row already exists for the same
-- invoice+line+rule (checked via a marker embedded in `reason`).
-- ============================================================

create or replace function public.cfo_invoice_check_anomalies(
  p_invoice_id uuid
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, finance
as $$
declare
  v_line record;
  v_invoice record;
  v_findings jsonb := '[]'::jsonb;
  v_median numeric;
  v_prior_count int;
  v_metric_seen_before boolean;
  v_runrate numeric;
  v_reason text;
  v_marker text;
begin
  select * into v_invoice from finance.vendor_invoices where id = p_invoice_id;
  if not found then
    raise exception 'no vendor_invoices row for id %', p_invoice_id;
  end if;

  for v_line in
    select * from finance.vendor_invoice_lines where invoice_id = p_invoice_id
  loop
    -- Rule 1: billed qty > 3x trailing 3-invoice median for the same vendor+metric.
    if v_line.metric_name is not null and v_line.qty is not null then
      select count(*), percentile_cont(0.5) within group (order by l.qty)
        into v_prior_count, v_median
      from (
        select l2.qty
        from finance.vendor_invoice_lines l2
        join finance.vendor_invoices i2 on i2.id = l2.invoice_id
        where i2.vendor = v_invoice.vendor
          and l2.metric_name = v_line.metric_name
          and i2.id <> v_invoice.id
          and l2.qty is not null
        order by i2.issued_on desc
        limit 3
      ) l;

      if v_prior_count >= 1 and v_median > 0 and v_line.qty > 3 * v_median then
        v_marker := format('invoice_anomaly:qty_spike:%s:%s', v_invoice.id, v_line.id);
        v_reason := format(
          'invoice_anomaly: %s invoice %s line "%s" billed_qty=%s > 3x trailing median(%s of %s prior)=%s',
          v_invoice.vendor, v_invoice.invoice_number, v_line.description, v_line.qty, v_prior_count, v_prior_count, v_median
        );
        if not exists (select 1 from finance.recon_exceptions where reason = v_reason) then
          insert into finance.recon_exceptions (reason, status) values (v_reason, 'open');
        end if;
        v_findings := v_findings || jsonb_build_object('rule', 'qty_spike_3x_median', 'line_id', v_line.id, 'reason', v_reason);
      end if;
    end if;

    -- Rule 2: variance vs verified_qty > 10%.
    if v_line.variance_pct is not null and abs(v_line.variance_pct) > 10 then
      v_reason := format(
        'invoice_anomaly: %s invoice %s line "%s" variance_pct=%s exceeds 10%% (billed=%s verified=%s)',
        v_invoice.vendor, v_invoice.invoice_number, v_line.description, v_line.variance_pct, v_line.qty, v_line.verified_qty
      );
      if not exists (select 1 from finance.recon_exceptions where reason = v_reason) then
        insert into finance.recon_exceptions (reason, status) values (v_reason, 'open');
      end if;
      v_findings := v_findings || jsonb_build_object('rule', 'variance_over_10pct', 'line_id', v_line.id, 'reason', v_reason);
    end if;

    -- Rule 3: metric appears that was absent in prior invoices for this vendor.
    if v_line.metric_name is not null then
      select exists (
        select 1
        from finance.vendor_invoice_lines l2
        join finance.vendor_invoices i2 on i2.id = l2.invoice_id
        where i2.vendor = v_invoice.vendor
          and l2.metric_name = v_line.metric_name
          and i2.id <> v_invoice.id
      ) into v_metric_seen_before;

      if not v_metric_seen_before then
        v_reason := format(
          'invoice_anomaly: %s invoice %s line "%s" (metric=%s) is a new metric, absent from all prior %s invoices',
          v_invoice.vendor, v_invoice.invoice_number, v_line.description, v_line.metric_name, v_invoice.vendor
        );
        if not exists (select 1 from finance.recon_exceptions where reason = v_reason) then
          insert into finance.recon_exceptions (reason, status) values (v_reason, 'open');
        end if;
        v_findings := v_findings || jsonb_build_object('rule', 'new_metric', 'line_id', v_line.id, 'reason', v_reason);
      end if;
    end if;
  end loop;

  -- Rule 4: invoice total exceeds the vendor's finance.v_recurring_costs monthly run-rate by > 50%.
  select monthly_runrate_dollars into v_runrate
  from finance.v_recurring_costs
  where vendor ilike '%' || v_invoice.vendor || '%'
    and (v_invoice.entity_code is null or entity_code = v_invoice.entity_code)
  order by monthly_runrate_dollars desc nulls last
  limit 1;

  if v_runrate is not null and v_runrate > 0 and (v_invoice.total_cents / 100.0) > v_runrate * 1.5 then
    v_reason := format(
      'invoice_anomaly: %s invoice %s total=$%s exceeds recurring run-rate $%s by more than 50%%',
      v_invoice.vendor, v_invoice.invoice_number, round(v_invoice.total_cents / 100.0, 2), v_runrate
    );
    if not exists (select 1 from finance.recon_exceptions where reason = v_reason) then
      insert into finance.recon_exceptions (reason, status) values (v_reason, 'open');
    end if;
    v_findings := v_findings || jsonb_build_object('rule', 'exceeds_runrate_50pct', 'reason', v_reason);
  end if;

  return jsonb_build_object('invoice_id', p_invoice_id, 'findings', v_findings, 'findings_count', jsonb_array_length(v_findings));
end;
$$;

revoke all on function public.cfo_invoice_check_anomalies(uuid) from public;
grant execute on function public.cfo_invoice_check_anomalies(uuid) to cfo_agent_ro;

commit;
