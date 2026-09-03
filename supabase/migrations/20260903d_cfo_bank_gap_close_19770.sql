-- CFO v1 Issue L (#19770): close the 2026-01-01 -> 2026-03-05 bank data gap.
-- Follow-up to #19768 (which built finance.v_bank_coverage / mask fix / simplefin_backfill fix).
-- This migration adds:
--   1. finance.v_data_coverage -- the exact view shape the issue names (account/mask/entity/
--      first_txn/last_txn/missing_ranges[]), distinct from v_bank_coverage (19768's dashboard
--      banner shape) but sourced from the same tables so the two never drift.
--   2. public.bank_engine_import_account_options() -- backs the /import upload form's account
--      dropdown (issue requirement: "pick the target account from the four real accounts by
--      mask -- not free-text -- and show which date range each account already covers").
--   3. public.bank_engine_data_coverage() -- PostgREST wrapper so the Worker can show "new
--      coverage" in the /import response after the post-import pipeline runs.
-- Housekeeping done live before this file (not part of the migration, no schema change): deleted
-- 4 leftover unposted "...FIXTURE" test bank_transactions (mask 9998/9999, zero journal_entry
-- links, zero downstream references) left over from a prior file-import test session -- found
-- live while re-deriving finance.v_bank_coverage for this issue. Left untouched otherwise, they
-- would have been swept into the ledger by the post-import daily_close call this migration wires
-- in below.

begin;

-- =========================================================================
-- 1. finance.v_data_coverage
-- =========================================================================
create or replace view finance.v_data_coverage as
select
  ba.id as bank_account_id,
  ba.name as account,
  ba.mask,
  bc.entity_code as entity,
  bc.status,
  min(bt.posted_on) as first_txn,
  max(bt.posted_on) as last_txn,
  case
    when min(bt.posted_on) is null then array[]::text[]
    when min(bt.posted_on) > date '2026-01-01'
      then array[format('%s to %s', '2026-01-01', (min(bt.posted_on) - 1)::text)]
    else array[]::text[]
  end as missing_ranges
from finance.bank_accounts ba
join finance.bank_connections bc on bc.id = ba.connection_id
left join finance.bank_transactions bt on bt.bank_account_id = ba.id
where bc.status in ('simplefin','active','manual')
group by ba.id, ba.name, ba.mask, bc.entity_code, bc.status
order by bc.entity_code, ba.mask;

comment on view finance.v_data_coverage is
  'Issue #19770 item 4 -- per-account coverage vs 2026-01-01, exact shape the issue named (account/mask/entity/first_txn/last_txn/missing_ranges[]). Same source tables as finance.v_bank_coverage (#19768, dashboard-banner shape) -- kept as two views because two different consumers already depend on the two different column shapes; do not let them diverge in underlying logic.';

grant select on finance.v_data_coverage to service_role, cfo_agent_ro;

-- =========================================================================
-- 2. Import-form account picker (real WF-linked accounts only -- 'simplefin'
--    or 'manual' status; excludes the Plaid-sandbox/synthetic 'active' fixture
--    accounts that v_bank_coverage/v_data_coverage also carry).
-- =========================================================================
create or replace function public.bank_engine_import_account_options()
returns table (
  entity_code text,
  mask text,
  account_name text,
  first_txn date,
  last_txn date,
  coverage_label text
)
language sql
security definer
set search_path = pg_catalog, public, finance
as $$
  select
    entity,
    mask,
    account,
    first_txn,
    last_txn,
    case
      when first_txn is null then 'No transactions yet'
      when array_length(missing_ranges, 1) > 0 then format('Covers %s to %s (gap: %s)', first_txn, last_txn, missing_ranges[1])
      else format('Covers %s to %s', first_txn, last_txn)
    end as coverage_label
  from finance.v_data_coverage
  where status in ('simplefin','manual')
  order by entity, mask;
$$;

revoke all on function public.bank_engine_import_account_options() from public;
grant execute on function public.bank_engine_import_account_options() to service_role;

comment on function public.bank_engine_import_account_options() is
  'Issue #19770 -- backs GET /import''s account dropdown (Worker importPage.ts). Real WF-linked accounts only (simplefin/manual), each labeled with its live coverage so Ariel can see exactly what to export before uploading.';

-- =========================================================================
-- 3. Coverage read-back for the /import response ("show the new coverage").
-- =========================================================================
create or replace function public.bank_engine_data_coverage()
returns jsonb
language sql
security definer
set search_path = pg_catalog, public, finance
as $$
  select coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) from finance.v_data_coverage t;
$$;

revoke all on function public.bank_engine_data_coverage() from public;
grant execute on function public.bank_engine_data_coverage() to service_role;

comment on function public.bank_engine_data_coverage() is
  'Issue #19770 -- PostgREST wrapper so the Worker can read finance.v_data_coverage back into the /import response after the post-import categorize/post/recon pipeline runs.';

commit;
