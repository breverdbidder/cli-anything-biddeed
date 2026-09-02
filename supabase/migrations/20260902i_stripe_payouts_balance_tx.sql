-- Issue #19738 CFO v1 Issue D Part 1: stripe.payouts + stripe.balance_transactions
-- @stripe/sync-engine (installed in #19717) does not sync payouts/balance_transactions
-- (Sigma-only in that library). These tables are hand-rolled to mirror Stripe's own
-- field names 1:1 (created/available_on/arrival_date as bigint epoch, matching the
-- sync-engine's convention on every other stripe.* table), populated by the
-- stripe-payouts-sync GHA job (scripts/stripe_payouts_sync.py) via the restricted key's
-- newly-granted Payouts Read / Balance Transaction Sources Read scopes.

create table if not exists stripe.payouts (
  id text primary key,
  object text,
  amount bigint,
  application_fee text,
  application_fee_amount bigint,
  arrival_date bigint,
  automatic boolean,
  balance_transaction text,
  created bigint,
  currency text,
  description text,
  destination text,
  failure_balance_transaction text,
  failure_code text,
  failure_message text,
  livemode boolean,
  metadata jsonb,
  method text,
  original_payout text,
  payout_method text,
  reconciliation_status text,
  reversed_by text,
  source_type text,
  statement_descriptor text,
  status text,
  trace_id jsonb,
  type text,
  _account_id text,
  _last_synced_at timestamptz default now(),
  _updated_at timestamptz default now()
);

-- payout_id is not a native Stripe field on balance_transaction (it only appears when
-- the API is queried with ?payout=po_xxx, which is exactly what "Balance Transaction
-- Sources Read" gates). The sync job stamps it explicitly per-row when it walks each
-- payout's sources -- everything else mirrors the raw Stripe object.
create table if not exists stripe.balance_transactions (
  id text primary key,
  object text,
  amount bigint,
  available_on bigint,
  balance_type text,
  created bigint,
  currency text,
  description text,
  exchange_rate numeric,
  fee bigint,
  fee_details jsonb,
  net bigint,
  reporting_category text,
  source text,
  status text,
  type text,
  payout_id text,
  _account_id text,
  _last_synced_at timestamptz default now(),
  _updated_at timestamptz default now()
);

create index if not exists idx_stripe_payouts_created on stripe.payouts(created);
create index if not exists idx_stripe_payouts_arrival_date on stripe.payouts(arrival_date);
create index if not exists idx_stripe_balance_transactions_created on stripe.balance_transactions(created);
create index if not exists idx_stripe_balance_transactions_source on stripe.balance_transactions(source);
create index if not exists idx_stripe_balance_transactions_payout_id on stripe.balance_transactions(payout_id);

alter table stripe.payouts enable row level security;
alter table stripe.balance_transactions enable row level security;

drop policy if exists cfo_agent_ro_select on stripe.payouts;
create policy cfo_agent_ro_select on stripe.payouts for select to cfo_agent_ro using (true);

drop policy if exists cfo_agent_ro_select on stripe.balance_transactions;
create policy cfo_agent_ro_select on stripe.balance_transactions for select to cfo_agent_ro using (true);

grant select on stripe.payouts, stripe.balance_transactions to cfo_agent_ro;
