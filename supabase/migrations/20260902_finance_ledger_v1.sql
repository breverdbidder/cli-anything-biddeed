-- CFO v1 Issue A (CP2+CP5): true double-entry ledger in finance.* + posting
-- rules from revenue_ledger/expense_ledger + balance invariant.
-- Issue #19716. Operating contract: CC_META_PROMPT.md.
--
-- CP0 confirmed live 2026-09-02: finance schema had only
-- entities/revenue_ledger/expense_ledger/invoices/cfo_checkpoints. No
-- accounts/journal_entries/postings existed despite prior claims of a live
-- double-entry ledger (everest-ledger fork). everest-ledger
-- (breverdbidder/everest-ledger) is a separate repo (TypeScript/Postgres,
-- forked from radzserg/lefra) with its own `database/` migrations targeting
-- its own schema convention (ledger/account/transaction/entry naming, not
-- finance.*) -- reviewed, not directly reusable as SQL against this
-- project's finance.* naming/FK/RLS conventions, so this migration is
-- written fresh against the live finance.* schema and the CP2 spec below,
-- not copy-pasted from that repo.
--
-- PostgREST exposure: finance schema is already in
-- authenticator's pgrst.db_schemas (fixed in #19688 with an
-- ALTER ROLE authenticator SET pgrst.db_schemas + NOTIFY pgrst, reload).
-- That part of #19688's 3-bug fix does not need to be repeated here -- the
-- part that DOES need repeating per new table is bug #3 from that fix:
-- RLS enabled with zero policies returns 200-empty via PostgREST, not an
-- error. Every new table below gets RLS enabled + a cfo_agent_ro_select
-- policy (USING true), same as revenue_ledger/expense_ledger/invoices.

begin;

-- ============================================================
-- 1. finance.accounts
-- ============================================================

create table finance.accounts (
  id uuid primary key default gen_random_uuid(),
  entity_code text not null references finance.entities(code),
  code text not null,
  name text not null,
  type text not null check (type in ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE')),
  plaid_account_id text,
  stripe_account text,
  is_bank boolean not null default false,
  created_at timestamptz not null default now(),
  unique (entity_code, code)
);

alter table finance.accounts enable row level security;
create policy cfo_agent_ro_select on finance.accounts for select to cfo_agent_ro using (true);
grant select on finance.accounts to cfo_agent_ro;

-- ============================================================
-- 2. finance.journal_entries
-- ============================================================

create table finance.journal_entries (
  id uuid primary key default gen_random_uuid(),
  entity_code text not null references finance.entities(code),
  entry_date date not null,
  memo text,
  source text not null,
  ref_table text,
  ref_id uuid,
  posted_at timestamptz,
  created_by text not null default 'finance_migration',
  created_at timestamptz not null default now()
);

-- Idempotency for post_revenue/post_expense: one journal entry per source row.
create unique index journal_entries_ref_uniq
  on finance.journal_entries (ref_table, ref_id)
  where ref_table is not null and ref_id is not null;

alter table finance.journal_entries enable row level security;
create policy cfo_agent_ro_select on finance.journal_entries for select to cfo_agent_ro using (true);
grant select on finance.journal_entries to cfo_agent_ro;

-- ============================================================
-- 3. finance.postings + balance invariant
-- ============================================================

create table finance.postings (
  id uuid primary key default gen_random_uuid(),
  entry_id uuid not null references finance.journal_entries(id) on delete cascade,
  account_id uuid not null references finance.accounts(id),
  debit_cents bigint not null default 0,
  credit_cents bigint not null default 0,
  memo text,
  check (debit_cents >= 0 and credit_cents >= 0 and (debit_cents = 0 or credit_cents = 0))
);

alter table finance.postings enable row level security;
create policy cfo_agent_ro_select on finance.postings for select to cfo_agent_ro using (true);
grant select on finance.postings to cfo_agent_ro;

-- finance.assert_balanced(): entries where SUM(debit) <> SUM(credit).
-- Must return 0 rows for a healthy ledger.
create or replace function finance.assert_balanced()
returns table (entry_id uuid, debit_total bigint, credit_total bigint)
language sql stable as $$
  select p.entry_id, sum(p.debit_cents), sum(p.credit_cents)
  from finance.postings p
  group by p.entry_id
  having sum(p.debit_cents) <> sum(p.credit_cents);
$$;

-- Deferrable constraint trigger: fires once per affected row, but since it is
-- INITIALLY DEFERRED it runs at commit time against the then-current table
-- state, so a debit+credit pair inserted in the same transaction (the normal
-- case for post_revenue/post_expense) is fully visible when it checks.
create or replace function finance.check_posting_balance()
returns trigger
language plpgsql as $$
declare
  v_entry_id uuid;
  v_debit bigint;
  v_credit bigint;
begin
  v_entry_id := coalesce(new.entry_id, old.entry_id);
  select coalesce(sum(debit_cents), 0), coalesce(sum(credit_cents), 0)
    into v_debit, v_credit
  from finance.postings
  where entry_id = v_entry_id;
  if v_debit <> v_credit then
    raise exception 'finance.postings: entry % unbalanced (debit=% credit=%)',
      v_entry_id, v_debit, v_credit;
  end if;
  return null;
end;
$$;

create constraint trigger trg_postings_balance
  after insert or update or delete on finance.postings
  deferrable initially deferred
  for each row execute function finance.check_posting_balance();

-- ============================================================
-- 4. Plaid bank sync tables (schema only -- no Plaid code here, track C)
-- ============================================================

create table finance.bank_connections (
  id uuid primary key default gen_random_uuid(),
  plaid_item_id text unique,
  entity_code text not null references finance.entities(code),
  institution_name text,
  cursor text,
  status text,
  last_synced_at timestamptz,
  created_at timestamptz not null default now()
);

alter table finance.bank_connections enable row level security;
create policy cfo_agent_ro_select on finance.bank_connections for select to cfo_agent_ro using (true);
grant select on finance.bank_connections to cfo_agent_ro;

create table finance.bank_accounts (
  id uuid primary key default gen_random_uuid(),
  connection_id uuid not null references finance.bank_connections(id),
  plaid_account_id text unique,
  name text,
  mask text,
  subtype text,
  currency text,
  current_balance_cents bigint,
  available_balance_cents bigint,
  ledger_account_id uuid references finance.accounts(id)
);

alter table finance.bank_accounts enable row level security;
create policy cfo_agent_ro_select on finance.bank_accounts for select to cfo_agent_ro using (true);
grant select on finance.bank_accounts to cfo_agent_ro;

-- amount_cents follows Plaid's sign convention: positive = money leaving the
-- account (an outflow/expense from the account holder's perspective),
-- negative = money entering the account (an inflow/deposit). This is the
-- opposite sign of what "amount charged" intuitively suggests -- documented
-- here because track D (recon) will read this column directly.
create table finance.bank_transactions (
  id uuid primary key default gen_random_uuid(),
  bank_account_id uuid not null references finance.bank_accounts(id),
  plaid_transaction_id text unique,
  amount_cents bigint not null,
  posted_on date not null,
  authorized_on date,
  pending boolean not null default false,
  name text,
  merchant_name text,
  category text[],
  raw jsonb,
  created_at timestamptz not null default now()
);

alter table finance.bank_transactions enable row level security;
create policy cfo_agent_ro_select on finance.bank_transactions for select to cfo_agent_ro using (true);
grant select on finance.bank_transactions to cfo_agent_ro;

create table finance.recon_matches (
  id uuid primary key default gen_random_uuid(),
  bank_transaction_id uuid not null references finance.bank_transactions(id),
  matched_type text not null check (matched_type in ('ledger_entry','stripe_payout','stripe_charge','expense','revenue')),
  matched_id text not null,
  rule text,
  confidence numeric,
  matched_at timestamptz not null default now()
);

alter table finance.recon_matches enable row level security;
create policy cfo_agent_ro_select on finance.recon_matches for select to cfo_agent_ro using (true);
grant select on finance.recon_matches to cfo_agent_ro;

create table finance.recon_exceptions (
  id uuid primary key default gen_random_uuid(),
  bank_transaction_id uuid references finance.bank_transactions(id),
  entry_id uuid references finance.journal_entries(id),
  reason text,
  status text not null default 'open',
  opened_at timestamptz not null default now(),
  resolved_at timestamptz,
  resolution text
);

alter table finance.recon_exceptions enable row level security;
create policy cfo_agent_ro_select on finance.recon_exceptions for select to cfo_agent_ro using (true);
grant select on finance.recon_exceptions to cfo_agent_ro;

-- ============================================================
-- 5. Standard chart of accounts, seeded for all entities in finance.entities
--    (5 live today: biddeed, everest_capital, protection_partners,
--    winnerdata, zonewise -- driven from the table, not hardcoded, so a
--    6th entity added later per CFO_BOOKKEEPING_SOP.md sec 1 gets the same
--    chart automatically on next run of this block).
-- ============================================================

insert into finance.accounts (entity_code, code, name, type, is_bank)
select e.code, a.code, a.name, a.type, a.is_bank
from finance.entities e
cross join (values
  ('1000', 'Bank – Wells Fargo',              'ASSET',    true),
  ('1100', 'Stripe Clearing',                 'ASSET',    false),
  ('1200', 'Accounts Receivable',             'ASSET',    false),
  ('2000', 'Accounts Payable',                'LIABILITY',false),
  ('3000', 'Owner Equity',                    'EQUITY',   false),
  ('4000', 'Revenue – Reports/Subscriptions', 'REVENUE',  false),
  ('4100', 'Revenue – Fact Finder',           'REVENUE',  false),
  ('5000', 'Infra & Tooling',                 'EXPENSE',  false),
  ('5100', 'Data Vendors',                    'EXPENSE',  false),
  ('5200', 'Stripe Fees',                     'EXPENSE',  false),
  ('5900', 'Other Expense',                   'EXPENSE',  false)
) as a(code, name, type, is_bank)
on conflict (entity_code, code) do nothing;

-- ============================================================
-- 6. Posting rules (CP5)
-- ============================================================

-- Litigation gate (docs/EVEREST_CFO_AGENT_PLAN.md sec 2 / CP5 spec): the
-- entity under active litigation (Abreu v. Everest Capital of Brevard) is
-- finance.entities.code = 'everest_capital' ("Everest Capital USA /
-- Development") -- it is the only Everest Capital row in finance.entities;
-- there is no separate 'everest_capital_brevard' code live. Postings for
-- this entity are created posted_at = NULL (draft) and logged to
-- public.finance_ops_log as Tier 1 propose-only; never auto-posted.
create or replace function finance._litigation_gated(p_entity_code text)
returns boolean
language sql immutable as $$
  select p_entity_code = 'everest_capital';
$$;

-- finance.post_revenue(revenue_ledger.id)
-- DR 1100 Stripe Clearing (source implies Stripe) or 1200 Accounts
-- Receivable (otherwise) / CR 4100 Revenue – Fact Finder (source='ff_billing')
-- or 4000 Revenue – Reports/Subscriptions (any other source).
-- Idempotent via journal_entries_ref_uniq on (ref_table, ref_id).
-- Skips (no-op, returns NULL) rows with status='void' -- posting a voided
-- revenue_ledger row as real revenue would misstate the books. This is a
-- documented deviation from a literal "post ALL 13 rows" reading of the
-- brief: live data shows all 13 current rows are status='void'
-- (2026-09-01, issue #19659 -- "source billable_ff_events row lacks a
-- confirmed real send"), i.e. money that was never actually billed. Every
-- row is still run through this function during backfill; void ones
-- correctly produce zero journal entries rather than $117 of phantom
-- revenue. See docs/spec/19716.md for the full rationale.
create or replace function finance.post_revenue(p_revenue_id uuid)
returns uuid
language plpgsql as $$
declare
  v_row finance.revenue_ledger;
  v_entry_id uuid;
  v_debit_account uuid;
  v_credit_account uuid;
  v_is_stripe boolean;
  v_posted_at timestamptz;
begin
  select * into v_row from finance.revenue_ledger where id = p_revenue_id;
  if not found then
    raise exception 'finance.post_revenue: no revenue_ledger row %', p_revenue_id;
  end if;

  select id into v_entry_id
  from finance.journal_entries
  where ref_table = 'finance.revenue_ledger' and ref_id = p_revenue_id;
  if found then
    return v_entry_id;
  end if;

  if v_row.status = 'void' then
    return null;
  end if;

  v_is_stripe := v_row.stripe_payment_intent_id is not null or v_row.source ilike '%stripe%';

  select id into v_debit_account from finance.accounts
  where entity_code = v_row.entity_code
    and code = case when v_is_stripe then '1100' else '1200' end;

  select id into v_credit_account from finance.accounts
  where entity_code = v_row.entity_code
    and code = case when v_row.source = 'ff_billing' then '4100' else '4000' end;

  if v_debit_account is null or v_credit_account is null then
    raise exception 'finance.post_revenue: missing chart-of-accounts row for entity %', v_row.entity_code;
  end if;

  v_posted_at := case when finance._litigation_gated(v_row.entity_code) then null else now() end;

  insert into finance.journal_entries (
    entity_code, entry_date, memo, source, ref_table, ref_id, posted_at, created_by
  ) values (
    v_row.entity_code, v_row.occurred_on,
    format('Revenue: %s (%s)', v_row.customer, v_row.source),
    'revenue_ledger', 'finance.revenue_ledger', p_revenue_id, v_posted_at, 'finance.post_revenue'
  ) returning id into v_entry_id;

  insert into finance.postings (entry_id, account_id, debit_cents, memo)
  values (v_entry_id, v_debit_account, v_row.amount_cents, 'revenue receivable/clearing');
  insert into finance.postings (entry_id, account_id, credit_cents, memo)
  values (v_entry_id, v_credit_account, v_row.amount_cents, 'revenue recognized');

  insert into public.finance_ops_log (dispatch_id, entity, task, status, source_event_id, evidence, severity)
  values (
    '19716', v_row.entity_code, 'post_revenue',
    case when finance._litigation_gated(v_row.entity_code) then 'PARTIAL' else 'VERIFIED' end,
    p_revenue_id::text,
    jsonb_build_object('journal_entry_id', v_entry_id, 'amount_cents', v_row.amount_cents, 'source', v_row.source),
    case when finance._litigation_gated(v_row.entity_code) then 'warn' else 'info' end
  );

  return v_entry_id;
end;
$$;

-- finance.post_expense(expense_ledger.id)
-- DR 5xxx by category map (below) / CR 1000 Bank. expense_ledger has no
-- paid/unpaid flag (non-goal: no schema change to expense_ledger), so this
-- always credits 1000 Bank – Wells Fargo rather than 2000 Accounts Payable
-- -- the only determinable state given the live schema. If an
-- unpaid-liability workflow is added later, expense_ledger needs a status
-- column first; that is out of scope here.
create or replace function finance.post_expense(p_expense_id uuid)
returns uuid
language plpgsql as $$
declare
  v_row finance.expense_ledger;
  v_entry_id uuid;
  v_debit_code text;
  v_debit_account uuid;
  v_credit_account uuid;
  v_posted_at timestamptz;
begin
  select * into v_row from finance.expense_ledger where id = p_expense_id;
  if not found then
    raise exception 'finance.post_expense: no expense_ledger row %', p_expense_id;
  end if;

  select id into v_entry_id
  from finance.journal_entries
  where ref_table = 'finance.expense_ledger' and ref_id = p_expense_id;
  if found then
    return v_entry_id;
  end if;

  v_debit_code := case v_row.category
    when 'saas_subscription' then '5000'
    when 'ai_tts_vendor'     then '5000'
    when 'infra'             then '5000'
    when 'data_vendor'       then '5100'
    when 'stripe_fees'       then '5200'
    else '5900'
  end;

  select id into v_debit_account from finance.accounts
  where entity_code = v_row.entity_code and code = v_debit_code;
  select id into v_credit_account from finance.accounts
  where entity_code = v_row.entity_code and code = '1000';

  if v_debit_account is null or v_credit_account is null then
    raise exception 'finance.post_expense: missing chart-of-accounts row for entity %', v_row.entity_code;
  end if;

  v_posted_at := case when finance._litigation_gated(v_row.entity_code) then null else now() end;

  insert into finance.journal_entries (
    entity_code, entry_date, memo, source, ref_table, ref_id, posted_at, created_by
  ) values (
    v_row.entity_code, v_row.incurred_on,
    format('Expense: %s (%s)', v_row.vendor, v_row.category),
    'expense_ledger', 'finance.expense_ledger', p_expense_id, v_posted_at, 'finance.post_expense'
  ) returning id into v_entry_id;

  insert into finance.postings (entry_id, account_id, debit_cents, memo)
  values (v_entry_id, v_debit_account, v_row.amount_cents, v_row.category);
  insert into finance.postings (entry_id, account_id, credit_cents, memo)
  values (v_entry_id, v_credit_account, v_row.amount_cents, 'paid from bank');

  insert into public.finance_ops_log (dispatch_id, entity, task, status, source_event_id, evidence, severity)
  values (
    '19716', v_row.entity_code, 'post_expense',
    case when finance._litigation_gated(v_row.entity_code) then 'PARTIAL' else 'VERIFIED' end,
    p_expense_id::text,
    jsonb_build_object('journal_entry_id', v_entry_id, 'amount_cents', v_row.amount_cents, 'category', v_row.category),
    case when finance._litigation_gated(v_row.entity_code) then 'warn' else 'info' end
  );

  return v_entry_id;
end;
$$;

grant execute on function finance.post_revenue(uuid) to service_role;
grant execute on function finance.post_expense(uuid) to service_role;
grant execute on function finance.assert_balanced() to service_role, cfo_agent_ro;

-- ============================================================
-- 7. Backfill: post every existing revenue_ledger + expense_ledger row.
--    Void revenue_ledger rows correctly no-op inside post_revenue (see
--    function comment above) rather than being skipped by this loop.
-- ============================================================

do $$
declare
  r record;
begin
  for r in select id from finance.revenue_ledger order by occurred_on loop
    perform finance.post_revenue(r.id);
  end loop;
  for r in select id from finance.expense_ledger order by incurred_on loop
    perform finance.post_expense(r.id);
  end loop;
end $$;

commit;
