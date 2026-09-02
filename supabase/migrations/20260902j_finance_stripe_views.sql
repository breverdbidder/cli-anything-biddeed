-- Issue #19738 Part 1: finance.v_stripe_payouts + finance.v_stripe_charges_net
-- security_invoker=true per RLS gate convention (docs .claude CLAUDE.md M2 / rls_gate_violations
-- 'definer_view_anon') -- the view runs with the querying role's own RLS (cfo_agent_ro), never
-- escalates to the view owner's privileges.

create or replace view finance.v_stripe_payouts
with (security_invoker = true) as
select
  p.id as payout_id,
  p.status,
  p.method,
  p.type,
  p.amount,
  p.currency,
  to_timestamp(p.created) as created_at,
  to_timestamp(p.arrival_date) as arrival_date,
  p.destination,
  p.balance_transaction,
  (select coalesce(sum(bt.fee), 0) from stripe.balance_transactions bt
    where bt.payout_id = p.id and bt.reporting_category <> 'payout') as total_fees_cents,
  (select count(*) from stripe.balance_transactions bt
    where bt.payout_id = p.id and bt.reporting_category = 'charge') as charge_count
from stripe.payouts p;

grant select on finance.v_stripe_payouts to cfo_agent_ro;

-- charge -> balance_transaction -> payout: every charge's gross/fee/net and which payout
-- (if any) it landed in. Charges not yet paid out have payout_id/payout_arrival_date null.
create or replace view finance.v_stripe_charges_net
with (security_invoker = true) as
select
  c.id as charge_id,
  c.status as charge_status,
  c.amount as gross_amount_cents,
  c.currency,
  to_timestamp(c.created) as charge_created_at,
  c.customer,
  c.balance_transaction,
  bt.fee as fee_cents,
  bt.net as net_amount_cents,
  bt.reporting_category,
  bt.payout_id,
  po.status as payout_status,
  to_timestamp(po.arrival_date) as payout_arrival_date
from stripe.charges c
left join stripe.balance_transactions bt on bt.id = c.balance_transaction
left join stripe.payouts po on po.id = bt.payout_id;

grant select on finance.v_stripe_charges_net to cfo_agent_ro;
