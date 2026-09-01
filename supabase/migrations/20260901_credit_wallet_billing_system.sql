-- Token/credit wallet billing system (ChatGPT/Claude-style), Ariel directive
-- Aug 31 2026. Layers alongside the existing fixed tier-gate model
-- (mcp_subscription_tiers / STREAM_PRICE) — does NOT remove tier-gate checks
-- in this migration (issue is explicit: removal is a follow-up once credits
-- are proven in production with a real purchase). Additive only — does not
-- touch taxi_meter_tool_billing, gold_standard_*, multi_county_auctions,
-- insights (protected objects per CC_META_PROMPT.md).
--
-- Unit: 1 credit = $0.01 USD. Stored as bigint credits, never float dollars.

-- ============================================================
-- 1. mcp_credit_balances
-- ============================================================

create table if not exists public.mcp_credit_balances (
  customer_id uuid primary key references public.mcp_customers(customer_id),
  balance bigint not null default 0,
  updated_at timestamptz not null default now()
);

comment on table public.mcp_credit_balances is
  'Current credit wallet balance per customer. 1 credit = $0.01 USD. Written only via mcp_credit_spend/mcp_credit_grant (SECURITY DEFINER, service_role-only) — never patched directly by app code, so every balance change has a matching mcp_credit_ledger row.';

alter table public.mcp_credit_balances enable row level security;
alter table public.mcp_credit_balances force row level security;
revoke all on public.mcp_credit_balances from anon, authenticated;
drop policy if exists mcp_credit_balances_service_all on public.mcp_credit_balances;
create policy mcp_credit_balances_service_all
  on public.mcp_credit_balances
  for all
  to service_role
  using (true)
  with check (true);

-- ============================================================
-- 2. mcp_credit_ledger
-- ============================================================

create table if not exists public.mcp_credit_ledger (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.mcp_customers(customer_id),
  delta bigint not null,           -- negative = spend, positive = grant/purchase
  reason text not null,             -- 'tool_call' | 'purchase' | 'signup_grant' | 'refund' | 'monthly_refill' | 'migration_grant'
  tool_name text,                   -- null when reason != 'tool_call'
  mca_id uuid,                      -- property this call was for, when applicable
  stripe_payment_id text,
  balance_after bigint not null,
  created_at timestamptz not null default now()
);

comment on table public.mcp_credit_ledger is
  'Append-only audit trail for every credit balance change. balance_after lets any row be reconciled against mcp_credit_balances without replaying the whole history.';

create index if not exists mcp_credit_ledger_customer_created_idx
  on public.mcp_credit_ledger (customer_id, created_at desc);

alter table public.mcp_credit_ledger enable row level security;
alter table public.mcp_credit_ledger force row level security;
revoke all on public.mcp_credit_ledger from anon, authenticated;
drop policy if exists mcp_credit_ledger_service_all on public.mcp_credit_ledger;
create policy mcp_credit_ledger_service_all
  on public.mcp_credit_ledger
  for all
  to service_role
  using (true)
  with check (true);

-- ============================================================
-- 3. mcp_credit_pricing
-- ============================================================

create table if not exists public.mcp_credit_pricing (
  tool_name text primary key,
  credit_cost bigint not null,
  updated_at timestamptz not null default now()
);

comment on table public.mcp_credit_pricing is
  'Per-tool credit cost, looked up dynamically by mcp_credit_spend — never hardcode per-tool amounts in application code (same zero-deploy-pricing-change pattern as v_s5_report_template). tool_name values below are exactly as specified in the issue; see DEVIATION note further down for the parallel rows added so the deduction wrapper actually matches the real MCP HANDLERS keys in packages/biddeed-mcp/src/server.js.';

alter table public.mcp_credit_pricing enable row level security;
alter table public.mcp_credit_pricing force row level security;
revoke all on public.mcp_credit_pricing from anon, authenticated;
drop policy if exists mcp_credit_pricing_service_all on public.mcp_credit_pricing;
create policy mcp_credit_pricing_service_all
  on public.mcp_credit_pricing
  for all
  to service_role
  using (true)
  with check (true);

-- Issue-literal seed rows (verbatim tool_name values from the issue body).
insert into public.mcp_credit_pricing (tool_name, credit_cost) values
  ('s1_discovery_default', 10),
  ('get_lien_stack', 75),
  ('get_owner_intel', 75),
  ('get_zoning_far', 75),
  ('get_underwrite', 75),
  ('get_rent_estimate', 75),
  ('get_market_data', 75),
  ('deal_memo', 200),
  ('sales_comps', 200),
  ('bid_package', 200),
  ('scene_3d', 200),
  ('get_title_chain', 200),
  ('entitlement_feasibility', 200),
  ('skip_trace', 150),
  ('county_monitor_monthly', 100),
  ('predict_auction_outcome', 2500)  -- S5 Shapira, folded into credits per Ariel Aug 31 2026
on conflict (tool_name) do nothing;

-- DEVIATION (CC_META_PROMPT 2.3 — "the DoD query itself may be wrong"):
-- five of the issue's literal tool_name values do not match the actual
-- HANDLERS keys in packages/biddeed-mcp/src/server.js, so a caller charging
-- against the real tool name would never find a price row and the wrapper
-- would silently skip billing. Verified live against server.js HANDLERS:
--   'get_zoning_far'  has no handler -> real tool is check_zoning
--   'get_underwrite'  has no handler -> real tool is underwrite_deal
--   'deal_memo'       has no handler -> real tool is generate_deal_memo
--   'sales_comps'     has no handler -> real tool is get_sales_comps
--   'bid_package'     has no handler -> real tool is get_bid_package
-- 'scene_3d' and 'entitlement_feasibility' also have no current handler
-- (forward-looking tools not yet shipped) — left as issue-literal only,
-- no alias added, no ledger rows will ever reference them yet.
-- Keeping both the issue-literal rows (for spec compliance / future rename)
-- and these real-name alias rows (so the deduction wrapper is actually
-- live today) at the same price point.
insert into public.mcp_credit_pricing (tool_name, credit_cost) values
  ('check_zoning', 75),
  ('underwrite_deal', 75),
  ('generate_deal_memo', 200),
  ('get_sales_comps', 200),
  ('get_bid_package', 200)
on conflict (tool_name) do nothing;

-- ============================================================
-- 4. mcp_credit_spend — atomic deduction wrapper
-- ============================================================
-- Resolution order: exact tool_name match; else, if p_stream_id = 's1',
-- fall back to 's1_discovery_default'; else the tool has no credit price
-- defined (S1-S3/S6/S7 tools not explicitly listed in the issue's pricing
-- table stay on the existing tier-gate/Stripe-metered path only — "layer",
-- not "replace", per the issue) and this call is a no-op (ok:true,
-- charged:false) so the caller falls through to checkChargeAllowance
-- unchanged.
create or replace function public.mcp_credit_spend(
  p_customer_id uuid,
  p_tool_name text,
  p_stream_id text default null,
  p_mca_id uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  cost bigint;
  cur_balance bigint;
  new_balance bigint;
begin
  if p_customer_id is null then
    return jsonb_build_object('ok', false, 'code', 'missing_customer_id');
  end if;

  select credit_cost into cost
    from public.mcp_credit_pricing
    where tool_name = p_tool_name;

  if cost is null and p_stream_id = 's1' then
    select credit_cost into cost
      from public.mcp_credit_pricing
      where tool_name = 's1_discovery_default';
  end if;

  if cost is null then
    return jsonb_build_object('ok', true, 'charged', false, 'cost', 0);
  end if;

  insert into public.mcp_credit_balances (customer_id)
    values (p_customer_id)
    on conflict (customer_id) do nothing;

  select balance into cur_balance
    from public.mcp_credit_balances
    where customer_id = p_customer_id
    for update;

  if cur_balance < cost then
    return jsonb_build_object(
      'ok', false,
      'code', 'insufficient_credits',
      'balance', cur_balance,
      'cost', cost,
      'message', format('Insufficient credits: need %s, have %s. Top up at biddeed.ai/upgrade', cost, cur_balance)
    );
  end if;

  new_balance := cur_balance - cost;

  update public.mcp_credit_balances
    set balance = new_balance, updated_at = now()
    where customer_id = p_customer_id;

  insert into public.mcp_credit_ledger
    (customer_id, delta, reason, tool_name, mca_id, balance_after)
  values
    (p_customer_id, -cost, 'tool_call', p_tool_name, p_mca_id, new_balance);

  return jsonb_build_object('ok', true, 'charged', true, 'cost', cost, 'balance', new_balance);
end;
$$;

revoke all on function public.mcp_credit_spend(uuid, text, text, uuid) from public;
grant execute on function public.mcp_credit_spend(uuid, text, text, uuid) to service_role;

-- ============================================================
-- 5. mcp_credit_grant — atomic credit/purchase/refund wrapper
-- ============================================================

create or replace function public.mcp_credit_grant(
  p_customer_id uuid,
  p_delta bigint,
  p_reason text,
  p_stripe_payment_id text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  new_balance bigint;
begin
  if p_customer_id is null then
    return jsonb_build_object('ok', false, 'code', 'missing_customer_id');
  end if;
  if p_delta is null or p_delta <= 0 then
    return jsonb_build_object('ok', false, 'code', 'invalid_delta');
  end if;
  if p_reason not in ('purchase', 'signup_grant', 'refund', 'monthly_refill', 'migration_grant') then
    return jsonb_build_object('ok', false, 'code', 'invalid_reason');
  end if;

  insert into public.mcp_credit_balances (customer_id, balance)
    values (p_customer_id, p_delta)
    on conflict (customer_id) do update
      set balance = public.mcp_credit_balances.balance + excluded.balance,
          updated_at = now()
    returning balance into new_balance;

  insert into public.mcp_credit_ledger
    (customer_id, delta, reason, stripe_payment_id, balance_after)
  values
    (p_customer_id, p_delta, p_reason, p_stripe_payment_id, new_balance);

  return jsonb_build_object('ok', true, 'balance', new_balance);
end;
$$;

revoke all on function public.mcp_credit_grant(uuid, bigint, text, text) from public;
grant execute on function public.mcp_credit_grant(uuid, bigint, text, text) to service_role;

-- ============================================================
-- 6. Free signup grant — 500 credits, replaces the old "50 S1 calls"
--    free-tier cap for every NEW customer row going forward. Existing free-
--    tier customers are intentionally NOT backfilled here (see the separate
--    migration-grant block below, which is scoped to paying subscribers
--    only per the issue's explicit DoD).
-- ============================================================

create or replace function public.mcp_customer_signup_credit_grant()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  perform public.mcp_credit_grant(new.customer_id, 500, 'signup_grant');
  return new;
end;
$$;

drop trigger if exists mcp_customers_signup_credit_grant on public.mcp_customers;
create trigger mcp_customers_signup_credit_grant
  after insert on public.mcp_customers
  for each row
  execute function public.mcp_customer_signup_credit_grant();

-- ============================================================
-- 7. Migration grant — existing PAYING subscribers only (free tier
--    excluded; they get the signup-grant trigger going forward, and issue
--    DoD does not require backfilling existing free users). One-time grant
--    per current tier, ~ that tier's monthly $ value in credits, same 20%
--    bonus curve as the Growth/Pro Stripe packs:
--      investor $99  -> 9,900  * 1.20 = 11,880
--      pro      $199 -> 19,900 * 1.20 = 23,880
--      proplus  $299 -> 29,900 * 1.20 = 35,880
--    Idempotent: guarded by NOT EXISTS on an existing migration_grant ledger
--    row per customer, so re-running this migration is a no-op the 2nd time.
-- ============================================================

do $$
declare
  r record;
  credits bigint;
begin
  for r in
    select customer_id, tier_id
    from public.mcp_customers
    where active = true
      and tier_id in ('investor', 'pro', 'proplus')
      and not exists (
        select 1 from public.mcp_credit_ledger l
        where l.customer_id = mcp_customers.customer_id
          and l.reason = 'migration_grant'
      )
  loop
    credits := case r.tier_id
      when 'investor' then 11880
      when 'pro'      then 23880
      when 'proplus'  then 35880
    end;
    perform public.mcp_credit_grant(r.customer_id, credits, 'migration_grant');
  end loop;
end $$;
