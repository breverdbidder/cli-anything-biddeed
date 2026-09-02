-- Issue #19738 CFO v1 Issue D Part 3: dashboard-facing recon views.
-- everest-cfo-agent's Bank Reconciliation section needs (a) an entity-labeled exceptions
-- list (finance.recon_exceptions has no entity_code of its own -- it's reached only via
-- bank_transactions or journal_entries) and (b) a REAL/FIXTURE signal per row, driven off
-- finance.bank_connections.status (see 20260902k_recon_v1.sql for why status='fixture' is
-- the tag instead of a literal source column).

create or replace view finance.v_recon_exceptions
with (security_invoker = true) as
select
  e.id as exception_id,
  coalesce(bc.entity_code, je.entity_code) as entity_code,
  e.reason,
  e.status,
  coalesce(bt.posted_on, je.entry_date) as txn_date,
  coalesce(bt.amount_cents, 0) as amount_cents,
  coalesce(bt.name, je.memo) as description,
  case when bc.status = 'fixture' then 'FIXTURE' else 'REAL' end as data_source,
  e.opened_at,
  e.resolved_at,
  e.resolution
from finance.recon_exceptions e
left join finance.bank_transactions bt on bt.id = e.bank_transaction_id
left join finance.bank_accounts ba on ba.id = bt.bank_account_id
left join finance.bank_connections bc on bc.id = ba.connection_id
left join finance.journal_entries je on je.id = e.entry_id;

grant select on finance.v_recon_exceptions to cfo_agent_ro;

-- Re-create v_recon_summary with a data_source column (REAL / FIXTURE / MIXED) so the
-- dashboard can badge each period. Every other column is unchanged from 20260902k.
create or replace view finance.v_recon_summary
with (security_invoker = true) as
with bank_periods as (
  select
    bc.entity_code,
    date_trunc('month', bt.posted_on)::date as period,
    bt.id as bank_transaction_id,
    bt.amount_cents,
    bc.status as connection_status,
    exists (select 1 from finance.recon_matches m where m.bank_transaction_id = bt.id) as is_matched
  from finance.bank_transactions bt
  join finance.bank_accounts ba on ba.id = bt.bank_account_id
  join finance.bank_connections bc on bc.id = ba.connection_id
),
bank_agg as (
  select entity_code, period,
    count(*) as bank_rows,
    count(*) filter (where is_matched) as matched,
    sum(amount_cents) as month_bank_delta_cents,
    case
      when count(distinct connection_status) > 1 then 'MIXED'
      when bool_and(connection_status = 'fixture') then 'FIXTURE'
      else 'REAL'
    end as data_source
  from bank_periods
  group by entity_code, period
),
bank_running as (
  select entity_code, period, bank_rows, matched, data_source,
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
  (coalesce(lr.ledger_balance_cents, 0) - coalesce(br.bank_balance_cents, 0)) as variance_cents,
  br.data_source
from periods pr
left join bank_running br on br.entity_code = pr.entity_code and br.period = pr.period
left join ledger_running lr on lr.entity_code = pr.entity_code and lr.period = pr.period
left join exceptions_agg ex on ex.entity_code = pr.entity_code and ex.period = pr.period
order by pr.entity_code, pr.period;

grant select on finance.v_recon_summary to cfo_agent_ro;
