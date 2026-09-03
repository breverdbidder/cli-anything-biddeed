-- CFO v1 Issue K (#19768): TAX-YEAR 2026 readiness
-- Entity rollup, tax-mapped chart of accounts, 1099 tracking, loan schedule,
-- owner contributions, year-end package. Follow-up to #19755/#19762/#19765.

-- =========================================================================
-- 0. FINDINGS FIXED BEFORE BUILDING ON TOP OF THEM
-- =========================================================================

-- 0a. finance.simplefin_backfill() reintroduced the exact wrong-sign /
--     unprefixed duplicate-row bug that #19765 fixed in finance.simplefin_sync
--     (no `simplefin:` id prefix, un-negated amount sign, stub raw payload, no
--     credential/HTTP error handling). Live check before this migration:
--     347 unprefixed dup rows existed under bc.status='simplefin', ALL with a
--     matching prefixed opposite-sign counterpart, ZERO with a journal_entry
--     yet (confirmed live, not assumed) -- i.e. not yet posted to the ledger,
--     but the next process_bank_transactions()/daily_close() tick would have
--     posted all 347 as duplicate, wrong-signed, miscategorized entries
--     (a negative-signed "expense" duplicate lands as fake income). This
--     directly threatened the accuracy of every P&L/1099 view built below,
--     including double-counting the SHAPIRA MARIAM Zelle payments named in
--     scope item 6. Deleting bad code before removing the rows it created.

create or replace function finance.simplefin_backfill(p_from date, p_to date)
 returns table(mask text, inserted bigint)
 language plpgsql
 security definer
as $$
declare
  v_url text;
  v_resp jsonb;
  v_http extensions.http_response;
begin
  select decrypted_secret into v_url from vault.decrypted_secrets where name = 'simplefin_access_url';
  if v_url is null then
    raise exception 'simplefin_backfill: no simplefin_access_url in vault (credential missing)';
  end if;

  select * into v_http from extensions.http(
    ('GET', v_url || '/accounts?start-date=' || extract(epoch from p_from)::bigint
       || '&end-date=' || extract(epoch from p_to)::bigint,
     ARRAY[]::extensions.http_header[], NULL, NULL)::extensions.http_request);

  if v_http.status in (401, 403) then
    raise exception 'simplefin_backfill: SimpleFIN returned HTTP % (credential/auth error)', v_http.status;
  end if;
  if v_http.status <> 200 then
    raise exception 'simplefin_backfill: SimpleFIN /accounts returned HTTP %', v_http.status;
  end if;

  v_resp := v_http.content::jsonb;

  return query
  with flat as (
    select a->>'id' as aid, t as txn
    from jsonb_array_elements(coalesce(v_resp->'accounts', '[]'::jsonb)) a,
         jsonb_array_elements(coalesce(a->'transactions', '[]'::jsonb)) t
  ),
  ins as (
    insert into finance.bank_transactions (
      bank_account_id, plaid_transaction_id, amount_cents, posted_on, pending, name, merchant_name, raw
    )
    select
      ba.id,
      'simplefin:' || coalesce(
        nullif(f.txn->>'id', ''),
        md5(f.aid || ':' || (f.txn->>'posted') || ':' || (f.txn->>'amount') || ':' || coalesce(f.txn->>'description',''))
      ),
      -round((f.txn->>'amount')::numeric * 100)::bigint,
      to_timestamp((f.txn->>'posted')::bigint)::date,
      coalesce((f.txn->>'pending')::boolean, false),
      left(coalesce(f.txn->>'description', ''), 300),
      nullif(f.txn->>'payee', ''),
      jsonb_build_object('source', 'simplefin_backfill') || f.txn
    from flat f
    join finance.bank_accounts ba on ba.plaid_account_id = 'simplefin:' || f.aid
    on conflict (plaid_transaction_id) do nothing
    returning bank_account_id
  )
  select ba2.mask, count(*) from ins join finance.bank_accounts ba2 on ba2.id = ins.bank_account_id group by 1;
end;
$$;

-- Delete the 347 confirmed-duplicate stub rows. Guarded on the exact live
-- proof above: unprefixed id, under a simplefin connection, zero journal
-- entries, and a matching prefixed row with the exact opposite sign exists.
-- If a future run of this migration finds no such rows (already cleaned),
-- this is a no-op -- safe to re-run.
with dead as (
  select bt.id
  from finance.bank_transactions bt
  join finance.bank_accounts ba on ba.id = bt.bank_account_id
  join finance.bank_connections bc on bc.id = ba.connection_id
  where bc.status = 'simplefin'
    and bt.plaid_transaction_id not like 'simplefin:%'
    and not exists (
      select 1 from finance.journal_entries je
      where je.ref_table = 'finance.bank_transactions' and je.ref_id = bt.id
    )
    and exists (
      select 1 from finance.bank_transactions bt2
      where bt2.bank_account_id = bt.bank_account_id
        and bt2.plaid_transaction_id = 'simplefin:' || bt.plaid_transaction_id
        and bt2.amount_cents = -bt.amount_cents
    )
)
delete from finance.bank_transactions where id in (select id from dead);

-- 0b. finance.bank_accounts.mask regression. Root cause (found, not assumed):
--     workers/everest-bank-engine/src/simplefin.ts syncSimplefin() hardcodes
--     `mask: null` on every account upsert (SimpleFIN's protocol has no
--     top-level "mask" field -- it's embedded in the account name, e.g.
--     "BUSINESS CHECKING ...3519 (3519)"), and public.bank_engine_upsert_accounts
--     did `set mask = excluded.mask` unconditionally -- so every 6h cron tick
--     (and every manual /simplefin/sync call) blanked whatever mask had been
--     populated. Two-part fix: (1) stop the upsert from ever clobbering a good
--     mask with a null one, (2) actually extract the real mask from the name
--     going forward (Worker-side fix, see workers/everest-bank-engine commit).
create or replace function finance._extract_account_mask4(p_name text)
 returns text
 language sql
 immutable
as $$
  select substring(p_name from '\((\d{4})\)\s*$');
$$;

update finance.bank_accounts
set mask = finance._extract_account_mask4(name)
where mask is null and finance._extract_account_mask4(name) is not null;

create or replace function public.bank_engine_upsert_accounts(p_connection_id uuid, p_accounts jsonb)
 returns integer
 language plpgsql
 security definer
 set search_path to 'pg_catalog', 'public', 'finance'
as $function$
declare
  v_count int := 0;
  v_acct jsonb;
begin
  for v_acct in select * from jsonb_array_elements(p_accounts)
  loop
    insert into finance.bank_accounts (
      connection_id, plaid_account_id, name, mask, subtype, currency,
      current_balance_cents, available_balance_cents
    ) values (
      p_connection_id,
      v_acct->>'plaid_account_id',
      v_acct->>'name',
      coalesce(v_acct->>'mask', finance._extract_account_mask4(v_acct->>'name')),
      v_acct->>'subtype',
      v_acct->>'currency',
      nullif(v_acct->>'current_balance_cents','')::bigint,
      nullif(v_acct->>'available_balance_cents','')::bigint
    )
    on conflict (plaid_account_id) do update
      set name = excluded.name,
          -- never let an incoming null blank out a mask we already have --
          -- this exact unconditional overwrite was the root cause of the regression.
          mask = coalesce(excluded.mask, finance.bank_accounts.mask, finance._extract_account_mask4(excluded.name)),
          subtype = excluded.subtype,
          currency = excluded.currency,
          current_balance_cents = excluded.current_balance_cents,
          available_balance_cents = excluded.available_balance_cents;
    v_count := v_count + 1;
  end loop;
  return v_count;
end;
$function$;

-- =========================================================================
-- 1. ENTITY ROLLUP -- tax_entity mapping (Ariel, authoritative, 2026-09-03)
-- =========================================================================
-- Everest Capital of Brevard LLC is the only operating legal entity.
-- everest_capital (DBA) and biddeed/zonewise/winnerdata/protection_partners
-- (incubated product lines) all roll up into it for TAX purposes. The
-- per-code dimension (entity_code) is kept untouched for internal P&L by
-- product line. ariel_personal stays fully separate, never consolidated.

alter table finance.entities add column if not exists tax_entity text;

update finance.entities
set tax_entity = case when code = 'ariel_personal' then 'ariel_personal' else 'everest_capital_brevard' end
where tax_entity is null;

alter table finance.entities alter column tax_entity set not null;
comment on column finance.entities.tax_entity is
  'Tax-filing rollup entity (Ariel, 2026-09-03): every business entity_code files under one return (everest_capital_brevard). ariel_personal never consolidates. entity_code remains the internal per-product-line P&L dimension.';

-- =========================================================================
-- 2. TAX-MAPPED CHART OF ACCOUNTS
-- =========================================================================
-- Return type NOT YET CONFIRMED by Ariel (1065 vs 1120-S vs Schedule C) --
-- per the issue's own instruction, defaulting to a form-agnostic standard
-- category set and asking in the issue (see docs/spec/19768.md + issue
-- comment posted this session). tax_deductible: true=fully deductible,
-- false=never on the P&L (draws/transfers/personal/principal), null=partially
-- deductible pending a split (currently only 5400, see finance.loan_schedule).

alter table finance.accounts add column if not exists tax_line text;
alter table finance.accounts add column if not exists tax_deductible boolean;
alter table finance.accounts add column if not exists tax_note text;

-- Shared schema (biddeed / everest_capital / protection_partners / winnerdata / zonewise)
update finance.accounts set tax_line = null, tax_deductible = null, tax_note = 'balance sheet account, not a P&L line'
where code in ('1000','1100','1200','2000') and entity_code in ('biddeed','everest_capital','protection_partners','winnerdata','zonewise');

update finance.accounts set tax_line = null, tax_deductible = false, tax_note = 'owner equity -- not deductible, not P&L'
where code = '3000' and entity_code in ('biddeed','everest_capital','protection_partners','winnerdata','zonewise');

update finance.accounts set tax_line = 'Gross receipts', tax_deductible = null
where code in ('4000','4100') and entity_code in ('biddeed','everest_capital','protection_partners','winnerdata','zonewise');

update finance.accounts set tax_line = 'Office', tax_deductible = true
where code = '5000' and entity_code in ('biddeed','everest_capital','protection_partners','winnerdata','zonewise');

update finance.accounts set tax_line = 'Office', tax_deductible = true, tax_note = 'data vendor / SaaS subscriptions'
where code = '5100' and entity_code in ('biddeed','everest_capital','protection_partners','winnerdata','zonewise');

update finance.accounts set tax_line = 'Commissions & fees', tax_deductible = true, tax_note = 'payment-processor fees'
where code = '5200' and entity_code in ('biddeed','everest_capital','protection_partners','winnerdata','zonewise');

update finance.accounts set tax_line = 'Other', tax_deductible = true
where code = '5900' and entity_code in ('biddeed','everest_capital','protection_partners','winnerdata','zonewise');

-- everest_capital_brevard (operating LLC -- the tax_entity everything rolls into)
update finance.accounts set tax_line = null, tax_deductible = null, tax_note = 'balance sheet account, not a P&L line'
where entity_code = 'everest_capital_brevard' and code in ('1000','1001','1002','1200','2000');

update finance.accounts set tax_line = null, tax_deductible = false, tax_note = 'loan principal balance -- liability, not deductible, not P&L'
where entity_code = 'everest_capital_brevard' and code = '2200';

update finance.accounts set tax_line = null, tax_deductible = false, tax_note = 'owner equity -- not deductible, not P&L'
where entity_code = 'everest_capital_brevard' and code = '3000';

update finance.accounts set tax_line = 'Gross receipts', tax_deductible = null
where entity_code = 'everest_capital_brevard' and code = '4000';

update finance.accounts set tax_line = 'Other', tax_deductible = true, tax_note = 'generic operating-expense bucket -- may need finer categorization for filing'
where entity_code = 'everest_capital_brevard' and code = '5000';

update finance.accounts set tax_line = 'Office', tax_deductible = true, tax_note = 'data vendor / SaaS / PropTech subscriptions'
where entity_code = 'everest_capital_brevard' and code = '5100';

update finance.accounts set tax_line = 'Other', tax_deductible = true, tax_note = 'bank/wire fees -- not separately enumerated in the standard category list Ariel provided; confirm with CPA whether this should be its own line'
where entity_code = 'everest_capital_brevard' and code = '5300';

update finance.accounts set tax_line = 'Interest — mortgage / Loan principal (UNSPLIT)', tax_deductible = null,
  tax_note = 'Mixes WF mortgage ($3,221.51/mo) and SBA EIDL ($264+$74/mo) payments. 100% currently posted here undifferentiated -- $0 has been classified as deductible interest to date. BLOCKS filing: needs finance.loan_schedule terms from Ariel to split principal (non-deductible) from interest (deductible) via finance.loan_payment_split(). Do not deduct this balance as-is.'
where entity_code = 'everest_capital_brevard' and code = '5400';

update finance.accounts set tax_line = 'Other', tax_deductible = true
where entity_code = 'everest_capital_brevard' and code = '5900';

-- New account: 3100 Owner Contribution (for the commingling reclass proposals, item 7)
insert into finance.accounts (entity_code, code, name, type, is_bank)
values ('everest_capital_brevard', '3100', 'Owner Contribution (personally-funded business costs)', 'EQUITY', false)
on conflict (entity_code, code) do nothing;
update finance.accounts set tax_line = null, tax_deductible = false, tax_note = 'owner capital contribution -- not deductible, not P&L; offsets a personally-funded business expense recorded elsewhere on this entity''s books'
where entity_code = 'everest_capital_brevard' and code = '3100';

-- ariel_personal (excluded from every business tax view by tax_entity filter;
-- tagged here for completeness/consistency, not because it will ever appear
-- on a business return).
update finance.accounts set tax_line = null, tax_deductible = null, tax_note = 'personal -- never on a business return'
where entity_code = 'ariel_personal' and code in ('1000','2100');

update finance.accounts set tax_line = null, tax_deductible = false, tax_note = 'personal equity -- never on a business return'
where entity_code = 'ariel_personal' and code = '3000';

update finance.accounts set tax_line = null, tax_deductible = null, tax_note = 'personal income -- never on a business return'
where entity_code = 'ariel_personal' and code = '4000';

update finance.accounts set tax_line = null, tax_deductible = true,
  tax_note = 'business infra/SaaS paid personally -- see finance.v_owner_contributions for the proposed reclass onto everest_capital_brevard''s books; NOT itself a business-return line since this account lives on ariel_personal''s ledger'
where entity_code = 'ariel_personal' and code = '5100';

update finance.accounts set tax_line = null, tax_deductible = null, tax_note = 'personal -- never on a business return'
where entity_code = 'ariel_personal' and code in ('5300','5400','5900');

-- =========================================================================
-- 3. LOAN PRINCIPAL VS INTEREST
-- =========================================================================
create table if not exists finance.loan_schedule (
  id uuid primary key default gen_random_uuid(),
  loan_name text not null,
  entity_code text not null references finance.entities(code),
  orig_principal_cents bigint,
  rate_pct numeric,
  term_months int,
  start_date date,
  notes text,
  created_at timestamptz not null default now(),
  unique (loan_name, entity_code)
);

alter table finance.loan_schedule enable row level security;
drop policy if exists cfo_agent_ro_select on finance.loan_schedule;
create policy cfo_agent_ro_select on finance.loan_schedule for select to cfo_agent_ro using (true);
grant select on finance.loan_schedule to cfo_agent_ro;
grant select on finance.loan_schedule to service_role;

-- Rows intentionally left empty (orig_principal_cents/rate_pct/term_months/
-- start_date all NULL) pending Ariel's actual loan terms -- per the issue's
-- explicit instruction not to invent a split. `notes` records only what was
-- directly observed in the bank feed, never an assumed structure.
insert into finance.loan_schedule (loan_name, entity_code, notes) values
  ('Gavish -- Dvora', 'everest_capital_brevard',
   'Bank Hapoalim wire 2026-04-17, $47,397.66, reclassified from 5900 to liability 2200 Notes Payable -- private lenders (Gavish). Confirmed by Ariel as a loan repayment. Orig principal/rate/term/start date UNKNOWN -- Ariel to supply.'),
  ('Gavish -- Asaf', 'everest_capital_brevard',
   'Bank Hapoalim wire 2026-04-27, $35,722.75, reclassified from 5900 to liability 2200 Notes Payable -- private lenders (Gavish). Confirmed by Ariel as a loan repayment. Orig principal/rate/term/start date UNKNOWN -- Ariel to supply.'),
  ('WF Mortgage', 'everest_capital_brevard',
   'Observed recurring payment $3,221.51/mo posted 100% to 5400 Debt Service. Orig principal/rate/term/start date UNKNOWN -- Ariel to supply so principal (non-deductible) can be split from interest (deductible, "Interest — mortgage").'),
  ('SBA EIDL', 'everest_capital_brevard',
   'Observed recurring payments $264/mo + $74/mo (two components, posted together to 5400 Debt Service). Orig principal/rate/term/start date UNKNOWN -- Ariel to supply. Note: SBA EIDL loans are typically 3.75%/30yr -- NOT assumed here, must be confirmed against Ariel''s actual note.')
on conflict (loan_name, entity_code) do nothing;

comment on table finance.loan_schedule is
  'Loan terms for principal/interest splitting (issue #19768 item 5). Rows ship with structural fields NULL until Ariel supplies actual terms -- finance.loan_payment_split() falls back to "100% principal, interest unknown" rather than guessing.';

create or replace function finance.loan_payment_split(p_loan_name text, p_entity_code text, p_payment_cents bigint)
 returns table(principal_cents bigint, interest_cents bigint, method text)
 language plpgsql
 stable
as $$
declare
  v_loan finance.loan_schedule;
begin
  select * into v_loan from finance.loan_schedule
  where loan_name = p_loan_name and entity_code = p_entity_code;

  if not found then
    principal_cents := p_payment_cents;
    interest_cents := null;
    method := 'UNKNOWN_LOAN -- no finance.loan_schedule row for this loan_name/entity_code';
    return next;
    return;
  end if;

  if v_loan.orig_principal_cents is null or v_loan.rate_pct is null
     or v_loan.term_months is null or v_loan.start_date is null then
    principal_cents := p_payment_cents;
    interest_cents := null;
    method := 'PENDING_TERMS -- Ariel has not supplied orig_principal/rate/term/start_date; no split computed, do not deduct interest';
    return next;
    return;
  end if;

  -- Standard amortization: interest on the remaining balance as of the
  -- number of whole months elapsed since start_date, computed only once all
  -- four terms are known (never invented in the PENDING_TERMS branch above).
  declare
    v_months_elapsed int := greatest(0, (extract(year from now())::int - extract(year from v_loan.start_date)::int) * 12
                                        + (extract(month from now())::int - extract(month from v_loan.start_date)::int));
    v_monthly_rate numeric := v_loan.rate_pct / 100.0 / 12.0;
    v_balance numeric := v_loan.orig_principal_cents;
    v_i int;
    v_interest_this_period numeric;
  begin
    for v_i in 1..least(v_months_elapsed, v_loan.term_months) loop
      v_interest_this_period := v_balance * v_monthly_rate;
      v_balance := v_balance - (p_payment_cents - v_interest_this_period);
    end loop;
    interest_cents := round(greatest(v_balance * v_monthly_rate, 0));
    principal_cents := p_payment_cents - interest_cents;
    method := 'AMORTIZED -- computed from finance.loan_schedule terms';
    return next;
  end;
end;
$$;

-- =========================================================================
-- 4. 1099-NEC TRACKING
-- =========================================================================
-- Non-corporate payee, >= $600/calendar-year, from a real (status='simplefin')
-- business bank account, excluding transfers, loan payments, utilities, and
-- clearly-incorporated vendor names. This is a CANDIDATE list -- it flags,
-- it never auto-classifies (per the issue's explicit instruction for the
-- SHAPIRA MARIAM payments and every other ambiguous case).
--
-- finance.normalize_descriptor() alone is not enough here: it only strips the
-- WF card PURCHASE/RECURRING PAYMENT wrapper, so it leaves Zelle/wire memos
-- (which carry a per-transaction REF#/date/memo) fully distinct per row --
-- grouping on it would split a single real payee's payments across the year
-- into buckets that each individually miss the $600 threshold (caught live:
-- the 5 SHAPIRA MARIAM Zelle payments summed to $1,453.03 but never appeared
-- as a candidate until payee extraction was added). _extract_payee() pulls
-- the actual counterparty name out of Zelle ("... TO/FROM <name> ON ...")
-- and wire ("BNF=<name> ...") memos before falling back to normalize_descriptor.
create or replace function finance._extract_payee(p_name text)
 returns text
 language sql
 immutable
as $$
  select coalesce(
    substring(p_name from 'ZELLE (?:TO|FROM) (.+?) ON \d'),
    substring(p_name from 'BNF=(.+?)\s{2,}SRF'),
    substring(p_name from 'BNF=([^/]+)'),
    finance.normalize_descriptor(p_name),
    p_name
  );
$$;

create or replace view finance.v_1099_candidates as
with biz_out as (
  select
    bt.id as bank_transaction_id,
    bc.entity_code,
    e.tax_entity,
    date_part('year', bt.posted_on)::int as tax_year,
    finance._extract_payee(bt.name) as vendor_description,
    bt.name as raw_description,
    p.debit_cents,
    a.code as account_code,
    a.tax_line
  from finance.bank_transactions bt
  join finance.bank_accounts ba on ba.id = bt.bank_account_id
  join finance.bank_connections bc on bc.id = ba.connection_id
  join finance.entities e on e.code = bc.entity_code
  join finance.journal_entries je on je.ref_table = 'finance.bank_transactions'::text and je.ref_id = bt.id
  join finance.postings p on p.entry_id = je.id and p.debit_cents > 0
  join finance.accounts a on a.id = p.account_id and a.type = 'EXPENSE'::text and a.entity_code = bc.entity_code
  left join finance.category_rules cr on cr.id = (
    select r.id from finance.category_rules r
    where (r.entity_scope is null or r.entity_scope = bc.entity_code)
      and (r.direction = 'any'::text or r.direction = 'out'::text) and r.match_field = 'name'::text
      and (bt.name ilike '%' || r.pattern || '%' or coalesce(finance.normalize_descriptor(bt.name), ''::text) ilike '%' || r.pattern || '%')
    order by r.priority asc, r.id asc limit 1
  )
  where bc.status = 'simplefin'::text
    and bc.entity_code <> 'ariel_personal'::text
    and coalesce(cr.is_transfer, false) = false
    and coalesce(a.tax_line, ''::text) not ilike '%loan%'
    and finance._extract_payee(bt.name) !~* '(FPL|SPECTRUM|T-MOBILE|COMCAST|XFINITY|AT&T|DUKE ENERGY|WATER UTIL|VERIZON)'
    and bt.name !~* '\y(INC|CORP|CORPORATION|LTD|LLC|PLLC)\y'
)
select
  entity_code, tax_entity, tax_year, vendor_description,
  (array_agg(raw_description order by raw_description))[1] as sample_raw_description,
  count(*) as payment_count,
  round(sum(debit_cents) / 100.0, 2) as total_paid_dollars,
  case
    when vendor_description ilike '%mariam%' or vendor_description ilike '%shapira%'
      then 'RELATED_PARTY -- Ariel must classify (wages vs contractor vs draw), do not auto-file a 1099 without his decision'
    else 'CANDIDATE -- non-corporate payee >= $600/yr, verify business purpose before filing'
  end as flag_reason
from biz_out
group by 1, 2, 3, 4
having sum(debit_cents) >= 60000
order by tax_year, total_paid_dollars desc;

comment on view finance.v_1099_candidates is
  'Candidate 1099-NEC payees (issue #19768 item 6). Propose-only: exclusion heuristics (transfers/loan/utility/incorporated-name) are INFERRED, not authoritative -- every row still needs Ariel''s classification before filing, especially flag_reason=RELATED_PARTY rows (SHAPIRA MARIAM).';

-- =========================================================================
-- 5. COMMINGLING -> OWNER CONTRIBUTIONS (full year, Tier 1 propose-only)
-- =========================================================================
create or replace view finance.v_owner_contributions as
select
  bt.posted_on as txn_date,
  date_part('year', bt.posted_on)::int as tax_year,
  coalesce(finance.normalize_descriptor(bt.name), bt.name) as vendor_description,
  round(p.debit_cents::numeric / 100.0, 2) as amount_dollars,
  coalesce(cr.likely_business_entity, 'everest_capital_brevard') as proposed_tax_entity,
  format(
    'Propose-only, Tier 1 -- DR %s 5100 Data Vendors/SaaS & PropTech $%s / CR %s 3100 Owner Contribution. Ariel approves before posting.',
    coalesce(cr.likely_business_entity, 'everest_capital_brevard'),
    to_char(p.debit_cents::numeric / 100.0, 'FM999999990.00'),
    coalesce(cr.likely_business_entity, 'everest_capital_brevard')
  ) as suggested_reclass,
  case when cr.likely_business_entity is null then true else false end as entity_unclear,
  bt.id as bank_transaction_id,
  je.id as journal_entry_id
from finance.bank_transactions bt
join finance.bank_accounts ba on ba.id = bt.bank_account_id
join finance.bank_connections bc on bc.id = ba.connection_id
join finance.journal_entries je on je.ref_table = 'finance.bank_transactions'::text and je.ref_id = bt.id
join finance.postings p on p.entry_id = je.id and p.debit_cents > 0
join finance.accounts a on a.id = p.account_id and a.code = '5100'::text and a.entity_code = 'ariel_personal'::text
left join finance.category_rules cr on cr.id = (
  select r.id from finance.category_rules r
  where r.account_code = '5100'::text and r.entity_scope = 'ariel_personal'::text
    and (r.direction = any (array['out'::text, 'any'::text])) and r.match_field = 'name'::text
    and (bt.name ilike '%' || r.pattern || '%' or coalesce(finance.normalize_descriptor(bt.name), ''::text) ilike '%' || r.pattern || '%')
  order by r.priority asc, r.id asc limit 1
)
where bc.status = 'simplefin'::text and bc.entity_code = 'ariel_personal'::text
order by bt.posted_on;

comment on view finance.v_owner_contributions is
  'Issue #19768 item 7 -- full-year (not just 90-day) proposed reclass of personally-funded business costs into everest_capital_brevard 3100 Owner Contribution. Tier 1 propose-only: no auto-posting.';

-- =========================================================================
-- 6. YEAR-END PACKAGE -- supporting views/functions
-- =========================================================================

-- Real per-account coverage (item 2's evidence + the dashboard completeness banner).
create or replace view finance.v_bank_coverage as
select
  ba.id as bank_account_id, ba.name as account_name, ba.mask, bc.entity_code, bc.status,
  min(bt.posted_on) as first_txn_date, max(bt.posted_on) as last_txn_date, count(bt.id) as txn_count,
  (min(bt.posted_on) > date '2026-01-01') as has_gap_vs_jan1,
  case when min(bt.posted_on) > date '2026-01-01'
    then format('Missing %s to %s -- SimpleFIN Bridge confirmed empty for this range (probed live, not assumed); export from Wells Fargo via /import', '2026-01-01', (min(bt.posted_on) - 1)::text)
    else null
  end as gap_description
from finance.bank_accounts ba
join finance.bank_connections bc on bc.id = ba.connection_id
left join finance.bank_transactions bt on bt.bank_account_id = ba.id
where bc.status in ('simplefin','active','manual')
group by ba.id, ba.name, ba.mask, bc.entity_code, bc.status
order by bc.entity_code, ba.name;

comment on view finance.v_bank_coverage is
  'Real per-account transaction coverage (issue #19768 item 2/8). has_gap_vs_jan1/gap_description back the year-end package''s data-completeness banner.';

-- Open/unreconciled items for the year-end package.
create or replace view finance.v_unreconciled_items as
select
  re.id as recon_exception_id, re.reason, re.status, re.opened_at,
  bc.entity_code, e.tax_entity, bt.posted_on, bt.name as description,
  round(bt.amount_cents / 100.0, 2) as amount_dollars
from finance.recon_exceptions re
join finance.bank_transactions bt on bt.id = re.bank_transaction_id
join finance.bank_accounts ba on ba.id = bt.bank_account_id
join finance.bank_connections bc on bc.id = ba.connection_id
join finance.entities e on e.code = bc.entity_code
where re.status = 'open'
order by bc.entity_code, bt.posted_on;

comment on view finance.v_unreconciled_items is 'Open finance.recon_exceptions, joined for the year-end package''s uncategorized/unreconciled list (issue #19768 item 8).';

-- P&L by tax_line, grouped either by tax_entity (consolidated business return
-- view) or entity_code (internal per-product-line view) -- both required by
-- item 8. Includes drafts (posted_at is null): every everest_capital_brevard
-- journal_entry is currently a Tier-1 draft (litigation-gated, confirmed live
-- 192/192) -- excluding drafts would report $0 for the entire operating
-- entity, which is wrong for a CPA-prep tool. `draft_basis` flags this.
create or replace function finance.pnl_by_tax_line(p_year int, p_group_by text default 'tax_entity')
 returns table(
   group_key text, account_type text, tax_line text, tax_deductible boolean,
   amount_cents bigint, draft_count bigint, posted_count bigint
 )
 language plpgsql
 stable
as $$
begin
  if p_group_by not in ('tax_entity','entity_code') then
    raise exception 'pnl_by_tax_line: p_group_by must be tax_entity or entity_code, got %', p_group_by;
  end if;

  return query
  select
    case when p_group_by = 'tax_entity' then e.tax_entity else je.entity_code end as group_key,
    a.type as account_type,
    a.tax_line,
    a.tax_deductible,
    -- normal-balance sign: REVENUE is credit-normal (positive = money in),
    -- EXPENSE is debit-normal (positive = money out) -- avoids a P&L that
    -- shows revenue as a negative number.
    sum(case when a.type = 'REVENUE' then p.credit_cents - p.debit_cents else p.debit_cents - p.credit_cents end)::bigint as amount_cents,
    count(*) filter (where je.posted_at is null) as draft_count,
    count(*) filter (where je.posted_at is not null) as posted_count
  from finance.journal_entries je
  join finance.postings p on p.entry_id = je.id
  join finance.accounts a on a.id = p.account_id and a.entity_code = je.entity_code
  join finance.entities e on e.code = je.entity_code
  where a.type in ('REVENUE','EXPENSE')
    and date_part('year', je.entry_date)::int = p_year
  group by 1, 2, 3, 4
  order by 1, 2, 3;
end;
$$;

comment on function finance.pnl_by_tax_line(int, text) is
  'Issue #19768 item 8. p_group_by=tax_entity -> consolidated business return view; entity_code -> internal per-product-line P&L. Includes draft (unposted, litigation-gated) journal entries -- draft_count/posted_count expose the split so it is never silently treated as final.';

-- Balance sheet by tax_entity or entity_code, as-of a date (default: today).
create or replace function finance.balance_sheet(p_as_of date default null, p_group_by text default 'tax_entity')
 returns table(group_key text, account_type text, account_code text, account_name text, balance_cents bigint)
 language plpgsql
 stable
as $$
begin
  if p_group_by not in ('tax_entity','entity_code') then
    raise exception 'balance_sheet: p_group_by must be tax_entity or entity_code, got %', p_group_by;
  end if;

  return query
  select
    case when p_group_by = 'tax_entity' then e.tax_entity else je.entity_code end as group_key,
    a.type as account_type,
    a.code as account_code,
    a.name as account_name,
    -- normal-balance sign: ASSET is debit-normal; LIABILITY/EQUITY are credit-normal.
    sum(case when a.type = 'ASSET' then p.debit_cents - p.credit_cents else p.credit_cents - p.debit_cents end)::bigint as balance_cents
  from finance.journal_entries je
  join finance.postings p on p.entry_id = je.id
  join finance.accounts a on a.id = p.account_id and a.entity_code = je.entity_code
  join finance.entities e on e.code = je.entity_code
  where a.type in ('ASSET','LIABILITY','EQUITY')
    and (p_as_of is null or je.entry_date <= p_as_of)
  group by 1, 2, 3, 4
  order by 1, 2, 3;
end;
$$;

comment on function finance.balance_sheet(date, text) is 'Issue #19768 item 8. Balance-sheet accounts (ASSET/LIABILITY/EQUITY) as-of a date, grouped by tax_entity (default) or entity_code. Includes draft journal entries for the same reason as pnl_by_tax_line.';

grant execute on function finance.pnl_by_tax_line(int, text) to service_role, cfo_agent_ro;
grant execute on function finance.balance_sheet(date, text) to service_role, cfo_agent_ro;
grant execute on function finance.loan_payment_split(text, text, bigint) to service_role, cfo_agent_ro;
grant select on finance.v_1099_candidates to service_role, cfo_agent_ro;
grant select on finance.v_owner_contributions to service_role, cfo_agent_ro;
grant select on finance.v_bank_coverage to service_role, cfo_agent_ro;
grant select on finance.v_unreconciled_items to service_role, cfo_agent_ro;

-- =========================================================================
-- 7. public RPC wrapper -- PostgREST only exposes `public`, same reason every
--    other bank_engine_* wrapper exists (service_role has no USAGE on finance).
-- =========================================================================
create or replace function public.bank_engine_tax_package(p_year int default 2026)
 returns jsonb
 language sql
 security definer
 set search_path to 'pg_catalog', 'public', 'finance'
as $$
  select jsonb_build_object(
    'year', p_year,
    'pnl_consolidated', (select coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) from finance.pnl_by_tax_line(p_year, 'tax_entity') t),
    'pnl_by_product_line', (select coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) from finance.pnl_by_tax_line(p_year, 'entity_code') t),
    'balance_sheet', (select coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) from finance.balance_sheet(make_date(p_year,12,31), 'tax_entity') t),
    'candidates_1099', (select coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) from finance.v_1099_candidates t where tax_year = p_year),
    'owner_contributions', (select coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) from finance.v_owner_contributions t where tax_year = p_year),
    'unreconciled_items', (select coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) from finance.v_unreconciled_items t),
    'bank_coverage', (select coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) from finance.v_bank_coverage t),
    'loan_schedule', (select coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) from finance.loan_schedule t),
    'generated_at', now()
  );
$$;

revoke all on function public.bank_engine_tax_package(int) from public;
grant execute on function public.bank_engine_tax_package(int) to service_role;
grant execute on function public.bank_engine_tax_package(int) to cfo_agent_ro;

comment on function public.bank_engine_tax_package(int) is
  'Issue #19768 item 8 -- GET /api/tax/package?year=2026 backing RPC (everest-cfo-agent repo). PostgREST-exposed wrapper around finance.* year-end package views/functions.';
