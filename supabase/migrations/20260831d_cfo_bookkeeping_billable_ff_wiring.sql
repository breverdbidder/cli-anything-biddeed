-- ============================================================================
-- CFO Bookkeeping wiring: billable_ff_events backfill, revenue_ledger
-- auto-write trigger, invoice generator, manual expense entry.
--
-- Billability rule used: winnerdata.ff_batch_leads.qa_status = 'CONTACT_ENRICHED'
--   per docs/canon/FF_DAILY_SOP.md section 2 (qa_status vocabulary table --
--   the only status marked "Billable: Yes").
--
--   DEVIATION FROM DISPATCH BRIEF: the brief proposed a "2-of-3" field-presence
--   heuristic (principal_home_address OR phone OR email, 2 of 3 present) and
--   flagged it as unconfirmed against canon. Verified live 2026-08-31 that
--   heuristic does NOT appear anywhere in FF_DAILY_SOP.md, and it overcounts
--   vs the documented qa_status=CONTACT_ENRICHED gate by 1 row in each batch
--   (field-presence: 4+11=15 vs qa_status: 3+10=13). qa_status already
--   encodes identity resolution + DNC/litigator compliance screening, which
--   raw field presence does not, so it is the correct gate. Using qa_status
--   per CC_META_PROMPT.md rule 2.3 (do not silently use a brief's unverified
--   rule when it disagrees with canon -- use the corrected one and log it).
-- ============================================================================

-- 1. Idempotency substrate: link billable_ff_events back to its source
--    ff_batch_leads row via a real composite FK, not a jsonb text match.
alter table winnerdata.billable_ff_events
  add column if not exists source_batch_date date,
  add column if not exists source_auction_id uuid;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'billable_ff_events_source_fkey'
  ) then
    alter table winnerdata.billable_ff_events
      add constraint billable_ff_events_source_fkey
      foreign key (source_batch_date, source_auction_id)
      references winnerdata.ff_batch_leads(batch_date, auction_id);
  end if;
end $$;

create unique index if not exists billable_ff_events_source_uq
  on winnerdata.billable_ff_events(source_batch_date, source_auction_id)
  where source_batch_date is not null;

-- 2. Backfill function -- idempotent, re-runnable, one row per qualifying
--    ff_batch_leads case.
create or replace function winnerdata.winnerdata_billable_backfill()
returns table(out_batch_date date, out_auction_id uuid, out_case_number text, out_action text)
language plpgsql
as $$
declare
  v_org_id uuid := '032f4717-545f-4a18-b48b-28ea4257699d'; -- Protection Partners (winnerdata.organizations)
begin
  return query
  insert into winnerdata.billable_ff_events (
    org_id, delivered_at, monetization_tier_met, monetization_basis,
    source_batch_date, source_auction_id
  )
  select
    v_org_id,
    fbl.created_at,
    true,
    jsonb_build_object(
      'source', 'winnerdata_billable_backfill',
      'case_number', fbl.case_number,
      'qa_status', fbl.qa_status,
      'billability_rule', 'qa_status = CONTACT_ENRICHED (FF_DAILY_SOP.md sec 2)'
    ),
    fbl.batch_date,
    fbl.auction_id
  from winnerdata.ff_batch_leads fbl
  where fbl.qa_status = 'CONTACT_ENRICHED'
  on conflict (source_batch_date, source_auction_id) where source_batch_date is not null do nothing
  returning
    billable_ff_events.source_batch_date,
    billable_ff_events.source_auction_id,
    (billable_ff_events.monetization_basis ->> 'case_number'),
    'inserted'::text;
end;
$$;
-- (RETURNS TABLE column names above (out_*) are deliberately distinct from
-- winnerdata.billable_ff_events' own source_batch_date/source_auction_id
-- columns -- reusing the same names made "source_batch_date" ambiguous
-- inside the RETURN QUERY INSERT ... RETURNING clause, PL/pgSQL error 42702.)

-- 3. Trigger: every future billable event auto-writes a revenue_ledger row.
--    Status starts 'pending' (not yet invoiced) -- flipped to 'invoiced' by
--    finance.generate_invoice() below. Amount uses Scenario A (delivery-only
--    POC pricing, no close fee yet per dispatch context); Scenario B flat-fee
--    total is preserved in notes for comparison, matching
--    winnerdata.v_billable_ff_comparison which keeps both models side by side.
create or replace function finance.fn_billable_ff_events_to_revenue_ledger()
returns trigger
language plpgsql
as $$
declare
  v_amount_cents integer;
begin
  v_amount_cents := coalesce(NEW.scenario_a_delivery_fee_cents, 0)
    + case when NEW.bound_at is not null then coalesce(NEW.scenario_a_success_fee_cents, 0) else 0 end;

  insert into finance.revenue_ledger (
    occurred_on, entity_code, customer, source, ref_table, ref_id,
    amount_cents, status, notes
  ) values (
    coalesce(NEW.delivered_at::date, current_date),
    'protection_partners',
    'Protection Partners (Mariam)',
    'ff_billing',
    'winnerdata.billable_ff_events',
    NEW.id,
    v_amount_cents,
    'pending',
    format(
      'Scenario A (delivery-only POC pricing) billed: $%s. Scenario B flat-fee alt = $%s/FF (not billed, comparison only -- see winnerdata.v_billable_ff_comparison).',
      to_char(v_amount_cents / 100.0, 'FM999999990.00'),
      to_char(NEW.scenario_b_flat_fee_cents / 100.0, 'FM999999990.00')
    )
  );
  return NEW;
end;
$$;

drop trigger if exists trg_billable_ff_events_revenue_ledger on winnerdata.billable_ff_events;
create trigger trg_billable_ff_events_revenue_ledger
  after insert on winnerdata.billable_ff_events
  for each row
  when (NEW.monetization_tier_met = true)
  execute function finance.fn_billable_ff_events_to_revenue_ledger();

-- 4. Monthly invoice generator. Rolls up 'pending' revenue_ledger rows for
--    one entity/customer/period into a finance.invoices row, marks them
--    'invoiced'. Raises (does not silently no-op) if there is nothing to bill.
create or replace function finance.generate_invoice(
  p_entity_code text,
  p_customer text,
  p_period_start date,
  p_period_end date
) returns finance.invoices
language plpgsql
as $$
declare
  v_invoice finance.invoices;
  v_refs uuid[];
  v_total integer;
begin
  select array_agg(id), coalesce(sum(amount_cents), 0)
    into v_refs, v_total
  from finance.revenue_ledger
  where entity_code = p_entity_code
    and customer = p_customer
    and status = 'pending'
    and occurred_on between p_period_start and p_period_end;

  if v_refs is null or array_length(v_refs, 1) is null then
    raise exception 'generate_invoice: no pending revenue_ledger rows for entity=% customer=% period=%..%',
      p_entity_code, p_customer, p_period_start, p_period_end;
  end if;

  insert into finance.invoices (
    entity_code, customer, period_start, period_end, line_item_refs, total_cents, status
  ) values (
    p_entity_code, p_customer, p_period_start, p_period_end, v_refs, v_total, 'draft'
  )
  returning * into v_invoice;

  update finance.revenue_ledger
  set status = 'invoiced'
  where id = any(v_refs);

  return v_invoice;
end;
$$;

-- 5. Manual expense entry path. This is the ONLY expense-ingestion path that
--    exists today -- no bank/Stripe feed is connected (see
--    docs/canon/CFO_BOOKKEEPING_SOP.md and TODO hooks in
--    supabase/functions/stripe-webhook-revenue/ and
--    scripts/finance_plaid_expense_ingest.py).
create or replace function finance.record_expense(
  p_entity_code text,
  p_vendor text,
  p_category text,
  p_amount_cents integer,
  p_incurred_on date default current_date,
  p_notes text default null,
  p_is_recurring boolean default false,
  p_recurrence_period text default null
) returns finance.expense_ledger
language plpgsql
as $$
declare
  v_row finance.expense_ledger;
begin
  insert into finance.expense_ledger (
    incurred_on, entity_code, vendor, category, amount_cents,
    is_recurring, recurrence_period, source, notes
  ) values (
    p_incurred_on, p_entity_code, p_vendor, p_category, p_amount_cents,
    p_is_recurring, p_recurrence_period, 'manual', p_notes
  )
  returning * into v_row;
  return v_row;
end;
$$;
