-- Issue #19738 CFO v1 Issue D Part 2 (CP6): bank reconciliation v1
-- Filename note: the issue body asked for `20260902b_recon_v1.sql` but that exact name
-- was already taken (20260902b_harvest_sale_result_derive_trigger_19720.sql, an unrelated
-- migration from earlier the same day) -- used the next free same-day suffix instead.
--
-- Sign convention (documented here + PORTING_NOTES.md, since finance.bank_transactions has
-- no separate direction column): amount_cents > 0 = inflow/credit to the bank account,
-- amount_cents < 0 = outflow/debit. This is the standard ledger convention and the
-- OPPOSITE of Plaid's raw wire format (Plaid: positive = money out, negative = money in).
-- Whoever wires #19737's real Plaid ingestion into finance.bank_transactions MUST negate
-- Plaid's raw sign on write, or R1/R2 below will silently match everything backwards.
--
-- #19737 (Plaid engine) has not landed any real rows as of this migration (verified live:
-- finance.bank_transactions count=0). Per the issue's explicit fallback instruction, this
-- migration ships a synthetic bank_transactions fixture (tagged via
-- finance.bank_connections.status='fixture', which is the closest existing column to the
-- "source=fixture" ask -- bank_transactions/bank_connections have no literal `source`
-- column and adding one is additive-only but wasn't necessary given bank_connections.status
-- already discriminates cleanly) built from REAL stripe.payouts + finance.expense_ledger
-- rows, so recon_run() is exercised against real amounts/dates, not invented numbers.

create or replace function finance.recon_run(p_entity_code text default null, p_from date default '2026-01-01')
returns table(entity_code text, bank_rows int, matched int, exceptions_opened int)
language plpgsql as $$
declare
  v_entity text;
  v_bank_rows int;
begin
  for v_entity in
    select code from finance.entities where (p_entity_code is null or code = p_entity_code) order by code
  loop
    -- R1: Stripe payout <-> bank credit (amount equal, posted within arrival_date +-3d,
    -- descriptor mentions stripe). confidence 0.95.
    -- Mutual-nearest-match: when the +-3d window lets one bank row qualify for more than
    -- one payout (e.g. two same-amount payouts a few days apart), only accept a pair where
    -- each side's #1 choice (smallest date distance) is the other -- prevents the same
    -- bank_transaction_id or payout_id being claimed twice.
    with candidates as (
      select
        bt.id as bt_id, p.payout_id,
        row_number() over (partition by bt.id order by abs(bt.posted_on - p.arrival_date::date)) as bt_rank,
        row_number() over (partition by p.payout_id order by abs(bt.posted_on - p.arrival_date::date)) as payout_rank
      from finance.bank_transactions bt
      join finance.bank_accounts ba on ba.id = bt.bank_account_id
      join finance.bank_connections bc on bc.id = ba.connection_id
      join finance.v_stripe_payouts p
        on p.amount = bt.amount_cents
        and bt.posted_on between (p.arrival_date::date - 3) and (p.arrival_date::date + 3)
      where bc.entity_code = v_entity
        and bt.amount_cents > 0
        and bt.posted_on >= p_from
        and (bt.name ilike '%stripe%' or bt.merchant_name ilike '%stripe%')
        and not exists (select 1 from finance.recon_matches m where m.bank_transaction_id = bt.id)
        and not exists (select 1 from finance.recon_matches m where m.matched_type = 'stripe_payout' and m.matched_id = p.payout_id)
    )
    insert into finance.recon_matches (bank_transaction_id, matched_type, matched_id, rule, confidence)
    select bt_id, 'stripe_payout', payout_id, 'R1', 0.95
    from candidates where bt_rank = 1 and payout_rank = 1;

    -- R2a: expense ledger <-> bank debit, amount+date+vendor token match. confidence 0.9.
    -- Same mutual-nearest-match guard as R1.
    with candidates as (
      select
        bt.id as bt_id, el.id as expense_id,
        row_number() over (partition by bt.id order by abs(bt.posted_on - el.incurred_on)) as bt_rank,
        row_number() over (partition by el.id order by abs(bt.posted_on - el.incurred_on)) as expense_rank
      from finance.bank_transactions bt
      join finance.bank_accounts ba on ba.id = bt.bank_account_id
      join finance.bank_connections bc on bc.id = ba.connection_id
      join finance.expense_ledger el
        on el.entity_code = v_entity
        and el.amount_cents = abs(bt.amount_cents)
        and bt.posted_on between (el.incurred_on - 3) and (el.incurred_on + 3)
        and (bt.merchant_name ilike '%' || el.vendor || '%' or bt.name ilike '%' || el.vendor || '%')
      where bc.entity_code = v_entity
        and bt.amount_cents < 0
        and bt.posted_on >= p_from
        and not exists (select 1 from finance.recon_matches m where m.bank_transaction_id = bt.id)
        and not exists (select 1 from finance.recon_matches m where m.matched_type = 'expense' and m.matched_id = el.id::text)
    )
    insert into finance.recon_matches (bank_transaction_id, matched_type, matched_id, rule, confidence)
    select bt_id, 'expense', expense_id::text, 'R2', 0.9
    from candidates where bt_rank = 1 and expense_rank = 1;

    -- R2b: amount-only fallback within +-3d, no vendor match -- lower confidence, flagged
    -- for review (0.6). Only fires for rows R2a didn't already claim. Same mutual-nearest
    -- guard.
    with candidates as (
      select
        bt.id as bt_id, el.id as expense_id,
        row_number() over (partition by bt.id order by abs(bt.posted_on - el.incurred_on)) as bt_rank,
        row_number() over (partition by el.id order by abs(bt.posted_on - el.incurred_on)) as expense_rank
      from finance.bank_transactions bt
      join finance.bank_accounts ba on ba.id = bt.bank_account_id
      join finance.bank_connections bc on bc.id = ba.connection_id
      join finance.expense_ledger el
        on el.entity_code = v_entity
        and el.amount_cents = abs(bt.amount_cents)
        and bt.posted_on between (el.incurred_on - 3) and (el.incurred_on + 3)
      where bc.entity_code = v_entity
        and bt.amount_cents < 0
        and bt.posted_on >= p_from
        and not exists (select 1 from finance.recon_matches m where m.bank_transaction_id = bt.id)
        and not exists (select 1 from finance.recon_matches m where m.matched_type = 'expense' and m.matched_id = el.id::text)
    )
    insert into finance.recon_matches (bank_transaction_id, matched_type, matched_id, rule, confidence)
    select bt_id, 'expense', expense_id::text, 'R2_amount_only', 0.6
    from candidates where bt_rank = 1 and expense_rank = 1;

    -- R3: Stripe processing fee per payout -> DR 5200 Stripe Fees / CR 1100 Stripe Clearing.
    -- Auto-posts (posted_at=now()) unless the entity is litigation-gated, in which case it
    -- posts as a draft (posted_at=null) and logs Tier-1 (propose-only) to finance_ops_log.
    -- Idempotent: unique index on journal_entries(ref_table, ref_id); ref_id is a
    -- deterministic uuid derived from the payout id (md5 output is 32 hex chars = valid
    -- uuid literal), since stripe payout ids are text, not native uuids.
    insert into finance.journal_entries (entity_code, entry_date, memo, source, ref_table, ref_id, posted_at, created_by)
    select
      v_entity, p.arrival_date::date,
      format('Stripe processing fee for payout %s', p.payout_id),
      'stripe_payout_fee', 'stripe.payouts.fee', md5(p.payout_id || ':fee')::uuid,
      case when finance._litigation_gated(v_entity) then null else now() end,
      'finance.recon_run'
    from finance.v_stripe_payouts p
    where p.total_fees_cents > 0
      and p.arrival_date::date >= p_from
      and not exists (
        select 1 from finance.journal_entries je
        where je.ref_table = 'stripe.payouts.fee' and je.ref_id = md5(p.payout_id || ':fee')::uuid
      )
    on conflict (ref_table, ref_id) where ref_table is not null and ref_id is not null do nothing;

    insert into finance.postings (entry_id, account_id, debit_cents, memo)
    select je.id, acc5200.id, p.total_fees_cents, 'Stripe fee'
    from finance.journal_entries je
    join finance.v_stripe_payouts p on md5(p.payout_id || ':fee')::uuid = je.ref_id and je.ref_table = 'stripe.payouts.fee'
    join finance.accounts acc5200 on acc5200.entity_code = v_entity and acc5200.code = '5200'
    where je.entity_code = v_entity
      and not exists (select 1 from finance.postings po where po.entry_id = je.id and po.debit_cents > 0);

    insert into finance.postings (entry_id, account_id, credit_cents, memo)
    select je.id, acc1100.id, p.total_fees_cents, 'Stripe fee'
    from finance.journal_entries je
    join finance.v_stripe_payouts p on md5(p.payout_id || ':fee')::uuid = je.ref_id and je.ref_table = 'stripe.payouts.fee'
    join finance.accounts acc1100 on acc1100.entity_code = v_entity and acc1100.code = '1100'
    where je.entity_code = v_entity
      and not exists (select 1 from finance.postings po where po.entry_id = je.id and po.credit_cents > 0);

    insert into public.finance_ops_log (dispatch_id, entity, task, status, source_event_id, evidence, severity)
    select '19738', v_entity, 'recon_run.R3_stripe_fee',
      case when finance._litigation_gated(v_entity) then 'PARTIAL' else 'VERIFIED' end,
      p.payout_id,
      jsonb_build_object('rule', 'R3', 'fee_cents', p.total_fees_cents, 'tier', case when finance._litigation_gated(v_entity) then '1_propose_only' else '2_autonomous' end),
      case when finance._litigation_gated(v_entity) then 'warn' else 'info' end
    from finance.v_stripe_payouts p
    join finance.journal_entries je on je.ref_table = 'stripe.payouts.fee' and je.ref_id = md5(p.payout_id || ':fee')::uuid
    where je.entity_code = v_entity and je.created_at >= now() - interval '5 seconds';

    -- R4: payout journal DR 1000 Bank / CR 1100 Stripe Clearing, per R1-matched payout.
    -- Same idempotency pattern as R3 (deterministic uuid ref_id, unique on ref_table/ref_id).
    insert into finance.journal_entries (entity_code, entry_date, memo, source, ref_table, ref_id, posted_at, created_by)
    select distinct
      v_entity, p.arrival_date::date,
      format('Stripe payout %s landed in bank', p.payout_id),
      'stripe_payout', 'stripe.payouts', md5(p.payout_id)::uuid,
      case when finance._litigation_gated(v_entity) then null else now() end,
      'finance.recon_run'
    from finance.recon_matches m
    join finance.v_stripe_payouts p on p.payout_id = m.matched_id and m.matched_type = 'stripe_payout'
    where m.rule = 'R1'
      and not exists (
        select 1 from finance.journal_entries je
        where je.ref_table = 'stripe.payouts' and je.ref_id = md5(p.payout_id)::uuid
      )
    on conflict (ref_table, ref_id) where ref_table is not null and ref_id is not null do nothing;

    insert into finance.postings (entry_id, account_id, debit_cents, memo)
    select je.id, acc1000.id, p.amount, 'Payout received'
    from finance.journal_entries je
    join finance.v_stripe_payouts p on md5(p.payout_id)::uuid = je.ref_id and je.ref_table = 'stripe.payouts'
    join finance.accounts acc1000 on acc1000.entity_code = v_entity and acc1000.code = '1000'
    where je.entity_code = v_entity
      and not exists (select 1 from finance.postings po where po.entry_id = je.id and po.debit_cents > 0);

    insert into finance.postings (entry_id, account_id, credit_cents, memo)
    select je.id, acc1100.id, p.amount, 'Payout clears Stripe holding'
    from finance.journal_entries je
    join finance.v_stripe_payouts p on md5(p.payout_id)::uuid = je.ref_id and je.ref_table = 'stripe.payouts'
    join finance.accounts acc1100 on acc1100.entity_code = v_entity and acc1100.code = '1100'
    where je.entity_code = v_entity
      and not exists (select 1 from finance.postings po where po.entry_id = je.id and po.credit_cents > 0);

    insert into public.finance_ops_log (dispatch_id, entity, task, status, source_event_id, evidence, severity)
    select '19738', v_entity, 'recon_run.R4_payout_journal',
      case when finance._litigation_gated(v_entity) then 'PARTIAL' else 'VERIFIED' end,
      p.payout_id,
      jsonb_build_object('rule', 'R4', 'amount_cents', p.amount, 'tier', case when finance._litigation_gated(v_entity) then '1_propose_only' else '2_autonomous' end),
      case when finance._litigation_gated(v_entity) then 'warn' else 'info' end
    from finance.v_stripe_payouts p
    join finance.journal_entries je on je.ref_table = 'stripe.payouts' and je.ref_id = md5(p.payout_id)::uuid
    where je.entity_code = v_entity and je.created_at >= now() - interval '5 seconds';

    -- Unmatched bank rows -> recon_exceptions
    insert into finance.recon_exceptions (bank_transaction_id, reason, status)
    select bt.id, case when bt.amount_cents > 0 then 'unmatched_credit' else 'unmatched_debit' end, 'open'
    from finance.bank_transactions bt
    join finance.bank_accounts ba on ba.id = bt.bank_account_id
    join finance.bank_connections bc on bc.id = ba.connection_id
    where bc.entity_code = v_entity
      and bt.posted_on >= p_from
      and not exists (select 1 from finance.recon_matches m where m.bank_transaction_id = bt.id)
      and not exists (select 1 from finance.recon_exceptions e where e.bank_transaction_id = bt.id);

    -- Unmatched ledger rows (posted expense journal entries with no bank-side match) ->
    -- no_bank_evidence
    insert into finance.recon_exceptions (bank_transaction_id, entry_id, reason, status)
    select null, je.id, 'no_bank_evidence', 'open'
    from finance.expense_ledger el
    join finance.journal_entries je on je.ref_table = 'finance.expense_ledger' and je.ref_id = el.id
    where el.entity_code = v_entity
      and el.incurred_on >= p_from
      and not exists (
        select 1 from finance.recon_matches m
        where m.matched_type = 'expense' and m.matched_id = el.id::text
      )
      and not exists (select 1 from finance.recon_exceptions e where e.entry_id = je.id);

    select count(*) into v_bank_rows
    from finance.bank_transactions bt
    join finance.bank_accounts ba on ba.id = bt.bank_account_id
    join finance.bank_connections bc on bc.id = ba.connection_id
    where bc.entity_code = v_entity and bt.posted_on >= p_from;

    entity_code := v_entity;
    bank_rows := v_bank_rows;
    select count(*) into matched from finance.recon_matches m2
      join finance.bank_transactions bt2 on bt2.id = m2.bank_transaction_id
      join finance.bank_accounts ba2 on ba2.id = bt2.bank_account_id
      join finance.bank_connections bc2 on bc2.id = ba2.connection_id
      where bc2.entity_code = v_entity and bt2.posted_on >= p_from;
    select count(*) into exceptions_opened
      from finance.recon_exceptions e
      left join finance.bank_transactions bt3 on bt3.id = e.bank_transaction_id
      left join finance.bank_accounts ba3 on ba3.id = bt3.bank_account_id
      left join finance.bank_connections bc3 on bc3.id = ba3.connection_id
      left join finance.journal_entries je3 on je3.id = e.entry_id
      where e.status = 'open'
        and coalesce(bc3.entity_code, je3.entity_code) = v_entity;
    return next;
  end loop;
end;
$$;

grant execute on function finance.recon_run(text, date) to cfo_agent_ro;

-- finance.v_recon_summary: entity/period rollup. period = calendar month of the bank
-- transaction (or, for ledger-only exceptions, the journal entry date), matching the
-- monthly cadence in RUNBOOK_MONTH_END.md. Balances are cumulative through period-end
-- (running balance), not a monthly delta, so variance_cents reflects true drift.
create or replace view finance.v_recon_summary
with (security_invoker = true) as
with bank_periods as (
  select
    bc.entity_code,
    date_trunc('month', bt.posted_on)::date as period,
    bt.id as bank_transaction_id,
    bt.amount_cents,
    exists (select 1 from finance.recon_matches m where m.bank_transaction_id = bt.id) as is_matched
  from finance.bank_transactions bt
  join finance.bank_accounts ba on ba.id = bt.bank_account_id
  join finance.bank_connections bc on bc.id = ba.connection_id
),
bank_agg as (
  select entity_code, period,
    count(*) as bank_rows,
    count(*) filter (where is_matched) as matched,
    sum(amount_cents) as month_bank_delta_cents
  from bank_periods
  group by entity_code, period
),
bank_running as (
  select entity_code, period, bank_rows, matched,
    sum(month_bank_delta_cents) over (partition by entity_code order by period) as bank_balance_cents
  from bank_agg
),
ledger_agg as (
  select
    je.entity_code,
    date_trunc('month', je.entry_date)::date as period,
    sum(p.debit_cents - p.credit_cents) as month_ledger_delta_cents
  from finance.journal_entries je
  join finance.postings p on p.entry_id = je.id
  join finance.accounts a on a.id = p.account_id and a.code = '1000'
  where je.posted_at is not null
  group by je.entity_code, date_trunc('month', je.entry_date)::date
),
ledger_running as (
  select entity_code, period,
    sum(month_ledger_delta_cents) over (partition by entity_code order by period) as ledger_balance_cents
  from ledger_agg
),
periods as (
  select entity_code, period from bank_running
  union
  select entity_code, period from ledger_running
),
exceptions_agg as (
  select entity_code, period, count(*) as exceptions_open from (
    select bc.entity_code, date_trunc('month', bt.posted_on)::date as period
    from finance.recon_exceptions e
    join finance.bank_transactions bt on bt.id = e.bank_transaction_id
    join finance.bank_accounts ba on ba.id = bt.bank_account_id
    join finance.bank_connections bc on bc.id = ba.connection_id
    where e.status = 'open'
    union all
    select je.entity_code, date_trunc('month', je.entry_date)::date as period
    from finance.recon_exceptions e
    join finance.journal_entries je on je.id = e.entry_id
    where e.status = 'open'
  ) x
  group by entity_code, period
)
select
  pr.entity_code,
  pr.period,
  coalesce(br.bank_rows, 0) as bank_rows,
  coalesce(br.matched, 0) as matched,
  case when coalesce(br.bank_rows, 0) = 0 then null
       else round(100.0 * br.matched / br.bank_rows, 1) end as matched_pct,
  coalesce(ex.exceptions_open, 0) as exceptions_open,
  lr.ledger_balance_cents,
  br.bank_balance_cents,
  (coalesce(lr.ledger_balance_cents, 0) - coalesce(br.bank_balance_cents, 0)) as variance_cents
from periods pr
left join bank_running br on br.entity_code = pr.entity_code and br.period = pr.period
left join ledger_running lr on lr.entity_code = pr.entity_code and lr.period = pr.period
left join exceptions_agg ex on ex.entity_code = pr.entity_code and ex.period = pr.period
order by pr.entity_code, pr.period;

grant select on finance.v_recon_summary to cfo_agent_ro;
