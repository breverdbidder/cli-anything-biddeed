-- FF daily pipeline part 2: combined Tracerfy + Bright Data daily spend cap.
--
-- Spec (daily FF pipeline issue): "100 Tracerfy/Bright Data credits per day,
-- combined, hard cap ... The job must stop calling either API once the daily
-- 100-credit ceiling is hit ... Resume the next day's quota fresh; do not
-- carry over or borrow against future days."
--
-- CREDIT-UNIT DEFINITION (INFERRED, stated explicitly -- do not treat as an
-- invoiced fact): Tracerfy's own PAYG rate is $0.02/credit per the issue, but
-- scripts/tracerfy_client.py's ENHANCED_COST_CENTS=1500 constant is flagged
-- in its own comment as "verify against real invoice" -- i.e. not yet
-- reconciled against a real bill. Bright Data has no "credit" unit documented
-- anywhere in this repo either (it bills scraping-browser usage by
-- session/bandwidth, not a credit currency). Rather than invent a false-
-- precision conversion between two unreconciled cost models, this ledger
-- counts CALLS: one Tracerfy enhanced_trace() call = 1 unit, one Bright Data
-- realforeclose/realtaxdeed auction-detail-page fetch = 1 unit, combined hard
-- cap 100 units/UTC day. This is intentionally conservative (it will often
-- stop spend before the literal dollar cap implied by $0.02/credit x 100 is
-- reached) -- tighten scripts/ff_credit_ledger.py's per-call unit cost once a
-- real Tracerfy invoice reconciles ENHANCED_COST_CENTS.

create table if not exists public.ff_daily_credit_ledger (
    usage_date date primary key default current_date,
    tracerfy_calls int not null default 0,
    brightdata_calls int not null default 0,
    total_calls int generated always as (tracerfy_calls + brightdata_calls) stored,
    cap_hit_at timestamptz,
    updated_at timestamptz not null default now()
);

comment on table public.ff_daily_credit_ledger is
    'Combined Tracerfy+BrightData daily call ledger for the FF daily pipeline. Hard cap enforced in ff_ledger_spend(), 100 combined units/UTC day, no carryover. See migration header for the call-unit definition (INFERRED, not an invoiced credit conversion).';

-- Atomic spend-or-reject: increments the requested source by p_n only if
-- doing so would not push total_calls past 100 for today; otherwise makes no
-- change and reports how many units were actually available. Callers must
-- check `granted` in the response and stop calling the vendor API once it is
-- false, logging the skip with a reason (never a silent truncation).
create or replace function public.ff_ledger_spend(p_source text, p_n int default 1)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  cap constant int := 100;
  today date := (now() at time zone 'utc')::date;
  cur_total int;
  granted_n int;
  new_total int;
begin
  if p_source not in ('tracerfy', 'brightdata') then
    return jsonb_build_object('granted', false, 'error', 'unknown_source', 'total_calls', null);
  end if;
  if p_n is null or p_n < 1 then
    return jsonb_build_object('granted', false, 'error', 'invalid_n', 'total_calls', null);
  end if;

  insert into public.ff_daily_credit_ledger (usage_date)
  values (today)
  on conflict (usage_date) do nothing;

  select total_calls into cur_total from public.ff_daily_credit_ledger where usage_date = today for update;

  granted_n := least(p_n, greatest(cap - cur_total, 0));

  if granted_n <= 0 then
    update public.ff_daily_credit_ledger
      set cap_hit_at = coalesce(cap_hit_at, now()), updated_at = now()
      where usage_date = today;
    return jsonb_build_object('granted', false, 'granted_n', 0, 'total_calls', cur_total, 'cap', cap);
  end if;

  if p_source = 'tracerfy' then
    update public.ff_daily_credit_ledger
      set tracerfy_calls = tracerfy_calls + granted_n, updated_at = now()
      where usage_date = today
      returning total_calls into new_total;
  else
    update public.ff_daily_credit_ledger
      set brightdata_calls = brightdata_calls + granted_n, updated_at = now()
      where usage_date = today
      returning total_calls into new_total;
  end if;

  if new_total >= cap then
    update public.ff_daily_credit_ledger
      set cap_hit_at = coalesce(cap_hit_at, now())
      where usage_date = today;
  end if;

  return jsonb_build_object(
    'granted', true,
    'granted_n', granted_n,
    'partial', granted_n < p_n,
    'total_calls', new_total,
    'cap', cap
  );
end;
$$;

revoke all on function public.ff_ledger_spend(text, int) from public;
grant execute on function public.ff_ledger_spend(text, int) to service_role;
