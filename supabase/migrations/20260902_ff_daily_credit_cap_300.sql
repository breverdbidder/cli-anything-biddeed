-- Issue #19731: persist the daily Tracerfy+BrightData call cap raise (100 -> 300)
-- that the AI Architect already applied live in Supabase on 2026-09-02, so a
-- future migration replay of 20260824_ff_daily_credit_ledger.sql does not
-- silently revert public.ff_ledger_spend()'s cap back to 100.
--
-- Ariel authorized raising the combined daily cap from 100 to 300 on
-- 2026-09-02 and confirmed Tracerfy's real PAYG rate is $0.02/call (see
-- scripts/tracerfy_client.py ENHANCED_COST_CENTS, fixed to 2 in this same
-- issue). This migration is IDEMPOTENT and reproduces exactly what is
-- already live (verified via `pg_get_functiondef` + `obj_description` against
-- production before writing this file) -- applying it changes nothing on a
-- database where the live change has already been made; it only makes the
-- repo match production so `supabase db push` on a fresh/rebuilt database
-- lands on 300, not the superseded 100 from 20260824_ff_daily_credit_ledger.sql.

create or replace function public.ff_ledger_spend(p_source text, p_n int default 1)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  cap constant int := 300;
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

comment on table public.ff_daily_credit_ledger is
    'Combined Tracerfy+BrightData daily call ledger for the FF daily pipeline. Hard cap enforced in ff_ledger_spend(), 300 combined units/UTC day (raised from 100 by Ariel 2026-09-02; Tracerfy confirmed $0.02/call), no carryover.';
